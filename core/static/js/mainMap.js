// ============================================================
// mainMap.js — page-level wiring for mainMap.html: map init, the bottom
// Actions menu (import buttons + year selector), guided tour, and the
// admin-unit-driven panel registry (ADMIN_PANEL_TOOLS / syncPanelBtns / refreshActivePanel).
// Depends on: config.js, map_init.js (and window.MAPBOX_ACCESS_TOKEN, set
// inline by mainMap.html before this file loads).
// ============================================================

// Initialize the Urban Twin map — only pass server-side values here;
// all other defaults live in Config.js
document.addEventListener("DOMContentLoaded", () => {
  initializeUrbanTwinMap({ mapboxToken: window.MAPBOX_ACCESS_TOKEN });
});


// ── ACTIONS MENU ───────────────────────────────────────────────────────────
// Drop-up opened from the bottom bar's Actions button; holds the import
// buttons and the year selector. The menu is a sibling of .bottom-bar (see
// mainMap.css for why), so it is anchored to its button here.
const actionsMenuBtn = document.getElementById('actions-menu-btn');
const actionsMenu = document.getElementById('actions-menu');

function positionActionsMenu() {
  const wrap = actionsMenu.offsetParent;   // .map-wrapper; null while the menu is hidden
  if (!wrap) return;
  const w = wrap.getBoundingClientRect();
  const b = actionsMenuBtn.getBoundingClientRect();
  const left = b.left - w.left - wrap.clientLeft;
  const maxLeft = wrap.clientWidth - actionsMenu.offsetWidth - 8;
  actionsMenu.style.left = `${Math.max(8, Math.min(left, maxLeft))}px`;
  actionsMenu.style.bottom = `${wrap.clientHeight - (b.top - w.top - wrap.clientTop) + 8}px`;
}

function setActionsMenuOpen(open) {
  actionsMenu.classList.toggle('visible', open);
  actionsMenuBtn.classList.toggle('active', open);
  actionsMenuBtn.setAttribute('aria-expanded', open);
  if (open) positionActionsMenu();
}

if (actionsMenuBtn && actionsMenu) {
  actionsMenuBtn.addEventListener('click', () => {
    setActionsMenuOpen(!actionsMenu.classList.contains('visible'));
  });
  // Close on a click anywhere else (the map included) and on Escape.
  document.addEventListener('click', (evt) => {
    if (!actionsMenu.contains(evt.target) && !actionsMenuBtn.contains(evt.target)) {
      setActionsMenuOpen(false);
    }
  });
  document.addEventListener('keydown', (evt) => {
    if (evt.key === 'Escape') setActionsMenuOpen(false);
  });
  window.addEventListener('resize', positionActionsMenu);
  // The button shifts when the pills beside it change width (e.g. the
  // population count updating), so re-anchor an open menu then too.
  if (typeof ResizeObserver !== 'undefined') {
    new ResizeObserver(positionActionsMenu).observe(actionsMenuBtn.parentElement);
  }
}

document.getElementById('importDataBtn')?.addEventListener('click', () => {
  console.log('Import Data clicked');
  // Redirect to import page or open modal
  window.location.href = '/importer/';
});

document.getElementById('getDataBtn')?.addEventListener('click', () => {
  console.log('Import Data clicked');
  // Redirect to import page or open modal
  window.location.href = '/importer/external/';
});

document.getElementById('scenario1Btn')?.addEventListener('click', () => {
  console.log('Scenario 1 clicked');
  // Toggle scenario 1
});

document.getElementById('calculateBtn')?.addEventListener('click', () => {
  console.log('Calculate Results clicked');
  // Trigger calculation
});

document.getElementById('settingsBtn')?.addEventListener('click', () => {
  console.log('Settings clicked');
  // Open settings panel
});

// Sets the active year (population projection year) as if its button were
// clicked: highlights the button, updates the Actions label, the panel URLs,
// the open panel and the population dock. Also called by the Scenarios panel
// (Panels.js): current climate -> 2025, 2050 / 2100 scenarios -> that year,
// with {refreshPanel: false} so the Scenarios panel is not replaced.
function setActiveYear(year, {refreshPanel = true} = {}) {
  year = parseInt(year);
  if (!year || year === window.ACTIVE_YEAR) return;
  document.querySelectorAll('.year-btn').forEach(b =>
    b.classList.toggle('active', parseInt(b.dataset.year) === year));
  window.ACTIVE_YEAR = year;

  // The Actions button shows the active year while the menu is collapsed
  const yearLabel = document.getElementById('actions-menu-year');
  if (yearLabel) yearLabel.textContent = String(year);

  // Update panel button URLs with new year
  syncPanelBtns();

  // If an admin-unit-driven panel is already open, reload it with new context
  if (refreshPanel) refreshActivePanel();
  if (typeof loadPopulationPanel === 'function') loadPopulationPanel();   // no-op unless the dock is open
}
window.setActiveYear = setActiveYear;

// The other direction: a year chosen in the Actions menu sets the climate
// scenario of that period (weather/calculations/climate.py::population_year):
// 2050 / 2100 -> that horizon, keeping the chosen pathway (High, dry when
// none), any other year -> the current climate. The heat mode is kept.
const CLIMATE_HORIZONS = [2050, 2100];
const CLIMATE_PATHWAY_LABELS = { Ld: 'Low, dry', Ln: 'Low, wet', Hd: 'High, dry', Hn: 'High, wet' };

function climateKeyForYear(year) {
  if (!CLIMATE_HORIZONS.includes(year)) return 'current';
  const current = window.CLIMATE_SCENARIO || 'current';
  const pathway = current.includes('_') ? current.split('_')[1] : 'Hd';
  return `${year}_${pathway}`;
}

// The Scenarios button's badge, as the panel renders it (climate_panel.html data-climate-label).
function climateBadgeLabel(key) {
  if (key === 'current') return '';
  const [horizon, pathway] = key.split('_');
  const heat = window.CLIMATE_HEAT || 'average';
  const suffix = heat === 'warmest' ? ' · warmest day' : (heat !== 'average' ? ` · ${heat}` : '');
  return `${horizon} ${CLIMATE_PATHWAY_LABELS[pathway] || pathway}${suffix}`;
}

function scenariosPanelOpen() {
  return !!document.querySelector('#panel-body #climate-panel') &&
    document.getElementById('side-panel')?.classList.contains('visible');
}

function syncClimateToYear(year) {
  const key = climateKeyForYear(year);
  if (key === (window.CLIMATE_SCENARIO || 'current')) return false;
  window.CLIMATE_SCENARIO = key;
  if (typeof renderClimateBadge === 'function') renderClimateBadge(climateBadgeLabel(key));
  syncPanelBtns();
  // An open Scenarios panel re-renders with the new scenario (its afterSwap
  // sees the same key, so it does not set the year back).
  if (scenariosPanelOpen() && typeof showScenarios === 'function') showScenarios();
  window.dispatchEvent(new CustomEvent('crosstwin:climate-changed',
    { detail: { key, heat: window.CLIMATE_HEAT || 'average' } }));
  return true;
}

document.querySelectorAll('.year-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    const year = parseInt(btn.dataset.year);
    const sameYear = year === window.ACTIVE_YEAR;
    const climateChanged = syncClimateToYear(year);
    setActiveYear(year, { refreshPanel: !scenariosPanelOpen() });
    // setActiveYear does nothing for the same year: refresh for the new climate here
    if (sameYear && climateChanged && !scenariosPanelOpen()) refreshActivePanel();
  });
});



let tourStep = 0;

function startTour() {
  tourStep = 0;
  document.getElementById('onboarding-hint').style.display = 'none';
  const tourEl = document.getElementById('demo-tour');
  tourEl.classList.remove('hidden');
  // Re-trigger animation on each open
  tourEl.style.animation = 'none';
  requestAnimationFrame(() => { tourEl.style.animation = ''; });
  renderTourStep(tourStep);
}

function endTour() {
  document.getElementById('demo-tour').classList.add('hidden');
  clearTourHighlight();
  localStorage.setItem('crosstwin_tour_seen', '1');
  // Show hint as a restart button
  const hint = document.getElementById('onboarding-hint');
  hint.style.display = '';
  hint.querySelector('p').textContent = 'Want to see the walkthrough again?';
  const btn = hint.querySelector('#start-tour-btn');
  if (btn) btn.textContent = '↺ Restart Tour';
}

function renderTourStep(idx) {
  const step = TOUR_STEPS[idx];
  document.getElementById('tour-step-num').textContent = step.num;
  document.getElementById('tour-step-title').textContent = step.title;
  document.getElementById('tour-step-desc').textContent = step.desc;

  document.querySelectorAll('.tour-step-dot').forEach((dot, i) => {
    dot.classList.remove('active', 'completed');
    if (i < idx) dot.classList.add('completed');
    if (i === idx) dot.classList.add('active');
  });

  document.getElementById('tour-prev').disabled = (idx === 0);
  document.getElementById('tour-next').textContent =
    idx === TOUR_STEPS.length - 1 ? 'Finish ✓' : 'Next →';

  clearTourHighlight();
  if (step.target) {
    const el = document.querySelector(step.target);
    if (el) el.classList.add('tour-highlight');
  }
}

function clearTourHighlight() {
  document.querySelectorAll('.tour-highlight').forEach(el => el.classList.remove('tour-highlight'));
}

document.getElementById('start-tour-btn')?.addEventListener('click', startTour);

document.getElementById('tour-prev')?.addEventListener('click', () => {
  if (tourStep > 0) renderTourStep(--tourStep);
});

document.getElementById('tour-next')?.addEventListener('click', () => {
  if (tourStep < TOUR_STEPS.length - 1) {
    renderTourStep(++tourStep);
  } else {
    endTour();
  }
});

document.getElementById('tour-skip')?.addEventListener('click', endTour);

document.querySelectorAll('.tour-step-dot').forEach((dot, i) => {
  dot.addEventListener('click', () => { tourStep = i; renderTourStep(tourStep); });
});

// Auto-start on first visit (after map loads)
if (!localStorage.getItem('crosstwin_tour_seen')) {
  setTimeout(startTour, 1200);
}
// ── END GUIDED TOUR ────────────────────────────────────────────────────────

document.body.addEventListener('htmx:afterSwap', function(evt) {
  if (evt.detail.target.id === 'panel-body') {
    const title = evt.detail.elt?.dataset?.panelTitle || 'INFO';
    // 'visible' is the class the CSS shows the panel with (there is no rule for
    // 'open'). Tools without a TOOL_CONTENT entry (e.g. Housing) never got it
    // from the toolbar click handler, so the panel stayed hidden.
    document.getElementById('side-panel').classList.add('visible');
    document.getElementById('panel-title').textContent = title;
  }
});

// Population what-if chosen with the controls in the dashboard / indicator
// panels (applyPopulationControls in Panels.js), passed on to every panel that
// is year- and population-aware.
function populationQuery() {
  const scenario = encodeURIComponent(window.POP_SCENARIO || 'prognose');
  const growth = encodeURIComponent(window.POP_GROWTH || 0);
  return `?pop_scenario=${scenario}&pop_growth=${growth}`;
}

// KNMI'23 climate scenario chosen in the Scenarios panel (Panels.js,
// weather/calculations/climate.py), passed on to the panels whose
// meteorology it changes (heat: weather sliders; water: rain and recharge),
// with the heat mode (average day | warmest = heat-wave day; heat panel only).
function climateParam() {
  return `climate=${encodeURIComponent(window.CLIMATE_SCENARIO || 'current')}` +
    `&climate_heat=${encodeURIComponent(window.CLIMATE_HEAT || 'average')}`;
}

// Registry of toolbar panels driven by the selected administrative unit
// (level/location[/year]). Add an entry here when wiring up a new
// indicator panel (e.g. housing, energy) to admin-unit selection —
// syncPanelBtns/refreshActivePanel then handle it automatically, no other
// changes needed in Map_init.js.
const ADMIN_PANEL_TOOLS = {
  water: (level, location) =>
    `/watersupply/indicators/${level}/${location}/${window.ACTIVE_YEAR}/${populationQuery()}&${climateParam()}`,
  // Urban heat has no year and does not depend on population.
  temperature: (level, location) =>
    `/urban_heat/indicators/${level}/${location}/?${climateParam()}`,
  // Same URL shape as water: housing/urls.py is indicators/<level>/<location>/<year>/.
  housing: (level, location) =>
    `/housing/indicators/${level}/${location}/${window.ACTIVE_YEAR}/${populationQuery()}`,
  // The building stock has no year; year + population only drive the per-capita cards.
  builtup: (level, location) =>
    `/builtup/indicators/${level}/${location}/${window.ACTIVE_YEAR}/${populationQuery()}`,
};

function syncPanelBtns() {
  const level = window.ACTIVE_LEVEL || 'province';
  const location = window.ACTIVE_LOCATION || 'Demo';
  for (const [tool, urlBuilder] of Object.entries(ADMIN_PANEL_TOOLS)) {
    const btn = document.querySelector(`[data-tool="${tool}"]`);
    if (!btn) continue;
    btn.setAttribute('hx-get', urlBuilder(level, location));
    htmx.process(btn);
  }
}

// Finds which registered admin-panel tool (if any) is the currently
// selected toolbar tool (the button with the 'active' class, set by
// events.js on every toolbar click). This reflects which layer/tool the
// user is actually in, regardless of whether the side panel has finished
// (re)opening yet — matching on panel-title text instead was a race: it
// only reflected reality after that tool's own htmx swap had completed.
function findActiveAdminTool() {
  const activeTool = document.querySelector('.tool-button.active')?.dataset.tool;
  return activeTool && ADMIN_PANEL_TOOLS[activeTool] ? activeTool : null;
}

// Refreshes whichever admin-panel-driven panel is currently open. Pass
// fallbackTool to open one when none is open yet (e.g. first map click);
// omit it to no-op when the open panel isn't admin-unit-driven.
function refreshActivePanel(fallbackTool = null) {
  // Panning or a click on a neighbourhood must not replace the edit form
  if (typeof isEditing === 'function' && isEditing()) return;
  const tool = findActiveAdminTool() || fallbackTool;
  const btn = tool && document.querySelector(`[data-tool="${tool}"]`);
  if (!btn) return;
  htmx.ajax('GET', btn.getAttribute('hx-get'), {
    target: '#panel-body',
    swap: 'innerHTML',
    source: btn,
  });
}

window.syncPanelBtns = syncPanelBtns;
window.refreshActivePanel = refreshActivePanel;
