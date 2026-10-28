// ============================================================
// SolweigTool.js — SOLWEIG thermal comfort (Tmrt, UTCI, PET) for the area in
// view and one hour. Opened from the Actions menu (#solweigToolBtn).
//   GET  urban_heat/solweig/info/   DSM, grid, cell limit, sun position, device
//   GET  urban_heat/solweig/met/    nearest KNMI station / ERA5 values (prefill)
//   POST urban_heat/solweig/calculate/ -> a run in the background, polled at
//   GET  urban_heat/solweig/runs/<id>/ until done; then its three layers are added.
// Also owns the stale-results mark: after a building edit (feature-saved,
// backup-restored) or a map move it asks urban_heat/solweig/stale/ which SVF
// and thermal-comfort results in view are older than a building change, and
// shows a dot on the Actions button and on the SVF / thermal comfort rows.
// Depends on: Config.js (map, availableLayers, layerVisibility),
// Layers.js (addLayer, removeLayer), MapUI.js (renderLayerList), Draggable.js.
// ============================================================

(function () {
  'use strict';

  const MET_FIELDS = ['ta_c', 'rh_pct', 'wind_ms', 'wind_dir_deg', 'kdown_wm2', 'pressure_kpa'];
  const POLL_MS = 3000;

  function init() {
    const card = document.getElementById('solweig-card');
    const openBtn = document.getElementById('solweigToolBtn');
    if (!card || !openBtn) return;

    const el = {
      close: document.getElementById('solweig-card-close'),
      date: document.getElementById('solweig-date'),
      hour: document.getElementById('solweig-hour'),
      resolution: document.getElementById('solweig-resolution'),
      source: document.getElementById('solweig-source'),
      fetch: document.getElementById('solweig-fetch'),
      metInfo: document.getElementById('solweig-met-info'),
      info: document.getElementById('solweig-view-info'),
      calculate: document.getElementById('solweig-calculate'),
      status: document.getElementById('solweig-status'),
    };
    const met = Object.fromEntries(MET_FIELDS.map(f => [f, document.getElementById(`solweig-${f}`)]));
    const canCalculate = card.dataset.canCalculate === '1';
    let busy = false;
    let ready = false;
    let infoRequest = null;
    let metLabel = 'manual';  // source of the values in the form ("KNMI 290 Twenthe Airport", "ERA5", "manual")
    let stale = { svf: [], thermal: [] };

    // Default: a week ago at 15:00 (KNMI's validated hourly data and ERA5 lag a few days).
    for (let h = 0; h < 24; h++) el.hour.add(new Option(`${String(h).padStart(2, '0')}:00`, h));
    const lastWeek = new Date(Date.now() - 7 * 86400000);
    el.date.value = lastWeek.toISOString().slice(0, 10);
    el.hour.value = 15;

    // ---- helpers ---------------------------------------------------------

    function viewBbox() {
      const b = map.getBounds();
      return [b.getWest(), b.getSouth(), b.getEast(), b.getNorth()].map(v => v.toFixed(6)).join(',');
    }

    function when() {
      return `${el.date.value}T${String(el.hour.value).padStart(2, '0')}:00`;
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
      el.calculate.textContent = stale.thermal.length ? 'Recalculate thermal comfort' : 'Calculate thermal comfort';
    }

    async function readJson(response) {
      let data = {};
      try { data = await response.json(); } catch (e) { /* non-JSON error page */ }
      if (!response.ok) throw new Error(data.error || `HTTP ${response.status}`);
      return data;
    }

    function duration(seconds) {
      return seconds < 90 ? `${seconds} s` : `${Math.round(seconds / 60)} min`;
    }

    // ---- stale mark ------------------------------------------------------

    function showStale() {
      const svfDot = document.querySelector('#svfToolBtn .stale-dot');
      const thermalDot = openBtn.querySelector('.stale-dot');
      const menuDot = document.querySelector('#actions-menu-btn .stale-dot');
      if (svfDot) svfDot.hidden = !stale.svf.length;
      if (thermalDot) thermalDot.hidden = !stale.thermal.length;
      if (menuDot) menuDot.hidden = !(stale.svf.length || stale.thermal.length);
      refreshButton();
    }

    async function refreshStale() {
      if (!map) return;
      try {
        stale = await readJson(await fetch(`${card.dataset.staleUrl}?bbox=${viewBbox()}`));
      } catch (e) {
        stale = { svf: [], thermal: [] };
      }
      showStale();
    }

    // ---- view info -------------------------------------------------------

    async function loadInfo() {
      if (busy) return;
      infoRequest?.abort();
      infoRequest = new AbortController();
      ready = false;
      refreshButton();
      el.info.textContent = 'Checking the inputs for this view…';
      const p = new URLSearchParams({ bbox: viewBbox(), datetime: when(), resolution: el.resolution.value });
      try {
        const data = await readJson(await fetch(`${card.dataset.infoUrl}?${p}`, { signal: infoRequest.signal }));
        stale = data.stale || stale;
        showStale();
        const sun = data.sun
          ? `Sun ${data.sun.altitude}° high, azimuth ${data.sun.azimuth}°` + (data.sun.altitude <= 0 ? ' (below the horizon)' : '')
          : '';
        if (!data.available) {
          el.info.textContent = sun;
          setStatus(data.install_hint, 'warn');
        } else if (!data.dsm) {
          el.info.textContent = sun;
          setStatus(data.error, 'error');
        } else {
          const g = data.grid;
          const partial = data.coverage < 0.99 ? ` · DSM covers ${Math.round(data.coverage * 100)} %` : '';
          el.info.textContent =
            `${sun} · DSM #${data.dsm.id} · ${g.width}×${g.height} @ ${g.resolution} m + ${data.halo_m} m halo` +
            `${partial} · ${data.device.toUpperCase()}, first run ~${duration(data.estimate_s)}`;
          ready = true;
          if (!canCalculate) setStatus('Calculating needs a staff login (Log in, top right).', 'warn');
          else if (stale.thermal.length) setStatus('Buildings changed here since the last thermal-comfort run.', 'warn');
          else if (!busy) setStatus('');
        }
      } catch (error) {
        if (error.name === 'AbortError') return;
        el.info.textContent = '';
        setStatus(error.message, 'error');
      }
      refreshButton();
    }

    // ---- weather ---------------------------------------------------------

    async function fetchMet() {
      if (el.source.value === 'manual') {
        metLabel = 'manual';
        el.metInfo.textContent = 'Manual values.';
        return;
      }
      el.fetch.disabled = true;
      el.metInfo.textContent = el.source.value === 'knmi' ? 'Finding the nearest KNMI station…' : 'Reading ERA5…';
      const p = new URLSearchParams({ bbox: viewBbox(), datetime: when(), source: el.source.value });
      try {
        const data = await readJson(await fetch(`${card.dataset.metUrl}?${p}`));
        MET_FIELDS.forEach(f => {
          const v = data.met[f];
          met[f].value = (f === 'wind_dir_deg' && v < 0) ? '' : v;
        });
        metLabel = data.met.source;
        el.metInfo.textContent = data.station
          ? `KNMI ${data.station.id} ${data.station.name}, ${data.station.distance_km} km from the view centre`
          : `${data.met.source} at the view centre`;
      } catch (error) {
        el.metInfo.textContent = error.message;
      }
      el.fetch.disabled = false;
    }

    // ---- open / close ----------------------------------------------------

    function open() {
      // Same corner as the LST and SVF cards: show one at a time.
      ['lst-card', 'svf-card'].forEach(id => document.getElementById(id)?.classList.remove('visible'));
      card.classList.add('visible');
      if (typeof setActionsMenuOpen === 'function') setActionsMenuOpen(false);
      loadInfo();
      if (metLabel === 'manual' && el.source.value !== 'manual') fetchMet();
    }

    function close() {
      card.classList.remove('visible');
      infoRequest?.abort();
    }

    // ---- calculate -------------------------------------------------------

    async function showLayers(run) {
      const replaced = run.stats?.replaced || {};
      const models = { mrt: 'MeanRadiantTemperature', utci: 'UTCI', pet: 'PET' };
      Object.entries(models).forEach(([key, model]) => (replaced[key] || []).forEach(id => {
        if (typeof removeLayer === 'function') removeLayer(`raster-urban_heat-${model}-${id}`);
      }));
      for (const layer of run.layers) {
        if (!availableLayers.some(l => l.key === layer.key)) availableLayers.push(layer);
        // Only UTCI is switched on; Tmrt and PET are listed for the user to toggle.
        layerVisibility[layer.key] = layer.model_name === 'UTCI';
      }
      if (typeof renderLayerList === 'function') renderLayerList();
      const utci = run.layers.find(l => l.model_name === 'UTCI');
      if (utci) await addLayer(utci);
    }

    async function poll(runId, started) {
      const url = card.dataset.runUrl.replace(/0\/$/, `${runId}/`);
      for (;;) {
        await new Promise(resolve => setTimeout(resolve, POLL_MS));
        const run = await readJson(await fetch(url));
        const elapsed = Math.round((Date.now() - started) / 1000);
        if (run.status === 'done' || run.status === 'failed') return run;
        setStatus(`${run.message || 'Queued…'} ${duration(elapsed)}`, 'working');
      }
    }

    async function calculate() {
      if (busy || !ready || !canCalculate) return;
      const body = new URLSearchParams({
        bbox: viewBbox(), datetime: when(), resolution: el.resolution.value, source: metLabel,
      });
      MET_FIELDS.forEach(f => body.set(f, met[f].value));
      busy = true;
      card.classList.add('busy');
      refreshButton();
      setStatus('Starting…', 'working');
      try {
        const queued = await readJson(await fetch(card.dataset.calculateUrl, {
          method: 'POST', headers: { 'X-CSRFToken': csrfToken() }, body,
        }));
        const run = await poll(queued.id, Date.now());
        if (run.status === 'failed') throw new Error(run.message);
        const s = run.stats;
        setStatus(`Run #${run.id} (${run.device.toUpperCase()}): Tmrt ${s.tmrt.min}–${s.tmrt.max} °C, ` +
                  `UTCI ${s.utci.min}–${s.utci.max} °C, PET ${s.pet.min}–${s.pet.max} °C.`, 'ok');
        await showLayers(run);
      } catch (error) {
        setStatus(error.message, 'error');
      }
      busy = false;
      card.classList.remove('busy');
      await refreshStale();
    }

    // ---- wiring ----------------------------------------------------------

    openBtn.addEventListener('click', open);
    el.close.addEventListener('click', close);
    el.calculate.addEventListener('click', calculate);
    el.fetch.addEventListener('click', fetchMet);
    el.source.addEventListener('change', fetchMet);
    // Values typed by hand are the user's own, whatever was fetched before.
    MET_FIELDS.forEach(f => met[f].addEventListener('input', () => {
      if (metLabel !== 'manual') {
        metLabel = 'manual';
        el.source.value = 'manual';
        el.metInfo.textContent = 'Manual values (edited).';
      }
    }));
    [el.date, el.hour, el.resolution].forEach(input => input.addEventListener('change', () => {
      if (!card.classList.contains('visible')) return;
      loadInfo();
      if (input !== el.resolution && el.source.value !== 'manual') fetchMet();
    }));

    // A building edit or a Restore can make results stale.
    document.body.addEventListener('feature-saved', refreshStale);
    document.body.addEventListener('backup-restored', refreshStale);

    // The map is created after DOMContentLoaded (mainMap.js): bind once it exists.
    (function bindMap() {
      if (!map) { setTimeout(bindMap, 500); return; }
      map.on('moveend', () => {
        clearTimeout(bindMap.timer);
        bindMap.timer = setTimeout(() => {
          if (card.classList.contains('visible') && !busy) loadInfo();
          else refreshStale();
        }, 400);
      });
      map.once('idle', refreshStale);
    })();

    if (typeof makeDraggable === 'function' && window.matchMedia('(min-width: 769px)').matches) {
      makeDraggable(card, '.lst-card-header');
    }
  }

  document.addEventListener('DOMContentLoaded', init);
})();
