// ============================================================
// config.js — Global state, configuration & constants
// ============================================================

let map;
let availableLayers = [];
const loadedLayers = {};
const layerVisibility = {};
let activeBasemap = 'light';
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
  overview:      ['administrative', 'urban_heat', 'watersupply', 'weather', 'builtup', 'Energy', 'housing', 'nature', 'groundwater'],
  administrative:['administrative'],
  temperature:   ['administrative', 'temperature', 'heat', 'weather', 'urban_heat'],
  builtup:       ['administrative', 'builtup'],
  energy:        ['administrative', 'Energy'],
  housing:       ['administrative', 'housing'],
  green:         ['administrative', 'physicalEnv', 'nature', 'green', 'vegetation', 'trees', 'Park', 'LandCover'],
  water:         ['administrative', 'watersupply'],
  groundwater:   ['administrative', 'groundwater'],
  satellite:     null,
};

const TOOL_CONTENT = {
  overview: {
    title: 'OVERVIEW',
    body: `
      <p>Welcome to the Urban Digital Twin. Use camera tools to explore the 3D city.</p>
      <p>Click the <strong>📑 Layers</strong> button to manage database layers, or select thematic views from the toolbar.</p>
    `
  },
  temperature: {
    title: 'URBAN HEAT',
    body: `
      <p>Visualize heat stress hotspots by overlaying land surface temperature data.</p>
      <p>Use this view for metrics like average heat index, exposed population, and priority cooling areas.</p>
    `
  },
  green: {
    title: 'GREEN INFRASTRUCTURE',
    body: `<p>View parks, trees, and green spaces. Combine with heat indicators to locate greening priorities.</p>`
  },
  water: {
    title: 'WATER INFRASTRUCTURE',
    body: `<p>Display water pipes, wells, and supply network. Relate demand to housing and population forecasts.</p>`
  },
  groundwater: {
    title: 'GROUNDWATER LEVELS',
    body: `
      <p>Groundwater depth measurements from the Dutch national registry (BRO).</p>
      <p>GHG = Average Highest Groundwater Level (Gemiddeld Hoogste Grondwaterstand)</p>
    `
  }
};