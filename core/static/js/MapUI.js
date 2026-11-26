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
    if (isWeatherPillLayer(layer)) return;   // the rain radar: weather pill only
    if (!groups[layer.app_label]) groups[layer.app_label] = [];
    groups[layer.app_label].push(layer);
  });

  // The restore point (backup bar) lives in the Edit mode banner (mainMap.html).
  // ＋ (draw a new object) only in Edit mode (Modes.js); the catalog marks
  // layers editable for staff only.
  const editing = window.MAP_MODE === 'edit';
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
            <span class="layer-name" title="${layer.display_name}">${layer.display_name}</span>
            <span class="layer-count"${layer.count_estimated ? ' title="Estimate (planner statistics)"' : ''}>${layer.count_estimated ? '~' : ''}${layer.count}</span>
          </div>
          <div class="layer-actions">
            ${editing && layer.editable ? `<button onclick="startCreate('${layer.key}')" title="Draw a new object">＋</button>` : ''}
            ${layer.layer_type === 'raster' ? `<button class="layer-3d-btn" onclick="Raster3D.open('${layer.key}')" title="View as 3D columns (averaged containers)" aria-label="View as 3D columns"><svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.3" stroke-linejoin="round" stroke-linecap="round"><path d="M7 1.2 12.2 4v6L7 12.8 1.8 10V4z"/><path d="M1.8 4 7 7l5.2-3M7 7v5.8"/></svg></button>` : ''}
            <button onclick="zoomToLayer('${layer.key}')" title="Zoom to layer">🔍</button>
          </div>
        </div>`;
    });

    html += '</div>';
  }

  container.innerHTML = html;
  filterLayersByLens(activeTool);   // the open lens's layers only, rest in the drawer
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

/**
 * Draw the left rail from Config.js::LENSES: Overview (no lens), then one
 * labelled group per LENS_GROUPS entry. Lenses with an indicator panel get
 * their htmx attributes here and their URL from mainMap.js::syncPanelBtns.
 */
function renderLensRail() {
  const rail = document.getElementById('lens-rail');
  if (!rail) return;

  const button = (id, { label, title, icon, panel, tools }) => `
    <button type="button" class="tool-button" data-tool="${id}" title="${title}" aria-label="${title}"
            aria-pressed="false"${panel ? `
            data-panel-title="${title}" hx-target="#panel-body" hx-indicator="#map-loader" hx-swap="innerHTML"` : ''}>
      <span class="bi ${icon}" aria-hidden="true"></span>
      <span class="tool-label">${label}</span>${tools && tools.length ? `
      <span class="stale-dot" hidden title="Buildings changed in this view: recalculate in the Calculate tab"></span>` : ''}
    </button>`;

  let html = button('overview', { label: 'Overview', title: 'Overview: no topic, all your layers', icon: 'bi-map' });
  for (const group of LENS_GROUPS) {
    const lenses = Object.entries(LENSES).filter(([, lens]) => lens.group === group.id);
    if (!lenses.length) continue;
    html += `<div class="lens-group" role="group" aria-labelledby="lens-group-${group.id}">
      <span class="lens-group-label" id="lens-group-${group.id}">${group.label}</span>
      ${lenses.map(([id, lens]) => button(id, lens)).join('')}
    </div>`;
  }
  rail.innerHTML = html;
  markActiveLens(activeTool);
  if (typeof syncPanelBtns === 'function') syncPanelBtns();   // sets hx-get + htmx.process
}

/** Highlight the rail button of the open lens (Overview when none). */
function markActiveLens(toolId) {
  document.querySelectorAll('#toolbar .tool-button').forEach(btn => {
    const active = btn.dataset.tool === toolId;
    btn.classList.toggle('active', active);
    btn.setAttribute('aria-pressed', String(active));
  });
}
