// ============================================================
// water.js — Water Supply indicators: consumption-slider zone styling
// and gauge/pip animation. Shared by water_indicators.html (standalone
// page) and watersupply/partials/indicators_panel.html (htmx side-panel
// partial) — both render the same slider/gauge ids. Wrapped in an IIFE
// with a guarded htmx listener so it's safe to re-run every time htmx
// swaps the panel back in.
// ============================================================
(function () {

  function zoneStyle(val) {
    if (val < 150)      return { col: '#22c55e', label: 'Optimal',  cls: 'ok'   };
    else if (val < 250) return { col: '#f59e0b', label: 'Elevated', cls: 'warn' };
    else                return { col: '#ef4444', label: 'Excess',   cls: 'bad'  };
  }

  function applyZone(val) {
    const z    = zoneStyle(val);
    const sl   = document.getElementById('consumption-slider');
    const tag  = document.getElementById('zone-tag');
    const disp = document.getElementById('slider-display');
    if (disp) disp.textContent = val;
    if (sl)   sl.style.setProperty('--thumb-col', z.col);
    if (tag)  { tag.textContent = z.label; tag.className = 'threshold-tag ' + z.cls; }
  }

  const slider = document.getElementById('consumption-slider');
  if (slider) {
    applyZone(parseInt(slider.value, 10));
    slider.addEventListener('input', e => applyZone(parseInt(e.target.value, 10)));
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

      if (id === 'gauge-supply' || id === 'gauge-demand') {
        const total  = 157.08;
        const capped = Math.min(val, 100);
        requestAnimationFrame(() => {
          path.style.strokeDashoffset = total - (total * capped / 100);
        });
        if (txt) txt.textContent = display;

      } else if (id === 'gauge-sec') {
        const circ   = 238.76;
        const MAX    = 200;
        const capped = Math.min(val, MAX);
        let col;
        if      (val > 110) col = '#00e57a';
        else if (val >= 80) col = '#f59e0b';
        else if (val >= 50) col = '#ef4444';
        else                col = '#ff5252';
        path.setAttribute('stroke', col);
        requestAnimationFrame(() => {
          path.style.strokeDashoffset = circ - (circ * capped / MAX);
        });
        if (txt) txt.textContent = Math.round(val) + '%';
        const sub   = document.getElementById('gauge-sec-sub');
        const badge = document.getElementById('gauge-sec-badge');
        if (val > 110) {
          if (sub)   sub.textContent = '% surplus';
          if (badge) { badge.style.display = 'block'; badge.style.color = col; }
        } else {
          if (sub)   sub.textContent = '% covered';
          if (badge) badge.style.display = 'none';
        }
      }
    });

    // Pip dots — Service Time
    document.querySelectorAll('[data-pip-id]').forEach(card => {
      const val  = parseFloat(card.dataset.pipVal) || 0;
      const id   = card.dataset.pipId;
      const wrap = document.getElementById(id);
      if (!wrap) return;
      const pips   = wrap.querySelectorAll('.pip');
      const filled = Math.round(val / 100 * pips.length);
      // reset first (important after HTMX swap re-adds existing pips)
      pips.forEach(p => p.classList.remove('on'));
      pips.forEach((p, i) => {
        if (i < filled) setTimeout(() => p.classList.add('on'), i * 60);
      });
    });
  };

  // Run on first load
  window.initGauges();

  // Re-run after every HTMX swap targeting #indicators-grid. Guarded so
  // re-running this script (e.g. the panel partial swapped back in) never
  // attaches a second listener.
  if (!window._waterGaugeListenerAttached) {
    document.body.addEventListener('htmx:afterSwap', function (evt) {
      if (evt.detail.target.id === 'indicators-grid') window.initGauges();
    });
    window._waterGaugeListenerAttached = true;
  }

})();
