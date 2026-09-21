// ============================================================
// panels.js — Dashboard & Scenario side-panel content
// Depends on: config.js
// ============================================================

/**
 * Dashboard button handler: open/close the side panel.
 *
 * Closed -> open: if an indicator tool (water / heat / housing) is the active
 * toolbar tool, reload its indicators (refreshActivePanel, defined in
 * mainMap.html); otherwise show the summary panel below.
 * Open -> close. The button's own "active" state follows the panel (see the
 * MutationObserver in events.js), so the ✕ button, the layer pills and the
 * toolbar all keep it consistent.
 */
function toggleDashboard() {
  const sidePanel = document.getElementById('side-panel');
  if (!sidePanel) return;

  if (sidePanel.classList.contains('visible')) {
    sidePanel.classList.remove('visible');
    return;
  }

  document.getElementById('layers-panel')?.classList.remove('visible');

  const tool = typeof findActiveAdminTool === 'function' ? findActiveAdminTool() : null;
  if (tool && typeof window.refreshActivePanel === 'function') {
    window.refreshActivePanel();
  } else {
    showDashboardSummary();
  }
  sidePanel.classList.add('visible');
}

/**
 * Summary panel: number of layers available, and the total population of the
 * selected administrative unit (or the city around the map center if none is
 * selected — resolved server-side by /api/dashboard/summary/).
 */
function showDashboardSummary() {
  const panelTitle = document.getElementById('panel-title');
  const panelBody  = document.getElementById('panel-body');

  const visibleLayers = Object.values(layerVisibility).filter(Boolean).length;
  const loadedCount   = Object.keys(loadedLayers).length;

  if (panelTitle) panelTitle.textContent = 'DASHBOARD';
  if (panelBody) {
    panelBody.innerHTML = `
      <div class="dashboard-grid">
        <div class="kpi-card">
          <div class="kpi-header"><span>Layers available</span><span class="kpi-dot"></span></div>
          <div class="kpi-value">${availableLayers.length}</div>
          <div class="kpi-sub">From the database</div>
        </div>
        <div class="kpi-card">
          <div class="kpi-header"><span>Layers visible</span><span class="kpi-dot"></span></div>
          <div class="kpi-value">${visibleLayers}</div>
          <div class="kpi-sub">${loadedCount} loaded on the map</div>
        </div>
      </div>

      <div id="dashboard-population" style="margin-top:12px;">
        <div class="kpi-card"><div class="kpi-sub">Loading population…</div></div>
      </div>

      <p class="dashboard-note">
        Pick a thematic tool (Water Supply, Heat, Housing) on the left toolbar to see its indicators.
      </p>
    `;
  }

  loadDashboardPopulation();
}

/**
 * (Re)load the population card of the summary panel. Safe to call any time:
 * it does nothing unless the summary panel is currently showing.
 */
async function loadDashboardPopulation() {
  const target = document.getElementById('dashboard-population');
  if (!target) return;

  const params = new URLSearchParams();
  const selected = window.SELECTED_UNIT;   // set on an explicit click (map_init.js)
  if (selected?.level && selected?.location) {
    params.set('level', selected.level);
    params.set('location', selected.location);
  }
  if (typeof map !== 'undefined' && map) {
    const center = map.getCenter();
    params.set('lng', center.lng);
    params.set('lat', center.lat);
  }

  try {
    const response = await fetch(`/api/dashboard/summary/?${params}`);
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    target.innerHTML = await response.text();
  } catch (error) {
    console.error('Error loading dashboard population:', error);
    target.innerHTML = '<div class="kpi-card"><div class="kpi-sub">Could not load the population.</div></div>';
  }
}

/**
 * Show the scenario manager panel
 */
function showScenarios() {
  const panelTitle = document.getElementById('panel-title');
  const panelBody  = document.getElementById('panel-body');
  const sidePanel  = document.getElementById('side-panel');

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