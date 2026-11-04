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
//
// Precipitation: Mapbox has no rain radar outside Japan, only a screen-wide
// particle effect (map.setRain / setSnow, GL JS >= 3.9, experimental) that
// can't vary in space. So the live weather code at the map centre switches
// that effect on as ambience (only zoomed in, fading between z11 and z13),
// and while it rains a "Radar" button beside the pill toggles the KNMI radar
// nowcast WMS layer, which shows where it actually rains. The what-if never
// drives either: the heat panel has no precipitation slider.
// ============================================================
(function () {
  const REFRESH_MS = 10 * 60 * 1000;
  const GRID_DEG = 0.02;          // same cell size as weather/live.py
  const MOVE_DEBOUNCE_MS = 800;
  const HEAVY_PRECIP_MM = 2;      // Open-Meteo current precipitation at which the effect is at full strength

  let live = null;                // last live answer
  let whatif = null;              // heat panel's what-if values, or null
  let lastKey = null;
  let pending = null;             // AbortController of the running request
  let debounce = null;
  let effectKey = null;           // last applied precipitation effect, to skip no-op updates

  const el = id => document.getElementById(id);

  // ---- Precipitation effect --------------------------------------------

  // WMO weather codes (Open-Meteo weather_code)
  function precipKind(values) {
    const code = values && values.weather_code;
    if (code === null || code === undefined) {
      return values && values.precip_mm > 0 ? 'rain' : null;
    }
    if ((code >= 71 && code <= 77) || code === 85 || code === 86) return 'snow';
    if ((code >= 51 && code <= 67) || (code >= 80 && code <= 82) || code >= 95) return 'rain';
    return null;
  }

  const reducedMotion = () => window.matchMedia &&
    window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  // Same zoom fade as Mapbox's defaults: nothing below z11, full at z13
  const zoomReveal = value => ['interpolate', ['linear'], ['zoom'], 11, 0, 13, value];

  function applyPrecipEffect(force) {
    if (typeof map === 'undefined' || !map || typeof map.setRain !== 'function') return;
    const kind = reducedMotion() ? null : precipKind(live);
    const strength = kind
      ? Math.min(1, Math.max(0.2, (Number(live.precip_mm) || 0) / HEAVY_PRECIP_MM))
      : 0;
    const key = kind ? `${kind}:${strength.toFixed(2)}` : 'none';
    if (!force && key === effectKey) return;
    effectKey = key;
    try {
      // Explicit colours: the defaults read measure-light, which only the
      // Standard style sets; CrossTwin's basemaps are classic styles.
      map.setRain(kind === 'rain' ? {
        density: zoomReveal(0.25 + 0.5 * strength),
        intensity: strength,
        color: '#a8adbc',
        opacity: 0.7,
        vignette: zoomReveal(0.6 * strength),
        'vignette-color': '#464646',
        direction: [0, 80],
        'droplet-size': [2.6, 18.2],
        'distortion-strength': 0.5,
        'center-thinning': 0.4,
      } : null);
      map.setSnow(kind === 'snow' ? {
        density: zoomReveal(0.3 + 0.5 * strength),
        intensity: strength,
        color: '#ffffff',
        opacity: 0.9,
        vignette: zoomReveal(0.3 * strength),
        'vignette-color': '#ffffff',
        'center-thinning': 0.4,
      } : null);
    } catch (err) {
      console.warn('Precipitation effect unavailable:', err);
    }
  }

  // ---- Radar toggle (KNMI radar nowcast WMS layer) ---------------------

  function radarLayer() {
    if (typeof availableLayers === 'undefined') return null;
    return availableLayers.find(l =>
      l.layer_type === 'wms' && l.has_time_dimension && /radar/i.test(l.key)) || null;
  }

  let radarLoading = false;       // switched on here, addAnimatedWmsLayer still fetching its time steps

  function radarVisible(key) {
    if (typeof layerVisibility === 'undefined' || layerVisibility[key] === false) return false;
    const loaded = typeof loadedLayers !== 'undefined' && !!loadedLayers[key];
    if (loaded) radarLoading = false;
    return loaded || radarLoading;
  }

  function renderRadarButton() {
    const btn = el('weather-pill-radar');
    if (!btn) return;
    const layer = radarLayer();
    const visible = layer ? radarVisible(layer.key) : false;
    // Keep the button while the radar is on, so it can be switched off again after the rain stops
    btn.hidden = !layer || el('weather-pill').hidden || (precipKind(live) === null && !visible);
    btn.setAttribute('aria-pressed', visible ? 'true' : 'false');
    btn.title = visible ? 'Hide the KNMI rain radar' : 'Show the KNMI rain radar (2-hour nowcast)';
  }

  function toggleRadar() {
    const layer = radarLayer();
    if (!layer || typeof toggleLayerVisibility !== 'function') return;
    const show = !radarVisible(layer.key);
    radarLoading = show;
    toggleLayerVisibility(layer.key, show);
    const cb = el(`toggle-${layer.key}`);   // keep the layers panel in step
    if (cb) cb.checked = show;
    renderRadarButton();
  }

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
    renderRadarButton();
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
        applyPrecipEffect(false);
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
    el('weather-pill-radar')?.addEventListener('click', toggleRadar);
    // The layers panel's checkbox for the radar layer: keep the button in step
    document.addEventListener('change', evt => {
      const layer = radarLayer();
      if (layer && evt.target.id === `toggle-${layer.key}`) {
        radarLoading = evt.target.checked;
        renderRadarButton();
      }
    });
    // Rain and snow are style properties: a basemap switch (setStyle) drops them
    map.on('style.load', () => applyPrecipEffect(true));
    window.matchMedia?.('(prefers-reduced-motion: reduce)')
      .addEventListener?.('change', () => applyPrecipEffect(true));
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
    // The layer catalog may arrive after the first weather answer
    let tries = 0;
    const waitForCatalog = setInterval(() => {
      if (radarLayer() || ++tries >= 30) {
        clearInterval(waitForCatalog);
        renderRadarButton();
      }
    }, 1000);
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
