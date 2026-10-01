// ============================================================
// layers.js — Layer fetching, adding, toggling, zoom
// Depends on: config.js, map-init.js (for map & safeFitBounds)
// ============================================================

let loaderTimeout = null;
const LOADER_SHOW_DELAY_MS = 5000;  // only surface it for genuinely slow loads

/**
 * Show/hide loading indicator
 */
function showLoader(show) {
  const loader = document.getElementById('map-loader');
  if (!loader) return;

  if (show) {
    loaderTimeout = setTimeout(() => loader.classList.add('visible'), LOADER_SHOW_DELAY_MS);
  } else {
    clearTimeout(loaderTimeout);
    loader.classList.remove('visible');
  }
}

// ---- Fetch & render ---------------------------------------------------

/**
 * Fetch available layers from Django API.
 *
 * /api/layers/ costs at least one DB query per registered model (a full
 * .objects.all() for WMS/raster entries), so asking for the whole registry
 * up front was the main contributor to slow map init. Load the small,
 * always-needed 'administrative' admin-hierarchy layers (province/city/district/
 * neighborhood — these drive the city-click handlers and indicator panels)
 * first so the map UI is usable immediately, then fetch every other app's
 * layers in the background and merge them in once they arrive.
 */
async function fetchAvailableLayers() {
  try {
    await loadLayerCatalog('administrative');
  } catch (error) {
    console.error('Error fetching layers:', error);
    const container = document.getElementById('layer-list');
    if (container) {
      container.innerHTML = '<div class="no-layers">Error loading layers. Check API connection.</div>';
    }
    return;
  }

  loadLayerCatalog().catch(error => {
    console.error('Error fetching remaining layers:', error);
  });
}

/**
 * Fetch one batch of the layer catalog and merge it into availableLayers.
 * @param {string} [appLabels] - comma-separated app_labels to restrict to; omit for everything.
 */
async function loadLayerCatalog(appLabels) {
  const url = appLabels
    ? `${CONFIG.layersApiUrl}?app_labels=${encodeURIComponent(appLabels)}`
    : CONFIG.layersApiUrl;

  const response = await fetch(url);
  if (!response.ok) throw new Error('Failed to fetch layers');
  const data = await response.json();

  // Merge rather than replace — a later batch (e.g. the unfiltered
  // background fetch) re-includes 'administrative' layers already loaded, and
  // must not clobber their loadedLayers/visibility state.
  const existingKeys = new Set(availableLayers.map(l => l.key));
  for (const layer of data.layers) {
    if (!existingKeys.has(layer.key)) {
      availableLayers.push(layer);
      // is_active is only set on WMS layers; a slow-loading one (e.g. the
      // KNMI radar) can be flagged inactive so it starts unchecked instead
      // of auto-loading when its panel opens.
      layerVisibility[layer.key] = layer.is_active !== false;
    }
  }

  renderLayerList();
  updateIndicators();
}

// ---- Add layers -------------------------------------------------------

/**
 * Add a layer to the map (vector, raster, or WMS)
 */
async function addLayer(layerConfig) {
  const { key, url, color, geometry_type, display_name, layer_type, app_label, model_name, raster_id, style_layers } = layerConfig;

  if (loadedLayers[key]) return;

  if (layer_type === 'wms' && layerConfig.has_time_dimension) { addAnimatedWmsLayer(layerConfig); return; }
  if (layer_type === 'wms')    { addWmsLayer(layerConfig); return; }
  if (layer_type === 'raster') { await addRasterLayerFromConfig(layerConfig); return; }

  // Vector layer
  const viewport = usesViewportLoading(layerConfig);
  console.log(`Loading layer "${key}"${viewport ? ' (viewport only)' : ''}...`);

  try {
    showLoader(true);

    const response = await fetch(viewport ? `${url}?${viewportQuery()}` : url);
    if (!response.ok) throw new Error(`Failed to load ${key}`);

    const geojson = await response.json();

    map.addSource(key, { type: 'geojson', data: geojson });

    const layerIds = [];

    if (style_layers && style_layers.length > 0) {
      // Use explicit Mapbox layer definitions from the API
      style_layers.forEach((def, i) => {
        const layerId = `${key}-custom-${i}`;
        map.addLayer({
          id: layerId,
          type: def.type,
          source: key,
          paint: def.paint || {},
          layout: def.layout || {},
        });
        layerIds.push(layerId);
      });

    } else if (geometry_type === 'point') {
      map.addLayer({
        id: `${key}-points`, type: 'circle', source: key,
        paint: {
          'circle-radius': 6, 'circle-color': color,
          'circle-stroke-width': 2, 'circle-stroke-color': '#ffffff'
        }
      });
      layerIds.push(`${key}-points`);

    } else if (geometry_type === 'line') {
      map.addLayer({
        id: `${key}-lines`, type: 'line', source: key,
        paint: { 'line-color': color, 'line-width': 3 }
      });
      layerIds.push(`${key}-lines`);

    } else {
      // Polygon
      map.addLayer({
        id: `${key}-fill`, type: 'fill', source: key,
        paint: { 'fill-color': color, 'fill-opacity': 0.35 }
      });
      map.addLayer({
        id: `${key}-outline`, type: 'line', source: key,
        paint: { 'line-color': color, 'line-width': 2 }
      });
      layerIds.push(`${key}-fill`, `${key}-outline`);
    }

    loadedLayers[key] = { layerIds, geojson, config: layerConfig, viewport };
    if (viewport) bindViewportReload();

    if (layerConfig.legend && layerConfig.legend.length) {
      addCategoricalLegend(key, display_name, layerConfig.legend);
    }

    if (typeof onAdminLayerLoaded === 'function') onAdminLayerLoaded(key, layerIds);

    // Popup on click: handled once for all layers by initFeaturePopup(), so
    // overlapping features from several layers share a single popup.
    const clickLayerId = layerIds[0];
    popupLayers.set(clickLayerId, { key, name: display_name, fields: layerConfig.fields || {}, color });
    map.on('mouseenter', clickLayerId, () => { map.getCanvas().style.cursor = 'pointer'; });
    map.on('mouseleave', clickLayerId, () => { map.getCanvas().style.cursor = ''; });

    console.log(`Layer "${key}" loaded with ${geojson.features.length} features`);
    sync3DBuildings();
    updateIndicators();

  } catch (error) {
    console.error(`Error loading layer "${key}":`, error);
  } finally {
    showLoader(false);
  }
}

// ---- Viewport-loaded vector layers --------------------------------------
//
// A layer with many features (buildings, streets, land cover) would
// otherwise be fetched whole, however little of it is on screen. These
// layers ask the GeoJSON endpoint for the current viewport only (it filters
// on the spatial index and simplifies geometry below zoom 14) and re-fetch
// after each pan/zoom. Superseded requests are aborted so a fast pan never
// paints an older viewport over a newer one.

let viewportReloadBound = false;
let viewportReloadTimer = null;

function usesViewportLoading(layerConfig) {
  return layerConfig.app_label !== 'administrative'
    && Number(layerConfig.count) >= VIEWPORT_LOAD_MIN_FEATURES;
}

function viewportQuery() {
  const b = map.getBounds();
  const clamp = (v, lo, hi) => Math.min(Math.max(v, lo), hi);
  // Rounded *outward* to COORD_DECIMALS, so the box never shrinks and drops
  // features at the edge of the screen.
  const step = 10 ** COORD_DECIMALS;
  const down = v => (Math.floor(v * step) / step).toFixed(COORD_DECIMALS);
  const up = v => (Math.ceil(v * step) / step).toFixed(COORD_DECIMALS);
  const bbox = [
    down(clamp(b.getWest(), -180, 180)), down(clamp(b.getSouth(), -90, 90)),
    up(clamp(b.getEast(), -180, 180)), up(clamp(b.getNorth(), -90, 90)),
  ].join(',');
  return `bbox=${bbox}&zoom=${Math.floor(map.getZoom())}`;
}

function bindViewportReload() {
  if (viewportReloadBound) return;
  viewportReloadBound = true;
  map.on('moveend', () => {
    clearTimeout(viewportReloadTimer);
    viewportReloadTimer = setTimeout(() => {
      for (const [key, entry] of Object.entries(loadedLayers)) {
        if (entry.viewport) reloadViewportLayer(key);
      }
    }, VIEWPORT_RELOAD_DELAY_MS);
  });
}

async function reloadViewportLayer(key) {
  const entry = loadedLayers[key];
  if (!entry || !entry.viewport || layerVisibility[key] === false) return;

  entry.abortController?.abort();
  const controller = new AbortController();
  entry.abortController = controller;

  try {
    const response = await fetch(`${entry.config.url}?${viewportQuery()}`, { signal: controller.signal });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const geojson = await response.json();
    // The layer may have been removed (basemap switch) while this was in flight
    if (loadedLayers[key] !== entry) return;
    map.getSource(key)?.setData(geojson);
    entry.geojson = geojson;
    updateIndicators();
  } catch (error) {
    if (error.name !== 'AbortError') console.error(`Error reloading layer "${key}":`, error);
  }
}

// ---- WMS layers -------------------------------------------------------

function addWmsLayer(layerConfig) {
  const { key, wms_url, wms_layers, opacity, display_name } = layerConfig;
  if (map.getSource(key)) return;

  const tileUrl = wms_url +
    '?service=WMS&request=GetMap&version=1.3.0' +
    `&layers=${wms_layers}&styles=&format=image/png&transparent=true` +
    `&width=${WMS_TILE_SIZE}&height=${WMS_TILE_SIZE}&crs=EPSG:3857&bbox={bbox-epsg-3857}`;

  map.addSource(key, { type: 'raster', tiles: [tileUrl], tileSize: WMS_TILE_SIZE });
  map.addLayer({
    id: key, type: 'raster', source: key,
    layout: { visibility: 'visible' },
    paint: { 'raster-opacity': opacity || 0.7 }
  });

  loadedLayers[key] = {
    layerIds: [key],
    geojson: { features: [] },
    config: layerConfig
  };

  if (layerConfig.legend_url) addWmsLegend(key, display_name, layerConfig.legend_url);
  console.log(`WMS layer "${key}" added`);
  updateIndicators();
}

function addWmsLegend(key, title, legendUrl) {
  const existing = document.getElementById(`legend-${key}`);
  if (existing) existing.remove();

  const legend = document.createElement('div');
  legend.id = `legend-${key}`;
  legend.className = 'map-legend dynamic-legend';
  legend.innerHTML = `
    <div class="legend-title">${title}</div>
    <img src="${legendUrl}" alt="${title} legend" />
  `;
  document.getElementById('legend-stack')?.appendChild(legend);
  legend.querySelector('img').addEventListener('load', repositionDynamicLegends);
  repositionDynamicLegends();
}

// ---- Time-dimension WMS layers ------------------------------------------
//
// A single raster source/layer is reused for every time step (source.setTiles
// swaps the TIME param) rather than one layer per frame — remote WMS servers
// commonly rate-limit (e.g. KNMI's anonymous tier: 1 request/sec/IP). Loading
// all frames as separate always-visible layers up front, or panning/zooming
// with N stacked layers, multiplies tile requests by the frame count and can
// blow through that limit almost immediately. A single source only ever
// requests tiles for the one frame currently shown, and slider drags are
// debounced (WMS_RATE_LIMIT_MS) so fast dragging can't outrun the 1 req/sec cap.

const wmsAnimations = {};       // key -> { times, index, refreshTimer, debounceTimer }
const DEFAULT_TIME_REFRESH_MINUTES = 5;  // fallback if a layer doesn't specify its own cadence
const WMS_RATE_LIMIT_MS = 1100;          // stay safely under a 1 request/sec/IP cap

function wmsTileUrlForTime(wms_url, wms_layers, time) {
  const separator = wms_url.includes('?') ? '&' : '?';
  return wms_url + separator +
    'service=WMS&request=GetMap&version=1.3.0' +
    `&layers=${wms_layers}&styles=&format=image/png&transparent=true` +
    `&width=${WMS_TILE_SIZE}&height=${WMS_TILE_SIZE}&crs=EPSG:3857&bbox={bbox-epsg-3857}&TIME=${time}`;
}

async function addAnimatedWmsLayer(layerConfig) {
  const { key, wms_url, wms_layers, opacity, display_name, time_endpoint } = layerConfig;
  if (map.getSource(key)) return;

  const timeData = await fetchWmsTimeSteps(time_endpoint);
  if (!timeData || !timeData.times || !timeData.times.length) {
    console.error(`No time steps available for animated WMS layer "${key}"`);
    return;
  }

  const times = timeData.times;
  const startIndex = times.length - 1;  // most recent frame first

  map.addSource(key, {
    type: 'raster',
    tiles: [wmsTileUrlForTime(wms_url, wms_layers, times[startIndex])],
    tileSize: WMS_TILE_SIZE,
  });
  map.addLayer({
    id: key, type: 'raster', source: key,
    layout: { visibility: 'visible' },
    paint: { 'raster-opacity': opacity || 0.7 },
  });

  loadedLayers[key] = {
    layerIds: [key],
    geojson: { features: [] },
    config: layerConfig,
  };

  wmsAnimations[key] = { times, index: startIndex, refreshTimer: null, debounceTimer: null };
  updateWmsTimeLabel(key);
  renderWmsScrubberDock(key, layerConfig);
  scheduleWmsTimeRefresh(key, layerConfig);

  if (layerConfig.legend_url) addWmsLegend(key, display_name, layerConfig.legend_url);
  console.log(`Time-dimension WMS layer "${key}" added with ${times.length} time steps`);
  updateIndicators();
}

async function fetchWmsTimeSteps(time_endpoint) {
  try {
    const response = await fetch(time_endpoint);
    if (!response.ok) throw new Error(`Failed to fetch time steps from ${time_endpoint}`);
    return await response.json();
  } catch (error) {
    console.error('Error fetching WMS time steps:', error);
    return null;
  }
}

function scheduleWmsTimeRefresh(key, layerConfig) {
  const state = wmsAnimations[key];
  if (!state) return;

  const refreshMinutes = layerConfig.time_refresh_minutes || DEFAULT_TIME_REFRESH_MINUTES;
  const refreshMs = refreshMinutes * 60 * 1000;

  state.refreshTimer = setInterval(async () => {
    const timeData = await fetchWmsTimeSteps(layerConfig.time_endpoint);
    if (!timeData || !timeData.times || !timeData.times.length) return;

    const current = wmsAnimations[key];
    if (!current) return;
    // Same time list as before (no new run published yet) — nothing to update.
    if (JSON.stringify(current.times) === JSON.stringify(timeData.times)) return;

    current.times = timeData.times;
    current.index = current.times.length - 1;
    applyWmsFrame(key);
  }, refreshMs);
}

function applyWmsFrame(key) {
  const state = wmsAnimations[key];
  const config = loadedLayers[key] && loadedLayers[key].config;
  const source = map.getSource(key);
  if (!state || !config || !source) return;

  const time = state.times[state.index];
  source.setTiles([wmsTileUrlForTime(config.wms_url, config.wms_layers, time)]);
  updateWmsTimeLabel(key);
}

function scrubWmsAnimation(key, index) {
  const state = wmsAnimations[key];
  if (!state) return;

  state.index = ((parseInt(index, 10) % state.times.length) + state.times.length) % state.times.length;
  updateWmsTimeLabel(key);  // instant slider/label feedback — no network yet

  // Debounce the actual tile fetch so scrubbing quickly can't exceed the
  // remote WMS's rate limit; only the frame you settle on gets fetched.
  clearTimeout(state.debounceTimer);
  state.debounceTimer = setTimeout(() => applyWmsFrame(key), WMS_RATE_LIMIT_MS);
}

function updateWmsTimeLabel(key) {
  const label = document.getElementById(`time-label-${key}`);
  const slider = document.getElementById(`scrub-${key}`);
  const state = wmsAnimations[key];
  if (!state) return;
  if (label) label.textContent = state.times[state.index].replace('T', ' ').replace('Z', ' UTC');
  if (slider) slider.value = state.index;
}

// ---- Floating time-scrubber dock (bottom center of map) ---------------

function renderWmsScrubberDock(key, layerConfig) {
  const dock = document.getElementById('wms-time-dock');
  if (!dock) return;

  const frameCount = layerConfig.time_frame_count || (wmsAnimations[key] && wmsAnimations[key].times.length) || 12;

  const scrubber = document.createElement('div');
  scrubber.className = 'wms-time-scrubber';
  scrubber.id = `scrubber-${key}`;
  scrubber.innerHTML = `
    <span class="wms-time-name">${layerConfig.display_name}</span>
    <input type="range" class="zone-slider" id="scrub-${key}"
           min="0" max="${frameCount - 1}" value="${frameCount - 1}"
           oninput="scrubWmsAnimation('${key}', this.value)">
    <span class="wms-time-label" id="time-label-${key}"></span>
  `;

  const existing = document.getElementById(`scrubber-${key}`);
  if (existing) existing.remove();
  dock.appendChild(scrubber);

  if (typeof makeDraggable === 'function') {
    makeDraggable(scrubber, '.wms-time-name');
  }
}

// ---- Raster (TiTiler) layers -----------------------------------------

async function addRasterLayerFromConfig(layerConfig) {
  const { key, app_label, model_name, raster_id, opacity, display_name } = layerConfig;
  try {
    const legend = await addRasterLayer(map, app_label, model_name, raster_id, opacity);
    loadedLayers[key] = {
      layerIds: [`raster-layer-${model_name}-${raster_id}`],
      geojson: { features: [] },
      config: layerConfig
    };
    if (legend) addRasterLegend(key, display_name, legend);
    console.log(`Raster layer "${key}" added`);
    updateIndicators();
  } catch (error) {
    console.error(`Failed to add raster layer ${key}:`, error);
  }
}

async function addRasterLayer(map, appLabel, modelName, rasterID, opacity = 0.7) {
  const tilesURL = rasterID
    ? `/api/raster/${appLabel}/${modelName}/tiles/?id=${rasterID}`
    : `/api/raster/${appLabel}/${modelName}/tiles/`;
  const infoURL = rasterID
    ? `/api/raster/${appLabel}/${modelName}/info/?id=${rasterID}`
    : `/api/raster/${appLabel}/${modelName}/info/`;

  console.log(`Loading raster layer from: ${infoURL}`);

  try {
    const infoResponse = await fetch(infoURL);
    if (!infoResponse.ok) throw new Error(`Failed to get raster info: ${infoResponse.statusText}`);
    const infoData = await infoResponse.json();

    const tilesResponse = await fetch(tilesURL);
    if (!tilesResponse.ok) throw new Error(`Failed to load raster tiles: ${tilesResponse.statusText}`);
    const tilesData = await tilesResponse.json();

    const sourceId = `raster-source-${modelName}-${rasterID}`;
    const layerId  = `raster-layer-${modelName}-${rasterID}`;

    map.addSource(sourceId, {
      type: 'raster',
      tiles: [tilesData.tile_url],
      tileSize: 256,
      bounds: infoData.bounds,
      minzoom: infoData.minzoom,
      maxzoom: infoData.maxzoom,
    });

    map.addLayer({
      id: layerId, source: sourceId, type: 'raster',
      paint: { 'raster-opacity': opacity }
    });

    const [minLng, minLat, maxLng, maxLat] = infoData.bounds;
    map.fitBounds([[minLng, minLat], [maxLng, maxLat]], { padding: 50, duration: 1000 });

    console.log(`✅ Raster layer "${tilesData.name}" loaded and zoomed to bounds`);
    return tilesData.legend || null;
  } catch (error) {
    console.error(`❌ Error loading raster layer "${appLabel}.${modelName}":`, error);
    throw error;
  } finally {
    showLoader(false);
  }
}

// ---- Raster legend ------------------------------------------------------

/**
 * Render a color-range legend for an active raster layer: a gradient bar
 * sampled server-side from the exact colormap TiTiler used to paint the
 * tiles (core/rasterStyles.py::colormap_legend_stops), plus min/max labels.
 * Categorical products (land cover classes) still get a gradient over their
 * value range rather than a per-class key, which is a reasonable stand-in
 * given there's no class-label metadata to draw from yet.
 */
function addRasterLegend(key, title, legend) {
  const existing = document.getElementById(`legend-${key}`);
  if (existing) existing.remove();

  const stops = legend.stops || [];
  if (!stops.length) return;

  const gradientCss = `linear-gradient(to right, ${stops.map(s => s.color).join(', ')})`;
  const unitSuffix = legend.unit ? ` ${legend.unit}` : '';

  const legendEl = document.createElement('div');
  legendEl.id = `legend-${key}`;
  legendEl.className = 'map-legend dynamic-legend';
  legendEl.innerHTML = `
    <div class="legend-title">${legend.label || title} ${unitSuffix}</div>
    <div class="legend-gradient" style="background: ${gradientCss}"></div>
    <div class="legend-range">
      <span>${Number(legend.min).toFixed(2)}</span>
      <span>${Number(legend.max).toFixed(2)}</span>
    </div>
  `;
  document.getElementById('legend-stack')?.appendChild(legendEl);
  repositionDynamicLegends();
}

// ---- Categorical (per-class) legend --------------------------------------

/**
 * Render a swatch-per-category legend for a vector layer colored by a
 * `match` expression on some property (e.g. LandCoverVector.land_cover_type
 * — see core/landCoverStyles.py::build_landcover_style_and_legend), as
 * opposed to addRasterLegend's continuous gradient bar.
 * @param {string} key - layer key, used to id/find/remove the legend element.
 * @param {string} title - legend heading.
 * @param {Array<{label: string, color: string}>} categories
 */
function addCategoricalLegend(key, title, categories) {
  const existing = document.getElementById(`legend-${key}`);
  if (existing) existing.remove();

  const items = categories.map(({ label, color }) => `
    <div class="legend-item">
      <span class="legend-swatch" style="background:${color}"></span>
      <span class="legend-label">${label}</span>
    </div>
  `).join('');

  const legendEl = document.createElement('div');
  legendEl.id = `legend-${key}`;
  legendEl.className = 'map-legend dynamic-legend';
  legendEl.innerHTML = `
    <div class="legend-title">${title}</div>
    <div class="legend-list">${items}</div>
  `;
  document.getElementById('legend-stack')?.appendChild(legendEl);
  repositionDynamicLegends();
}

/**
 * Legends (dynamic raster/WMS/categorical ones, plus the static
 * #legend-groundwater block) all live inside #legend-stack, which lays them
 * out vertically itself (flex + gap) — this function only has to place the
 * *stack* so it never overlaps the side panel or the population dock, both
 * of which can independently open in the same bottom-right corner of the
 * map. If the stack has been dragged by the user (Draggable.js sets
 * data-dragged), leave its position alone.
 */
function repositionDynamicLegends() {
  const stack = document.getElementById('legend-stack');
  if (!stack) return;

  const hasVisibleLegend = Array.from(stack.querySelectorAll('.map-legend'))
    .some(el => el.style.display !== 'none');
  stack.style.display = hasVisibleLegend ? 'flex' : 'none';
  if (!hasVisibleLegend || stack.dataset.dragged) return;

  const wrapper = document.querySelector('.map-wrapper');
  const sidePanel = document.getElementById('side-panel');
  const populationPanel = document.getElementById('population-panel');
  if (!wrapper) return;

  const wrapperRect = wrapper.getBoundingClientRect();
  let right = 10;
  let bottom = 66;

  if (sidePanel && sidePanel.classList.contains('visible')) {
    const panelRect = sidePanel.getBoundingClientRect();
    right = Math.max(right, wrapperRect.right - panelRect.left + 12);
  }
  if (populationPanel && populationPanel.classList.contains('visible')) {
    const dockRect = populationPanel.getBoundingClientRect();
    bottom = Math.max(bottom, wrapperRect.bottom - dockRect.top + 10);
  }

  stack.style.right = `${right}px`;
  stack.style.bottom = `${bottom}px`;
}

// ---- Visibility & zoom ------------------------------------------------

/**
 * Hide Mapbox's own extruded buildings ('3d-buildings', Map_init.js) while
 * any builtup layer is shown, so they don't cover the database's buildings,
 * streets and parks. Only builtup layers do this; every other app's layers
 * leave the 3D buildings on.
 */
function sync3DBuildings() {
  if (!map || !map.getLayer('3d-buildings')) return;
  const builtupShown = Object.entries(loadedLayers).some(([key, entry]) =>
    entry.config.app_label === 'builtup' && layerVisibility[key] !== false);
  map.setLayoutProperty('3d-buildings', 'visibility', builtupShown ? 'none' : 'visible');
}

function toggleLayerVisibility(key, visible) {
  layerVisibility[key] = visible;

  const legendEl = document.getElementById(`legend-${key}`);
  if (legendEl) legendEl.style.display = visible ? 'block' : 'none';
  repositionDynamicLegends();

  if (visible && !loadedLayers[key]) {
    const config = availableLayers.find(l => l.key === key);
    if (config) addLayer(config);
  } else if (!visible && loadedLayers[key]) {
    loadedLayers[key].layerIds.forEach(id => map.setLayoutProperty(id, 'visibility', 'none'));
    if (wmsAnimations[key]) {
      const scrubber = document.getElementById(`scrubber-${key}`);
      if (scrubber) scrubber.style.display = 'none';
    }
  } else if (visible && loadedLayers[key]) {
    loadedLayers[key].layerIds.forEach(id => map.setLayoutProperty(id, 'visibility', 'visible'));
    // The map may have moved while the layer was hidden
    if (loadedLayers[key].viewport) reloadViewportLayer(key);
    if (wmsAnimations[key]) {
      const scrubber = document.getElementById(`scrubber-${key}`);
      if (scrubber) scrubber.style.display = 'flex';
    }
  }

  sync3DBuildings();
  updateIndicators();
}

async function zoomToLayer(key) {
  if (!loadedLayers[key]) return;
  const { geojson, viewport, config } = loadedLayers[key];

  // A viewport-loaded layer only holds what is on screen; ask the server
  // for the extent of the whole layer instead.
  if (viewport) {
    try {
      const response = await fetch(`/api/layers/${config.app_label}/${config.model_name}/bounds/`);
      const data = await response.json();
      if (data.bounds) safeFitBounds(data.bounds, { padding: 50, duration: 800 });
    } catch (error) {
      console.error(`Error fetching bounds of "${key}":`, error);
    }
    return;
  }
  const bounds = new mapboxgl.LngLatBounds();

  geojson.features.forEach(f => {
    if (f.geometry) addCoordinatesToBounds(f.geometry.coordinates, bounds, f.geometry.type);
  });

  if (!bounds.isEmpty()) safeFitBounds(bounds, { padding: 50, duration: 800 });
}

function zoomToAllVisible() {
  const bounds = new mapboxgl.LngLatBounds();

  for (const [key, data] of Object.entries(loadedLayers)) {
    if (layerVisibility[key] !== false) {
      data.geojson.features.forEach(f => {
        if (f.geometry) addCoordinatesToBounds(f.geometry.coordinates, bounds, f.geometry.type);
      });
    }
  }

  if (!bounds.isEmpty()) safeFitBounds(bounds, { padding: 50, duration: 800 });
}

function selectAllLayers() {
  availableLayers.forEach(layer => {
    toggleLayerVisibility(layer.key, true);
    const cb = document.getElementById(`toggle-${layer.key}`);
    if (cb) cb.checked = true;
  });
}

function selectNoLayers() {
  availableLayers.forEach(layer => {
    toggleLayerVisibility(layer.key, false);
    const cb = document.getElementById(`toggle-${layer.key}`);
    if (cb) cb.checked = false;
  });
}

function toggleGroundwaterLayer() {
  const layerId = 'groundwater-level';
  const legendEl = document.getElementById('legend-groundwater');
  if (!map.getLayer(layerId)) return;

  const visibility = map.getLayoutProperty(layerId, 'visibility');
  if (visibility === 'visible') {
    map.setLayoutProperty(layerId, 'visibility', 'none');
    if (legendEl) legendEl.style.display = 'none';
  } else {
    map.setLayoutProperty(layerId, 'visibility', 'visible');
    if (legendEl) legendEl.style.display = 'block';
  }
  repositionDynamicLegends();
}

// ---- Tool-based filtering ---------------------------------------------

function filterLayersByTool(toolId) {
  activeTool = toolId;
  const categories = TOOL_CATEGORIES[toolId] || [];

  availableLayers.forEach(layer => {
    const layerEl = document.getElementById(`layer-item-${layer.key}`);
    const matches = categories.includes(layer.app_label);
    if (layerEl) layerEl.style.display = matches ? '' : 'none';
  });

  document.querySelectorAll('.app-group').forEach(group => {
    const visibleItems = group.querySelectorAll('.layer-item:not([style*="display: none"])');
    group.style.display = visibleItems.length > 0 ? '' : 'none';
  });

  const panelTitle = document.querySelector('.layers-panel-title');
  if (panelTitle) {
    const toolNames = {
      overview: 'All Layers',
      temperature: 'Urban Heat Layers', green: 'Green and Park Layers',
      water: 'Water supply Layers', groundwater: 'Groundwater Layers',
    };
    panelTitle.innerHTML = `<i class="bi bi-layers"></i> ${toolNames[toolId] || 'Layers'}`;
  }
}

function activateToolLayers(toolId) {
  const categories = TOOL_CATEGORIES[toolId];
  if (!categories) return;

  availableLayers.forEach(layer => {
    const matches = categories.includes(layer.app_label);
    toggleLayerVisibility(layer.key, matches);
    const cb = document.getElementById(`toggle-${layer.key}`);
    if (cb) cb.checked = matches;
  });
}

// ---- Helpers ----------------------------------------------------------

function addCoordinatesToBounds(coords, bounds, type) {
  switch (type) {
    case 'Point':       bounds.extend(coords); break;
    case 'LineString':  coords.forEach(c => bounds.extend(c)); break;
    case 'Polygon':     coords[0].forEach(c => bounds.extend(c)); break;
    case 'MultiPolygon':     coords.forEach(p => p[0].forEach(c => bounds.extend(c))); break;
    case 'MultiLineString':  coords.forEach(l => l.forEach(c => bounds.extend(c))); break;
    case 'MultiPoint':       coords.forEach(c => bounds.extend(c)); break;
  }
}

const _numFmt    = new Intl.NumberFormat(undefined, { maximumFractionDigits: 2, useGrouping: true });
const _intFmt    = new Intl.NumberFormat(undefined, { maximumFractionDigits: 0, useGrouping: true });
const _dateTimeFmt = new Intl.DateTimeFormat(undefined, { year: 'numeric', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
// Date-only values ('2025-01-01') parse as UTC midnight: format them in UTC,
// or every timezone west of Greenwich shows the day before.
const _dateFmt   = new Intl.DateTimeFormat(undefined, { year: 'numeric', month: 'short', day: 'numeric', timeZone: 'UTC' });
const _skipKeys  = new Set(['pk', 'id']);

function _formatValue(value, fieldMeta, key = '') {
  if (value === null || value === undefined || value === '') return '—';

  if (fieldMeta?.type === 'datetime' || fieldMeta?.type === 'date') {
    const date = new Date(value);
    if (!isNaN(date)) return (fieldMeta.type === 'date' ? _dateFmt : _dateTimeFmt).format(date);
  }

  if (typeof value === 'number' || (typeof value === 'string' && !isNaN(value) && value.trim() !== '')) {
    const num = Number(value);
    // Years (constructionYear, year) are labels, not quantities: 1912, not 1,912
    if (Number.isInteger(num) && /year$/i.test(key)) return String(num);
    const formatted = Number.isInteger(num) ? _intFmt.format(num) : _numFmt.format(num);
    const unit = fieldMeta?.unit;
    return unit ? `${formatted} <span class="popup-unit">${unit}</span>` : formatted;
  }

  if (typeof value === 'boolean') return value ? 'Yes' : 'No';

  // Mapbox serialises array properties (e.g. Building.usageFunction) to JSON strings
  if (typeof value === 'string' && value.startsWith('[')) {
    try {
      const list = JSON.parse(value);
      if (Array.isArray(list)) return list.length ? list.join(', ') : '—';
    } catch (e) { /* not JSON: show as-is */ }
  }
  return String(value);
}

function createPopupContent(properties, layerName, fields = {}, color = null) {
  const titleKey = _featureTitleKey(properties);
  return `<div class="popup-feature" style="--layer-color:${color || 'var(--text-dim)'}">
    ${_popupHead(properties, layerName, titleKey)}
    ${_popupTable(properties, fields, titleKey)}
  </div>`;
}

// ---- Shared feature popup ----------------------------------------------

// Mapbox layer id → { key, name, fields, color } for every vector layer whose
// features open the popup. Filled by addLayer(); read by initFeaturePopup().
const popupLayers = new Map();
let featurePopup = null;

/**
 * One map-level click handler for every vector layer, instead of one
 * map.on('click', layerId) per layer: with per-layer handlers a click on
 * overlapping features opened one popup per layer (and only ever showed the
 * top feature of each). Registered once from Map_init.js's 'load' handler;
 * map-level listeners survive setStyle(), so a basemap switch doesn't
 * stack duplicate handlers.
 */
function initFeaturePopup() {
  map.on('click', (e) => {
    const layers = [...popupLayers.keys()].filter(id => map.getLayer(id));
    if (!layers.length) return;

    // Hidden layers (visibility: none) are not rendered, so they are not returned.
    const features = map.queryRenderedFeatures(e.point, { layers });
    const entries = _uniquePopupEntries(features);
    if (!entries.length) return;

    if (featurePopup) featurePopup.remove();
    featurePopup = new mapboxgl.Popup({ maxWidth: '300px', className: 'feature-popup' })  // width matches mainMap.css
      .setLngLat(e.lngLat)
      .setHTML(createMultiFeaturePopupContent(entries))
      .addTo(map);
  });
}

/**
 * [{ name, fields, color, properties }] for the clicked features, topmost
 * first. queryRenderedFeatures can return the same feature more than once
 * (a polygon split across tile boundaries), so drop repeats per layer.
 */
function _uniquePopupEntries(features) {
  const seen = new Set();
  const entries = [];
  for (const f of features) {
    const layer = popupLayers.get(f.layer.id);
    if (!layer) continue;
    const id = `${layer.key}|${f.id ?? JSON.stringify(f.properties)}`;
    if (seen.has(id)) continue;
    seen.add(id);
    entries.push({ name: layer.name, fields: layer.fields, color: layer.color, properties: f.properties });
  }
  return entries;
}

/**
 * Key of the property that names the feature: the first "…name" property
 * (cityName, neighborhoodName, name, …), else an address (buildings).
 */
function _featureTitleKey(properties) {
  const keys = Object.keys(properties).filter(k => properties[k] !== null && properties[k] !== '');
  return keys.find(k => /name$/i.test(k)) || keys.find(k => /^address$/i.test(k)) || null;
}

/** Feature name as the title, its layer underneath; just the layer when the feature has no name. */
function _popupHead(properties, layerName, titleKey) {
  if (!titleKey) return `<div class="popup-head"><div class="popup-title">${layerName}</div></div>`;
  return `<div class="popup-head">
    <div class="popup-title">${properties[titleKey]}</div>
    <div class="popup-layer">${layerName}</div>
  </div>`;
}

/**
 * Popup HTML for one or more features at the clicked point. Several
 * features are stacked in one scrollable box, one collapsible section each,
 * with the topmost feature expanded.
 */
function createMultiFeaturePopupContent(entries) {
  if (entries.length === 1) {
    const { properties, name, fields, color } = entries[0];
    return createPopupContent(properties, name, fields, color);
  }

  const sections = entries.map(({ properties, name, fields, color }, i) => {
    const titleKey = _featureTitleKey(properties);
    return `<details class="popup-feature popup-section" style="--layer-color:${color || 'var(--text-dim)'}"${i === 0 ? ' open' : ''}>
      <summary>${_popupHead(properties, name, titleKey)}</summary>
      ${_popupTable(properties, fields, titleKey)}
    </details>`;
  }).join('');

  return `<div class="popup-count">${entries.length} features here</div>
    <div class="popup-multi">${sections}</div>`;
}

/** "Current Population" → "Current population"; all-caps words (OPEX, NRW) stay as they are. */
function _sentenceCase(label) {
  return label.replace(/(\s)([A-Z])([a-z])/g, (m, sp, first, next) => sp + first.toLowerCase() + next);
}

/** "Area km2" → "Area" when the value already shows km², so the unit isn't said twice. */
function _withoutUnit(label, unit) {
  if (!unit) return label;
  const words = label.split(' ');
  const last = (words[words.length - 1] || '').replace(/2$/, '²').replace(/3$/, '³');
  return words.length > 1 && last === unit ? words.slice(0, -1).join(' ') : label;
}

function _popupTable(properties, fields = {}, skipKey = null) {
  let html = '<dl class="popup-rows">';

  for (const [key, value] of Object.entries(properties)) {
    if (value === null || value === undefined || _skipKeys.has(key) || key === skipKey) continue;

    // Skip raw FK id columns (e.g. province_id, city_id) — not meaningful in a popup
    if (key.endsWith('_id') && fields[key.slice(0, -3)]) continue;

    const meta  = fields[key] || null;
    const label = _withoutUnit(_sentenceCase(meta?.label || key.replace(/_/g, ' ').replace(/^\w/, c => c.toUpperCase())), meta?.unit);
    const title = meta?.help_text ? ` title="${meta.help_text}"` : '';

    html += `<div class="popup-row"><dt${title}>${label}</dt><dd>${_formatValue(value, meta, key)}</dd></div>`;
  }

  html += '</dl>';
  return html;
}

// Expose to global scope
window.toggleLayerVisibility = toggleLayerVisibility;
window.zoomToLayer = zoomToLayer;