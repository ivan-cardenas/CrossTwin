// ============================================================
// AccessibilityTool.js — Network accessibility card (Built-up lens › Calculate tab, #accessToolBtn).
// Shows what is stored (GET builtup/accessibility/info/): the walk and bike network,
// the buildings scored and their mean score, per mode. Staff can recompute every
// building (POST builtup/accessibility/calculate/); after that, edits to facilities, parks
// and network segments keep the scores current on the server (builtup/signals.py), and this
// card only reloads the layer that is on screen. The map layer is a smooth raster of the scores
// (builtup/calculations/access_raster.py); the Walk / Bike switch shows one at a time.
// Method: builtup/calculations/chain.py (distance decay to the nearest amenities per category).
// Depends on: Config.js (availableLayers, layerVisibility),
// Layers.js (toggleLayerVisibility, reloadLayer, renderLayerList), Panels.js.
// ============================================================

(function () {
  'use strict';

  const MODE_LABEL = { walk: 'Walking', bike: 'Cycling' };

  function init() {
    const card = document.getElementById('access-card');
    const openBtn = document.getElementById('accessToolBtn');
    if (!card || !openBtn) return;

    const el = {
      close: document.getElementById('access-card-close'),
      mode: document.getElementById('access-mode'),
      info: document.getElementById('access-view-info'),
      calculate: document.getElementById('access-calculate'),
      status: document.getElementById('access-status'),
    };
    let busy = false;
    let canCalculate = card.dataset.canCalculate === '1';
    let state = null;

    function csrfToken() {
      return card.querySelector('[name=csrfmiddlewaretoken]')?.value || '';
    }

    function setStatus(message, kind = '') {
      el.status.textContent = message;
      el.status.className = `lst-status ${kind}`;
    }

    async function readJson(response) {
      let data = {};
      try { data = await response.json(); } catch (e) { /* non-JSON error page */ }
      if (!response.ok) throw new Error(data.error || `HTTP ${response.status}`);
      return data;
    }

    const fmt = (n) => Math.round(n).toLocaleString();
    // The map shows the smooth raster (builtup.AccessibilityRaster); the building dots stay a separate layer.
    const rasterEntry = () => state?.modes?.[el.mode.value]?.raster_layer;
    const allKeys = () => Object.values(state?.modes || {}).flatMap(m => [m.layer, m.raster_layer?.key]).filter(Boolean);

    function render(data) {
      state = data;
      canCalculate = !!data.can_calculate;
      const mode = data.modes[el.mode.value];
      el.calculate.disabled = busy || !canCalculate || !data.has_network;
      el.calculate.textContent = mode.buildings ? 'Recalculate every building' : 'Calculate every building';
      if (!data.has_network) {
        el.info.textContent = 'No street network stored yet. Import "Walk & bike network (OpenStreetMap)" ' +
          'and the amenities first (Data menu › Retrieve Data from APIs).';
        setStatus('');
        return;
      }
      const scored = mode.buildings
        ? `${fmt(mode.buildings)} of ${fmt(data.buildings)} buildings scored · mean ${mode.mean_score} / 100`
        : 'No building scored yet';
      el.info.textContent = `${MODE_LABEL[el.mode.value]}: ${fmt(mode.edges)} network segments` +
        (mode.network_snapshot ? ` (OpenStreetMap, ${mode.network_snapshot})` : '') + `. ${scored}. ` +
        `Full value within ${fmt(mode.full_value_m)} m, nothing beyond ${fmt(mode.cutoff_m)} m.`;
      if (!canCalculate) {
        setStatus(mode.buildings ? 'Kept current automatically. Recalculating needs a staff login.'
          : 'Calculating needs a staff login (Log in, top right).', mode.buildings ? '' : 'warn');
      } else {
        setStatus(mode.buildings
          ? 'Kept current automatically when facilities, parks or the street network change.'
          : 'Run it once; after that edits keep it current.');
      }
    }

    async function loadInfo() {
      el.info.textContent = 'Reading the stored scores…';
      try {
        render(await readJson(await fetch(card.dataset.infoUrl)));
      } catch (error) {
        el.info.textContent = '';
        setStatus(error.message, 'error');
      }
    }

    function showLayer() {
      if (typeof toggleLayerVisibility !== 'function' || !state) return;
      const wanted = rasterEntry();
      allKeys().forEach(key => {
        if (key !== wanted?.key && layerVisibility[key]) toggleLayerVisibility(key, false);
      });
      if (!wanted) return;
      if (!availableLayers.some(l => l.key === wanted.key)) availableLayers.push(wanted);
      if (typeof refreshRasterTiles === 'function') refreshRasterTiles(wanted.app_label, wanted.model_name);
      toggleLayerVisibility(wanted.key, true);
      if (typeof renderLayerList === 'function') renderLayerList();
    }

    function open() {
      ['lst-card', 'svf-card', 'solweig-card', 'degurba-card', 'generator-card']
        .forEach(id => document.getElementById(id)?.classList.remove('visible'));
      card.classList.add('visible');
      loadInfo();
    }

    async function calculate() {
      if (busy || !canCalculate) return;
      busy = true;
      card.classList.add('busy');
      el.calculate.disabled = true;
      const started = Date.now();
      const tick = () => setStatus(`Routing every building to its nearest amenities… ${Math.round((Date.now() - started) / 1000)} s`, 'working');
      tick();
      const timer = setInterval(tick, 1000);
      try {
        const data = await readJson(await fetch(card.dataset.calculateUrl, {
          method: 'POST', headers: { 'X-CSRFToken': csrfToken() },
        }));
        clearInterval(timer);
        busy = false;
        card.classList.remove('busy');
        render(data);
        const done = Object.entries(data.written || {}).map(([m, n]) => `${fmt(n)} ${m}`).join(', ');
        setStatus(`Scored ${done || 'no'} building rows.`, 'ok');
        showLayer();
      } catch (error) {
        clearInterval(timer);
        busy = false;
        card.classList.remove('busy');
        el.calculate.disabled = !canCalculate;
        setStatus(error.message, 'error');
      }
    }

    openBtn.addEventListener('click', open);
    el.close.addEventListener('click', () => card.classList.remove('visible'));
    el.calculate.addEventListener('click', calculate);
    el.mode.addEventListener('change', () => {
      if (!state) return;
      render(state);
      if (state.modes[el.mode.value].raster_layer) showLayer();
    });
    // An edit on the map recomputes the scores around it inside the same request
    // (builtup/signals.py); reload the layer that is on screen and refresh the counts.
    async function afterEdit() {
      const shown = allKeys().filter(key => layerVisibility[key]);
      if (!card.classList.contains('visible') && !shown.length) return;
      if (typeof reloadLayer === 'function') shown.filter(key => !key.startsWith('raster-')).forEach(key => reloadLayer(key));
      if (typeof refreshRasterTiles === 'function') refreshRasterTiles('builtup', 'AccessibilityRaster');
      if (card.classList.contains('visible')) loadInfo();
    }
    ['feature-saved', 'backup-restored'].forEach(name => document.body.addEventListener(name, afterEdit));
  }

  document.addEventListener('DOMContentLoaded', init);
})();
