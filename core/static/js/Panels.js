// ============================================================
// panels.js — Dashboard & Scenario side-panel content
// Depends on: config.js
// ============================================================

/**
 * Show the city dashboard panel
 */
function showDashboard() {
  const panelTitle = document.getElementById('panel-title');
  const panelBody  = document.getElementById('panel-body');
  const sidePanel  = document.getElementById('side-panel');

  let totalFeatures = 0;
  let visibleLayers = 0;

  for (const [key, data] of Object.entries(loadedLayers)) {
    totalFeatures += data.geojson.features.length;
    if (layerVisibility[key]) visibleLayers++;
  }

  // Mini bar chart (mock monthly data)
  const monthlyData = [65, 72, 78, 85, 92, 88, 82, 76, 70, 68, 62, 60];
  const maxVal = Math.max(...monthlyData);
  const barsHTML = monthlyData.map(v => {
    const h = Math.round((v / maxVal) * 100);
    return `<div class="mini-bar" style="--h:${h}%"></div>`;
  }).join('');

  if (panelTitle) panelTitle.textContent = 'CITY DASHBOARD';
  if (panelBody) {
    panelBody.innerHTML = `
      <div class="dashboard-grid">
        <div class="kpi-card">
          <div class="kpi-header"><span>Total Layers</span><span class="kpi-dot"></span></div>
          <div class="kpi-value">${availableLayers.length}</div>
          <div class="kpi-sub">From database</div>
        </div>

        <div class="kpi-card">
          <div class="kpi-header"><span>Total Features</span><span class="kpi-dot"></span></div>
          <div class="kpi-value">${totalFeatures.toLocaleString()}</div>
          <div class="kpi-sub">Loaded on map</div>
        </div>

        <div class="gauge-card">
          <div class="gauge-ring" style="--value:${Math.round(visibleLayers / availableLayers.length * 100)};">
            <div class="gauge-center">${visibleLayers}/${availableLayers.length}</div>
          </div>
          <div class="gauge-text">
            <div class="gauge-label">Visible Layers</div>
            <div class="gauge-sub">Currently displayed</div>
          </div>
        </div>

        <div class="gauge-card">
          <div class="gauge-ring" style="--value:72;">
            <div class="gauge-center">72%</div>
          </div>
          <div class="gauge-text">
            <div class="gauge-label">Data Coverage</div>
            <div class="gauge-sub">Area with spatial data</div>
          </div>
        </div>
      </div>

      <div class="kpi-card" style="margin-top:12px;">
        <div class="kpi-header"><span>Activity Trend (12 months)</span><span class="kpi-dot"></span></div>
        <div class="mini-chart">${barsHTML}</div>
        <div class="kpi-sub" style="margin-top:6px;">Data updates and feature additions over time</div>
      </div>

      <p class="dashboard-note">
        Dashboard values are dynamically calculated from loaded layers. Some metrics are placeholders.
      </p>
    `;
  }

  sidePanel?.classList.add('visible');
  document.getElementById('layers-panel')?.classList.remove('visible');
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