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

// 'administrative' (Province/City/District/Neighborhood) is included in
// every tool's categories so the administrative boundaries used to select a
// unit for the indicator panels stay clickable no matter which tool is active.
const TOOL_CATEGORIES = {
  overview:      ['administrative', 'urban_heat', 'watersupply', 'physicalEnv', 'weather', 'builtup', 'Energy', 'housing', 'nature', 'groundwater'],
  administrative:['administrative'],
  temperature:   ['administrative', 'temperature', 'weather', 'urban_heat'],
  builtup:       ['administrative', 'builtup'],
  energy:        ['administrative', 'Energy'],
  housing:       ['administrative', 'housing'],
  green:         ['administrative', 'nature', 'green', 'vegetation', 'trees', 'GreenSpaces', 'LandCover'],
  physicalEnv:   ['administrative', 'physicalEnv'],
  water:         ['administrative', 'watersupply'],
  // groundwater:   ['administrative', 'groundwater'],
  satellite:     null,
};

const TOOL_CONTENT = {
  overview: {
    title: 'Overview',
    body: `
      <p>Welcome to the Urban Digital Twin. Use the camera buttons to explore the 3D city.</p>
      <p>Pick a topic on the left to see its indicators, or open <strong>Layers</strong> in the bottom bar to switch map layers on and off.</p>
    `
  },
  temperature: {
    title: 'Urban heat',
    body: `
      <p>Visualize heat stress hotspots by overlaying land surface temperature data.</p>
      <p>Use this view for metrics like average heat index, exposed population, and priority cooling areas.</p>
    `
  },
  green: {
    title: 'Green and blue space',
    body: `
      <p class="no-indicators">No indicators yet.</p>
      <p>Its map layers (parks, trees, green spaces, water bodies) are switched on and listed in the Layers panel. Combine them with the Heat topic to find where greening helps most.</p>
    `
  },
  water: {
    title: 'Water supply',
    body: `<p>Display water pipes, wells, and supply network. Relate demand to housing and population forecasts.</p>`
  },
  groundwater: {
    title: 'Groundwater levels',
    body: `
      <p>Groundwater depth measurements from the Dutch national registry (BRO).</p>
      <p>GHG = Average Highest Groundwater Level (Gemiddeld Hoogste Grondwaterstand)</p>
    `
  },
  // Topics without an indicator panel yet: say so, and point at their layers
  // (switched on by Events.js::activateToolLayers when the topic is picked).
  administrative: {
    title: 'Administrative units',
    body: `
      <p class="no-indicators">No indicators yet.</p>
      <p>Provinces, cities, districts and neighbourhoods are listed in the Layers panel. Click a unit on the map to make it the area the other topics report on.</p>
    `
  },
  energy: {
    title: 'Energy',
    body: `
      <p class="no-indicators">No indicators yet.</p>
      <p>Its map layers are switched on and listed in the Layers panel.</p>
    `
  },
  physicalEnv: {
    title: 'Ground',
    body: `
      <p class="no-indicators">No indicators yet.</p>
      <p>Soil, terrain (DEM, DSM), land cover and groundwater layers are switched on and listed in the Layers panel. Soil and groundwater feed the Water topic's recharge card.</p>
    `
  },
};

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
    desc: "Start by picking a topic from the left toolbar: Housing, Energy, Heat, Water and more. Each one switches the data context for the whole platform.",
    target: ".toolbar",
  },
  {
    num: 2,
    title: "② Explore Current Data",
    desc: "Click Areas to open the Layers panel with the administrative units, or Layers in the bottom bar for every dataset. Switch layers on and off and choose a basemap style.",
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
    desc: "Use the Dashboard and Scenarios buttons at the bottom-right. Adjust sliders and input overrides (e.g. consumption, interest rate) to model what-if futures and compare years.",
    target: ".bottom-right",
  },
  {
    num: 5,
    title: "⑤ Import Data",
    desc: "Open the Actions menu in the bottom bar. Upload your own GeoJSON or Shapefile with 'Upload Data', or pull live datasets from PDOK, CBS, Sentinel-2, and Google Earth Engine via 'Retrieve Data from APIs'.",
    target: "#actions-menu-btn",
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
    desc: "Results populate the side panel as charts, KPI cards, and new map layers. Use the year selector in the Actions menu to compare the current baseline against future scenario projections.",
    target: "#panel-body",
  },
  {
    num: 8,
    title: "⑧ Export Results",
    desc: "Download scenario outputs as GeoJSON, CSV, or raster files. Share results with stakeholders or import into external GIS tools and technical reports.",
    target: null,
  },
];