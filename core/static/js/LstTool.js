// ============================================================
// LstTool.js — Land Surface Temperature for the area in view.
// Opened from the Actions menu (#lstToolBtn). Lists the Landsat scenes over
// the view (GET urban_heat/lst/scenes/), then computes and stores one LST
// raster (POST urban_heat/lst/calculate/) and shows it as a map layer.
// Recalculating the same scene over the same (or a larger) view replaces the
// earlier raster; the server says which ids it replaced.
// Depends on: Config.js (map, availableLayers, layerVisibility),
// Layers.js (addLayer, removeLayer), MapUI.js (renderLayerList), Draggable.js.
// ============================================================

(function () {
  'use strict';

  function init() {
    const card = document.getElementById('lst-card');
    const openBtn = document.getElementById('lstToolBtn');
    if (!card || !openBtn) return;

    const el = {
      close: document.getElementById('lst-card-close'),
      from: document.getElementById('lst-from'),
      to: document.getElementById('lst-to'),
      resolution: document.getElementById('lst-resolution'),
      useNdvi: document.getElementById('lst-use-ndvi'),
      find: document.getElementById('lst-find'),
      info: document.getElementById('lst-view-info'),
      scenes: document.getElementById('lst-scenes'),
      calculate: document.getElementById('lst-calculate'),
      status: document.getElementById('lst-status'),
    };
    const canCalculate = card.dataset.canCalculate === '1';
    let busy = false;
    let searchedBbox = null;

    // ---- helpers ---------------------------------------------------------

    function viewBbox() {
      const b = map.getBounds();
      return [b.getWest(), b.getSouth(), b.getEast(), b.getNorth()].map(v => v.toFixed(6)).join(',');
    }

    function csrfToken() {
      return card.querySelector('[name=csrfmiddlewaretoken]')?.value || '';
    }

    function pct(value) {
      return value == null ? '–' : `${Math.round(value * 100)} %`;
    }

    function setStatus(message, kind = '') {
      el.status.textContent = message;
      el.status.className = `lst-status ${kind}`;
    }

    function setBusy(on, label) {
      busy = on;
      el.find.disabled = on;
      el.calculate.disabled = on || !canCalculate || !selectedScene();
      card.classList.toggle('busy', on);
      clearInterval(setBusy.timer);
      if (on) {
        const started = Date.now();
        const tick = () => setStatus(`${label} ${Math.round((Date.now() - started) / 1000)} s`, 'working');
        tick();
        setBusy.timer = setInterval(tick, 1000);
      }
    }

    function selectedScene() {
      return el.scenes.querySelector('input[name=lst-scene]:checked')?.value || '';
    }

    function commonParams() {
      const params = new URLSearchParams({
        bbox: viewBbox(),
        resolution: el.resolution.value,
      });
      if (el.from.value) params.set('from', el.from.value);
      if (el.to.value) params.set('to', el.to.value);
      return params;
    }

    async function readJson(response) {
      let data = {};
      try { data = await response.json(); } catch (e) { /* non-JSON error page */ }
      if (!response.ok) throw new Error(data.error || `HTTP ${response.status}`);
      return data;
    }

    // ---- open / close ----------------------------------------------------

    function open() {
      // Same corner as the SVF card: show one at a time.
      document.getElementById('svf-card')?.classList.remove('visible');
      card.classList.add('visible');
      if (typeof setActionsMenuOpen === 'function') setActionsMenuOpen(false);
      if (!canCalculate) {
        setStatus('Viewing scenes works for everyone; calculating needs a staff login (Log in, top right).', 'warn');
      }
      if (!searchedBbox) findScenes();
    }

    function close() {
      card.classList.remove('visible');
    }

    // ---- scenes ----------------------------------------------------------

    function renderScenes(scenes) {
      if (!scenes.length) {
        el.scenes.innerHTML = '<div class="lst-empty">No scene in this window. Widen the dates.</div>';
        return;
      }
      el.scenes.innerHTML = scenes.map((s, i) => {
        const when = new Date(s.acquired);
        const day = when.toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' });
        const time = when.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' });
        const poor = s.view_clear != null && s.view_clear < 0.2 ? ' poor' : '';
        return `
          <label class="lst-scene${poor}" title="${s.id}">
            <input type="radio" name="lst-scene" value="${s.id}" ${i === 0 ? 'checked' : ''}>
            <span class="lst-scene-date">${day} <small>${time}</small></span>
            <span class="lst-scene-clear">${pct(s.view_clear)} clear</span>
            <span class="lst-scene-meta">covers ${pct(s.view_coverage)} · scene cloud ${Math.round(s.cloud_cover)} %</span>
          </label>`;
      }).join('');
    }

    async function findScenes() {
      if (busy) return;
      el.scenes.innerHTML = '';
      el.info.textContent = '';
      setBusy(true, 'Searching Landsat scenes over this view…');
      const bbox = viewBbox();
      try {
        const data = await readJson(await fetch(`${card.dataset.scenesUrl}?${commonParams()}`));
        searchedBbox = bbox;
        if (!el.from.value) el.from.value = data.window.from;
        if (!el.to.value) el.to.value = data.window.to;
        const ndvi = data.ndvi.map(n => `#${n.id}${n.date ? ` (${n.date})` : ''}`).join(', ');
        el.info.textContent = `NDVI ${ndvi} · grid ${data.grid.width}×${data.grid.height} @ ${data.grid.resolution} m`;
        renderScenes(data.scenes);
        setBusy(false);
        setStatus(data.scenes.length ? `${data.scenes.length} scene(s), clearest over this view first.` : '');
      } catch (error) {
        setBusy(false);
        setStatus(error.message, 'error');
      }
      el.calculate.disabled = busy || !canCalculate || !selectedScene();
    }

    // ---- calculate -------------------------------------------------------

    async function showResult(data) {
      (data.replaced || []).forEach(id => {
        const key = `raster-urban_heat-LandSurfaceTemperature-${id}`;
        if (typeof removeLayer === 'function') removeLayer(key);
      });
      const layer = data.layer;
      if (!layer) return;
      if (!availableLayers.some(l => l.key === layer.key)) availableLayers.push(layer);
      layerVisibility[layer.key] = true;
      if (typeof renderLayerList === 'function') renderLayerList();
      await addLayer(layer);
    }

    async function calculate() {
      const scene = selectedScene();
      if (busy || !scene || !canCalculate) return;
      setBusy(true, 'Calculating LST (Earth Engine download + SMW)…');
      const body = commonParams();
      body.set('scene', scene);
      body.set('use_ndvi', el.useNdvi.checked ? '1' : '0');
      try {
        const data = await readJson(await fetch(card.dataset.calculateUrl, {
          method: 'POST',
          headers: { 'X-CSRFToken': csrfToken() },
          body,
        }));
        setBusy(false);
        const s = data.stats;
        const replaced = data.replaced.length ? ` Replaced #${data.replaced.join(', #')}.` : '';
        setStatus(
          `Saved LST #${data.id}: ${s.min.toFixed(1)}–${s.max.toFixed(1)} °C (mean ${s.mean.toFixed(1)}), ` +
          `${pct(data.valid_fraction)} of the area clear (water vapour: ${data.tpw_source}).${replaced}`,
          'ok'
        );
        await showResult(data);
      } catch (error) {
        setBusy(false);
        setStatus(error.message, 'error');
      }
    }

    // ---- wiring ----------------------------------------------------------

    openBtn.addEventListener('click', open);
    el.close.addEventListener('click', close);
    el.find.addEventListener('click', findScenes);
    el.calculate.addEventListener('click', calculate);
    el.scenes.addEventListener('change', () => {
      el.calculate.disabled = busy || !canCalculate || !selectedScene();
    });
    // New dates or cell size only take effect after a new search.
    [el.from, el.to, el.resolution].forEach(input => input.addEventListener('change', () => {
      if (card.classList.contains('visible')) setStatus('Settings changed: find scenes again.', 'warn');
    }));

    // The scene list belongs to the view it was searched for; Calculate
    // always uses the current view, so only flag the list as possibly stale.
    const watchView = () => {
      if (!map || watchView.bound) return;
      watchView.bound = true;
      map.on('moveend', () => {
        if (!busy && searchedBbox && card.classList.contains('visible') && viewBbox() !== searchedBbox) {
          setStatus('The view changed: Calculate uses the new view; find scenes again to re-rank them for it.', 'warn');
        }
      });
    };
    openBtn.addEventListener('click', watchView);

    if (typeof makeDraggable === 'function' && window.matchMedia('(min-width: 769px)').matches) {
      makeDraggable(card, '.lst-card-header');
    }
  }

  document.addEventListener('DOMContentLoaded', init);
})();
