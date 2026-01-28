/**
 * Urban Twin Map - Combined CrossTwin + Urban Twin Interface
 * Merges dynamic database layer loading with polished Urban Twin UI
 */

// ============================================================
// GLOBAL STATE
// ============================================================
let map;
let availableLayers = [];
const loadedLayers = {};
const layerVisibility = {};
let activeBasemap = 'light';
let tilted = true;

// Configuration (set from Django template)
let CONFIG = {
  mapboxToken: '{{ mapbox_access_token }}',
  layersApiUrl: '/map/api/layers/',
  initialCenter: [6.895, 52.219],
  initialZoom: 13,
  initialPitch: 60,
  initialBearing: -35
};

// Basemap styles
const BASEMAPS = {
  light: 'mapbox://styles/mapbox/light-v11',
  dark: 'mapbox://styles/mapbox/dark-v11',
  streets: 'mapbox://styles/mapbox/streets-v12',
  satellite: 'mapbox://styles/mapbox/satellite-streets-v12',
  outdoors: 'mapbox://styles/mapbox/outdoors-v12'
};

// Tool content for side panel
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
    body: `
      <p>View parks, trees, and green spaces. Combine with heat indicators to locate greening priorities.</p>
    `
  },
  water: {
    title: 'WATER INFRASTRUCTURE',
    body: `
      <p>Display water pipes, wells, and supply network. Relate demand to housing and population forecasts.</p>
    `
  },
  groundwater: {
    title: 'GROUNDWATER LEVELS',
    body: `
      <p>Groundwater depth measurements from the Dutch national registry (BRO).</p>
      <p>GHG = Average Highest Groundwater Level (Gemiddeld Hoogste Grondwaterstand)</p>
    `
  }
};

// ============================================================
// INITIALIZATION
// ============================================================

/**
 * Initialize the Urban Twin map
 * @param {object} config - Configuration from Django template
 */
function initializeUrbanTwinMap(config) {
  CONFIG = { ...CONFIG, ...config };
  mapboxgl.accessToken = CONFIG.mapboxToken;

  // Create map
  map = new mapboxgl.Map({
    container: 'map',
    style: BASEMAPS[activeBasemap],
    center: CONFIG.initialCenter,
    zoom: CONFIG.initialZoom,
    pitch: CONFIG.initialPitch,
    bearing: CONFIG.initialBearing
  });

  // Add controls
  map.addControl(new mapboxgl.NavigationControl(), 'top-right');
  map.addControl(new mapboxgl.ScaleControl(), 'bottom-right');

  // Initialize on load
  map.on('load', () => {
    console.log('Map loaded successfully');
    add3DBuildings();
    addExternalLayers();
    fetchAvailableLayers();
  });

  // Error handling
  map.on('error', (e) => {
    console.error('Map error:', e.error);
  });

  // Initialize UI
  initializeUI();

  return map;
}

function safeFitBounds(bounds, options = {}) {
  if (!map) return;

  map.resize(); // 🔑 critical

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
          13, 0,
          16, ['get', 'height']
        ],
        'fill-extrusion-base': [
          'interpolate', ['linear'], ['zoom'],
          13, 0,
          16, ['get', 'min_height']
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
  // Groundwater WMS layer
  if (!map.getSource('groundwater-level')) {
    map.addSource('groundwater-level', {
      type: 'raster',
      tiles: [
        'https://service.pdok.nl/bzk/bro-grondwaterspiegeldiepte/wms/v2_0' +
        '?service=WMS&request=GetMap&version=1.3.0' +
        '&layers=bro-grondwaterspiegeldieptemetingen-GHG' +
        '&styles=' +
        '&format=image/png' +
        '&transparent=true' +
        '&width=256&height=256' +
        '&crs=EPSG:3857' +
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

// ============================================================
// LAYER MANAGEMENT (from CrossTwin)
// ============================================================

/**
 * Show/hide loading indicator
 */
function showLoader(show) {
  const loader = document.getElementById('map-loader');
  if (loader) {
    loader.classList.toggle('visible', show);
  }
}

/**
 * Fetch available layers from Django API
 */
async function fetchAvailableLayers() {
  try {
    const response = await fetch(CONFIG.layersApiUrl);
    if (!response.ok) throw new Error('Failed to fetch layers');

    const data = await response.json();
    availableLayers = data.layers;

    // Initialize visibility (all visible by default)
    availableLayers.forEach(layer => {
      layerVisibility[layer.key] = true;
    });

    renderLayerList();
    updateIndicators();

    // Load all layers
    for (const layer of availableLayers) {
      await addLayer(layer);
    }

    // Fit to all features
    zoomToAllVisible();

  } catch (error) {
    console.error('Error fetching layers:', error);
    const container = document.getElementById('layer-list');
    if (container) {
      container.innerHTML = '<div class="no-layers">Error loading layers. Check API connection.</div>';
    }
  }
}

/**
 * Add a layer to the map
 */
async function addLayer(layerConfig) {
  const { key, url, color, geometry_type, display_name } = layerConfig;

  if (loadedLayers[key]) return;

  console.log(`Loading layer "${key}"...`);

  try {
    showLoader(true);

    const response = await fetch(url);
    if (!response.ok) throw new Error(`Failed to load ${key}`);

    const geojson = await response.json();

    if (!geojson.features || geojson.features.length === 0) {
      console.log(`Layer "${key}" has no features`);
      showLoader(false);
      return;
    }

    // Add source
    map.addSource(key, {
      type: 'geojson',
      data: geojson
    });

    // Add layer(s) based on geometry type
    const layerIds = [];

    if (geometry_type === 'point') {
      map.addLayer({
        id: `${key}-points`,
        type: 'circle',
        source: key,
        paint: {
          'circle-radius': 6,
          'circle-color': color,
          'circle-stroke-width': 2,
          'circle-stroke-color': '#ffffff'
        }
      });
      layerIds.push(`${key}-points`);

    } else if (geometry_type === 'line') {
      map.addLayer({
        id: `${key}-lines`,
        type: 'line',
        source: key,
        paint: {
          'line-color': color,
          'line-width': 3
        }
      });
      layerIds.push(`${key}-lines`);

    } else {
      // Polygon
      map.addLayer({
        id: `${key}-fill`,
        type: 'fill',
        source: key,
        paint: {
          'fill-color': color,
          'fill-opacity': 0.35
        }
      });
      map.addLayer({
        id: `${key}-outline`,
        type: 'line',
        source: key,
        paint: {
          'line-color': color,
          'line-width': 2
        }
      });
      layerIds.push(`${key}-fill`, `${key}-outline`);
    }

    loadedLayers[key] = { layerIds, geojson, config: layerConfig };

    // Add click handler for popups
    const clickLayerId = layerIds[0];
    map.on('click', clickLayerId, (e) => {
      const properties = e.features[0].properties;
      new mapboxgl.Popup()
        .setLngLat(e.lngLat)
        .setHTML(createPopupContent(properties, display_name))
        .addTo(map);
    });

    // Cursor changes
    map.on('mouseenter', clickLayerId, () => {
      map.getCanvas().style.cursor = 'pointer';
    });
    map.on('mouseleave', clickLayerId, () => {
      map.getCanvas().style.cursor = '';
    });

    console.log(`Layer "${key}" loaded with ${geojson.features.length} features`);
    updateIndicators();

  } catch (error) {
    console.error(`Error loading layer "${key}":`, error);
  } finally {
    showLoader(false);
  }
}

/**
 * Create popup HTML content
 */
function createPopupContent(properties, layerName) {
  let html = `<h6>${layerName}</h6><table>`;

  for (const [key, value] of Object.entries(properties)) {
    if (value !== null && value !== undefined && key !== 'pk') {
      let displayValue = value;
      if (typeof value === 'number') {
        displayValue = Number.isInteger(value) ? value : value.toFixed(2);
      }
      html += `<tr><td>${key.replace(/_/g, ' ')}</td><td>${displayValue}</td></tr>`;
    }
  }

  html += '</table>';
  return html;
}

/**
 * Toggle layer visibility
 */
function toggleLayerVisibility(key, visible) {
  layerVisibility[key] = visible;

  if (visible && !loadedLayers[key]) {
    const config = availableLayers.find(l => l.key === key);
    if (config) addLayer(config);
  } else if (!visible && loadedLayers[key]) {
    loadedLayers[key].layerIds.forEach(id => {
      map.setLayoutProperty(id, 'visibility', 'none');
    });
  } else if (visible && loadedLayers[key]) {
    loadedLayers[key].layerIds.forEach(id => {
      map.setLayoutProperty(id, 'visibility', 'visible');
    });
  }

  updateIndicators();
}

/**
 * Zoom to layer bounds
 */
function zoomToLayer(key) {
  if (!loadedLayers[key]) return;

  const { geojson } = loadedLayers[key];
  const bounds = new mapboxgl.LngLatBounds();

  geojson.features.forEach(feature => {
    if (feature.geometry) {
      addCoordinatesToBounds(feature.geometry.coordinates, bounds, feature.geometry.type);
    }
  });

  if (!bounds.isEmpty()) {
    safeFitBounds(bounds, { padding: 50, duration: 800 });
  }
}

/**
 * Zoom to all visible layers
 */
function zoomToAllVisible() {
  const bounds = new mapboxgl.LngLatBounds();

  for (const [key, data] of Object.entries(loadedLayers)) {
    if (layerVisibility[key] !== false) {
      data.geojson.features.forEach(feature => {
        if (feature.geometry) {
          addCoordinatesToBounds(feature.geometry.coordinates, bounds, feature.geometry.type);
        }
      });
    }
  }

  if (!bounds.isEmpty()) {
    safeFitBounds(bounds, { padding: 50, duration: 800 });
  }
}

/**
 * Helper to add coordinates to bounds
 */
function addCoordinatesToBounds(coords, bounds, type) {
  switch (type) {
    case 'Point':
      bounds.extend(coords);
      break;
    case 'LineString':
      coords.forEach(coord => bounds.extend(coord));
      break;
    case 'Polygon':
      coords[0].forEach(coord => bounds.extend(coord));
      break;
    case 'MultiPolygon':
      coords.forEach(polygon => polygon[0].forEach(coord => bounds.extend(coord)));
      break;
    case 'MultiLineString':
      coords.forEach(line => line.forEach(coord => bounds.extend(coord)));
      break;
    case 'MultiPoint':
      coords.forEach(coord => bounds.extend(coord));
      break;
  }
}

/**
 * Select all layers
 */
function selectAllLayers() {
  availableLayers.forEach(layer => {
    toggleLayerVisibility(layer.key, true);
    const checkbox = document.getElementById(`toggle-${layer.key}`);
    if (checkbox) checkbox.checked = true;
  });
}

/**
 * Deselect all layers
 */
function selectNoLayers() {
  availableLayers.forEach(layer => {
    toggleLayerVisibility(layer.key, false);
    const checkbox = document.getElementById(`toggle-${layer.key}`);
    if (checkbox) checkbox.checked = false;
  });
}

/**
 * Change basemap style
 */
function changeBasemap(basemapKey) {
  if (!BASEMAPS[basemapKey] || activeBasemap === basemapKey) return;

  activeBasemap = basemapKey;
  const currentVisibility = { ...layerVisibility };

  map.setStyle(BASEMAPS[basemapKey]);

  map.once('style.load', () => {
    // Re-add 3D buildings and external layers
    add3DBuildings();
    addExternalLayers();

    // Clear loaded layers tracking
    for (const key of Object.keys(loadedLayers)) {
      delete loadedLayers[key];
    }

    // Reload visible layers
    for (const layer of availableLayers) {
      if (currentVisibility[layer.key]) {
        addLayer(layer);
      }
    }
  });
}

// ============================================================
// UI RENDERING
// ============================================================

/**
 * Render the layer list
 */
function renderLayerList() {
  const container = document.getElementById('layer-list');
  if (!container) return;

  if (availableLayers.length === 0) {
    container.innerHTML = '<div class="no-layers">No layers available</div>';
    return;
  }

  // Group by app_label
  const groups = {};
  availableLayers.forEach(layer => {
    if (!groups[layer.app_label]) {
      groups[layer.app_label] = [];
    }
    groups[layer.app_label].push(layer);
  });

  let html = '';

  for (const [appLabel, layers] of Object.entries(groups)) {
    html += `<div class="app-group">
      <div class="app-group-header">${appLabel}</div>`;

    layers.forEach(layer => {
      const checked = layerVisibility[layer.key] !== false ? 'checked' : '';
      const legendIcon = getLayerLegendIcon(layer.geometry_type, layer.color);

      html += `
        <div class="layer-item">
          <div class="layer-info">
            <input type="checkbox"
                   id="toggle-${layer.key}"
                   ${checked}
                   onchange="toggleLayerVisibility('${layer.key}', this.checked)">
            ${legendIcon}
            <span class="layer-name">${layer.display_name}</span>
            <span class="layer-count">${layer.count}</span>
          </div>
          <div class="layer-actions">
            <button onclick="zoomToLayer('${layer.key}')" title="Zoom to layer">🔍</button>
          </div>
        </div>`;
    });

    html += '</div>';
  }

  container.innerHTML = html;
}

/**
 * Generate SVG legend icon
 */
function getLayerLegendIcon(geometryType, color) {
  const size = 16;

  switch (geometryType) {
    case 'point':
      return `<svg width="${size}" height="${size}" class="layer-icon">
        <circle cx="${size/2}" cy="${size/2}" r="5" fill="${color}" stroke="#fff" stroke-width="1.5"/>
      </svg>`;

    case 'line':
      return `<svg width="${size}" height="${size}" class="layer-icon">
        <line x1="2" y1="${size-3}" x2="${size-2}" y2="3" stroke="${color}" stroke-width="3" stroke-linecap="round"/>
      </svg>`;

    default:
      return `<svg width="${size}" height="${size}" class="layer-icon">
        <rect x="2" y="2" width="${size-4}" height="${size-4}" fill="${color}" fill-opacity="0.4" stroke="${color}" stroke-width="1.5"/>
      </svg>`;
  }
}

/**
 * Update bottom bar indicators
 */
function updateIndicators() {
  const layersEl = document.getElementById('layers-count');
  const featuresEl = document.getElementById('features-count');
  const visibleEl = document.getElementById('visible-count');

  if (layersEl) {
    layersEl.textContent = availableLayers.length;
  }

  if (featuresEl) {
    let totalFeatures = 0;
    for (const data of Object.values(loadedLayers)) {
      totalFeatures += data.geojson.features.length;
    }
    featuresEl.textContent = totalFeatures.toLocaleString();
  }

  if (visibleEl) {
    let visibleCount = 0;
    for (const [key, visible] of Object.entries(layerVisibility)) {
      if (visible && loadedLayers[key]) visibleCount++;
    }
    visibleEl.textContent = visibleCount;
  }
}

// ============================================================
// UI EVENT HANDLERS
// ============================================================

/**
 * Initialize all UI interactions
 */
function initializeUI() {
  // Toolbar buttons
  const toolbar = document.getElementById('toolbar');
  const sidePanel = document.getElementById('side-panel');
  const layersPanel = document.getElementById('layers-panel');
  const panelTitle = document.getElementById('panel-title');
  const panelBody = document.getElementById('panel-body');
  const hint = document.getElementById('onboarding-hint');

  // Tool button clicks
  toolbar?.addEventListener('click', (evt) => {
    const btn = evt.target.closest('.tool-button');
    if (!btn) return;

    const tool = btn.dataset.tool;

    // Update active state
    toolbar.querySelectorAll('.tool-button').forEach(b => 
      b.classList.toggle('active', b === btn)
    );

    // Remove onboarding hint
    if (hint) hint.remove();

    // Handle tool actions
    if (tool === 'layers') {
      layersPanel?.classList.toggle('visible');
      sidePanel?.classList.remove('visible');
    } else if (tool === 'satellite') {
      changeBasemap('satellite');
      layersPanel?.classList.remove('visible');
    } else if (tool === 'groundwater') {
      toggleGroundwaterLayer();
      const content = TOOL_CONTENT[tool];
      if (content && panelTitle && panelBody) {
        panelTitle.textContent = content.title;
        panelBody.innerHTML = content.body;
        sidePanel?.classList.add('visible');
      }
      layersPanel?.classList.remove('visible');
    } else {
      // Show tool content in side panel
      if (tool !== 'satellite') {
        changeBasemap('light');
      }
      
      const content = TOOL_CONTENT[tool];
      if (content && panelTitle && panelBody) {
        panelTitle.textContent = content.title;
        panelBody.innerHTML = content.body;
        sidePanel?.classList.add('visible');
      }
      layersPanel?.classList.remove('visible');
    }
  });

  // Panel close buttons
  document.getElementById('panel-close')?.addEventListener('click', () => {
    sidePanel?.classList.remove('visible');
  });

  document.getElementById('layers-panel-close')?.addEventListener('click', () => {
    layersPanel?.classList.remove('visible');
  });

  // Camera controls
  document.getElementById('btn-tilt')?.addEventListener('click', () => {
    tilted = !tilted;
    map.easeTo({ pitch: tilted ? 60 : 0, duration: 600 });
  });

  document.getElementById('btn-reset')?.addEventListener('click', () => {
    map.easeTo({
      center: CONFIG.initialCenter,
      zoom: CONFIG.initialZoom,
      pitch: CONFIG.initialPitch,
      bearing: CONFIG.initialBearing,
      duration: 800
    });
  });

  // Layer controls
  document.getElementById('btn-select-all')?.addEventListener('click', selectAllLayers);
  document.getElementById('btn-select-none')?.addEventListener('click', selectNoLayers);
  document.getElementById('btn-fit-all')?.addEventListener('click', zoomToAllVisible);

  // Basemap selector
  document.getElementById('basemap-select')?.addEventListener('change', (e) => {
    changeBasemap(e.target.value);
  });

  // Dashboard button
  document.getElementById('btn-dashboard')?.addEventListener('click', () => {
    showDashboard();
  });

  // Scenarios button
  document.getElementById('btn-scenarios')?.addEventListener('click', () => {
    showScenarios();
  });

  // Indicator pills
  document.querySelectorAll('.indicator-pill').forEach(pill => {
    pill.addEventListener('click', () => {
      const type = pill.dataset.indicator;
      if (type === 'layers' || type === 'visible') {
        layersPanel?.classList.toggle('visible');
        sidePanel?.classList.remove('visible');
      }
    });
  });
}

/**
 * Toggle groundwater layer visibility
 */
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
}

/**
 * Show dashboard panel
 */
function showDashboard() {
  const panelTitle = document.getElementById('panel-title');
  const panelBody = document.getElementById('panel-body');
  const sidePanel = document.getElementById('side-panel');

  // Calculate stats
  let totalFeatures = 0;
  let visibleLayers = 0;
  
  for (const [key, data] of Object.entries(loadedLayers)) {
    totalFeatures += data.geojson.features.length;
    if (layerVisibility[key]) visibleLayers++;
  }

  // Mock data for demo
  const monthlyData = [65, 72, 78, 85, 92, 88, 82, 76, 70, 68, 62, 60];
  const maxVal = Math.max(...monthlyData);
  const barsHTML = monthlyData.map(v => {
    const h = Math.round((v / maxVal) * 100);
    return `<div class="mini-bar" style="--h:${h}%"></div>`;
  }).join('');

  if (panelTitle) panelTitle.textContent = 'CITY DASHBOARD';
  if (panelBody) {
    panelBody.innerHTML = `
      <div class="dashboard-grid">
        <div class="kpi-card">
          <div class="kpi-header">
            <span>Total Layers</span>
            <span class="kpi-dot"></span>
          </div>
          <div class="kpi-value">${availableLayers.length}</div>
          <div class="kpi-sub">From database</div>
        </div>
        
        <div class="kpi-card">
          <div class="kpi-header">
            <span>Total Features</span>
            <span class="kpi-dot"></span>
          </div>
          <div class="kpi-value">${totalFeatures.toLocaleString()}</div>
          <div class="kpi-sub">Loaded on map</div>
        </div>
        
        <div class="gauge-card">
          <div class="gauge-ring" style="--value:${Math.round(visibleLayers / availableLayers.length * 100)};">
            <div class="gauge-center">${visibleLayers}/${availableLayers.length}</div>
          </div>
          <div class="gauge-text">
            <div class="gauge-label">Visible Layers</div>
            <div class="gauge-sub">Currently displayed</div>
          </div>
        </div>
        
        <div class="gauge-card">
          <div class="gauge-ring" style="--value:72;">
            <div class="gauge-center">72%</div>
          </div>
          <div class="gauge-text">
            <div class="gauge-label">Data Coverage</div>
            <div class="gauge-sub">Area with spatial data</div>
          </div>
        </div>
      </div>
      
      <div class="kpi-card" style="margin-top:12px;">
        <div class="kpi-header">
          <span>Activity Trend (12 months)</span>
          <span class="kpi-dot"></span>
        </div>
        <div class="mini-chart">${barsHTML}</div>
        <div class="kpi-sub" style="margin-top:6px;">
          Data updates and feature additions over time
        </div>
      </div>
      
      <p class="dashboard-note">
        Dashboard values are dynamically calculated from loaded layers. Some metrics are placeholders.
      </p>
    `;
  }

  sidePanel?.classList.add('visible');
  document.getElementById('layers-panel')?.classList.remove('visible');
}

/**
 * Show scenarios panel
 */
function showScenarios() {
  const panelTitle = document.getElementById('panel-title');
  const panelBody = document.getElementById('panel-body');
  const sidePanel = document.getElementById('side-panel');

  if (panelTitle) panelTitle.textContent = 'SCENARIO MANAGER';
  if (panelBody) {
    panelBody.innerHTML = `
      <p>Compare different urban development scenarios and their impacts.</p>
      
      <div style="display: flex; flex-direction: column; gap: 10px; margin-top: 12px;">
        <div class="indicator-pill" style="width: 100%;">
          <div class="indicator-icon">'25</div>
          <div class="indicator-meta">
            <span class="indicator-label">Baseline 2025</span>
            <span class="indicator-value">Current state</span>
          </div>
        </div>
        
        <div class="indicator-pill" style="width: 100%;">
          <div class="indicator-icon">'30</div>
          <div class="indicator-meta">
            <span class="indicator-label">Scenario 2030</span>
            <span class="indicator-value">Moderate growth</span>
          </div>
        </div>
        
        <div class="indicator-pill" style="width: 100%;">
          <div class="indicator-icon">'50</div>
          <div class="indicator-meta">
            <span class="indicator-label">Scenario 2050</span>
            <span class="indicator-value">Climate adaptation</span>
          </div>
        </div>
      </div>
      
      <p class="dashboard-note" style="margin-top: 16px;">
        Scenario comparison functionality coming soon. This will allow switching between baseline and future projections.
      </p>
    `;
  }

  sidePanel?.classList.add('visible');
  document.getElementById('layers-panel')?.classList.remove('visible');
}

// Make functions available globally
window.toggleLayerVisibility = toggleLayerVisibility;
window.zoomToLayer = zoomToLayer;
window.initializeUrbanTwinMap = initializeUrbanTwinMap;