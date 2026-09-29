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
  const dashboardBtn = document.getElementById('btn-dashboard');
  dashboardBtn?.addEventListener('click', toggleDashboard);
  document.getElementById('btn-scenarios')?.addEventListener('click', showScenarios);

  // Keep the Dashboard button's "active" state equal to "side panel is open",
  // whichever control opened or closed it (✕, layer pills, toolbar, htmx swap).
  if (sidePanel && dashboardBtn) {
    const syncDashboardBtn = () =>
      dashboardBtn.classList.toggle('active', sidePanel.classList.contains('visible'));
    new MutationObserver(syncDashboardBtn)
      .observe(sidePanel, { attributes: true, attributeFilter: ['class'] });
    syncDashboardBtn();
  }

  // ---- Population dock --------------------------------------------------
  const populationPanel = document.getElementById('population-panel');
  const populationPill = document.querySelector('.indicator-pill[data-indicator="population"]');
  document.getElementById('population-panel-close')?.addEventListener('click', () => {
    populationPanel?.classList.remove('visible');
  });
  if (populationPanel && populationPill) {
    const syncPopulationPill = () =>
      populationPill.classList.toggle('active', populationPanel.classList.contains('visible'));
    new MutationObserver(syncPopulationPill)
      .observe(populationPanel, { attributes: true, attributeFilter: ['class'] });
    syncPopulationPill();
  }

  // ---- Indicator pills --------------------------------------------------
  document.querySelectorAll('.indicator-pill').forEach(pill => {
    pill.addEventListener('click', () => {
      const type = pill.dataset.indicator;
      if (type === 'layers' || type === 'visible') {
        layersPanel?.classList.toggle('visible');
        sidePanel?.classList.remove('visible');
      }
      // The population dock is independent of the side panel: an indicator
      // panel stays open while it is shown.
      if (type === 'population') togglePopulationPanel();
    });
  });

  // ---- Legend stack repositioning ---------------------------------------
  // The legend stack (bottom-right) must dodge the side panel and the
  // population dock whenever either opens/closes, resizes, or the window
  // resizes — not just when a legend itself is added/removed (Layers.js
  // already calls repositionDynamicLegends() for that).
  if (typeof repositionDynamicLegends === 'function') {
    const populationPanel = document.getElementById('population-panel');
    [sidePanel, populationPanel].filter(Boolean).forEach(panel => {
      new MutationObserver(repositionDynamicLegends)
        .observe(panel, { attributes: true, attributeFilter: ['class'] });
      if (typeof ResizeObserver !== 'undefined') {
        new ResizeObserver(repositionDynamicLegends).observe(panel);
      }
    });
    window.addEventListener('resize', repositionDynamicLegends);
  }

  // ---- Draggable overlays ------------------------------------------------
  // Skip on the mobile breakpoint, where panels already reflow into a fixed
  // stacked layout (see mainMap.css's max-width: 768px rules).
  if (typeof makeDraggable === 'function' && window.matchMedia('(min-width: 769px)').matches) {
    const populationPanel = document.getElementById('population-panel');
    const demoTour = document.getElementById('demo-tour');
    const legendStack = document.getElementById('legend-stack');

    makeDraggable(layersPanel, '.layers-panel-header');
    makeDraggable(sidePanel, '.side-panel-header');
    makeDraggable(populationPanel, '.population-panel-header');
    makeDraggable(toolbar, '.toolbar-grip');
    makeDraggable(demoTour, '.tour-step-badge');
    makeDraggable(legendStack, '.legend-title', {
      onReset: () => { if (typeof repositionDynamicLegends === 'function') repositionDynamicLegends(); },
    });
  }
}

