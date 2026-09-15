// ============================================================
// ui.js — Layer list rendering, indicators, legend icons
// Depends on: config.js, layers.js
// ============================================================

/**
 * Render the layer list in the layers panel
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
    if (!groups[layer.app_label]) groups[layer.app_label] = [];
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
        <div class="layer-item" id="layer-item-${layer.key}">
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
 * Generate SVG legend icon for a layer
 */
function getLayerLegendIcon(geometryType, color) {
  const s = 16;
  switch (geometryType) {
    case 'point':
      return `<svg width="${s}" height="${s}" class="layer-icon">
        <circle cx="${s/2}" cy="${s/2}" r="5" fill="${color}" stroke="#fff" stroke-width="1.5"/>
      </svg>`;
    case 'line':
      return `<svg width="${s}" height="${s}" class="layer-icon">
        <line x1="2" y1="${s-3}" x2="${s-2}" y2="3" stroke="${color}" stroke-width="3" stroke-linecap="round"/>
      </svg>`;
    default:
      return `<svg width="${s}" height="${s}" class="layer-icon">
        <rect x="2" y="2" width="${s-4}" height="${s-4}" fill="${color}" fill-opacity="0.4" stroke="${color}" stroke-width="1.5"/>
      </svg>`;
  }
}

/**
 * Update bottom-bar indicator counts
 */
function updateIndicators() {
  const layersEl   = document.getElementById('layers-count');
  const featuresEl = document.getElementById('features-count');
  const visibleEl  = document.getElementById('visible-count');

  if (layersEl) layersEl.textContent = availableLayers.length;

  if (featuresEl) {
    let total = 0;
    for (const data of Object.values(loadedLayers)) total += data.geojson.features.length;
    featuresEl.textContent = total.toLocaleString();
  }

  if (visibleEl) {
    let count = 0;
    for (const [key, visible] of Object.entries(layerVisibility)) {
      if (visible && loadedLayers[key]) count++;
    }
    visibleEl.textContent = count;
  }
}