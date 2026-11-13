// ============================================================
// UnservedWater.js — homes without water supply, on the map
// While the Water Supply tool is active, every home with residents that no
// pipe reaches (outside the city's service buffer, the complement of
// UsersLocation.populationServed) gets a floating water drop with a
// prohibited sign. Data: /watersupply/unserved/?bbox= (users.unserved_properties).
// Nearby homes are clustered; a cluster's drop is larger and shows the count.
// Depends on: map (Map_init.js), repositionDynamicLegends (Layers.js)
// ============================================================
(function () {
  const SOURCE = 'unserved-homes';
  const SHADOW = 'unserved-homes-shadow';
  const DROP = 'unserved-homes-drop';
  const ICON = 'unserved-water-drop';
  const LEGEND_ID = 'legend-unserved-water';
  const MIN_ZOOM = 10;          // below this the request would cover several cities
  const FLOAT_PX = 4;           // bob amplitude
  const FLOAT_PERIOD_MS = 2400;
  const FLOAT_BASE_PX = 8;      // drop always hovers this high above its home

  let active = false;
  let controller = null;
  let reloadTimer = null;
  let frame = null;
  let lastData = { type: 'FeatureCollection', features: [] };

  const reducedMotion = () => window.matchMedia &&
    window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  // ---- Icon: blue drop, red prohibition ring + slash ----------------------
  function dropImage() {
    const ratio = 2, w = 48, h = 56;
    const canvas = document.createElement('canvas');
    canvas.width = w * ratio;
    canvas.height = h * ratio;
    const ctx = canvas.getContext('2d');
    ctx.scale(ratio, ratio);

    // drop: tip at the top, round body below
    const cx = 24, cy = 33, r = 15;
    ctx.beginPath();
    ctx.moveTo(cx, 4);
    ctx.bezierCurveTo(cx + 4, 13, cx + r, 21, cx + r, cy);
    ctx.arc(cx, cy, r, 0, Math.PI, false);
    ctx.bezierCurveTo(cx - r, 21, cx - 4, 13, cx, 4);
    ctx.closePath();
    const fill = ctx.createLinearGradient(0, 4, 0, cy + r);
    fill.addColorStop(0, '#7cc6ff');
    fill.addColorStop(1, '#1f6fd1');
    ctx.fillStyle = fill;
    ctx.fill();
    ctx.lineWidth = 2;
    ctx.strokeStyle = '#ffffff';
    ctx.stroke();

    // highlight
    ctx.beginPath();
    ctx.ellipse(cx - 6, cy - 6, 2.5, 5, -0.5, 0, 2 * Math.PI);
    ctx.fillStyle = 'rgba(255,255,255,0.55)';
    ctx.fill();

    // prohibited sign over the body
    const sr = 11;
    ctx.lineWidth = 3.5;
    ctx.strokeStyle = '#ffffff';                   // white outline keeps it legible on blue
    ctx.beginPath();
    ctx.arc(cx, cy, sr, 0, 2 * Math.PI);
    ctx.moveTo(cx - sr * 0.7071, cy - sr * 0.7071);
    ctx.lineTo(cx + sr * 0.7071, cy + sr * 0.7071);
    ctx.stroke();
    ctx.lineWidth = 2.2;
    ctx.strokeStyle = '#e02424';
    ctx.beginPath();
    ctx.arc(cx, cy, sr, 0, 2 * Math.PI);
    ctx.moveTo(cx - sr * 0.7071, cy - sr * 0.7071);
    ctx.lineTo(cx + sr * 0.7071, cy + sr * 0.7071);
    ctx.stroke();

    return { image: ctx.getImageData(0, 0, canvas.width, canvas.height), ratio, url: canvas.toDataURL() };
  }

  let icon = null;
  const getIcon = () => (icon = icon || dropImage());

  // ---- Layers -------------------------------------------------------------
  function ensureLayers() {
    if (typeof map === 'undefined' || !map || !map.isStyleLoaded()) return false;
    if (!map.hasImage(ICON)) {
      const { image, ratio } = getIcon();
      map.addImage(ICON, image, { pixelRatio: ratio });
    }
    if (!map.getSource(SOURCE)) {
      map.addSource(SOURCE, {
        type: 'geojson', data: lastData,
        cluster: true, clusterRadius: 40, clusterMaxZoom: 16,
        clusterProperties: { residents: ['+', ['get', 'residents']] },
      });
    }
    if (!map.getLayer(SHADOW)) {
      map.addLayer({
        id: SHADOW, type: 'circle', source: SOURCE,
        paint: {
          'circle-color': '#0b2545',
          'circle-opacity': 0.3,
          'circle-blur': 1,
          'circle-pitch-alignment': 'map',
          'circle-radius': ['case', ['has', 'point_count'], 9, 6],
        },
      });
    }
    if (!map.getLayer(DROP)) {
      map.addLayer({
        id: DROP, type: 'symbol', source: SOURCE,
        layout: {
          'icon-image': ICON,
          'icon-anchor': 'bottom',
          'icon-allow-overlap': true,
          'icon-ignore-placement': true,
          'icon-size': ['case', ['has', 'point_count'],
            ['interpolate', ['linear'], ['get', 'point_count'], 2, 0.8, 100, 1.1, 1000, 1.4],
            0.6],
          'text-field': ['case', ['has', 'point_count'], ['get', 'point_count_abbreviated'], ''],
          'text-size': 11,
          'text-anchor': 'top',
          'text-offset': [0, 0.3],
          'text-allow-overlap': true,
        },
        paint: {
          'icon-translate': [0, -FLOAT_BASE_PX],
          'text-color': '#7a1010',
          'text-halo-color': '#ffffff',
          'text-halo-width': 1.5,
        },
      });
    }
    return true;
  }

  function setVisible(visible) {
    if (typeof map === 'undefined' || !map) return;
    [SHADOW, DROP].forEach(id => {
      if (map.getLayer(id)) map.setLayoutProperty(id, 'visibility', visible ? 'visible' : 'none');
    });
  }

  // ---- Floating -----------------------------------------------------------
  function animate(now) {
    if (!active || !map.getLayer(DROP)) { frame = null; return; }
    const phase = Math.sin((2 * Math.PI * now) / FLOAT_PERIOD_MS);   // -1..1
    const lift = FLOAT_BASE_PX + FLOAT_PX * (1 + phase) / 2;
    map.setPaintProperty(DROP, 'icon-translate', [0, -lift]);
    // shadow shrinks and fades as the drop rises
    const k = (1 + phase) / 2;
    map.setPaintProperty(SHADOW, 'circle-opacity', 0.32 - 0.14 * k);
    frame = requestAnimationFrame(animate);
  }

  function startFloat() {
    if (frame || reducedMotion()) return;
    frame = requestAnimationFrame(animate);
  }

  function stopFloat() {
    if (frame) cancelAnimationFrame(frame);
    frame = null;
  }

  // ---- Data ---------------------------------------------------------------
  function bboxParam() {
    const b = map.getBounds();
    const clamp = (v, lo, hi) => Math.min(hi, Math.max(lo, v));
    return [clamp(b.getWest(), -180, 180), clamp(b.getSouth(), -90, 90),
            clamp(b.getEast(), -180, 180), clamp(b.getNorth(), -90, 90)]
      .map(v => v.toFixed(5)).join(',');
  }

  function setData(data) {
    lastData = data;
    ensureLayers();
    map.getSource(SOURCE)?.setData(data);
    updateLegend();
  }

  async function reload() {
    if (!active || typeof map === 'undefined' || !map) return;
    if (map.getZoom() < MIN_ZOOM) { setData({ type: 'FeatureCollection', features: [] }); return; }
    controller?.abort();
    controller = new AbortController();
    try {
      const res = await fetch(`/watersupply/unserved/?bbox=${bboxParam()}`, { signal: controller.signal });
      if (!res.ok) return;
      const data = await res.json();
      if (active) setData(data);
    } catch (err) {
      if (err.name !== 'AbortError') console.warn('Unserved homes:', err);
    }
  }

  function scheduleReload() {
    clearTimeout(reloadTimer);
    reloadTimer = setTimeout(reload, 400);
  }

  // ---- Legend -------------------------------------------------------------
  function updateLegend() {
    let el = document.getElementById(LEGEND_ID);
    if (!active) {
      el?.remove();
      if (typeof repositionDynamicLegends === 'function') repositionDynamicLegends();
      return;
    }
    if (!el) {
      el = document.createElement('div');
      el.id = LEGEND_ID;
      el.className = 'map-legend dynamic-legend';
      document.getElementById('legend-stack')?.appendChild(el);
    }
    const homes = lastData.features.length;
    const people = lastData.features.reduce((s, f) => s + (Number(f.properties.residents) || 0), 0);
    const note = map.getZoom() < MIN_ZOOM
      ? 'Zoom in to see them'
      : `${homes.toLocaleString()} homes, ≈ ${Math.round(people).toLocaleString()} residents in view`;
    el.innerHTML = `
      <div class="legend-title">Without water supply</div>
      <div class="legend-list">
        <div class="legend-item">
          <img src="${getIcon().url}" alt="" style="width:18px;height:21px;margin-right:6px">
          <span class="legend-label">No pipe within the service buffer</span>
        </div>
        <div class="legend-label" style="opacity:.75">${note}</div>
      </div>`;
    if (typeof repositionDynamicLegends === 'function') repositionDynamicLegends();
  }

  // ---- Interaction --------------------------------------------------------
  function bindInteractions() {
    map.on('click', DROP, (e) => {
      const f = e.features && e.features[0];
      if (!f) return;
      if (f.properties.point_count) {
        map.getSource(SOURCE).getClusterExpansionZoom(f.properties.cluster_id, (err, zoom) => {
          if (!err) map.easeTo({ center: f.geometry.coordinates, zoom });
        });
        return;
      }
      const residents = Number(f.properties.residents) || 0;
      new mapboxgl.Popup({ offset: 24 })
        .setLngLat(f.geometry.coordinates)
        .setHTML(`<strong>No water supply</strong><br>
          ≈ ${residents.toFixed(1)} residents<br>
          No pipe within ${Math.round(f.properties.buffer_m)} m`)
        .addTo(map);
    });
    map.on('mouseenter', DROP, () => { map.getCanvas().style.cursor = 'pointer'; });
    map.on('mouseleave', DROP, () => { map.getCanvas().style.cursor = ''; });
  }

  // ---- Activation ---------------------------------------------------------
  function setActive(on) {
    if (on === active) return;
    active = on;
    if (on) {
      if (ensureLayers()) setVisible(true);
      else map.once('idle', () => { if (active && ensureLayers()) setVisible(true); });
      startFloat();
      reload();
    } else {
      controller?.abort();
      stopFloat();
      setVisible(false);
    }
    updateLegend();
  }

  function syncWithToolbar() {
    const tool = document.querySelector('.tool-button.active')?.dataset.tool;
    setActive(tool === 'water');
  }

  function init() {
    if (typeof map === 'undefined' || !map) { setTimeout(init, 300); return; }
    document.getElementById('toolbar')?.addEventListener('click', () => setTimeout(syncWithToolbar, 0));
    // a basemap switch drops custom sources and images
    map.on('style.load', () => {
      if (!active) return;
      ensureLayers();
      setVisible(true);
      startFloat();
    });
    map.on('moveend', () => { if (active) scheduleReload(); });
    ['feature-saved', 'backup-restored'].forEach(name =>
      document.body.addEventListener(name, () => { if (active) scheduleReload(); }));
    window.matchMedia?.('(prefers-reduced-motion: reduce)')
      .addEventListener?.('change', () => { if (reducedMotion()) stopFloat(); else if (active) startFloat(); });
    bindInteractions();
    syncWithToolbar();
  }

  document.addEventListener('DOMContentLoaded', init);
})();
