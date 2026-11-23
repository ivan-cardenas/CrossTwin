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
    // and re-filter every layer's visibility via openLens() —
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
  // A basemap switch drops the lens's grey wash with the old style.
  map.on('style.load', syncLensDim);

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
    bindBuildingMaskEvents();
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
 * Colour of the 3D buildings for the active tool. A list of shades becomes a
 * `match` on the feature id modulo the list length: deterministic, so a
 * building keeps its shade across tiles, zooms and reloads (no Math.random).
 * Features without an id take the first shade.
 */
function buildingColorForTool() {
  const tool = document.querySelector('.tool-button.active')?.dataset.tool;
  const color = BUILDING_COLOR_BY_TOOL[tool] || BUILDING_COLOR_DEFAULT;
  if (!Array.isArray(color)) return color;
  if (color.length === 1) return color[0];
  const cases = color.slice(1).flatMap((shade, i) => [i + 1, shade]);
  return ['match', ['%', ['to-number', ['id'], 0], color.length], ...cases, color[0]];
}

/**
 * Update the color of 3D buildings
 */
function sync3DBuildingColor() {
  // Only the stored buildings follow the tool; the basemap's stay faint grey
  if (map.getLayer(DB_BASE_BUILDINGS_ID)) {
    map.setPaintProperty(DB_BASE_BUILDINGS_ID, 'fill-extrusion-color', buildingColorForTool());
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

const LENS_DIM_ID = 'lens-dim';

/**
 * Grey the basemap while a lens is open (Config.js::LENSES): a translucent
 * `background` layer drawn above the basemap and below our own layers.
 * Placed under the lowest loaded catalog layer, or on top when none is
 * loaded yet (layers added later go above it). Fades in and out; instant
 * with prefers-reduced-motion.
 */
function syncLensDim() {
  let style;
  try { style = map && map.getStyle(); } catch (_) { return; }
  if (!style) return;
  const on = !!LENSES[activeTool];
  const fade = window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 0 : LENS_DIM_FADE_MS;

  if (!map.getLayer(LENS_DIM_ID)) {
    if (!on) return;
    const ownIds = new Set(Object.values(loadedLayers).flatMap(entry => entry.layerIds));
    const beforeId = style.layers.find(layer => ownIds.has(layer.id))?.id;
    map.addLayer({
      id: LENS_DIM_ID,
      type: 'background',
      paint: {
        'background-color': LENS_DIM_COLOR,
        'background-opacity': 0,
      },
    }, beforeId);
  }
  map.setPaintProperty(LENS_DIM_ID, 'background-opacity-transition', { duration: fade, delay: 0 });
  map.setPaintProperty(LENS_DIM_ID, 'background-opacity', on ? LENS_DIM_OPACITY : 0);
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
        // Faint grey context (Config.js); the stored buildings
        // (db-base-buildings) keep the tool colours
        'fill-extrusion-color': BASEMAP_BUILDING_COLOR,
        'fill-extrusion-height': [
          'interpolate', ['linear'], ['zoom'],
          13, 0, 16, ['get', 'height']
        ],
        'fill-extrusion-base': [
          'interpolate', ['linear'], ['zoom'],
          13, 0, 16, ['get', 'min_height']
        ],
        'fill-extrusion-opacity': BASEMAP_BUILDING_OPACITY,
        // A see-through building casting a solid shadow looks wrong
        'fill-extrusion-cast-shadows': false,
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
  // Stored buildings above the extrusions and their edges; the clip that
  // erases the basemap's buildings goes on top of the style
  addBuildingMask(labelLayerId);

  // Stays hidden while a builtup layer is shown (also after a basemap switch,
  // which re-creates this layer)
  if (typeof sync3DBuildings === 'function') sync3DBuildings();
}

// ---- Stored buildings over the basemap's ------------------------------
//
// The basemap's 3D buildings know nothing of the database: a building added,
// generated or deleted on the map would not show outside the Built-up tool.
// Wherever the database holds buildings (50 m cells, mainMap/views.py::
// building_mask) a `clip` layer erases the basemap's extrusions and the
// stored buildings are drawn instead; elsewhere the basemap's stay.

const DB_BUILDING_MASK_ID = 'db-building-mask';
const DB_BASE_BUILDINGS_ID = 'db-base-buildings';
const EMPTY_FEATURE_COLLECTION = { type: 'FeatureCollection', features: [] };
let buildingMaskData = null;      // last mask FeatureCollection
let buildingMaskBounds = null;    // its [west, south, east, north], null when empty
let baseBuildingsAbort = null;
let baseBuildingsTimer = null;

/** [west, south, east, north] of a FeatureCollection's coordinates, or null when empty. */
function featureCollectionBounds(fc) {
  let w = Infinity, s = Infinity, e = -Infinity, n = -Infinity;
  const visit = (c) => {
    if (typeof c[0] === 'number') {
      w = Math.min(w, c[0]); e = Math.max(e, c[0]);
      s = Math.min(s, c[1]); n = Math.max(n, c[1]);
    } else c.forEach(visit);
  };
  for (const f of fc.features || []) if (f.geometry) visit(f.geometry.coordinates);
  return w === Infinity ? null : [w, s, e, n];
}

/** Whether the mask reaches into the current view (bounding boxes only). */
function buildingMaskInView() {
  if (!buildingMaskBounds || !map) return false;
  const b = map.getBounds();
  const [w, s, e, n] = buildingMaskBounds;
  return !(e < b.getWest() || w > b.getEast() || n < b.getSouth() || s > b.getNorth());
}

/**
 * Height of a stored building: the catalog style's expression (mainMap/
 * styles/layerStyles.py: height_m, else floors x storey, else a default), so
 * both drawings of the layer agree; a plain fallback until the catalog is in.
 */
function dbBuildingHeight() {
  const entry = (typeof availableLayers !== 'undefined' ? availableLayers : []).find(l => l.key === DB_BUILDINGS_KEY);
  const paint = entry?.style_layers?.find(def => def.type === 'fill-extrusion')?.paint;
  return paint?.['fill-extrusion-height'] ?? ['to-number', ['coalesce', ['get', 'height_m'], 10]];
}

/** Clip layer + stored-building layer below `beforeId`; (re)loads their data. */
function addBuildingMask(beforeId) {
  if (!map.getSource(DB_BUILDING_MASK_ID)) {
    map.addSource(DB_BUILDING_MASK_ID, { type: 'geojson', data: buildingMaskData || EMPTY_FEATURE_COLLECTION });
  }
  if (!map.getLayer(DB_BUILDING_MASK_ID)) {
    // On top of everything (keepBuildingMaskOnTop), not just above
    // '3d-buildings': Mapbox GL compares the clip's index in the draw order
    // with a building layer's index in style.order, and every layer a tool
    // adds pushes '3d-buildings' further down style.order than down the draw
    // order, so a clip right above it stops clipping once e.g. the Water
    // Supply layers load. Only fill-extrusions of a vector 'building' source
    // layer are clipped, so the stored buildings (GeoJSON) never are.
    map.addLayer({
      id: DB_BUILDING_MASK_ID,
      type: 'clip',
      source: DB_BUILDING_MASK_ID,
      minzoom: DB_BUILDINGS_MIN_ZOOM,
      // 'model' also takes the basemap's 3D models (trees, landmarks) out of
      // built cells; the scope keeps our own model layers (nature.Tree). Labels stay.
      layout: { 'clip-layer-types': ['model'], 'clip-layer-scope': ['basemap'] },
    });
  }
  if (!map.getSource(DB_BASE_BUILDINGS_ID)) {
    // promoteId: ['id'] is then the BAG id, so buildingColorForTool() gives
    // stored buildings the same per-building shades as the basemap's
    map.addSource(DB_BASE_BUILDINGS_ID, { type: 'geojson', data: EMPTY_FEATURE_COLLECTION, promoteId: 'id' });
  }
  if (!map.getLayer(DB_BASE_BUILDINGS_ID)) {
    map.addLayer({
      id: DB_BASE_BUILDINGS_ID,
      type: 'fill-extrusion',
      source: DB_BASE_BUILDINGS_ID,
      minzoom: DB_BUILDINGS_MIN_ZOOM,
      layout: { 'fill-extrusion-edge-radius': 0.5 },
      paint: {
        'fill-extrusion-color': buildingColorForTool(),
        'fill-extrusion-height': dbBuildingHeight(),
        'fill-extrusion-base': 0,
        'fill-extrusion-opacity': 1,
        'fill-extrusion-cast-shadows': true,
        'fill-extrusion-ambient-occlusion-intensity': 0.35,
        'fill-extrusion-ambient-occlusion-wall-radius': 3,
        'fill-extrusion-ambient-occlusion-ground-radius': 5,
        'fill-extrusion-vertical-gradient': true,
      },
    }, beforeId);
  }
  keepBuildingMaskOnTop();   // the stored-building layer may have landed above it
  reloadBuildingMask();
}

/** Re-fetch the mask, then the stored buildings in view. After edits and imports. */
async function reloadBuildingMask() {
  try {
    const response = await fetch(DB_BUILDINGS_MASK_URL);
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    buildingMaskData = await response.json();
    buildingMaskBounds = featureCollectionBounds(buildingMaskData);
    map.getSource(DB_BUILDING_MASK_ID)?.setData(buildingMaskData);
  } catch (error) {
    console.error('Error loading the building mask:', error);
  }
  reloadBaseBuildings();
  if (typeof sync3DBuildings === 'function') sync3DBuildings();
}

/** Stored buildings in the current view (nothing below the min zoom or outside the mask). */
async function reloadBaseBuildings() {
  const source = map.getSource(DB_BASE_BUILDINGS_ID);
  if (!source) return;
  if (map.getZoom() < DB_BUILDINGS_MIN_ZOOM || !buildingMaskInView()) return;

  baseBuildingsAbort?.abort();
  const controller = new AbortController();
  baseBuildingsAbort = controller;
  try {
    const response = await fetch(
      `/api/layers/builtup/Building/geojson/?${viewportQuery()}`, { signal: controller.signal });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const geojson = await response.json();
    if (baseBuildingsAbort !== controller) return;   // superseded
    source.setData(geojson);
    if (map.getLayer(DB_BASE_BUILDINGS_ID)) {
      map.setPaintProperty(DB_BASE_BUILDINGS_ID, 'fill-extrusion-height', dbBuildingHeight());
    }
  } catch (error) {
    if (error.name !== 'AbortError') console.error('Error loading stored buildings:', error);
  }
}

/** Move the clip layer back to the top after another layer was added above it. */
function keepBuildingMaskOnTop() {
  if (!map.getLayer(DB_BUILDING_MASK_ID)) return;
  // getLayersOrder() (GL JS v3) lists the root style's ids without
  // serialising the whole style as getStyle() would on every styledata
  let order;
  try {
    order = typeof map.getLayersOrder === 'function'
      ? map.getLayersOrder() : map.getStyle().layers.map(l => l.id);
  } catch (_) { return; }
  if (order.length && order[order.length - 1] !== DB_BUILDING_MASK_ID) map.moveLayer(DB_BUILDING_MASK_ID);
}

function bindBuildingMaskEvents() {
  // Fires on every addLayer/moveLayer; after our own move the clip is last,
  // so the check stops there
  map.on('styledata', keepBuildingMaskOnTop);
  map.on('moveend', () => {
    clearTimeout(baseBuildingsTimer);
    baseBuildingsTimer = setTimeout(() => {
      reloadBaseBuildings();
      if (typeof sync3DBuildings === 'function') sync3DBuildings();   // edges follow the mask
    }, VIEWPORT_RELOAD_DELAY_MS);
  });
  ['feature-saved', 'backup-restored'].forEach(name =>
    document.body.addEventListener(name, () => reloadBuildingMask()));
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