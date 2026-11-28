// ============================================================
// housing_panel.js — Housing indicators: persons-per-home-slider zone
// styling and gauge/bar animation, for housing/partials/
// indicators_panel.html (htmx side-panel partial). There is no
// standalone housing page equivalent to water_page.js/heat.js —
// housing_indicators.html just includes this same partial directly.
// Wrapped in an IIFE with a guarded htmx listener so it's safe to
// re-run every time htmx swaps the panel back in.
// ============================================================
(function () {  // ← IIFE wrapper — all vars are local, no redeclaration

  // Persons per home: the NL average is ~2.1; the track is split in thirds (1-2, 2-3, 3-4).
  function zoneStyle(val) {
    if (val < 2)      return { col: '#f59e0b', label: 'Small households', cls: 'warn' };
    else if (val < 3) return { col: '#22c55e', label: 'Typical',          cls: 'ok'   };
    else              return { col: '#f59e0b', label: 'Large households', cls: 'warn' };
  }

  function applyZone(val) {
    const z    = zoneStyle(val);
    const sl   = document.getElementById('household-size-slider');
    const tag  = document.getElementById('zone-tag');
    const disp = document.getElementById('slider-display');
    if (disp) disp.textContent = val.toFixed(2);
    if (sl)   sl.style.setProperty('--thumb-col', z.col);
    if (tag)  { tag.textContent = z.label; tag.className = 'threshold-tag ' + z.cls; }
  }

  const slider = document.getElementById('household-size-slider');
  if (slider) {
    applyZone(parseFloat(slider.value));
    slider.addEventListener('input', e => applyZone(parseFloat(e.target.value)));
  }

  // Residents-living-alone slider: live value read-out (the grid is recalculated by htmx)
  const lonely = document.getElementById('alone-slider');
  if (lonely) {
    const show = v => {
      const el = document.getElementById('alone-display');
      if (el) el.textContent = v.toFixed(1);
    };
    lonely.addEventListener('input', e => show(parseFloat(e.target.value)));
  }

  // House Price Index year = the scenario year: dragging previews it, releasing sets it for the whole map
  // (setTime reloads the open panel, so the chart window and the modelled prices follow). A scenario change
  // re-renders this card with the new year, which moves the slider. Standalone page: opens that year's URL.
  (function () {
    const el = document.getElementById('hpi-year-slider');
    if (!el) return;
    const show = () => {
      const d = document.getElementById('hpi-year-display');
      if (d) d.textContent = el.value;
    };
    el.addEventListener('input', show);
    el.addEventListener('change', () => {
      const year = parseInt(el.value, 10);
      if (typeof window.setTime === 'function') window.setTime({ year });
      else window.location.href = el.dataset.urlTemplate.replace('9999', String(year));
    });
    show();
  })();

  // House Price Index long-run growth what-if (never written): live read-out; the grid is recalculated by htmx.
  (function () {
    const el = document.getElementById('hpi-long-run-slider');
    if (!el) return;
    const show = () => {
      const d = document.getElementById('hpi-long-run-display');
      const v = parseFloat(el.value);
      if (d && !isNaN(v)) d.textContent = v.toFixed(2);
    };
    el.addEventListener('input', show);
    show();
  })();

  // Mortgage-rate what-if (never written): live read-out; the slider starts at the historical rate of the year.
  (function () {
    const el = document.getElementById('mortgage-rate-slider');
    if (!el) return;
    const show = () => {
      const d = document.getElementById('mortgage-rate-display');
      const v = parseFloat(el.value);
      if (d && !isNaN(v)) d.textContent = v.toFixed(2);
    };
    el.addEventListener('input', show);
    show();
  })();

  // Recalculate the indicator grid, so the modelled-price card shows what was just written.
  function refreshCard() {
    if (!window.htmx) return;
    const slider = document.getElementById('household-size-slider') || document.getElementById('alone-slider');
    if (slider) { window.htmx.trigger(slider, 'input'); return; }
    // no slider of the input kind: any enabled what-if slider of the grid recalculates it on 'change'
    const other = document.querySelector('#indicators-grid input[hx-get]:not([disabled])');
    if (other) window.htmx.trigger(other, 'change');
  }

  // Staff buttons of the modelled-price card (fit / reprice). The card is swapped by htmx, so the
  // handler is delegated once on the body.
  if (!window._housingPriceModelListenerAttached) {
    document.body.addEventListener('click', function (evt) {
      const btn = evt.target.closest('[data-price-model-url]');
      if (!btn) return;
      const card = btn.closest('#modelled-price-card');
      const status = card && card.querySelector('.pm-status');
      const token = (document.cookie.match(/(?:^|; )csrftoken=([^;]*)/) || [])[1] || '';
      card.querySelectorAll('.pm-btn').forEach(b => { b.disabled = true; });
      if (status) status.textContent = 'Working…';
      const body = new URLSearchParams();
      if (btn.dataset.priceModelMode) body.set('mode', btn.dataset.priceModelMode);
      fetch(btn.dataset.priceModelUrl, { method: 'POST', body, headers: { 'X-CSRFToken': decodeURIComponent(token) } })
        .then(r => r.json().then(data => ({ ok: r.ok, data })))
        .then(({ ok, data }) => {
          if (!ok) throw new Error(data.error || 'Failed');
          if (data.message) { if (status) status.textContent = data.message; return; }
          if (status) status.textContent = data.exploratory
            ? 'Exploratory fit ' + data.id + ' stored (n = ' + data.n + ', ' + data.terms_kept + ' of ' + data.terms_candidates + ' terms, Moran p ' + data.morans_p.toFixed(3) + '): not applied, not interpretable.'
            : 'Model ' + data.id + ' (' + data.terms_kept + ' of ' + data.terms_candidates + ' amenity terms kept): ' + data.repriced + ' dwellings repriced.';
          refreshCard();
        })
        .catch(err => { if (status) status.textContent = err.message; })
        .finally(() => { card.querySelectorAll('.pm-btn').forEach(b => { b.disabled = false; }); });
    });
    window._housingPriceModelListenerAttached = true;
  }

  // "Add amenity": switch the map to Edit mode, make the amenity layer editable (staff) and open the new-object
  // form, where the amenity is placed on the map. Saving it recomputes the accessibility around it and the
  // modelled prices inside the same request (builtup/signals.py -> housing/signals.py); the card then refreshes.
  if (!window._housingAddAmenityListenerAttached) {
    document.body.addEventListener('click', function (evt) {
      const btn = evt.target.closest('[data-add-amenity]');
      if (!btn) return;
      const card = btn.closest('#modelled-price-card');
      const status = card && card.querySelector('.pm-status');
      const say = text => { if (status) status.textContent = text; };
      if (typeof setMapMode !== 'function' || typeof startCreate !== 'function') {
        say('Open the map to place an amenity.');
        return;
      }
      const key = btn.dataset.addAmenity;
      const token = (document.cookie.match(/(?:^|; )csrftoken=([^;]*)/) || [])[1] || '';
      fetch('/api/settings/editable/', {
        method: 'POST', body: new URLSearchParams({ key, enabled: 'on' }),
        headers: { 'X-CSRFToken': decodeURIComponent(token) },
      })
        .then(r => {
          if (!r.ok || !r.headers.get('HX-Trigger')) throw new Error('Log in as a staff user to add amenities.');
          setMapMode('edit');
          startCreate(key);
          say('Pick the type, place the amenity on the map and save.');
        })
        .catch(err => say(err.message));
    });
    document.body.addEventListener('feature-saved', function (evt) {
      const layer = evt.detail && evt.detail.layer;
      if (layer === 'builtup.Facility' || layer === 'builtup.Building') refreshCard();
    });
    window._housingAddAmenityListenerAttached = true;
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
