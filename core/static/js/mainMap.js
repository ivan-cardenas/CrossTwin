// ============================================================
// mainMap.js — page-level wiring for mainMap.html: map init, the time chip
// (year + climate scenario, setTime), guided tour, and the
// admin-unit-driven panel registry (ADMIN_PANEL_TOOLS / syncPanelBtns / refreshActivePanel).
// The Explore / Plan / Edit modes are Modes.js.
// Depends on: config.js, map_init.js, Modes.js (and window.MAPBOX_ACCESS_TOKEN,
// set inline by mainMap.html before this file loads).
// ============================================================

// Initialize the Urban Twin map — only pass server-side values here;
// all other defaults live in Config.js
document.addEventListener("DOMContentLoaded", () => {
  initializeUrbanTwinMap({ mapboxToken: window.MAPBOX_ACCESS_TOKEN });
});


// Overlays (side panel, population dock, tool cards, legends) stop at
// --bottom-clear so they never cover the bottom bar's Dashboard button. The bar wraps to two rows on phones, so measure it.
function syncBottomClear() {
  const bar = document.querySelector('.bottom-bar');
  if (!bar) return;
  document.documentElement.style.setProperty('--bottom-clear', `${Math.ceil(bar.offsetHeight) + 6}px`);
}
syncBottomClear();
if (window.ResizeObserver) {
  const bar = document.querySelector('.bottom-bar');
  if (bar) new ResizeObserver(syncBottomClear).observe(bar);
}

// ── TIME: year + climate scenario, one state (Map simplification step 3) ──
// The time chip in the status strip is the one place to set them; the
// Scenarios panel (Panels.js) reports its choice through setTime too, so
// there is no two-way sync. State:
//   window.ACTIVE_YEAR       population projection year (the panel URLs)
//   window.CLIMATE_PATHWAY   Ld | Ln | Hd | Hn (weather/calculations/climate.py::PATHWAYS)
//   window.CLIMATE_HEAT      heat day (climate.HEAT_MODES)
//   window.CLIMATE_SCENARIO  derived: "<year>_<pathway>" for a decade of
//                            climate.SCENARIO_YEARS (2030-2100; 2050 and 2100
//                            published, the others interpolated), else "current"
const CLIMATE_HORIZONS = [2030, 2040, 2050, 2060, 2070, 2080, 2090, 2100];
const CLIMATE_PUBLISHED = [2050, 2100];   // KNMI'23 horizons; other decades are interpolated
const POPULATION_PROJECTION_END = 2050;   // CBS projection; later years are a trend extrapolation
const DEFAULT_PATHWAY = 'Hd';             // the heat and drought stress case (climate.KEA_PRESETS)

const yearPicker = document.getElementById('year-picker');
const PICKER_YEARS = yearPicker
  ? yearPicker.dataset.years.split(',').map(Number) : [];
const timeChip = document.getElementById('time-chip');
const timeMenu = document.getElementById('time-menu');

window.CLIMATE_PATHWAY = window.CLIMATE_PATHWAY || DEFAULT_PATHWAY;

function pathwayLabel(code) {
  return document.querySelector(`.time-pathway[data-pathway="${code}"]`)?.textContent.trim() || code;
}

function heatLabel(mode) {
  return document.querySelector(`#time-heat option[value="${mode}"]`)?.textContent.trim() || mode;
}

function climateKey(year, pathway) {
  return CLIMATE_HORIZONS.includes(year) ? `${year}_${pathway}` : 'current';
}

function scenariosPanelOpen() {
  return !!document.querySelector('#panel-body #climate-panel') &&
    document.getElementById('side-panel')?.classList.contains('visible');
}

/**
 * Change the year, pathway and/or heat day (omitted parts stay). Updates the
 * chip and menu, the panel URLs, the population dock and the open panel
 * (the Scenarios panel re-renders for the new scenario). refreshPanel: false
 * when the caller is the open panel itself.
 */
function setTime({ year, pathway, heat } = {}, { refreshPanel = true } = {}) {
  const y = year != null ? parseInt(year) : window.ACTIVE_YEAR;
  const p = pathway || window.CLIMATE_PATHWAY;
  const h = heat || window.CLIMATE_HEAT || 'average';
  const key = climateKey(y, p);
  const yearChanged = y !== window.ACTIVE_YEAR;
  const climateChanged = key !== (window.CLIMATE_SCENARIO || 'current') || h !== (window.CLIMATE_HEAT || 'average');

  window.ACTIVE_YEAR = y;
  window.CLIMATE_PATHWAY = p;
  window.CLIMATE_HEAT = h;
  window.CLIMATE_SCENARIO = key;
  renderTime();
  if (!yearChanged && !climateChanged) return;

  // A what-if year or climate is Plan (Modes.js): Explore shows the baseline only
  if (window.MAP_MODE === 'explore' && !isBaselineTime()) setMapMode('plan');
  if (typeof renderModeBanner === 'function') renderModeBanner();

  syncPanelBtns();
  if (climateChanged) {
    // Tools that follow the scenario (SolweigTool.js) listen to this
    window.dispatchEvent(new CustomEvent('crosstwin:climate-changed', { detail: { key, heat: h } }));
  }
  if (yearChanged && typeof loadPopulationPanel === 'function') loadPopulationPanel();   // no-op unless the dock is open
  if (!refreshPanel) return;
  if (scenariosPanelOpen()) showScenarios();
  else refreshActivePanel();
}
window.setTime = setTime;

// What a year means for the panels: population source and climate.
function yearStatus(year) {
  const population = year <= PICKER_YEARS[0] ? 'Current population'
    : year <= POPULATION_PROJECTION_END ? 'CBS projection' : 'Population trend';
  if (!CLIMATE_HORIZONS.includes(year)) return `${population}, current climate`;
  const kind = CLIMATE_PUBLISHED.includes(year) ? "KNMI'23" : "KNMI'23 interpolated";
  return `${population}, ${kind} ${pathwayLabel(window.CLIMATE_PATHWAY).toLowerCase()}`;
}

// The chip's second line: "Current climate" or "High, dry" (+ the heat day
// when it is not the observed season).
function climateChipLabel() {
  if ((window.CLIMATE_SCENARIO || 'current') === 'current') return 'Current climate';
  const heat = window.CLIMATE_HEAT || 'average';
  const label = pathwayLabel(window.CLIMATE_PATHWAY);
  if (heat === 'average') return label;
  return `${label}, ${heat === 'warmest' ? 'warmest day' : heatLabel(heat).toLowerCase()}`;
}

/** Chip, year picker, pathway buttons and heat select from the state. */
function renderTime() {
  const year = window.ACTIVE_YEAR || PICKER_YEARS[0];
  const scenario = (window.CLIMATE_SCENARIO || 'current') !== 'current';
  document.getElementById('time-chip-year').textContent = String(year);
  document.getElementById('time-chip-climate').textContent = climateChipLabel();
  timeChip?.classList.toggle('is-scenario', scenario);
  // Edit mode works on the stored baseline: no year or scenario what-ifs
  if (timeChip) {
    const locked = window.MAP_MODE === 'edit';
    timeChip.disabled = locked;
    timeChip.title = locked ? 'Year and climate are fixed to today in Edit mode' : 'Year and climate scenario';
    if (locked && timeMenu) setTimeMenuOpen(false);
  }
  showYearInPicker(year);
  document.querySelectorAll('.time-pathway').forEach(btn => {
    btn.setAttribute('aria-pressed', String(btn.dataset.pathway === window.CLIMATE_PATHWAY));
    btn.disabled = !CLIMATE_HORIZONS.includes(year);
  });
  document.getElementById('time-pathway-hint').hidden = CLIMATE_HORIZONS.includes(year);
  const heat = document.getElementById('time-heat');
  if (heat) {
    heat.value = window.CLIMATE_HEAT || 'average';
    heat.disabled = !scenario;
  }
}

// Moves the slider and readout to `year` without applying it.
function showYearInPicker(year) {
  if (!yearPicker) return;
  const index = PICKER_YEARS.indexOf(year);
  const slider = document.getElementById('year-slider');
  if (index >= 0) {
    slider.value = String(index);
    slider.setAttribute('aria-valuetext', String(year));
  }
  document.getElementById('year-value').textContent = String(year);
  document.getElementById('year-status').textContent = yearStatus(year);
  yearPicker.classList.toggle('is-future', year > PICKER_YEARS[0]);
}

function initYearPicker() {
  if (!yearPicker) return;
  const slider = document.getElementById('year-slider');
  slider.max = String(PICKER_YEARS.length - 1);
  const ticks = document.getElementById('year-ticks');
  const last = PICKER_YEARS.length - 1;
  yearPicker.dataset.ticks.split(',').map(Number).forEach(year => {
    const tick = document.createElement('span');
    tick.textContent = String(year);
    tick.style.left = `${PICKER_YEARS.indexOf(year) / last * 100}%`;
    ticks.appendChild(tick);
  });
  // Dragging previews; releasing (or a key press, which fires change) applies.
  slider.addEventListener('input', () => {
    const year = PICKER_YEARS[parseInt(slider.value)];
    document.getElementById('year-value').textContent = String(year);
    document.getElementById('year-status').textContent = yearStatus(year);
  });
  slider.addEventListener('change', () => setTime({ year: PICKER_YEARS[parseInt(slider.value)] }));
  yearPicker.querySelectorAll('.year-step').forEach(btn => btn.addEventListener('click', () => {
    const index = PICKER_YEARS.indexOf(window.ACTIVE_YEAR) + parseInt(btn.dataset.step);
    if (index >= 0 && index <= last) setTime({ year: PICKER_YEARS[index] });
  }));
}

// ── Time menu: drops down from the chip ──────────────────────────────────
function positionTimeMenu() {
  const wrap = timeMenu.offsetParent;   // .map-wrapper; null while hidden
  if (!wrap) return;
  const w = wrap.getBoundingClientRect();
  const c = timeChip.getBoundingClientRect();
  const left = c.left + c.width / 2 - w.left - timeMenu.offsetWidth / 2;
  timeMenu.style.left = `${Math.max(8, Math.min(left, wrap.clientWidth - timeMenu.offsetWidth - 8))}px`;
  timeMenu.style.top = `${c.bottom - w.top + 8}px`;
}

function setTimeMenuOpen(open) {
  timeMenu.classList.toggle('visible', open);
  timeChip.classList.toggle('active', open);
  timeChip.setAttribute('aria-expanded', String(open));
  if (open) positionTimeMenu();
}

if (timeChip && timeMenu) {
  timeChip.addEventListener('click', () => setTimeMenuOpen(!timeMenu.classList.contains('visible')));
  document.addEventListener('click', (evt) => {
    if (!timeMenu.contains(evt.target) && !timeChip.contains(evt.target)) setTimeMenuOpen(false);
  });
  document.addEventListener('keydown', (evt) => {
    if (evt.key === 'Escape' && timeMenu.classList.contains('visible')) {
      setTimeMenuOpen(false);
      timeChip.focus();
    }
  });
  window.addEventListener('resize', positionTimeMenu);
  if (typeof ResizeObserver !== 'undefined') new ResizeObserver(positionTimeMenu).observe(timeChip);

  document.querySelectorAll('.time-pathway').forEach(btn =>
    btn.addEventListener('click', () => setTime({ pathway: btn.dataset.pathway })));
  document.getElementById('time-heat')?.addEventListener('change', (evt) =>
    setTime({ heat: evt.target.value }));
  document.getElementById('time-compare')?.addEventListener('click', () => {
    setTimeMenuOpen(false);
    setMapMode('plan');   // scenarios are a what-if (Modes.js)
    showScenarios();
  });
}

initYearPicker();
renderTime();



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
    // Panel refreshes sent with htmx.ajax (admin-unit clicks, year changes)
    // have no source element: fall back to the active topic's title.
    // htmx.ajax's `source` arrives as requestConfig.elt (detail.elt is then the target).
    const title = evt.detail.elt?.dataset?.panelTitle
      || evt.detail.requestConfig?.elt?.dataset?.panelTitle
      || document.querySelector('#toolbar .tool-button.active')?.dataset?.panelTitle
      || 'Info';
    // 'visible' is the class the CSS shows the panel with (there is no rule for
    // 'open'). Lenses with a panel URL (e.g. Housing) don't get it from the
    // rail click handler, so the swap shows the panel.
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

// Registry of rail panels driven by the selected administrative unit
// (level/location[/year]): every lens with a `panel` URL builder in
// Config.js::LENSES. Give a new indicator panel's lens a `panel` there —
// syncPanelBtns/refreshActivePanel then handle it automatically, no other
// changes needed in Map_init.js.
const ADMIN_PANEL_TOOLS = Object.fromEntries(
  Object.entries(LENSES).filter(([, lens]) => lens.panel).map(([id, lens]) => [id, lens.panel]));

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
// omit it to no-op when the open panel isn't admin-unit-driven. The fallback
// applies under Overview only: a lens without an indicator panel (Population,
// Energy, ...) keeps its own panel when a unit is clicked.
function refreshActivePanel(fallbackTool = null) {
  // Panning or a click on a neighbourhood must not replace the edit form
  if (typeof isEditing === 'function' && isEditing()) return;
  const tool = findActiveAdminTool() || (LENSES[activeTool] ? null : fallbackTool);
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
