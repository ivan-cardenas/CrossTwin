// Fills the rail of plain range sliders from the left up to the thumb (CSS var --fill, in %).
(function () {
  function paint(el) {
    const min = parseFloat(el.min || 0), max = parseFloat(el.max || 100), v = parseFloat(el.value || 0);
    const pct = max > min ? Math.min(100, Math.max(0, ((v - min) / (max - min)) * 100)) : 0;
    el.style.setProperty('--fill', pct + '%');
  }
  function paintAll(root) {
    (root || document).querySelectorAll('input[type="range"].zone-slider').forEach(paint);
  }
  if (!window.__sliderFillBound) {
    window.__sliderFillBound = true;
    document.addEventListener('input', e => { if (e.target.matches?.('input[type="range"].zone-slider')) paint(e.target); });
    document.body.addEventListener('htmx:afterSwap', () => paintAll());
    document.body.addEventListener('htmx:afterSettle', () => paintAll());
  }
  window.paintSliderFill = paintAll;
  paintAll();
})();
