// ============================================================
// housing_panel.js — Housing indicators: mortgage-rate-slider zone
// styling and gauge/bar animation, for housing/partials/
// indicators_panel.html (htmx side-panel partial). There is no
// standalone housing page equivalent to water_page.js/heat.js —
// housing_indicators.html just includes this same partial directly.
// Wrapped in an IIFE with a guarded htmx listener so it's safe to
// re-run every time htmx swaps the panel back in.
// ============================================================
(function () {  // ← IIFE wrapper — all vars are local, no redeclaration

  function zoneStyle(val) {
    if (val < 4)      return { col: '#22c55e', label: 'Favorable', cls: 'ok'   };
    else if (val < 8) return { col: '#f59e0b', label: 'Elevated',  cls: 'warn' };
    else              return { col: '#ef4444', label: 'High',      cls: 'bad'  };
  }

  function applyZone(val) {
    const z    = zoneStyle(val);
    const sl   = document.getElementById('mortgage-rate-slider');
    const tag  = document.getElementById('zone-tag');
    const disp = document.getElementById('slider-display');
    if (disp) disp.textContent = val;
    if (sl)   sl.style.setProperty('--thumb-col', z.col);
    if (tag)  { tag.textContent = z.label; tag.className = 'threshold-tag ' + z.cls; }
  }

  const slider = document.getElementById('mortgage-rate-slider');
  if (slider) {
    applyZone(parseFloat(slider.value));
    slider.addEventListener('input', e => applyZone(parseFloat(e.target.value)));
  }

  // initGauges needs to be global so htmx:afterSwap can call it
  window.initGauges = function() {
    document.querySelectorAll('[data-gauge-id]').forEach(card => {
      const val     = parseFloat(card.dataset.gaugeVal) || 0;
      const id      = card.dataset.gaugeId;
      const display = card.dataset.gaugeDisplay || '';
      const path    = document.getElementById(id);
      const txt     = document.getElementById(id + '-txt');
      if (!path) return;

      if (id === 'gauge-coverage') {
        const total  = 157.08;
        const capped = Math.min(val, 100);
        let col = '#22c55e';
        if (val < 60) col = '#ef4444'; else if (val < 90) col = '#f59e0b';
        path.setAttribute('stroke', col);
        requestAnimationFrame(() => {
          path.style.strokeDashoffset = total - (total * capped / 100);
        });
        if (txt) txt.textContent = Math.round(val) + '%';
        const displayEl = document.getElementById(id + '-txt');
        if (displayEl && display) displayEl.setAttribute('data-full', display);

      } else if (id === 'gauge-afford') {
        // Lower price-to-income multiple is better (affordable); 3 = ok, 5 = stretched, >5 = stressed
        const circ   = 238.76;
        const MAX    = 10;
        const capped = Math.min(val, MAX);
        let col;
        if      (val <= 3) col = '#22c55e';
        else if (val <= 5) col = '#f59e0b';
        else               col = '#ef4444';
        path.setAttribute('stroke', col);
        requestAnimationFrame(() => {
          path.style.strokeDashoffset = circ - (circ * capped / MAX);
        });
        if (txt) txt.textContent = val ? val.toFixed(1) : '–';
      }
    });

    // Mortgage rate bar
    const mtgCard = document.querySelector('[data-mortgage-rate]');
    const mtgBar  = document.getElementById('mortgage-rate-bar');
    if (mtgCard && mtgBar) {
      const rate = parseFloat(mtgCard.dataset.mortgageRate) || 0;
      const pct  = Math.min(rate / 10 * 100, 100);
      requestAnimationFrame(() => { mtgBar.style.width = pct + '%'; });
    }
  };

  // Run on panel load
  window.initGauges();

  // Register listener only once
  if (!window._housingGaugeListenerAttached) {
    document.body.addEventListener('htmx:afterSwap', function(evt) {
      if (evt.detail.target.id === 'indicators-grid') window.initGauges();
    });
    window._housingGaugeListenerAttached = true;
  }

})();  // ← end IIFE
