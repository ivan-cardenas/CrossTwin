/**
 * 3D view of a raster layer: the raster is cut into square containers of N x N
 * cells (N from a slider), each container's mean (server side,
 * core/calculations/raster_blocks.py) becomes a column whose height encodes the
 * value. Drawn with deck.gl's GridCellLayer inside the Mapbox map
 * (MapboxOverlay, interleaved), coloured with the raster's own colormap.
 *
 * One raster at a time. Containers are aligned to the raster's pixel grid, so
 * panning never reshuffles them; the view reloads after the map settles.
 */
(function () {
  const MAX_SIZE_CELLS = 100;       // slider range (server allows 200)
  const DEFAULT_SIZE_CELLS = 5;
  const DEFAULT_HEIGHT_M = 200;     // height of the tallest column
  const MIN_COLUMN_FRACTION = 0.01; // the lowest value still shows as a sliver
  const RELOAD_DEBOUNCE_MS = 400;
  const VIEW_PITCH = 55;

  let overlay = null;
  let state = null;                 // {key, cfg, data, lut, abort}
  let reloadTimer = null;

  const $ = id => document.getElementById(id);

  function hexToRgb(h) {
    return [1, 3, 5].map(i => parseInt(h.slice(i, i + 2), 16));
  }

  /** 256-step colour lookup from the legend's evenly spaced stops. */
  function buildLut(legend) {
    const stops = (legend?.stops || []).map(s => hexToRgb(s.color));
    if (stops.length < 2) return null;
    return Array.from({ length: 256 }, (_, i) => {
      const f = (i / 255) * (stops.length - 1);
      const a = Math.floor(f), b = Math.min(a + 1, stops.length - 1), t = f - a;
      return stops[a].map((c, k) => Math.round(c + (stops[b][k] - c) * t));
    });
  }

  function ensureOverlay() {
    if (overlay) return true;
    if (typeof deck === 'undefined' || !deck.MapboxOverlay) {
      setStatus('deck.gl could not be loaded.', true);
      return false;
    }
    overlay = new deck.MapboxOverlay({ interleaved: true, layers: [] });
    map.addControl(overlay);
    return true;
  }

  function setStatus(text, isError) {
    const el = $('raster3d-status');
    if (!el) return;
    el.textContent = text || '';
    el.style.color = isError ? 'var(--danger, #e5484d)' : '';
  }

  const sizeCells = () => Number($('raster3d-size').value);
  const heightM = () => Number($('raster3d-height').value);
  const opacity = () => Number($('raster3d-opacity').value) / 100;

  function updateReadouts() {
    const n = sizeCells();
    const cell = state?.data?.native_cell_m;
    $('raster3d-size-value').textContent = cell
      ? `${n} × ${n} cells (≈ ${Math.round(n * cell)} m)` : `${n} × ${n} cells`;
    $('raster3d-height-value').textContent = `${heightM()} m`;
    $('raster3d-opacity-value').textContent = `${Math.round(opacity() * 100)} %`;
  }

  function draw() {
    if (!overlay) return;
    if (!state?.data || !state.lut) { overlay.setProps({ layers: [] }); return; }
    const { data, lut } = state;
    const lo = data.legend?.min ?? data.min, hi = data.legend?.max ?? data.max;
    const span = hi > lo ? hi - lo : 1;
    const norm = v => Math.min(1, Math.max(0, (v - lo) / span));
    const unit = data.legend?.unit ? ` ${data.legend.unit}` : '';
    const rows = state.rows;

    overlay.setProps({
      getTooltip: ({ object }) => object && {
        text: `${object.v.toFixed(2)}${unit}  (mean of ${data.block}×${data.block} cells)`,
      },
      layers: [new deck.GridCellLayer({
        id: 'raster3d-columns',
        data: rows,
        pickable: true,
        extruded: true,
        cellSize: data.cell_size_m,
        coverage: 1,
        opacity: opacity(),
        elevationScale: heightM(),
        getPosition: d => d.p,
        getElevation: d => MIN_COLUMN_FRACTION + (1 - MIN_COLUMN_FRACTION) * norm(d.v),
        getFillColor: d => lut[Math.round(norm(d.v) * 255)],
        material: { ambient: 0.6, diffuse: 0.6, shininess: 24 },
        updateTriggers: { getElevation: [lo, hi], getFillColor: [lo, hi] },
      })],
    });
  }

  async function load() {
    if (!state) return;
    state.abort?.abort();
    const abort = state.abort = new AbortController();
    const { app_label, model_name, raster_id } = state.cfg;
    const b = map.getBounds();
    const bbox = [b.getWest(), b.getSouth(), b.getEast(), b.getNorth()].join(',');
    const idParam = raster_id ? `id=${raster_id}&` : '';
    setStatus('Loading…');
    try {
      const resp = await fetch(
        `/api/raster/${app_label}/${model_name}/blocks/?${idParam}size=${sizeCells()}&bbox=${bbox}`,
        { signal: abort.signal });
      const body = await resp.json();
      if (!resp.ok) throw new Error(body.error || resp.statusText);
      state.data = body;
      state.lut = buildLut(body.legend);
      state.rows = body.lng.map((lng, i) => ({ p: [lng, body.lat[i]], v: body.value[i] }));
      updateReadouts();
      draw();
      setStatus(`${body.value.length.toLocaleString()} columns`
        + (body.legend ? ` · ${body.legend.min.toFixed(1)}–${body.legend.max.toFixed(1)} ${body.legend.unit || ''}` : ''));
    } catch (e) {
      if (e.name === 'AbortError') return;
      state.data = null;
      draw();
      setStatus(e.message, true);
    }
  }

  function scheduleReload() {
    clearTimeout(reloadTimer);
    reloadTimer = setTimeout(load, RELOAD_DEBOUNCE_MS);
  }

  function open(key) {
    const cfg = availableLayers.find(l => l.key === key);
    if (!cfg || cfg.layer_type !== 'raster' || !ensureOverlay()) return;
    state = { key, cfg, data: null, lut: null, rows: [], abort: null };
    $('raster3d-title').textContent = `3D · ${cfg.display_name}`;
    $('raster3d-card').classList.add('visible');
    updateReadouts();
    if (map.getPitch() < 30) map.easeTo({ pitch: VIEW_PITCH, duration: 800 });
    map.on('moveend', scheduleReload);
    load();
  }

  function close() {
    clearTimeout(reloadTimer);
    state?.abort?.abort();
    map.off('moveend', scheduleReload);
    state = null;
    overlay?.setProps({ layers: [] });
    $('raster3d-card')?.classList.remove('visible');
  }

  document.addEventListener('DOMContentLoaded', () => {
    $('raster3d-size')?.setAttribute('max', MAX_SIZE_CELLS);
    $('raster3d-size') && ($('raster3d-size').value = DEFAULT_SIZE_CELLS);
    $('raster3d-height') && ($('raster3d-height').value = DEFAULT_HEIGHT_M);
    $('raster3d-card-close')?.addEventListener('click', close);
    // Container size changes the data: refetch on release; the others redraw live.
    $('raster3d-size')?.addEventListener('input', updateReadouts);
    $('raster3d-size')?.addEventListener('change', load);
    ['raster3d-height', 'raster3d-opacity'].forEach(id =>
      $(id)?.addEventListener('input', () => { updateReadouts(); draw(); }));
  });

  // A raster removed from the map (e.g. replaced LST) takes its 3D view along.
  window.addEventListener('crosstwin:layer-removed', e => { if (state?.key === e.detail?.key) close(); });

  window.Raster3D = { open, close };
})();
