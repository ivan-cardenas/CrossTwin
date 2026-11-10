// ============================================================
// DegurbaTool.js — Degree of Urbanisation card (Actions menu, #degurbaToolBtn).
// Shows the stored grid (GET builtup/degurba/info/): population year, cells
// and classes at 100 m (CrossTwin's local variant) and 1 km (the original
// method on the same data), the cities' class and urbanisation rate. Staff can
// rebuild it (POST builtup/degurba/calculate/); after that, edits to
// neighborhoods, dwellings, buildings and land cover keep it current on the
// server (builtup/signals.py). The 100 m / 1 km switch shows one layer at a time.
// Method: docs/DEGREE_OF_URBANISATION.md.
// Depends on: Config.js (map, availableLayers, layerVisibility),
// Layers.js (toggleLayerVisibility, reloadLayer), MapUI.js, Draggable.js.
// ============================================================

(function () {
  'use strict';

  const LAYERS = { 100: 'builtup.UrbanisationCellLocal', 1000: 'builtup.UrbanisationCellOriginal' };

  function init() {
    const card = document.getElementById('degurba-card');
    const openBtn = document.getElementById('degurbaToolBtn');
    if (!card || !openBtn) return;

    const el = {
      close: document.getElementById('degurba-card-close'),
      resolution: document.getElementById('degurba-resolution'),
      info: document.getElementById('degurba-view-info'),
      cities: document.getElementById('degurba-cities'),
      calculate: document.getElementById('degurba-calculate'),
      status: document.getElementById('degurba-status'),
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

    function render(data) {
      state = data;
      canCalculate = !!data.can_calculate;
      el.calculate.disabled = busy || !canCalculate;
      el.calculate.textContent = data.built ? 'Recalculate the whole grid' : 'Build the grid';
      el.cities.replaceChildren();
      if (!data.built) {
        el.info.textContent = `Not built yet. Population year ${data.population_year}.`;
        setStatus(canCalculate ? '' : 'Building the grid needs a staff login (Log in, top right).', canCalculate ? '' : 'warn');
        return;
      }
      const r = data.resolutions[el.resolution.value] || {};
      const classes = (r.classes || []).map(c => `${c.label}: ${c.cells}`).join(' · ');
      const notes = [];
      if (r.edge_clusters) notes.push(`${r.edge_clusters} cluster(s) touch the edge of the imported area`);
      if (data.area_allocated) notes.push(`${data.area_allocated} neighborhood(s) without dwellings spread by area`);
      el.info.textContent =
        `Year ${data.year} · ${fmt(r.cells || 0)} cells · ${fmt(r.population || 0)} people in ` +
        `${fmt(r.dwellings || 0)} dwellings. ${classes}` + (notes.length ? `. ${notes.join('; ')}.` : '');
      (data.cities || []).forEach(city => {
        const row = document.createElement('div');
        const local = city['100'] || {};
        const original = city['1000'] || {};
        const rate = local.rate == null ? 'rate needs a second year'
          : `${local.rate >= 0 ? '+' : ''}${local.rate.toFixed(2)} %/yr urban area since ${local.base_year}`;
        row.textContent = `${city.name}: ${local.class || '–'} (100 m) / ${original.class || '–'} (1 km) · ` +
          `${(local.urban_area_km2 ?? 0).toFixed(2)} km² urban · ${rate}`;
        el.cities.appendChild(row);
      });
      if (data.stale_year) {
        setStatus(`The neighborhoods now hold ${data.population_year} population: rebuild to add that year.`, 'warn');
      } else if (!canCalculate) {
        setStatus('Kept current automatically. Recalculating needs a staff login.', '');
      } else {
        setStatus('Kept current automatically when people, dwellings, buildings or land cover change.');
      }
    }

    async function loadInfo() {
      el.info.textContent = 'Reading the stored grid…';
      try {
        render(await readJson(await fetch(card.dataset.infoUrl)));
      } catch (error) {
        el.info.textContent = '';
        setStatus(error.message, 'error');
      }
    }

    function showLayer() {
      if (typeof toggleLayerVisibility !== 'function') return;
      const wanted = LAYERS[el.resolution.value];
      Object.values(LAYERS).forEach(key => {
        if (key !== wanted && layerVisibility[key]) toggleLayerVisibility(key, false);
      });
      if (!availableLayers.some(l => l.key === wanted)) return;
      if (typeof reloadLayer === 'function') reloadLayer(wanted);
      toggleLayerVisibility(wanted, true);
      if (typeof renderLayerList === 'function') renderLayerList();
    }

    function open() {
      ['lst-card', 'svf-card', 'solweig-card'].forEach(id => document.getElementById(id)?.classList.remove('visible'));
      card.classList.add('visible');
      if (typeof setActionsMenuOpen === 'function') setActionsMenuOpen(false);
      loadInfo();
    }

    async function calculate() {
      if (busy || !canCalculate) return;
      busy = true;
      card.classList.add('busy');
      el.calculate.disabled = true;
      const started = Date.now();
      const tick = () => setStatus(`Allocating people to dwellings and classifying… ${Math.round((Date.now() - started) / 1000)} s`, 'working');
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
        setStatus(`Built ${data.year}: ${fmt(data.resolutions[100]?.cells || 0)} cells at 100 m, ` +
          `${fmt(data.resolutions[1000]?.cells || 0)} at 1 km.`, 'ok');
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
    el.resolution.addEventListener('change', () => {
      if (state) render(state);
      if (state?.built) showLayer();
    });
    // Edits on the map change the grid on the server, in a background worker
    // (builtup/urbanisation.py): poll the info until it is no longer
    // refreshing, then show the new grid. A newer edit supersedes the wait.
    let editToken = 0;
    async function afterEdit() {
      const shown = Object.values(LAYERS).filter(key => layerVisibility[key]);
      if (!card.classList.contains('visible') && !shown.length) return;
      const token = ++editToken;
      const deadline = Date.now() + DEGURBA_POLL_TIMEOUT_MS;
      let info = null;
      while (Date.now() < deadline) {
        try {
          info = await readJson(await fetch(card.dataset.infoUrl));
        } catch (error) {
          setStatus(error.message, 'error');
          return;
        }
        if (token !== editToken) return;
        if (!info.refreshing) break;
        setStatus('Updating the grid after the edit…');
        await new Promise(resolve => setTimeout(resolve, DEGURBA_POLL_MS));
      }
      if (token !== editToken) return;
      if (info && !info.refreshing) setStatus('');
      if (info && card.classList.contains('visible')) render(info);
      if (typeof reloadLayer === 'function') shown.forEach(key => reloadLayer(key));
    }
    ['feature-saved', 'backup-restored'].forEach(name => document.body.addEventListener(name, afterEdit));

    if (typeof makeDraggable === 'function' && window.matchMedia('(min-width: 769px)').matches) {
      makeDraggable(card, '.lst-card-header');
    }
  }

  document.addEventListener('DOMContentLoaded', init);
})();
