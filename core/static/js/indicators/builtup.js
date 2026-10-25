// ============================================================
// builtup.js — Built-up indicators: park-area slider display and
// gauge animation. Shared by builtup_indicators.html (standalone page)
// and builtup/partials/indicators_panel.html (htmx side-panel partial),
// which render the same slider/gauge ids. Wrapped in an IIFE with a
// guarded htmx listener so it's safe to re-run every time htmx swaps the
// panel back in.
// ============================================================
(function () {

  const slider = document.getElementById('green-added-slider');
  if (slider) {
    const disp = document.getElementById('green-slider-display');
    const show = () => { if (disp) disp.textContent = slider.value; };
    show();
    slider.addEventListener('input', show);
  }

  function animate(path, total, fraction) {
    requestAnimationFrame(() => {
      path.style.strokeDashoffset = total - total * Math.max(0, Math.min(fraction, 1));
    });
  }

  // Global so htmx:afterSwap can call it after every recalculation
  window.initGauges = function () {
    // Built-up coverage — semicircle, 0–50 % (beyond half the area is
    // covered by footprints only in dense city centres)
    const cov = document.querySelector('[data-gauge-id="gauge-built-coverage"]');
    const covPath = document.getElementById('gauge-built-coverage');
    if (cov && covPath) {
      const val = parseFloat(cov.dataset.gaugeVal) || 0;
      animate(covPath, 157.08, val / 50);
      const txt = document.getElementById('gauge-built-coverage-txt');
      if (txt) txt.textContent = val.toFixed(1) + '%';
    }

    // Park area per inhabitant — ring, full at the WHO ideal, in the Park
    // layer's colour; the WHO status (below minimum / ideal) is on the tag
    const green = document.querySelector('[data-gauge-id="gauge-green"]');
    const greenPath = document.getElementById('gauge-green');
    if (green && greenPath) {
      const val = parseFloat(green.dataset.gaugeVal) || 0;
      const max = parseFloat(green.dataset.gaugeMax) || 50;
      if (green.dataset.gaugeColor) greenPath.setAttribute('stroke', green.dataset.gaugeColor);
      animate(greenPath, 238.76, val / max);
      const txt = document.getElementById('gauge-green-txt');
      if (txt) txt.textContent = val ? val.toFixed(1) : '–';
    }
  };

  window.initGauges();

  if (!window._builtupGaugeListenerAttached) {
    document.body.addEventListener('htmx:afterSwap', function (evt) {
      if (evt.detail.target.id === 'indicators-grid') window.initGauges();
    });
    window._builtupGaugeListenerAttached = true;
  }

})();
