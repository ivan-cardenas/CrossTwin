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

// Configuration (set from Django template via initializeUrbanTwinMap)
let CONFIG = {
  mapboxToken: '{{ mapbox_access_token }}',
  layersApiUrl: '/api/layers/',
  initialCenter: [6.895, 52.219],
  initialZoom: 16,
  initialPitch: 60,
  initialBearing: -35
};

// Basemap styles
const BASEMAPS = {
  light:     'mapbox://styles/mapbox/light-v11',
  dark:      'mapbox://styles/mapbox/dark-v11',
  streets:   'mapbox://styles/mapbox/streets-v12',
  satellite: 'mapbox://styles/mapbox/satellite-streets-v12',
  outdoors:  'mapbox://styles/mapbox/outdoors-v12'
};

// 'common' (Province/City/District/Neighborhood) is included in every
// tool's categories so the administrative boundaries used to select a
// unit for the indicator panels stay clickable no matter which tool is active.
const TOOL_CATEGORIES = {
  overview:    ['common', 'urbanHeat', 'watersupply', 'weather', 'builtup', 'Energy', 'housing', 'nature', 'groundwater'],
  common:      ['common'],
  temperature: ['common', 'temperature', 'heat', 'weather', 'urban_heat,'],
  builtup:     ['common', 'builtup'],
  energy:      ['common', 'Energy'],
  housing:     ['common', 'housing'],
  green:       ['common', 'green', 'vegetation', 'trees', 'Park', 'LandCover'],
  water:       ['common', 'watersupply'],
  groundwater: ['common', 'groundwater'],
  satellite:   null,
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