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

  if (panelTitle) panelTitle.textContent = 'Dashboard';
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
        Pick a thematic tool (Water Supply, Heat, Housing, Built-up) on the left toolbar to see its indicators.
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
    params.set('lng', roundCoord(center.lng));
    params.set('lat', roundCoord(center.lat));
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
        `${nearest.year}${nearest.trend ? ' · trend extrapolation' : ''} · low ${fmt(nearest.low)} · median ${fmt(nearest.median)} · high ${fmt(nearest.high)}`;
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
 * Scenarios panel: the KNMI'23 climate scenarios of the Klimaateffectatlas,
 * rendered by the server (weather/views.py::climate_panel), opened by the
 * time menu's Compare button. It shows the scenario of the time state
 * (mainMap.js::setTime: window.CLIMATE_SCENARIO, CLIMATE_HEAT = 'average'
 * observed season | 'winter' … 'autumn' | 'warmest' heat-wave day), and a
 * choice in it goes back through setTime. The map centre picks the station
 * marked nearest in the panel's heat table.
 */
function showScenarios() {
  const sidePanel = document.getElementById('side-panel');
  const key = encodeURIComponent(window.CLIMATE_SCENARIO || 'current');
  const heat = encodeURIComponent(window.CLIMATE_HEAT || 'average');
  const c = (typeof map !== 'undefined' && map.getCenter) ? map.getCenter() : null;
  const loc = c ? `&lat=${c.lat.toFixed(4)}&lng=${c.lng.toFixed(4)}` : '';
  const unit = window.ACTIVE_LEVEL
    ? `&level=${encodeURIComponent(window.ACTIVE_LEVEL)}&location=${encodeURIComponent(window.ACTIVE_LOCATION || '')}`
    : '';
  htmx.ajax('GET', `/weather/climate/panel/?climate=${key}&heat=${heat}${loc}${unit}`, {
    target: '#panel-body',
    swap: 'innerHTML',
    source: document.getElementById('time-compare'),
  });
  sidePanel?.classList.add('visible');
  document.getElementById('layers-panel')?.classList.remove('visible');
}

// After the panel is swapped in, its scenario becomes the time state
// (mainMap.js::setTime): the year is the scenario's population year
// (current -> 2025, a horizon -> that year, data-climate-year), the pathway
// the key's suffix. The panel is the caller, so it is not refreshed again.
// If effects were shown, they are recalculated.
document.addEventListener('htmx:afterSwap', function (evt) {
  const panel = evt.detail.target?.querySelector?.('#climate-panel');
  if (!panel) return;
  const key = panel.dataset.climate || 'current';
  const heat = panel.dataset.climateHeat || 'average';
  const changed = key !== (window.CLIMATE_SCENARIO || 'current') || heat !== (window.CLIMATE_HEAT || 'average');
  if (changed) {
    setTime({
      year: panel.dataset.climateYear,
      pathway: key.includes('_') ? key.split('_')[1] : undefined,
      heat,
    }, { refreshPanel: false });
  }
  if (changed && window.CLIMATE_EFFECTS_SHOWN) loadClimateEffects();
});

/**
 * "Calculate effects": the Water Supply and Urban Heat indicators of the
 * selected unit, current climate (2025 population) vs the chosen scenario
 * (its horizon year's population), from mainMap/views.py::climate_effects.
 */
function loadClimateEffects() {
  const target = document.getElementById('climate-effects');
  if (!target) return;
  window.CLIMATE_EFFECTS_SHOWN = true;
  const params = new URLSearchParams({
    climate: window.CLIMATE_SCENARIO || 'current',
    heat: window.CLIMATE_HEAT || 'average',
    level: window.ACTIVE_LEVEL || 'province',
    location: window.ACTIVE_LOCATION || 'Demo',
    pop_scenario: window.POP_SCENARIO || 'prognose',
    pop_growth: window.POP_GROWTH || 0,
  });
  target.innerHTML = '<div class="climate-effects-loading">Calculating…</div>';
  htmx.ajax('GET', `/api/climate/effects/?${params}`, {
    target: '#climate-effects',
    swap: 'innerHTML',
  });
}

// ── Stored scenario runs (mainMap/views_climate.py) ──────────────────

function climateCsrf() {
  return document.querySelector('#climate-panel [name=csrfmiddlewaretoken]')?.value || '';
}

/** POST to a run endpoint and show the returned run partial in #climate-effects. */
async function climateRunPost(url, body) {
  const target = document.getElementById('climate-effects');
  const response = await fetch(url, {
    method: 'POST', body: body || new FormData(),
    headers: { 'X-CSRFToken': climateCsrf(), 'HX-Request': 'true' },
  });
  const text = await response.text();
  if (!response.ok) {
    if (target) {
      const error = document.createElement('div');
      error.className = 'climate-run-error';
      error.setAttribute('role', 'alert');
      error.textContent = text || `Error ${response.status}`;
      target.replaceChildren(error);
    }
    return null;
  }
  if (target) {
    target.innerHTML = text;
    htmx.process(target);
  }
  // HX-Trigger of fetch() responses is not read by htmx: fire it ourselves.
  const trigger = response.headers.get('HX-Trigger');
  if (trigger) {
    try {
      const events = trigger.trim().startsWith('{') ? JSON.parse(trigger) : { [trigger]: null };
      for (const [name, detail] of Object.entries(events)) {
        document.body.dispatchEvent(new CustomEvent(name, { detail: detail || {} }));
      }
    } catch (e) { /* malformed trigger: ignore */ }
  }
  return text;
}

/** "Calculate effects" (staff): store a scenario run for the selected unit and the map view. */
async function runClimateScenario(btn) {
  const panel = document.getElementById('climate-panel');
  if (!panel || btn.disabled) return;
  const body = new FormData();
  body.set('climate', window.CLIMATE_SCENARIO || 'current');
  body.set('heat', window.CLIMATE_HEAT || 'average');
  body.set('level', window.ACTIVE_LEVEL || '');
  body.set('location', window.ACTIVE_LOCATION || '');
  body.set('pop_scenario', window.POP_SCENARIO || 'prognose');
  body.set('pop_growth', window.POP_GROWTH || 0);
  if (typeof map !== 'undefined' && map.getBounds) {
    const b = map.getBounds();
    body.set('bbox', [b.getWest(), b.getSouth(), b.getEast(), b.getNorth()].map(v => v.toFixed(6)).join(','));
  }
  const value = (id) => document.getElementById(id)?.value || '';
  body.set('datetime', value('climate-run-datetime'));
  body.set('met_source', value('climate-run-met') || 'knmi');
  body.set('resolution', value('climate-run-resolution') || '2');
  body.set('run_heat', document.getElementById('climate-run-heat')?.checked === false ? '0' : '1');
  const target = document.getElementById('climate-effects');
  if (target) target.innerHTML = '<div class="climate-effects-loading">Calculating and storing the scenario run…</div>';
  btn.disabled = true;
  try {
    await climateRunPost('/api/climate/runs/', body);
  } finally {
    btn.disabled = false;
  }
}

/** Add a scenario raster (Tmrt / UTCI / PET / WBGT) to the map, as the LST tool does. */
async function addClimateRunLayer(layer) {
  if (typeof availableLayers !== 'undefined' && !availableLayers.some(l => l.key === layer.key)) {
    availableLayers.push(layer);
  }
  if (typeof layerVisibility !== 'undefined') layerVisibility[layer.key] = true;
  if (typeof renderLayerList === 'function') renderLayerList();
  if (typeof addLayer === 'function') await addLayer(layer);
}

document.addEventListener('click', function (evt) {
  const t = evt.target;
  if (t.closest?.('#climate-effects-btn')) { loadClimateEffects(); return; }
  const run = t.closest?.('#climate-run-btn');
  if (run) { runClimateScenario(run); return; }
  const open = t.closest?.('.climate-run-open');
  if (open) {
    htmx.ajax('GET', open.dataset.url, { target: '#climate-effects', swap: 'innerHTML' });
    return;
  }
  const chip = t.closest?.('.climate-run-layer');
  if (chip) {
    try { addClimateRunLayer(JSON.parse(chip.dataset.layer)); } catch (e) { console.warn('Bad layer entry', e); }
    return;
  }
  const action = t.closest?.('[data-climate-run-action]');
  if (action && !action.disabled) {
    const kind = action.dataset.climateRunAction;
    if (kind === 'delete') {
      // No browser confirm() dialog: a second click within 4 s confirms.
      if (action.dataset.armed !== '1') {
        action.dataset.armed = '1';
        action.textContent = 'Click again to delete';
        setTimeout(() => { action.dataset.armed = ''; action.textContent = 'Delete'; }, 4000);
        return;
      }
    }
    action.disabled = true;
    action.classList.add('is-busy');
    climateRunPost(action.dataset.url).finally(() => { action.disabled = false; action.classList.remove('is-busy'); });
  }
});

// A deleted run's layers leave the map.
document.addEventListener('climate-run-deleted', function (evt) {
  (evt.detail?.layers || []).forEach(key => {
    if (key && typeof removeLayer === 'function') removeLayer(key);
  });
});

// ── Lens panel tabs (Map simplification step 4) ─────────────────────────
// A lens's indicator panel (#panel-body holding .lens-panel) gets three tabs:
// Summary (headline cards), What-if (sliders + every card) and Calculate
// (the lens's tools, Config.js::LENSES[].tools, in #panel-calculate). The
// tab is kept while the panel re-renders (unit click, year) and reset to
// Summary when another lens opens (Events.js). Any other content in the
// side panel (Scenarios, Dashboard, an edit form) hides the tabs.
let panelTab = 'summary';

function lensToolIds() {
  return (typeof LENSES !== 'undefined' && LENSES[activeTool]?.tools) || [];
}

function setPanelTab(tab) {
  panelTab = tab;
  syncPanelTabs();
}

function syncPanelTabs() {
  const side = document.getElementById('side-panel');
  const tabs = document.getElementById('panel-tabs');
  const body = document.getElementById('panel-body');
  const calc = document.getElementById('panel-calculate');
  if (!side || !tabs || !body || !calc) return;

  const tools = lensToolIds();
  const lensPanel = !!body.querySelector('.lens-panel');
  let tab = lensPanel ? panelTab : null;
  if (tab === 'calculate' && !tools.length) tab = 'summary';

  tabs.hidden = !lensPanel;
  tabs.querySelectorAll('.panel-tab').forEach(btn => {
    btn.setAttribute('aria-selected', String(btn.dataset.tab === tab));
    if (btn.dataset.tab === 'calculate') btn.hidden = !tools.length;
  });
  if (tab) side.dataset.tab = tab; else delete side.dataset.tab;
  body.hidden = tab === 'calculate';
  calc.hidden = tab !== 'calculate';

  // Only this lens's tools; a card of another lens's tool closes
  const shown = [...calc.querySelectorAll('.calc-tool-btn')].filter(btn => {
    btn.hidden = !tools.includes(btn.dataset.calcTool);
    btn.classList.remove('is-wide');
    return !btn.hidden;
  });
  if (shown.length % 2) shown[shown.length - 1].classList.add('is-wide');
  calc.querySelectorAll('.lst-card').forEach(card => {
    if (!tools.includes(card.id.replace(/-card$/, ''))) card.classList.remove('visible');
  });
}

document.addEventListener('click', (evt) => {
  const tab = evt.target.closest?.('.panel-tab, [data-panel-tab]');
  if (tab) setPanelTab(tab.dataset.tab || tab.dataset.panelTab);
});

// Whatever replaces the panel's content (htmx swap, intro, edit form)
document.addEventListener('DOMContentLoaded', () => {
  const body = document.getElementById('panel-body');
  if (body) new MutationObserver(syncPanelTabs).observe(body, { childList: true });
  syncPanelTabs();
});
