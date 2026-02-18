// ============================================================
// map-init.js — Map creation, 3D buildings, external layers
// Depends on: config.js
// ============================================================

/**
 * Initialize the Urban Twin map
 * @param {object} config - Configuration from Django template
 */
function initializeUrbanTwinMap(config) {
  CONFIG = { ...CONFIG, ...config };
  mapboxgl.accessToken = CONFIG.mapboxToken;

  map = new mapboxgl.Map({
    container: 'map',
    style: BASEMAPS[activeBasemap],
    center: CONFIG.initialCenter,
    zoom: CONFIG.initialZoom,
    pitch: CONFIG.initialPitch,
    bearing: CONFIG.initialBearing
  });

  map.addControl(new mapboxgl.NavigationControl(), 'top-right');
  map.addControl(new mapboxgl.ScaleControl(), 'bottom-right');

  map.on('load', () => {
    console.log('Map loaded successfully');
    add3DBuildings();
    addExternalLayers();
    fetchAvailableLayers();
    updateCityName();

    map.on('moveend', () => {
      clearTimeout(cityNameTimeout);
      cityNameTimeout = setTimeout(updateCityName, 500);
    });
  });

  map.on('error', (e) => {
    console.error('Map error:', e.error);
  });

  initializeUI();
  return map;
}

/**
 * Safely fit bounds with size checks
 */
function safeFitBounds(bounds, options = {}) {
  if (!map) return;
  map.resize();

  const canvas = map.getCanvas();
  const w = canvas.clientWidth;
  const h = canvas.clientHeight;

  const p = options.padding || 0;
  const padX = typeof p === 'number' ? p * 2 : (p.left || 0) + (p.right || 0);
  const padY = typeof p === 'number' ? p * 2 : (p.top || 0) + (p.bottom || 0);

  if (w <= padX + 40 || h <= padY + 40) {
    console.warn('Skipping fitBounds: map too small', { w, h, p });
    return;
  }

  map.fitBounds(bounds, options);
}

/**
 * Add 3D building extrusions
 */
function add3DBuildings() {
  const layers = map.getStyle().layers;
  let labelLayerId;

  for (const layer of layers) {
    if (layer.type === 'symbol' && layer.layout['text-field']) {
      labelLayerId = layer.id;
      break;
    }
  }

  if (!map.getLayer('3d-buildings')) {
    map.addLayer({
      id: '3d-buildings',
      source: 'composite',
      'source-layer': 'building',
      filter: ['==', ['get', 'extrude'], 'true'],
      type: 'fill-extrusion',
      minzoom: 13,
      paint: {
        'fill-extrusion-color': '#d0e0f0',
        'fill-extrusion-height': [
          'interpolate', ['linear'], ['zoom'],
          13, 0, 16, ['get', 'height']
        ],
        'fill-extrusion-base': [
          'interpolate', ['linear'], ['zoom'],
          13, 0, 16, ['get', 'min_height']
        ],
        'fill-extrusion-opacity': 0.7
      }
    }, labelLayerId);
  }
}

/**
 * Add external WMS/raster layers (groundwater, etc.)
 */
function addExternalLayers() {
  if (!map.getSource('groundwater-level')) {
    map.addSource('groundwater-level', {
      type: 'raster',
      tiles: [
        'https://service.pdok.nl/bzk/bro-grondwaterspiegeldiepte/wms/v2_0' +
        '?service=WMS&request=GetMap&version=1.3.0' +
        '&layers=bro-grondwaterspiegeldieptemetingen-GHG' +
        '&styles=&format=image/png&transparent=true' +
        '&width=256&height=256&crs=EPSG:3857' +
        '&bbox={bbox-epsg-3857}'
      ],
      tileSize: 256
    });
  }

  if (!map.getLayer('groundwater-level')) {
    map.addLayer({
      id: 'groundwater-level',
      type: 'raster',
      source: 'groundwater-level',
      layout: { visibility: 'none' },
      paint: { 'raster-opacity': 0.7 }
    });
  }
}

/**
 * Change basemap style, preserving layer state
 */
function changeBasemap(basemapKey) {
  if (!BASEMAPS[basemapKey] || activeBasemap === basemapKey) return;

  activeBasemap = basemapKey;
  const currentVisibility = { ...layerVisibility };

  map.setStyle(BASEMAPS[basemapKey]);

  map.once('style.load', () => {
    add3DBuildings();
    addExternalLayers();

    for (const key of Object.keys(loadedLayers)) {
      delete loadedLayers[key];
    }

    for (const layer of availableLayers) {
      if (currentVisibility[layer.key]) {
        addLayer(layer);
      }
    }
  });
}

// Expose to global scope
window.initializeUrbanTwinMap = initializeUrbanTwinMap;