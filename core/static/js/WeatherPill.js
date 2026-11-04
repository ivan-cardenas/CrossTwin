// ============================================================
// WeatherPill.js — live weather pill at the top centre of the map.
//
// Shows the current weather at the map centre (/weather/live/, Open-Meteo
// through weather/live.py; the server caches per ~2 km cell for 10 min).
// Reloads after the map stops moving (only when the centre changed cell)
// and every REFRESH_MS. A click opens the Urban Heat panel, whose weather
// sliders adjust it: heat.js sends 'crosstwin:heat-weather' after every
// recalculation, and while those values are a what-if the pill shows them
// with a "What-if" badge. Closing the panel (or Reset there) returns the
// pill to the live values.
// ============================================================
(function () {
  const REFRESH_MS = 10 * 60 * 1000;
  const GRID_DEG = 0.02;          // same cell size as weather/live.py
  const MOVE_DEBOUNCE_MS = 800;

  let live = null;                // last live answer
  let whatif = null;              // heat panel's what-if values, or null
  let lastKey = null;
  let pending = null;             // AbortController of the running request
  let debounce = null;

  const el = id => document.getElementById(id);

  function fmt(value, digits) {
    return value === null || value === undefined || isNaN(value) ? '–' : Number(value).toFixed(digits);
  }

  function timeLabel(iso) {
    // Open-Meteo answers in the location's local time ("2026-11-03T14:15")
    return iso && iso.includes('T') ? iso.split('T')[1].slice(0, 5) : '';
  }

  function render() {
    const pill = el('weather-pill');
    if (!pill) return;
    const values = whatif || live;
    if (!values) {
      pill.hidden = !pill.classList.contains('is-error');
      return;
    }
    pill.hidden = false;
    pill.classList.remove('is-error');
    pill.classList.toggle('is-whatif', !!whatif);
    el('weather-pill-icon').textContent = (live && live.icon) || '🌡️';
    el('weather-pill-temp').textContent = `${fmt(values.ta_c, 1)}°C`;
    const parts = [
      `💧 ${fmt(values.rh_pct, 0)}%`,
      `💨 ${fmt(values.wind_ms, 1)} m/s`,
    ];
    if (whatif) {
      if (whatif.feels !== null && whatif.feels !== undefined) parts.push(`feels ${fmt(whatif.feels, 1)}°C`);
    } else {
      if (live.precip_mm) parts.push(`🌧 ${fmt(live.precip_mm, 1)} mm`);
      if (live.description) parts.push(live.description);
    }
    el('weather-pill-meta').textContent = parts.join(' · ');
    el('weather-pill-badge').hidden = !whatif;
    const when = live ? timeLabel(live.time) : '';
    pill.title = whatif
      ? 'Weather what-if from the Urban Heat panel — click to adjust, Reset there to return to live'
      : `Live weather at the map centre (${(live && live.source) || 'Open-Meteo'}${when ? ', ' + when : ''}) — click to adjust it in the Urban Heat panel`;
  }

  function showError(message) {
    const pill = el('weather-pill');
    if (!pill || live) return;    // keep the last good values
    pill.hidden = false;
    pill.classList.add('is-error');
    el('weather-pill-icon').textContent = '🌡️';
    el('weather-pill-temp').textContent = '–';
    el('weather-pill-meta').textContent = 'Weather unavailable';
    pill.title = message || 'Live weather unavailable';
  }

  function load(force) {
    const pill = el('weather-pill');
    if (!pill || typeof map === 'undefined' || !map) return;
    const c = map.getCenter();
    const key = `${Math.round(c.lat / GRID_DEG)}:${Math.round(c.lng / GRID_DEG)}`;
    if (!force && key === lastKey) return;
    lastKey = key;
    if (pending) pending.abort();
    pending = new AbortController();
    const url = `${pill.dataset.liveUrl}?lat=${c.lat.toFixed(4)}&lng=${c.lng.toFixed(4)}`;
    fetch(url, { signal: pending.signal })
      .then(r => r.json().then(body => ({ ok: r.ok, body })))
      .then(({ ok, body }) => {
        if (!ok) { showError(body.error); return; }
        live = body;
        render();
      })
      .catch(err => { if (err.name !== 'AbortError') showError(); });
  }

  function openHeatPanel() {
    const controls = document.querySelector('#heat-whatif .heat-weather-controls');
    if (controls) {                // already open: bring the sliders into view
      controls.scrollIntoView({ behavior: 'smooth', block: 'start' });
      return;
    }
    document.querySelector('.tool-button[data-tool="temperature"]')?.click();
  }

  function init() {
    const pill = el('weather-pill');
    if (!pill) return;
    pill.addEventListener('click', openHeatPanel);
    map.on('moveend', () => {
      clearTimeout(debounce);
      debounce = setTimeout(() => load(false), MOVE_DEBOUNCE_MS);
    });
    setInterval(() => load(true), REFRESH_MS);
    window.addEventListener('crosstwin:heat-weather', evt => {
      whatif = evt.detail && evt.detail.whatif ? evt.detail : null;
      render();
    });
    el('panel-close')?.addEventListener('click', () => { whatif = null; render(); });
    // Another panel replaced the heat panel: its what-if is gone
    document.body.addEventListener('htmx:afterSwap', evt => {
      if (whatif && evt.detail.target.id === 'panel-body' && !el('heat-whatif')) {
        whatif = null;
        render();
      }
    });
    load(true);
  }

  function whenMapReady(callback) {
    if (typeof map !== 'undefined' && map) {
      if (map.loaded()) callback();
      else map.once('load', callback);
    } else {
      setTimeout(() => whenMapReady(callback), 200);
    }
  }

  document.addEventListener('DOMContentLoaded', () => whenMapReady(init));
})();
