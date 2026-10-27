// ============================================================
// SvfTool.js — Sky-view factor from the DSM for the area in view.
// Opened from the Actions menu (#svfToolBtn). Asks the server what the view
// would compute (GET physicalEnv/svf/info/: DSM, grid size, existing SVF),
// then computes and stores one SVF raster over the view only
// (POST physicalEnv/svf/calculate/) and shows it as a map layer. The button
// reads "Recalculate" when a stored SVF of the same DSM already covers the
// view; the server replaces the rows inside the new one and returns their ids.
// Depends on: Config.js (map, availableLayers, layerVisibility),
// Layers.js (addLayer, removeLayer), MapUI.js (renderLayerList), Draggable.js.
// ============================================================

(function () {
  'use strict';

  function init() {
    const card = document.getElementById('svf-card');
    const openBtn = document.getElementById('svfToolBtn');
    if (!card || !openBtn) return;

    const el = {
      close: document.getElementById('svf-card-close'),
      radius: document.getElementById('svf-radius'),
      resolution: document.getElementById('svf-resolution'),
      info: document.getElementById('svf-view-info'),
      calculate: document.getElementById('svf-calculate'),
      status: document.getElementById('svf-status'),
    };
    const canCalculate = card.dataset.canCalculate === '1';
    let busy = false;
    let ready = false;        // the last info request found a computable view
    let infoRequest = null;   // AbortController of the pending info request

    // ---- helpers ---------------------------------------------------------

    function viewBbox() {
      const b = map.getBounds();
      return [b.getWest(), b.getSouth(), b.getEast(), b.getNorth()].map(v => v.toFixed(6)).join(',');
    }

    function csrfToken() {
      return card.querySelector('[name=csrfmiddlewaretoken]')?.value || '';
    }

    function setStatus(message, kind = '') {
      el.status.textContent = message;
      el.status.className = `lst-status ${kind}`;
    }

    function refreshButton() {
      el.calculate.disabled = busy || !ready || !canCalculate;
    }

    function setBusy(on, label) {
      busy = on;
      card.classList.toggle('busy', on);
      refreshButton();
      clearInterval(setBusy.timer);
      if (on) {
        const started = Date.now();
        const tick = () => setStatus(`${label} ${Math.round((Date.now() - started) / 1000)} s`, 'working');
        tick();
        setBusy.timer = setInterval(tick, 1000);
      }
    }

    function params() {
      const p = new URLSearchParams({ bbox: viewBbox(), radius: el.radius.value });
      if (el.resolution.value) p.set('resolution', el.resolution.value);
      return p;
    }

    async function readJson(response) {
      let data = {};
      try { data = await response.json(); } catch (e) { /* non-JSON error page */ }
      if (!response.ok) throw new Error(data.error || `HTTP ${response.status}`);
      return data;
    }

    // ---- view info -------------------------------------------------------

    async function loadInfo() {
      if (busy) return;
      infoRequest?.abort();
      infoRequest = new AbortController();
      ready = false;
      refreshButton();
      el.info.textContent = 'Checking the DSM for this view…';
      try {
        const data = await readJson(await fetch(
          `${card.dataset.infoUrl}?${params()}`, { signal: infoRequest.signal }));
        const g = data.grid;
        const partial = data.coverage < 0.99 ? ` · covers ${Math.round(data.coverage * 100)} % of the view` : '';
        el.info.textContent =
          `DSM #${data.dsm.id} (${data.dsm.source || 'unknown'}, ${data.dsm.year}) · ` +
          `${g.width}×${g.height} @ ${+g.resolution.toFixed(2)} m · radius ${+data.radius_m.toFixed(1)} m${partial}`;
        const existing = data.existing[0];
        el.calculate.textContent = existing ? 'Recalculate SVF for this view' : 'Calculate SVF for this view';
        ready = true;
        if (!canCalculate) {
          setStatus('Calculating needs a staff login (Log in, top right).', 'warn');
        } else if (existing) {
          setStatus(`SVF #${existing.id} already covers this view (${existing.method}).`);
        } else {
          setStatus('');
        }
      } catch (error) {
        if (error.name === 'AbortError') return;
        el.info.textContent = '';
        el.calculate.textContent = 'Calculate SVF for this view';
        setStatus(error.message, 'error');
      }
      refreshButton();
    }

    // ---- open / close ----------------------------------------------------

    function open() {
      // Same corner as the LST card: show one at a time.
      document.getElementById('lst-card')?.classList.remove('visible');
      card.classList.add('visible');
      if (typeof setActionsMenuOpen === 'function') setActionsMenuOpen(false);
      loadInfo();
    }

    function close() {
      card.classList.remove('visible');
      infoRequest?.abort();
    }

    // ---- calculate -------------------------------------------------------

    async function showResult(data) {
      (data.replaced || []).forEach(id => {
        if (typeof removeLayer === 'function') removeLayer(`raster-urban_heat-SkyViewFactor-${id}`);
      });
      const layer = data.layer;
      if (!layer) return;
      if (!availableLayers.some(l => l.key === layer.key)) availableLayers.push(layer);
      layerVisibility[layer.key] = true;
      if (typeof renderLayerList === 'function') renderLayerList();
      await addLayer(layer);
    }

    async function calculate() {
      if (busy || !ready || !canCalculate) return;
      setBusy(true, 'Calculating the sky-view factor…');
      try {
        const data = await readJson(await fetch(card.dataset.calculateUrl, {
          method: 'POST',
          headers: { 'X-CSRFToken': csrfToken() },
          body: params(),
        }));
        setBusy(false);
        const s = data.stats;
        const range = s.mean == null ? 'no valid cells'
          : `${s.min.toFixed(2)}–${s.max.toFixed(2)} (mean ${s.mean.toFixed(2)})`;
        const replaced = data.replaced.length ? ` Replaced #${data.replaced.join(', #')}.` : '';
        setStatus(`Saved SVF #${data.id}: ${range}, ${Math.round(data.valid_fraction * 100)} % of the cells valid.${replaced}`, 'ok');
        el.calculate.textContent = 'Recalculate SVF for this view';
        await showResult(data);
      } catch (error) {
        setBusy(false);
        setStatus(error.message, 'error');
      }
    }

    // ---- wiring ----------------------------------------------------------

    openBtn.addEventListener('click', open);
    el.close.addEventListener('click', close);
    el.calculate.addEventListener('click', calculate);
    [el.radius, el.resolution].forEach(input => input.addEventListener('change', () => {
      if (card.classList.contains('visible')) loadInfo();
    }));

    // The grid follows the view: re-check it after each move (debounced).
    const watchView = () => {
      if (!map || watchView.bound) return;
      watchView.bound = true;
      map.on('moveend', () => {
        if (!card.classList.contains('visible') || busy) return;
        clearTimeout(watchView.timer);
        watchView.timer = setTimeout(loadInfo, 400);
      });
    };
    openBtn.addEventListener('click', watchView);

    if (typeof makeDraggable === 'function' && window.matchMedia('(min-width: 769px)').matches) {
      makeDraggable(card, '.lst-card-header');
    }
  }

  document.addEventListener('DOMContentLoaded', init);
})();
