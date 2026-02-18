// ============================================================
// events.js — All UI event handlers
// Depends on: config.js, layers.js, panels.js, map-init.js
// ============================================================

/**
 * Initialize all UI interactions (called once from initializeUrbanTwinMap)
 */
function initializeUI() {
  const toolbar    = document.getElementById('toolbar');
  const sidePanel  = document.getElementById('side-panel');
  const layersPanel = document.getElementById('layers-panel');
  const panelTitle = document.getElementById('panel-title');
  const panelBody  = document.getElementById('panel-body');
  const hint       = document.getElementById('onboarding-hint');

  // ---- Toolbar clicks ---------------------------------------------------
  toolbar?.addEventListener('click', (evt) => {
    const btn = evt.target.closest('.tool-button');
    if (!btn) return;

    const tool = btn.dataset.tool;

    toolbar.querySelectorAll('.tool-button').forEach(b =>
      b.classList.toggle('active', b === btn)
    );

    if (hint) hint.remove();

    // Basemap switch
    changeBasemap(tool === 'satellite' ? 'satellite' : 'light');

    // Groundwater WMS toggle
    if (tool === 'groundwater') toggleGroundwaterLayer();

    // Filter & activate layers for the tool
    filterLayersByTool(tool);
    if (tool !== 'overview' && tool !== 'layers' && tool !== 'satellite') {
      activateToolLayers(tool);
    }

    layersPanel?.classList.add('visible');

    // Side panel info
    const content = TOOL_CONTENT[tool];
    if (content && panelTitle && panelBody) {
      panelTitle.textContent = content.title;
      panelBody.innerHTML = content.body;
      sidePanel?.classList.add('visible');
    }
  });

  // ---- Panel close buttons ----------------------------------------------
  document.getElementById('panel-close')?.addEventListener('click', () => {
    sidePanel?.classList.remove('visible');
  });

  document.getElementById('layers-panel-close')?.addEventListener('click', () => {
    layersPanel?.classList.remove('visible');
  });

  // ---- Camera controls --------------------------------------------------
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

  // ---- Layer bulk controls ----------------------------------------------
  document.getElementById('btn-select-all')?.addEventListener('click', selectAllLayers);
  document.getElementById('btn-select-none')?.addEventListener('click', selectNoLayers);
  document.getElementById('btn-fit-all')?.addEventListener('click', zoomToAllVisible);

  // ---- Basemap dropdown -------------------------------------------------
  document.getElementById('basemap-select')?.addEventListener('change', (e) => {
    changeBasemap(e.target.value);
  });

  // ---- Dashboard & Scenarios buttons ------------------------------------
  document.getElementById('btn-dashboard')?.addEventListener('click', showDashboard);
  document.getElementById('btn-scenarios')?.addEventListener('click', showScenarios);

  // ---- Indicator pills --------------------------------------------------
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