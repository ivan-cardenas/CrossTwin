/**
 * Map functionality for CrossTwin
 * Handles Mapbox map initialization, layer loading, and interactions
 */

// Global variables
let map;
let availableLayers = [];
const loadedLayers = {};
const layerVisibility = {};

// API endpoint for available layers
const LAYERS_API_URL = '/map/api/layers/';

const BASEMAPS = {
    standard : 'mapbox://styles/mapbox/standard',
    streets: 'mapbox://styles/mapbox/streets-v12',
    satellite: 'mapbox://styles/mapbox/satellite-streets-v12',
    outdoors: 'mapbox://styles/mapbox/outdoors-v12',
    light: 'mapbox://styles/mapbox/light-v11',
    dark: 'mapbox://styles/mapbox/dark-v11'
};

let activeBasemap = 'standard';


/**
 * Initialize the Mapbox map
 * @param {string} accessToken - Mapbox access token
 * @param {object} options - Optional map configuration
 */
function initializeMap(accessToken, options = {}) {
    // Set access token
    mapboxgl.accessToken = accessToken;
    
    // Default options
    const defaultOptions = {
        container: 'map',
        style: BASEMAPS[activeBasemap], // Default style
        center: [5.5, 52.2],  // Default: Netherlands
        zoom: 7
    };
    
    // Merge options
    const mapOptions = { ...defaultOptions, ...options };
    
    // Create map
    map = new mapboxgl.Map(mapOptions);
    
    // Add controls
    map.addControl(new mapboxgl.NavigationControl(), 'top-right');
    map.addControl(new mapboxgl.ScaleControl(), 'bottom-right');
    map.addControl(new mapboxgl.FullscreenControl(), 'top-right');
    
    // Initialize layers when map loads
    map.on('load', () => {
        console.log('Map loaded successfully');
        fetchAvailableLayers();
    });
    
    // Handle map errors
    map.on('error', (e) => {
        console.error('Map error:', e.error);
    });
    
    return map;
}

/**
 * Show or hide the loading indicator
 * @param {boolean} show - Whether to show the loader
 */
function showLoader(show) {
    const loader = document.getElementById('map-loader');
    if (loader) {
        loader.style.display = show ? 'flex' : 'none';
    }
}

/**
 * Create popup content from feature properties
 * @param {object} properties - Feature properties
 * @param {string} layerName - Display name of the layer
 * @returns {string} HTML content for popup
 */
function createPopupContent(properties, layerName) {
    let html = `<div class="feature-popup">
        <h6>${layerName}</h6>
        <table>`;
    
    for (const [key, value] of Object.entries(properties)) {
        if (value !== null && value !== undefined && key !== 'pk') {
            let displayValue = value;
            if (typeof value === 'number') {
                displayValue = Number.isInteger(value) ? value : value.toFixed(2);
            }
            html += `<tr>
                <td>${key.replace(/_/g, ' ')}</td>
                <td>${displayValue}</td>
            </tr>`;
        }
    }
    
    html += '</table></div>';
    return html;
}

/**
 * Add coordinates to bounds based on geometry type
 * @param {array} coords - Coordinates array
 * @param {LngLatBounds} bounds - Mapbox bounds object
 * @param {string} type - Geometry type
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
 * Load and add a layer to the map
 * @param {object} layerConfig - Layer configuration object
 */
async function addLayer(layerConfig) {
    const { key, url, color, geometry_type, display_name } = layerConfig;
    
    // Skip if already loaded
    if (loadedLayers[key]) {
        return;
    }

    console.log(`Loading layer "${key}" from ${url}...`);
    
    try {
        showLoader(true);
        
        const response = await fetch(url);
        if (!response.ok) throw new Error(`Failed to load ${key}`);
        
        const geojson = await response.json();
        
        // Skip empty layers
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
                    'fill-opacity': 0.3
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
        
        // Change cursor on hover
        map.on('mouseenter', clickLayerId, () => {
            map.getCanvas().style.cursor = 'pointer';
        });
        
        map.on('mouseleave', clickLayerId, () => {
            map.getCanvas().style.cursor = '';
        });
        
        console.log(`Layer "${key}" loaded with ${geojson.features.length} features`);
        
    } catch (error) {
        console.error(`Error loading layer "${key}":`, error);
    } finally {
        showLoader(false);
    }
}

/**
 * Remove a layer from the map
 * @param {string} key - Layer key
 */
function removeLayer(key) {
    if (!loadedLayers[key]) return;
    
    const { layerIds } = loadedLayers[key];
    
    layerIds.forEach(id => {
        if (map.getLayer(id)) map.removeLayer(id);
    });
    
    if (map.getSource(key)) map.removeSource(key);
    
    delete loadedLayers[key];
}

/**
 * Toggle layer visibility
 * @param {string} key - Layer key
 * @param {boolean} visible - Whether layer should be visible
 */
function toggleLayerVisibility(key, visible) {
    layerVisibility[key] = visible;
    
    if (visible && !loadedLayers[key]) {
        // Load the layer
        const config = availableLayers.find(l => l.key === key);
        if (config) addLayer(config);
    } else if (!visible && loadedLayers[key]) {
        // Hide the layer
        loadedLayers[key].layerIds.forEach(id => {
            map.setLayoutProperty(id, 'visibility', 'none');
        });
    } else if (visible && loadedLayers[key]) {
        // Show the layer
        loadedLayers[key].layerIds.forEach(id => {
            map.setLayoutProperty(id, 'visibility', 'visible');
        });
    }
}

/**
 * Zoom to a specific layer
 * @param {string} key - Layer key
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
        map.fitBounds(bounds, { padding: 50 });
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
        map.fitBounds(bounds, { padding: 50 });
    }
}

/**
 * Render the layer list grouped by app
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
                    <span class="layer-count">(${layer.count})</span>
                </div>
                <div class="layer-actions">
                    <button onclick="zoomToLayer('${layer.key}')" title="Zoom to layer">
                        <i class="bi bi-zoom-in text-blue-500"></i>
                    </button>
                </div>
            </div>`;
        });
        
        html += '</div>';
    }
    
    container.innerHTML = html;
}

/**
 * Generate an SVG legend icon based on geometry type
 * @param {string} geometryType - 'point', 'line', or 'polygon'
 * @param {string} color - Hex color for the icon
 * @returns {string} SVG markup
 */
function getLayerLegendIcon(geometryType, color) {
    const size = 18;
    
    switch (geometryType) {
        case 'point':
            return `
                <svg width="${size}" height="${size}" class="layer-icon">
                    <circle cx="${size/2}" cy="${size/2}" r="5" 
                            fill="${color}" stroke="#fff" stroke-width="1.5"/>
                </svg>`;
        
        case 'line':
            return `
                <svg width="${size}" height="${size}" class="layer-icon">
                    <line x1="2" y1="${size-4}" x2="${size-2}" y2="4" 
                          stroke="${color}" stroke-width="3" stroke-linecap="round"/>
                </svg>`;
        
        default: // polygon
            return `
                <svg width="${size}" height="${size}" class="layer-icon">
                    <rect x="2" y="2" width="${size-4}" height="${size-4}" 
                          fill="${color}" fill-opacity="0.4" 
                          stroke="${color}" stroke-width="1.5"/>
                </svg>`;
    }
}

/**
 * Fetch available layers from API
 */
async function fetchAvailableLayers() {
    try {
        const response = await fetch(LAYERS_API_URL);
        if (!response.ok) throw new Error('Failed to fetch layers');
        
        const data = await response.json();
        availableLayers = data.layers;
        
        // Initialize visibility (all visible by default)
        availableLayers.forEach(layer => {
            layerVisibility[layer.key] = true;
        });
        
        renderLayerList();
        
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
            container.innerHTML = '<div class="no-layers text-danger">Error loading layers</div>';
        }
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
 * Change the basemap style
 * @param {string} styleUrl - Mapbox style URL
 */
function changeBasemap(styleUrl) {
    const currentVisibility = { ...layerVisibility };
    
    map.setStyle(styleUrl);
    
    map.once('style.load', () => {
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


/** 
 * change the basemap style
 * @param {string} basemapKey - Key of the basemap to switch to
 */

function changeBasemap(basemapKey) {
    if (!BASEMAPS[basemapKey]) return;

    activeBasemap = basemapKey;
    const currentVisibility = { ...layerVisibility };

    map.setStyle(BASEMAPS[basemapKey]);

    map.once('style.load', () => {
        for (const layer of availableLayers) {
            if (currentVisibility[layer.key]) {
                addLayer(layer);
            }
        }
    });
}

/**
 * Initialize control panel event listeners
 */
function initializeControls() {
    // Select all button
    const btnSelectAll = document.getElementById('btn-select-all');
    if (btnSelectAll) {
        btnSelectAll.addEventListener('click', selectAllLayers);
    }
    
    // Select none button
    const btnSelectNone = document.getElementById('btn-select-none');
    if (btnSelectNone) {
        btnSelectNone.addEventListener('click', selectNoLayers);
    }
    
    // Fit all button
    const btnFitAll = document.getElementById('btn-fit-all');
    if (btnFitAll) {
        btnFitAll.addEventListener('click', zoomToAllVisible);
    }
    
    // Basemap selector
    const basemapSelect = document.getElementById('basemap-select');
    if (basemapSelect) {
        basemapSelect.addEventListener('change', (e) => {
            changeBasemap(e.target.value);
        });
    }
}



// Initialize controls when DOM is ready
document.addEventListener('DOMContentLoaded', initializeControls);


