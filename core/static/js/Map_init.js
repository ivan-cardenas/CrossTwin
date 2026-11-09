// ============================================================
// map-init.js — Map creation, 3D buildings, external layers
// Depends on: config.js
// ============================================================

// Maps each admin-hierarchy layer's registry key to the GeoJSON property
// (from mainMap/views.py:model_geojson) holding its display name, and the
// URL segment used to drive the watersupply/urban_heat indicator panels.
const ADMIN_LEVELS = {
  'administrative.Province':    { level: 'province',     nameField: 'ProvinceName' },
  'administrative.City':         { level: 'city',         nameField: 'cityName' },
  'administrative.District':     { level: 'district',     nameField: 'districtName' },
  'administrative.Neighborhood': { level: 'neighborhood', nameField: 'neighborhoodName' },
};

/**
 * Update the bottom-bar population pill. Shared by the admin-layer click
 * handler (population comes free on the clicked feature's properties) and
 * updateAdminUnitAtCenter (population comes from the point-in-polygon API).
 */
function setPopulationIndicator(pop) {
  const populationEl = document.getElementById('population-count');
  if (!populationEl) return;
  populationEl.textContent = (pop || pop === 0) ? Number(pop).toLocaleString() : '—';
}

/**
 * Called by layers.js once an admin-hierarchy layer's real Mapbox layer
 * IDs are known, so we never hardcode an ID that a LAYER_STYLES override
 * might have renamed.
 */
function onAdminLayerLoaded(key, layerIds) {
  const cfg = ADMIN_LEVELS[key];
  if (!cfg) return;

  map.on('click', layerIds[0], (e) => {
    // While editing, clicks are for the drawing tools, not for selecting a unit
    if (typeof isEditing === 'function' && isEditing()) return;
    const props = e.features[0].properties;
    window.ACTIVE_LEVEL = cfg.level;
    window.ACTIVE_LOCATION = props[cfg.nameField];
    // Explicit selection (unlike ACTIVE_*, which also tracks the map center
    // while panning): what the Dashboard summary reports the population of.
    window.SELECTED_UNIT = { level: cfg.level, location: props[cfg.nameField] };
    refreshPopulationViews();  // no-op for whatever is not showing

    // currentPopulation rides along on every admin-hierarchy feature's
    // properties (model_geojson serializes all non-geometry fields), so the
    // bottom-bar pill can update straight from the click — no extra request.
    setPopulationIndicator(props.currentPopulation);

    // syncPanelBtns/refreshActivePanel (defined in mainMap.html, driven by
    // the ADMIN_PANEL_TOOLS registry) update every admin-unit-driven panel's
    // URL and refresh whichever one is currently open — 'water' is only a
    // fallback for when no panel is open yet. Refreshing via htmx.ajax
    // rather than a real button click avoids bubbling into the #toolbar
    // delegated listener (events.js), which would treat it as a tool switch
    // and re-filter every layer's visibility via activateToolLayers() —
    // wiping out whatever visibility the user had set manually.
    syncPanelBtns();
    refreshActivePanel('water');
  });
}

/**
 * Point-in-polygon lookup against the map center, so the admin-unit state
 * (and the population pill) tracks panning, not just clicks on an
 * admin-hierarchy layer. Debounced from map.on('moveend'), same as
 * updateCityName — reverse geocoding and this hit different endpoints for
 * a similar reason: Nominatim gives a human place name for any point on
 * Earth, while this queries our own DB for the Province/City/District/
 * Neighborhood record that actually contains the point.
 */
async function updateAdminUnitAtCenter() {
  const center = map.getCenter();

  try {
    const response = await fetch(`/api/admin-unit/?lng=${roundCoord(center.lng)}&lat=${roundCoord(center.lat)}`);
    const data = await response.json();

    if (!data.level || !data.location) return;

    window.ACTIVE_LEVEL = data.level;
    window.ACTIVE_LOCATION = data.location;
    setPopulationIndicator(data.population);
    // Without an explicit selection the summary follows the map center's city
    if (!window.SELECTED_UNIT) refreshPopulationViews();

    syncPanelBtns();
    // No fallback tool here — panning shouldn't force a panel open, only
    // keep an already-open one in sync (unlike an explicit layer click).
    refreshActivePanel();
  } catch (error) {
    console.error('Error resolving admin unit at map center:', error);
  }
}

// sessionStorage (not localStorage) on purpose: camera position should
// follow the user across page navigations within the same browsing
// session — e.g. leaving for the watersupply dashboard and coming back —
// but a fresh tab/session should still land on CONFIG's configured default.
const CAMERA_STORAGE_KEY = 'crosstwin_map_camera';

/**
 * Persist the current camera position so it survives a navigation away
 * from the map page (a real Django page load, not a client-side route —
 * an in-memory JS variable wouldn't survive that).
 */
function saveCameraState() {
  if (!map) return;
  try {
    const center = map.getCenter();
    sessionStorage.setItem(CAMERA_STORAGE_KEY, JSON.stringify({
      center: [center.lng, center.lat],
      zoom: map.getZoom(),
      pitch: map.getPitch(),
      bearing: map.getBearing(),
    }));
  } catch (e) {
    // sessionStorage unavailable (private browsing, etc.) — camera just won't persist
  }
}

/**
 * Read back a previously saved camera position, if any.
 */
function getSavedCameraState() {
  try {
    const raw = sessionStorage.getItem(CAMERA_STORAGE_KEY);
    if (!raw) return null;
    const state = JSON.parse(raw);
    if (!Array.isArray(state.center) || state.center.length !== 2) return null;
    return state;
  } catch (e) {
    return null;
  }
}

/**
 * Initialize the Urban Twin map
 * @param {object} config - Configuration from Django template
 */
function initializeUrbanTwinMap(config) {
  CONFIG = { ...CONFIG, ...config };
  mapboxgl.accessToken = CONFIG.mapboxToken;

  // Resume wherever the user left the camera last time, instead of always
  // resetting to the configured default view.
  const savedCamera = getSavedCameraState();
  if (savedCamera) tilted = savedCamera.pitch > 0;

  map = new mapboxgl.Map({
    container: 'map',
    style: BASEMAPS[activeBasemap],
    center: savedCamera ? savedCamera.center : CONFIG.initialCenter,
    zoom: savedCamera ? savedCamera.zoom : CONFIG.initialZoom,
    pitch: savedCamera ? savedCamera.pitch : CONFIG.initialPitch,
    bearing: savedCamera ? savedCamera.bearing : CONFIG.initialBearing,
    // WMS tile URLs (KNMI radar, PDOK groundwater, ...) get their bbox from
    // Mapbox at full float precision; round it before the request goes out.
    transformRequest: (url, resourceType) => (
      resourceType === 'Tile' && /[?&]bbox=/i.test(url) ? { url: roundBboxInUrl(url) } : undefined
    ),
  });

  // Every style (the first one and each basemap switch) starts with its own
  // 3D trees visible; hide them again if the active tool needs it.
  map.on('style.load', syncBasemapTrees);

  map.addControl(new mapboxgl.NavigationControl(), 'top-right');
  map.addControl(new mapboxgl.FullscreenControl(), 'top-right');
  
 
  // Add the control to the map.
  map.addControl(new MapboxGeocoder({
            accessToken: mapboxgl.accessToken,
            useBrowserFocus: true,
            mapboxgl: mapboxgl,

        }), 'top-left');
  
  map.addControl(new mapboxgl.GeolocateControl({
    positionOptions: {
      enableHighAccuracy: true
    },
    trackUserLocation: true
  }), 'top-right');
  map.addControl(new mapboxgl.ScaleControl(), 'top-left');

  console.log('Map initialized');

  map.on('load', () => {
    console.log('Map loaded successfully');
    
    addExternalLayers();
    initFeaturePopup();
    fetchAvailableLayers();
    add3DBuildings();
    updateCityName();
    updateAdminUnitAtCenter();

    map.on('moveend', () => {
      clearTimeout(cityNameTimeout);
      cityNameTimeout = setTimeout(updateCityName, 500);
      clearTimeout(adminUnitTimeout);
      adminUnitTimeout = setTimeout(updateAdminUnitAtCenter, 500);
      saveCameraState();
    });
  });

  map.on('error', (e) => {
    console.error('Map error:', e.error);
  });

  window.ACTIVE_LEVEL = 'province'; /* For demo purposes, set a default level */
  window.ACTIVE_LOCATION = 'Demo'; /* For demo purposes, set a default location */
  window.ACTIVE_YEAR = 2025; /* For demo purposes, set a default year */

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
 * Determine the color for 3D buildings based on the active tool
 */
function buildingColorForTool() {
  const tool = document.querySelector('.tool-button.active')?.dataset.tool;
  return BUILDING_COLOR_BY_TOOL[tool] || BUILDING_COLOR_DEFAULT;
}

/**
 * Update the color of 3D buildings
 */
function sync3DBuildingColor() {
  if (map.getLayer('3d-buildings')) {
    map.setPaintProperty('3d-buildings', 'fill-extrusion-color', buildingColorForTool());
  }
}

/**
 * Tools that show the database's own trees (nature.Tree, a 3D model per row,
 * mainMap/styles/treeStyles.py): the basemap's generic 3D trees are hidden
 * while one of them is active, so every tree on screen is a stored one.
 */
const TOOLS_WITHOUT_BASEMAP_TREES = new Set(['green']);
const BASEMAP_TREE_PATTERN = /tree/i;

/**
 * Show or hide the basemap's own 3D trees for the active tool. Covers both
 * ways a Mapbox style can carry them:
 *  - an imported Mapbox Standard style: its `show3dTrees` config property
 *    (left alone when the import has no such property: `show3dObjects`
 *    would also take the 3D buildings away);
 *  - a classic style: `model` layers whose id or source layer names trees,
 *    and that are not one of our own layers (sources of loadedLayers).
 * Re-run after every tool click and every style.load (a basemap switch
 * recreates the style).
 */
function syncBasemapTrees() {
  // Not isStyleLoaded(): that is also false while tiles load. A style that is
  // not parsed yet is caught by the style.load listener instead.
  let style;
  try { style = map && map.getStyle(); } catch (_) { return; }
  if (!style) return;
  const tool = document.querySelector('.tool-button.active')?.dataset.tool;
  const show = !TOOLS_WITHOUT_BASEMAP_TREES.has(tool);

  for (const imp of style.imports || []) {
    try {
      if (map.getConfigProperty(imp.id, 'show3dTrees') != null) {
        map.setConfigProperty(imp.id, 'show3dTrees', show);
      }
    } catch (err) {
      console.warn(`Basemap import "${imp.id}": cannot toggle 3D trees`, err);
    }
  }

  const ownSources = new Set(Object.keys(typeof loadedLayers !== 'undefined' ? loadedLayers : {}));
  for (const layer of style.layers || []) {
    if (layer.type !== 'model' || ownSources.has(layer.source)) continue;
    if (!BASEMAP_TREE_PATTERN.test(layer.id) && !BASEMAP_TREE_PATTERN.test(layer['source-layer'] || '')) continue;
    map.setLayoutProperty(layer.id, 'visibility', show ? 'visible' : 'none');
  }
}

/**
 * Ids of the thin outline layers drawn on top of '3d-buildings'
 * (roof outline + footprint outline). Layers.js::sync3DBuildings shows and
 * hides them together with the extrusions.
 */
const BUILDING_EDGE_LAYER_IDS = ['3d-buildings-edges-roof', '3d-buildings-edges-base'];
const BUILDING_EDGE_COLOR = '#494949';

/**
 * Thin edges on the Mapbox 3D buildings.
 *
 * fill-extrusion has no outline property in the style spec, so the edges are
 * line layers on the same source-layer: the polygon rings raised to the roof
 * with line-z-offset, and one at the ground. line-occlusion-opacity hides the
 * parts behind other buildings. They start at zoom 16, where the extrusion
 * has reached its full height (its height interpolates over 13–16), so the
 * roof line sits on the roof. line-z-offset is a layout property, evaluated
 * per tile zoom, so it can't follow that interpolation smoothly.
 */
function add3DBuildingEdges(beforeId) {
  const common = {
    type: 'line',
    source: 'composite',
    'source-layer': 'building',
    filter: ['==', ['get', 'extrude'], 'true'],
    minzoom: 16,
    paint: {
      'line-color': BUILDING_EDGE_COLOR,
      'line-width': ['interpolate', ['linear'], ['zoom'], 16, 0.4, 18, 0.8, 20, 1.2],
      'line-opacity': ['interpolate', ['linear'], ['zoom'], 16, 0, 16.5, 0.7],
      'line-occlusion-opacity': 0,
    },
  };
  const edges = [
    { id: BUILDING_EDGE_LAYER_IDS[0], zOffset: ['get', 'height'] },
    { id: BUILDING_EDGE_LAYER_IDS[1], zOffset: ['get', 'min_height'] },
  ];
  for (const { id, zOffset } of edges) {
    if (map.getLayer(id)) continue;
    map.addLayer({
      ...common,
      id,
      layout: {
        'line-join': 'miter',
        'line-elevation-reference': 'ground',
        'line-z-offset': zOffset,
      },
    }, beforeId);
  }
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
      minzoom: 5,
      // Bevels every edge, so the vertical corners catch the light and read
      // as a lighter or darker line between two walls (fill-extrusion has
      // no stroke, and a line layer can only draw horizontal edges)
      layout: {
        'fill-extrusion-edge-radius': 0.5,
      },
      paint: {
        
        'fill-extrusion-color': buildingColorForTool(),
        'fill-extrusion-height': [
          'interpolate', ['linear'], ['zoom'],
          13, 0, 16, ['get', 'height']
        ],
        'fill-extrusion-base': [
          'interpolate', ['linear'], ['zoom'],
          13, 0, 16, ['get', 'min_height']
        ],
        'fill-extrusion-opacity': 1,
        // 'fill-extrusion-opacity': [
        //   'interpolate', ['linear'], ['zoom'],
        //   13, 1, 20, 0.80 ],        
        'fill-extrusion-cast-shadows': true,
        // Darkens the inside corners between walls and the foot of each wall
        // (~0.3 is the value the style spec calls plausible for buildings)
        'fill-extrusion-ambient-occlusion-intensity': 0.35,
        'fill-extrusion-ambient-occlusion-wall-radius': 3,
        'fill-extrusion-ambient-occlusion-ground-radius': 5,
        'fill-extrusion-vertical-gradient': true,
        'fill-extrusion-height-alignment': 'terrain',
      }
    }, labelLayerId);
  }

  add3DBuildingEdges(labelLayerId);

  // Stays hidden while a builtup layer is shown (also after a basemap switch,
  // which re-creates this layer)
  if (typeof sync3DBuildings === 'function') sync3DBuildings();
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
        `&width=${WMS_TILE_SIZE}&height=${WMS_TILE_SIZE}&crs=EPSG:3857` +
        '&bbox={bbox-epsg-3857}'
      ],
      tileSize: WMS_TILE_SIZE
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

  // setStyle() removes Draw's layers along with everything else
  if (typeof stopEdit === 'function') stopEdit();

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