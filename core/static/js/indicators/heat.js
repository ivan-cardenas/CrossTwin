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

  // ---- Weather what-if --------------------------------------------------
  // The weather sliders start at the live (or station) weather. Only the
  // sliders the user moved are sent (data-touched): a range input snaps its
  // value to its step, so an untouched slider would otherwise report a
  // slightly different value and count as a what-if. The grid's
  // #heat-weather-state tells the map's weather pill (WeatherPill.js) what
  // is in use after every recalculation.
  const WEATHER_FIELDS = ['ta_c', 'rh_pct', 'wind_ms', 'kdown_wm2'];
  const DEFAULTS = { ta_c: 20, rh_pct: 70, wind_ms: 3, kdown_wm2: 0 };

  function weatherInputs() {
    return Array.from(document.querySelectorAll('#heat-whatif .heat-weather-input'));
  }

  function showValue(input) {
    const out = document.querySelector(`#heat-whatif output[data-for="${input.name}"]`);
    if (out) out.textContent = input.value;
  }

  function anyTouched() {
    return weatherInputs().some(i => i.dataset.touched === '1');
  }

  function syncResetButton() {
    const reset = document.getElementById('heat-weather-reset');
    if (reset) reset.hidden = !anyTouched();
  }

  window.publishHeatWeather = function () {
    const state = document.getElementById('heat-weather-state');
    if (!state) return;
    const detail = { whatif: state.dataset.whatif === '1' };
    WEATHER_FIELDS.concat(['feels']).forEach(f => {
      const v = state.dataset[f];
      detail[f] = v === '' || v === undefined ? null : parseFloat(v);
    });
    window.dispatchEvent(new CustomEvent('crosstwin:heat-weather', { detail }));
  };

  function resetWeather() {
    const controls = document.querySelector('#heat-whatif .heat-weather-controls');
    weatherInputs().forEach(input => {
      const live = controls ? controls.getAttribute('data-live-' + input.name) : null;
      input.value = live ? live : DEFAULTS[input.name];
      delete input.dataset.touched;
      showValue(input);
    });
    syncResetButton();
    // Recalculate without weather overrides (untouched sliders are dropped)
    const veg = document.getElementById('vegetation-slider');
    if (veg) htmx.trigger(veg, 'input');
  }

  weatherInputs().forEach(input => {
    input.addEventListener('input', () => {
      input.dataset.touched = '1';
      showValue(input);
      syncResetButton();
    });
  });
  document.getElementById('heat-weather-reset')?.addEventListener('click', resetWeather);
  document.getElementById('heat-whatif')?.addEventListener('submit', e => e.preventDefault());
  window.resetHeatWeather = resetWeather;

  if (!window._heatWeatherListenersAttached) {
    document.body.addEventListener('htmx:configRequest', function (evt) {
      if (!evt.detail.elt.closest || !evt.detail.elt.closest('#heat-whatif')) return;
      weatherInputs().forEach(input => {
        if (input.dataset.touched !== '1') delete evt.detail.parameters[input.name];
      });
    });
    window._heatWeatherListenersAttached = true;
  }

  // Run on first load / panel open
  window.initGauges();
  window.publishHeatWeather();

  // Re-run after every HTMX swap targeting #indicators-grid. Guarded so
  // re-running this script (e.g. the panel partial swapped back in) never
  // attaches a second listener.
  if (!window._heatGaugeListenerAttached) {
    document.body.addEventListener('htmx:afterSwap', function (evt) {
      if (evt.detail.target.id === 'indicators-grid') {
        window.initGauges();
        window.publishHeatWeather();
      }
    });
    window._heatGaugeListenerAttached = true;
  }

})();
