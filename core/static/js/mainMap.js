// ============================================================
// mainMap.js — page-level wiring for mainMap.html: map init, right-panel
// buttons, year selector, guided tour, and the admin-unit-driven panel
// registry (ADMIN_PANEL_TOOLS / syncPanelBtns / refreshActivePanel).
// Depends on: config.js, map_init.js (and window.MAPBOX_ACCESS_TOKEN, set
// inline by mainMap.html before this file loads).
// ============================================================

// Initialize the Urban Twin map — only pass server-side values here;
// all other defaults live in Config.js
document.addEventListener("DOMContentLoaded", () => {
  initializeUrbanTwinMap({ mapboxToken: window.MAPBOX_ACCESS_TOKEN });
});


// Right panel button handlers
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

document.querySelectorAll('.year-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    // Update active state
    document.querySelectorAll('.year-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');

    window.ACTIVE_YEAR = parseInt(btn.dataset.year);

    // Update panel button URLs with new year
    syncPanelBtns();

    // If an admin-unit-driven panel is already open, reload it with new context
    refreshActivePanel();
    if (typeof loadPopulationPanel === 'function') loadPopulationPanel();   // no-op unless the dock is open
  });
});

// ── GUIDED TOUR ────────────────────────────────────────────────────────────
const TOUR_STEPS = [
  {
    num: 1,
    title: "① Select Topic",
    desc: "Start by picking a thematic domain from the left toolbar — Housing, Energy, Heat, Water Supply, and more. Each icon switches the data context for the entire platform.",
    target: ".toolbar",
  },
  {
    num: 2,
    title: "② Explore Current Data",
    desc: "Click the 📑 Administrative Data icon to open the Database Layers panel. Browse all available spatial datasets, toggle individual layers on/off, and choose a basemap style.",
    target: '[data-tool="administrative"]',
  },
  {
    num: 3,
    title: "③ Explore Indicators",
    desc: "Select a thematic tool like 🚰 Water Supply or 🌡️ Heat to load live KPI dashboards in the right panel. Indicators are calculated directly from the spatial database.",
    target: ".side-panel",
  },
  {
    num: 4,
    title: "④ Select Scenarios",
    desc: "Use the Dashboard and Scenarios buttons at the bottom-right. Adjust sliders and input overrides (e.g. consumption, interest rate) to model what-if futures and compare years.",
    target: ".bottom-right",
  },
  {
    num: 5,
    title: "⑤ Import Data",
    desc: "Upload your own GeoJSON or Shapefile with 'Upload Data', or pull live datasets from PDOK, CBS, Sentinel-2, and Google Earth Engine via 'Retrieve Data from APIs'.",
    target: ".right-actions-panel",
  },
  {
    num: 6,
    title: "⑥ Run Analysis",
    desc: "With scenario parameters set, trigger cross-domain calculations. The DPSIR causal network automatically links drivers (e.g. population growth) to urban impacts (heat, water stress).",
    target: null,
  },
  {
    num: 7,
    title: "⑦ View Results",
    desc: "Results populate the side panel as charts, KPI cards, and new map layers. Use the year buttons (2023–2030) to compare the current baseline against future scenario projections.",
    target: "#panel-body",
  },
  {
    num: 8,
    title: "⑧ Export Results",
    desc: "Download scenario outputs as GeoJSON, CSV, or raster files. Share results with stakeholders or import into external GIS tools and technical reports.",
    target: null,
  },
];

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

// Registry of toolbar panels driven by the selected administrative unit
// (level/location[/year]). Add an entry here when wiring up a new
// indicator panel (e.g. housing, energy) to admin-unit selection —
// syncPanelBtns/refreshActivePanel then handle it automatically, no other
// changes needed in Map_init.js.
const ADMIN_PANEL_TOOLS = {
  water: (level, location) =>
    `/watersupply/indicators/${level}/${location}/${window.ACTIVE_YEAR}/${populationQuery()}`,
  // Urban heat has no year and does not depend on population.
  temperature: (level, location) =>
    `/urban_heat/indicators/${level}/${location}/`,
  // Same URL shape as water: housing/urls.py is indicators/<level>/<location>/<year>/
  // (this entry used to omit <level>, so it matched nothing after a selection).
  Housing: (level, location) =>
    `/housing/indicators/${level}/${location}/${window.ACTIVE_YEAR}/${populationQuery()}`,
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
