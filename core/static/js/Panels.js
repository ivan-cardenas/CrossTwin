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
 * Query parameters shared by the two population endpoints: the explicitly
 * selected unit (if any), the map center (fallback: the city there), the
 * population what-if and the selected year.
 */
function populationRequestParams() {
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
  params.set('pop_scenario', window.POP_SCENARIO || 'prognose');
  params.set('pop_growth', window.POP_GROWTH || 0);
  if (window.ACTIVE_YEAR) params.set('year', window.ACTIVE_YEAR);
  return params;
}

/**
 * (Re)load the population value card of the Dashboard summary. Safe to call
 * any time: it does nothing unless the summary is currently showing.
 */
async function loadDashboardPopulation() {
  const target = document.getElementById('dashboard-population');
  if (!target) return;

  try {
    const response = await fetch(`/api/dashboard/summary/?${populationRequestParams()}`);
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    target.innerHTML = await response.text();
  } catch (error) {
    console.error('Error loading dashboard population:', error);
    target.innerHTML = '<div class="kpi-card"><div class="kpi-sub">Could not load the population.</div></div>';
  }
}

/**
 * Bottom "Population" dock (opened from the Population pill in the bottom bar).
 * It is independent of the side panel: an indicator panel can stay open next to
 * it, and the what-if made here is applied to that panel too.
 */
function togglePopulationPanel() {
  const panel = document.getElementById('population-panel');
  if (!panel) return;

  if (panel.classList.contains('visible')) {
    panel.classList.remove('visible');
    return;
  }
  panel.classList.add('visible');
  loadPopulationPanel();
}

/** (Re)load the dock's content. Does nothing while the dock is closed. */
async function loadPopulationPanel() {
  const panel = document.getElementById('population-panel');
  const body = document.getElementById('population-panel-body');
  if (!panel || !body || !panel.classList.contains('visible')) return;

  initPopulationHover();
  try {
    const response = await fetch(`/api/population/panel/?${populationRequestParams()}`);
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    body.innerHTML = await response.text();
  } catch (error) {
    console.error('Error loading population panel:', error);
    body.innerHTML = '<div class="pop-empty">Could not load the population.</div>';
  }
}

/** Reload everything that shows a population (both are no-ops while hidden). */
function refreshPopulationViews() {
  loadDashboardPopulation();
  loadPopulationPanel();
}

/**
 * Population what-if controls (Templates/partials/_population_controls.html).
 * Stores the chosen CBS forecast variant and extra growth globally, refreshes
 * the URLs of the indicator panels (syncPanelBtns, mainMap.html), reloads an
 * indicator panel that is currently open next to the dock, and redraws the dock.
 */
function applyPopulationControls(container) {
  if (!container) return;
  window.POP_SCENARIO = container.querySelector('.pop-scenario')?.value || 'prognose';
  window.POP_GROWTH = parseFloat(container.querySelector('.pop-growth')?.value) || 0;

  if (typeof syncPanelBtns === 'function') syncPanelBtns();

  // Only refresh an indicator panel that is really open: refreshActivePanel()
  // would otherwise swap content in and (through the htmx handler) open it.
  const sidePanelOpen = document.getElementById('side-panel')?.classList.contains('visible');
  const indicatorToolActive = typeof findActiveAdminTool === 'function' && findActiveAdminTool();
  if (sidePanelOpen && indicatorToolActive && typeof window.refreshActivePanel === 'function') {
    window.refreshActivePanel();
  }

  loadPopulationPanel();
}

/** Back to the median forecast with no extra growth. */
function resetPopulationControls(container) {
  if (!container) return;
  const scenario = container.querySelector('.pop-scenario');
  const growth = container.querySelector('.pop-growth');
  if (scenario) scenario.value = 'prognose';
  if (growth) growth.value = 0;
  applyPopulationControls(container);
}

/**
 * Hover read-out of the population graph. Bound once, by delegation, on the
 * dock's body because its content is replaced on every reload. The per-year
 * values come from the svg's data-points (mainMap/charts.py).
 */
function initPopulationHover() {
  const body = document.getElementById('population-panel-body');
  if (!body || body.dataset.hoverBound) return;
  body.dataset.hoverBound = '1';

  const fmt = (n) => (n === null || n === undefined) ? '—' : Number(n).toLocaleString();

  body.addEventListener('mousemove', (evt) => {
    const svg = evt.target.closest('.pop-graph');
    if (!svg) return;

    const points = svg._points || (svg._points = JSON.parse(svg.dataset.points || '[]'));
    if (!points.length) return;

    const box = svg.getBoundingClientRect();
    const x = (evt.clientX - box.left) / box.width * svg.viewBox.baseVal.width;
    const nearest = points.reduce((a, b) => (Math.abs(b.x - x) < Math.abs(a.x - x) ? b : a));

    const hover = svg.querySelector('.pop-hover');
    hover.style.display = '';
    const line = hover.querySelector('.pop-hover-line');
    line.setAttribute('x1', nearest.x);
    line.setAttribute('x2', nearest.x);
    for (const [cls, y] of [['high', nearest.y_high], ['median', nearest.y_median], ['low', nearest.y_low]]) {
      const dot = hover.querySelector(`.pop-hover-${cls}`);
      dot.setAttribute('cx', nearest.x);
      dot.setAttribute('cy', y ?? -10);
    }

    const readout = svg.parentElement.querySelector('.pop-readout');
    if (readout) {
      readout.textContent =
        `${nearest.year} · low ${fmt(nearest.low)} · median ${fmt(nearest.median)} · high ${fmt(nearest.high)}`;
    }
  });

  body.addEventListener('mouseout', (evt) => {
    const svg = evt.target.closest('.pop-graph');
    if (!svg || svg.contains(evt.relatedTarget)) return;
    svg.querySelector('.pop-hover').style.display = 'none';
    const readout = svg.parentElement.querySelector('.pop-readout');
    if (readout) readout.textContent = 'Move over the graph to read the population per year.';
  });
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