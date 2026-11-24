// ============================================================
// config.js — Global state, configuration & constants
// ============================================================

let map;
let availableLayers = [];
const loadedLayers = {};
const layerVisibility = {};
let activeBasemap = 'DigitalTwin';
let tilted = true;
let activeTool = 'overview';
let cityNameTimeout;
let adminUnitTimeout;

// Configuration (set from Django template via initializeUrbanTwinMap)
let CONFIG = {
  mapboxToken: '{{ mapbox_access_token }}',
  layersApiUrl: '/api/layers/',
  initialCenter: [6.895, 52.219],
  initialZoom: 16,
  initialPitch: 60,
  initialBearing: -35
};

// Vector layers with at least this many features load only what is in view
// (?bbox=&zoom= on the GeoJSON endpoint) and reload after the map moves,
// instead of the whole table at once. Administrative layers always load
// whole: their click handlers and the admin-unit panels need every unit.
// See docs/PERFORMANCE.md §1.
const VIEWPORT_LOAD_MIN_FEATURES = 5000;
// Edited DSM (physicalEnv/calculations/dsm_edited.py): status poll interval and give-up time after a map edit.
const DSM_EDIT_POLL_MS = 1000;
const DSM_EDIT_POLL_TIMEOUT_MS = 5 * 60 * 1000;
// Degree of Urbanisation card: poll while the grid refreshes after a map edit (builtup/calculations/urbanisation.py).
const DEGURBA_POLL_MS = 1500;
const DEGURBA_POLL_TIMEOUT_MS = 5 * 60 * 1000;
const VIEWPORT_RELOAD_DELAY_MS = 350;



// Coordinates sent to the server: 4 decimals of a degree is ~11 m (~7 m of
// longitude here), finer than any lookup needs. Shorter URLs, and requests
// for (almost) the same spot become identical, so caches can hit.
const COORD_DECIMALS = 4;

// WMS tiles are requested at Mapbox GL's native 512 px: a quarter of the
// requests of 256 px tiles for the same screen, at the same sharpness. Each
// request to a remote WMS (KNMI's radar through our proxy) costs ~2 s and
// counts against its rate limit, so the number of requests is what matters.
const WMS_TILE_SIZE = 512;

// Highest tile zoom requested from a time-dimension WMS (the KNMI radar).
// The radar grid is ~1 km; a 512 px tile at zoom 8 has ~190 m pixels at
// 52° N, still five per radar cell. Mapbox overzooms beyond it, so a city
// view needs 1–4 tiles per frame instead of ~12, and panning or zooming
// inside the city reuses them instead of asking KNMI again.
const WMS_TIME_MAX_ZOOM = 8;

// Minimum time between two prefetch requests that reach the remote WMS
// (cache hits are not throttled). One request is in flight at a time.
const WMS_PREFETCH_INTERVAL_MS = 500;

function roundCoord(value) {
  return Number(value.toFixed(COORD_DECIMALS));
}

/**
 * Round the numbers of a WMS `bbox=` parameter to COORD_DECIMALS. Mapbox
 * fills `{bbox-epsg-3857}` with full float precision (metres, e.g.
 * 764381.9463201226); four decimals is a tenth of a millimetre, and equal
 * tiles then produce equal URLs, so browser and proxy caches can hit.
 */
function roundBboxInUrl(url) {
  return url.replace(/([?&]bbox=)([^&]*)/i, (_, key, value) =>
    key + value.split(',').map(part => {
      const n = Number(part);
      return part !== '' && Number.isFinite(n) ? String(roundCoord(n)) : part;
    }).join(','));
}

// Basemap styles
const BASEMAPS = {
  DigitalTwin: 'mapbox://styles/cygnus26/cmh0rq554001y01sc2i2z9i6k',
  light:     'mapbox://styles/mapbox/light-v11',
  dark:      'mapbox://styles/mapbox/dark-v11',
  streets:   'mapbox://styles/mapbox/streets-v12',
  satellite: 'mapbox://styles/mapbox/satellite-streets-v12',
  outdoors:  'mapbox://styles/mapbox/outdoors-v12'
};

// ── LENSES (Map simplification step 2) ───────────────────────────────────
// A topic is a lens: picking it shows only its layers and their legends,
// greys the basemap (Map_init.js::syncLensDim) and opens its panel. Overview
// is "no lens" and restores the layers that were on before the first lens
// (Layers.js::openLens / closeLens). MapUI.js::renderLensRail draws the left
// rail from this table, grouped by LENS_GROUPS in this order.
//
// Per lens (the key is the button's data-tool, which other code still reads:
// ADMIN_PANEL_TOOLS, BUILDING_COLOR_BY_TOOL, TOOLS_WITHOUT_BASEMAP_TREES, the tour):
//   group  LENS_GROUPS id;  label  rail text;  title  panel/layers title;  icon  Bootstrap Icon
//   apps   app_labels whose catalog layers the lens shows. 'administrative'
//          is in every lens so the units that drive the panels stay clickable.
//   panel  (level, location) => indicator panel URL, follows the selected
//          unit (mainMap.js::ADMIN_PANEL_TOOLS);  or intro: static panel HTML
//   tools  ids of the "Calculate for this view" tools that belong to the lens
//          (buttons <id>ToolBtn in the panel's Calculate tab, #panel-calculate).
const LENS_GROUPS = [
  { id: 'systems',     label: 'City systems' },
  { id: 'people',      label: 'People' },
  { id: 'environment', label: 'Environment' },
];

const LENSES = {
  water: {
    group: 'systems', label: 'Water', title: 'Water supply', icon: 'bi-droplet',
    apps: ['administrative', 'watersupply'],
    panel: (level, location) =>
      `/watersupply/indicators/${level}/${location}/${window.ACTIVE_YEAR}/${populationQuery()}&${climateParam()}`,
    tools: [],
  },
  energy: {
    group: 'systems', label: 'Energy', title: 'Energy', icon: 'bi-lightning-charge',
    apps: ['administrative', 'Energy'],
    intro: `
      <p class="no-indicators">No indicators yet.</p>
      <p>Its map layers are on; open <strong>Layers</strong> in the bottom bar to switch them.</p>`,
    tools: [],
  },
  housing: {
    group: 'people', label: 'Housing', title: 'Housing', icon: 'bi-house-door',
    apps: ['administrative', 'housing'],
    // Same URL shape as water: housing/urls.py is indicators/<level>/<location>/<year>/.
    panel: (level, location) =>
      `/housing/indicators/${level}/${location}/${window.ACTIVE_YEAR}/${populationQuery()}`,
    tools: [],
  },
  builtup: {
    group: 'people', label: 'Built-up', title: 'Built-up', icon: 'bi-buildings',
    apps: ['administrative', 'builtup'],
    // The building stock has no year; year + population only drive the per-capita cards.
    panel: (level, location) =>
      `/builtup/indicators/${level}/${location}/${window.ACTIVE_YEAR}/${populationQuery()}`,
    tools: ['degurba'],
  },
  administrative: {
    group: 'people', label: 'Population', title: 'Population', icon: 'bi-people',
    apps: ['administrative'],
    intro: `
      <p>Click a city, district or neighbourhood on the map: every topic then reports on that area.</p>
      <p>The population forecast and its what-if controls are in the dock at the bottom.</p>`,
    opensPopulationDock: true,
    tools: [],
  },
  temperature: {
    group: 'environment', label: 'Heat', title: 'Urban heat', icon: 'bi-thermometer-sun',
    apps: ['administrative', 'temperature', 'weather', 'urban_heat'],
    // Urban heat has no year and does not depend on population.
    panel: (level, location) =>
      `/urban_heat/indicators/${level}/${location}/?${climateParam()}`,
    tools: ['lst', 'svf', 'solweig'],
  },
  green: {
    group: 'environment', label: 'Green', title: 'Green and blue space', icon: 'bi-tree',
    apps: ['administrative', 'nature', 'green', 'vegetation', 'trees', 'GreenSpaces', 'LandCover'],
    intro: `
      <p class="no-indicators">No indicators yet.</p>
      <p>Parks, trees, green spaces and water bodies are on the map. Combine them with Heat to find where greening helps most.</p>`,
    tools: [],
  },
  physicalEnv: {
    group: 'environment', label: 'Ground', title: 'Ground: soil, terrain and land cover', icon: 'bi-layers-half',
    apps: ['administrative', 'physicalEnv'],
    intro: `
      <p class="no-indicators">No indicators yet.</p>
      <p>Soil, terrain (DEM, DSM) and land cover are on the map. Soil and groundwater feed the Water topic's recharge card.</p>`,
    tools: [],
  },
};

// The basemap under an open lens: a cool slate wash drawn above the basemap
// and below the lens's layers, so their colours carry the map.
const LENS_DIM_COLOR = '#1c2529';
const LENS_DIM_OPACITY = 0.42;
const LENS_DIM_FADE_MS = 350;

const LOADER_SHOW_DELAY_MS = 8000;  // only surface it for genuinely slow loads

const HIDES_3D_BUILDINGS_APPS = new Set(['builtup']); // app to hide 3D buildings when any of its layers is visible
const HIDES_3D_BUILDINGS_KEYS = new Set(['physicalEnv.DSM']);

// Stored buildings in the default view (Map_init.js::addBuildingMask): a
// Mapbox `clip` layer erases the basemap's 3D buildings in the grid cells
// that hold stored buildings (mainMap/views.py::building_mask), and the
// stored ones are drawn there instead, loaded by viewport from this zoom on.
// Below it neither is shown, so the clip starts at the same zoom.
const DB_BUILDINGS_KEY = 'builtup.Building';
const DB_BUILDINGS_MASK_URL = '/api/layers/builtup/Building/mask/';
const DB_BUILDINGS_MIN_ZOOM = 14;
// The basemap's own 3D buildings ('3d-buildings', Map_init.js::add3DBuildings)
// are drawn as faint grey context, so the stored buildings stand out.
const BASEMAP_BUILDING_COLOR = '#9e9e9e';
const BASEMAP_BUILDING_OPACITY = 0.25;

// A colour, or a list of shades: each Mapbox building then takes one shade
// picked by its feature id (Map_init.js::buildingColorForTool), so the city
// looks less uniform and a building keeps its shade on every pan and reload.
const BUILDING_COLOR_DEFAULT = ['#bd643b', '#7c4d37', '#69351d'];
const BUILDING_COLOR_BY_TOOL = {
  water:       '#cde5fa',
  // temperature: '#c0504d',
  // housing:     '#d9a441',
  groundwater: '#b4e7e3',
};

// ── GUIDED TOUR ────────────────────────────────────────────────────────────
const TOUR_STEPS = [
  {
    num: 1,
    title: "① Select Topic",
    desc: "Pick a topic on the left: City systems, People or Environment. A topic shows only its own layers and legends and greys the rest of the map; Overview brings your own layers back.",
    target: ".toolbar",
  },
  {
    num: 2,
    title: "② Explore Current Data",
    desc: "Population shows the cities, districts and neighbourhoods: click one to make it the area every topic reports on. Layers in the bottom bar lists the topic's layers, with All layers for every dataset and the basemap style.",
    target: '[data-tool="administrative"]',
  },
  {
    num: 3,
    title: "③ Explore Indicators",
    desc: "Pick a topic like Water or Heat to load its indicators in the right panel. Indicators are calculated directly from the spatial database.",
    target: ".side-panel",
  },
  {
    num: 4,
    title: "④ Select Scenarios",
    desc: "The time chip at the top sets the year and the climate scenario for every panel. Compare scenarios opens the KNMI'23 scenarios; the sliders in a panel (e.g. consumption, interest rate) are what-ifs on top.",
    target: "#time-chip",
  },
  {
    num: 5,
    title: "⑤ Explore, Plan, Edit",
    desc: "The switch in the bottom bar sets the mode. Explore shows the stored data. Plan unlocks the what-if sliders and climate scenarios; a banner names every change from the stored baseline, and nothing is stored. Edit (staff) changes the data, draws new neighbourhoods and holds the restore point; staff import data from Data in the header.",
    target: "#mode-switch",
  },
  {
    num: 6,
    title: "⑥ Run Analysis",
    desc: "With scenario parameters set, trigger cross-domain calculations. The DPSIR causal network automatically links drivers (e.g. population growth) to urban impacts (heat, water stress).",
    target: null,
  },
  {
    num: 7,
    title: "⑦ View Results",
    desc: "Results populate the side panel as charts, KPI cards, and new map layers. Use the time chip at the top to compare the current baseline against future scenario projections.",
    target: "#panel-body",
  },
  {
    num: 8,
    title: "⑧ Export Results",
    desc: "Download scenario outputs as GeoJSON, CSV, or raster files. Share results with stakeholders or import into external GIS tools and technical reports.",
    target: null,
  },
];