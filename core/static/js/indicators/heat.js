// ============================================================
// heat.js — Urban Heat indicators: vegetation-slider zone styling and
// gauge animation. Shared by heat_indicators.html (standalone page) and
// urban_heat/partials/indicators_panel.html (htmx side-panel partial) —
// both render the same slider/gauge ids and identical thresholds, so one
// file covers both. Wrapped in an IIFE with a guarded htmx listener so
// it's safe to re-run every time htmx swaps the panel back in.
// ============================================================
(function () {

  function zoneStyle(val) {
    if (val >= 30)      return { col: '#22c55e', label: 'Good',     cls: 'ok'   };
    else if (val >= 15) return { col: '#f59e0b', label: 'Moderate', cls: 'warn' };
    else                return { col: '#ef4444', label: 'Low',      cls: 'bad'  };
  }

  function applyZone(val) {
    const z    = zoneStyle(val);
    const sl   = document.getElementById('vegetation-slider');
    const tag  = document.getElementById('zone-tag');
    const disp = document.getElementById('slider-display');
    if (disp) disp.textContent = val;
    if (sl)   sl.style.setProperty('--thumb-col', z.col);
    if (tag)  { tag.textContent = z.label; tag.className = 'threshold-tag ' + z.cls; }
  }

  const slider = document.getElementById('vegetation-slider');
  if (slider) {
    applyZone(parseFloat(slider.value));
    slider.addEventListener('input', e => applyZone(parseFloat(e.target.value)));
  }

  // initGauges needs to be global so htmx:afterSwap (and the grid
  // partial's own trailing script) can call it after every recalculation.
  window.initGauges = function () {
    document.querySelectorAll('[data-gauge-id]').forEach(card => {
      const val     = parseFloat(card.dataset.gaugeVal) || 0;
      const id      = card.dataset.gaugeId;
      const display = card.dataset.gaugeDisplay || '';
      const path    = document.getElementById(id);
      const txt     = document.getElementById(id + '-txt');
      if (!path) return;

      if (id === 'gauge-svf') {
        // Full ring gauge (SVF is 0-100%)
        const circ   = 238.76;
        const capped = Math.min(val, 100);
        let col;
        if      (val > 70) col = '#2E6478';
        else if (val > 40) col = '#f59e0b';
        else               col = '#ef4444';
        path.setAttribute('stroke', col);
        requestAnimationFrame(() => {
          path.style.strokeDashoffset = circ - (circ * capped / 100);
        });
        if (txt) txt.textContent = display;
      } else {
        // Semicircle gauges (LST, PET, UTCI, WBGT)
        const total  = 157.08;
        const capped = Math.min(val, 100);
        // Color by thermal stress
        let col;
        if      (val > 75) col = '#ff5252';
        else if (val > 50) col = '#ef4444';
        else if (val > 30) col = '#f59e0b';
        else               col = '#22c55e';
        path.setAttribute('stroke', col);
        requestAnimationFrame(() => {
          path.style.strokeDashoffset = total - (total * capped / 100);
        });
        if (txt) txt.textContent = display ? display + '°' : '–';
      }
    });
  };

  // Run on first load / panel open
  window.initGauges();

  // Re-run after every HTMX swap targeting #indicators-grid. Guarded so
  // re-running this script (e.g. the panel partial swapped back in) never
  // attaches a second listener.
  if (!window._heatGaugeListenerAttached) {
    document.body.addEventListener('htmx:afterSwap', function (evt) {
      if (evt.detail.target.id === 'indicators-grid') window.initGauges();
    });
    window._heatGaugeListenerAttached = true;
  }

})();
