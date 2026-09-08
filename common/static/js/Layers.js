// ============================================================
// layers.js — Layer fetching, adding, toggling, zoom
// Depends on: config.js, map-init.js (for map & safeFitBounds)
// ============================================================

let loaderTimeout = null;

/**
 * Show/hide loading indicator
 */
function showLoader(show) {
  const loader = document.getElementById('map-loader');
  if (!loader) return;

  if (show) {
    loaderTimeout = setTimeout(() => loader.classList.add('visible'), 2000);
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
 * always-needed 'common' admin-hierarchy layers (province/city/district/
 * neighborhood — these drive the city-click handlers and indicator panels)
 * first so the map UI is usable immediately, then fetch every other app's
 * layers in the background and merge them in once they arrive.
 */
async function fetchAvailableLayers() {
  try {
    await loadLayerCatalog('common');
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
  // background fetch) re-includes 'common' layers already loaded, and
  // must not clobber their loadedLayers/visibility state.
  const existingKeys = new Set(availableLayers.map(l => l.key));
  for (const layer of data.layers) {
    if (!existingKeys.has(layer.key)) {
      availableLayers.push(layer);
      layerVisibility[layer.key] = true;
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

  if (layer_type === 'wms')    { addWmsLayer(layerConfig); return; }
  if (layer_type === 'raster') { await addRasterLayerFromConfig(layerConfig); return; }

  // Vector layer
  console.log(`Loading layer "${key}"...`);

  try {
    showLoader(true);

    const response = await fetch(url);
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

    loadedLayers[key] = { layerIds, geojson, config: layerConfig };

    if (typeof onAdminLayerLoaded === 'function') onAdminLayerLoaded(key, layerIds);

    // Popup on click
    const clickLayerId = layerIds[0];
    map.on('click', clickLayerId, (e) => {
      const properties = e.features[0].properties;
      new mapboxgl.Popup()
        .setLngLat(e.lngLat)
        .setHTML(createPopupContent(properties, display_name, layerConfig.fields || {}))
        .addTo(map);
    });
    map.on('mouseenter', clickLayerId, () => { map.getCanvas().style.cursor = 'pointer'; });
    map.on('mouseleave', clickLayerId, () => { map.getCanvas().style.cursor = ''; });

    console.log(`Layer "${key}" loaded with ${geojson.features.length} features`);
    updateIndicators();

  } catch (error) {
    console.error(`Error loading layer "${key}":`, error);
  } finally {
    showLoader(false);
  }
}

// ---- WMS layers -------------------------------------------------------

function addWmsLayer(layerConfig) {
  const { key, wms_url, wms_layers, opacity, display_name } = layerConfig;
  if (map.getSource(key)) return;

  const tileUrl = wms_url +
    '?service=WMS&request=GetMap&version=1.3.0' +
    `&layers=${wms_layers}&styles=&format=image/png&transparent=true` +
    '&width=256&height=256&crs=EPSG:3857&bbox={bbox-epsg-3857}';

  map.addSource(key, { type: 'raster', tiles: [tileUrl], tileSize: 256 });
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
  document.querySelector('.map-wrapper').appendChild(legend);
  legend.querySelector('img').addEventListener('load', repositionDynamicLegends);
  repositionDynamicLegends();
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
    <div class="legend-title">${legend.label || title}</div>
    <div class="legend-gradient" style="background: ${gradientCss}"></div>
    <div class="legend-range">
      <span>${legend.min}${unitSuffix}</span>
      <span>${legend.max}${unitSuffix}</span>
    </div>
  `;
  document.querySelector('.map-wrapper').appendChild(legendEl);
  repositionDynamicLegends();
}

/**
 * All legends (dynamic raster/WMS ones, plus the static #legend-groundwater
 * block) share the same fixed corner via .map-legend's CSS, so with more than
 * one visible at once they'd render stacked exactly on top of each other.
 * Stack them vertically by their actual rendered height instead of a guessed
 * fixed height — WMS legend images vary a lot in size, so a fixed offset
 * either leaves gaps or overlaps depending on which legend is involved.
 */
function repositionDynamicLegends() {
  const legends = Array.from(document.querySelectorAll('.map-legend'))
    .filter(el => el.style.display !== 'none');
  const gap = 10;
  let bottom = 66;
  legends.forEach(el => {
    el.style.bottom = `${bottom}px`;
    bottom += el.offsetHeight + gap;
  });
}

// ---- Visibility & zoom ------------------------------------------------

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
  } else if (visible && loadedLayers[key]) {
    loadedLayers[key].layerIds.forEach(id => map.setLayoutProperty(id, 'visibility', 'visible'));
  }

  updateIndicators();
}

function zoomToLayer(key) {
  if (!loadedLayers[key]) return;
  const { geojson } = loadedLayers[key];
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
const _dateFmt   = new Intl.DateTimeFormat(undefined, { year: 'numeric', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
const _skipKeys  = new Set(['pk', 'id']);

function _formatValue(value, fieldMeta) {
  if (value === null || value === undefined || value === '') return '—';

  if (fieldMeta?.type === 'datetime' || fieldMeta?.type === 'date') {
    const date = new Date(value);
    if (!isNaN(date)) return _dateFmt.format(date);
  }

  if (typeof value === 'number' || (typeof value === 'string' && !isNaN(value) && value.trim() !== '')) {
    const num = Number(value);
    const formatted = Number.isInteger(num) ? _intFmt.format(num) : _numFmt.format(num);
    const unit = fieldMeta?.unit;
    return unit ? `${formatted} <span class="popup-unit">${unit}</span>` : formatted;
  }

  if (typeof value === 'boolean') return value ? 'Yes' : 'No';
  return String(value);
}

function createPopupContent(properties, layerName, fields = {}) {
  let html = `<div class="popup-header">${layerName}</div><table class="popup-table">`;

  for (const [key, value] of Object.entries(properties)) {
    if (value === null || value === undefined || _skipKeys.has(key)) continue;

    // Skip raw FK id columns (e.g. province_id, city_id) — not meaningful in a popup
    if (key.endsWith('_id') && fields[key.slice(0, -3)]) continue;

    const meta  = fields[key] || null;
    const label = meta?.label || key.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
    const title = meta?.help_text ? ` title="${meta.help_text}"` : '';

    html += `<tr>
      <td class="popup-label"${title}>${label}</td>
      <td class="popup-value">${_formatValue(value, meta)}</td>
    </tr>`;
  }

  html += '</table>';
  return html;
}

// Expose to global scope
window.toggleLayerVisibility = toggleLayerVisibility;
window.zoomToLayer = zoomToLayer;