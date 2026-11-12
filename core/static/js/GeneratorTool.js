// ============================================================
// GeneratorTool.js — Neighbourhood generator card (Actions menu, #generatorToolBtn).
// Draw an outline (or pick a housing project), choose a typology and a few
// sizes, and see the generated streets, plots and buildings live
// (POST builtup/generator/preview/, a what-if: nothing is stored). Staff can
// store it on a housing project as completed (POST builtup/generator/commit/):
// housing/signals.py then writes real streets, buildings and dwellings, and the
// usual receivers update land cover, the DSM, canyons and urbanisation
// (DAG edges New_Units -> Buildings, Streets -> Buildings, Streets -> LandCover).
// Every preview also returns the site check (builtup/calculations/site.py:
// Natura 2000 / NNN cut out in red hatching, zoning and other warnings in
// amber) and the indicative Bbl checks (builtup/calculations/regulations.py);
// a blocking finding disables Store.
// Geometry: builtup/calculations/generative.py.
// Depends on: Config.js (map, loadedLayers), Layers.js (reloadLayer,
// refreshDsmAfterEdit), Editing.js (isEditing), mapbox-gl-draw, Draggable.js.
// ============================================================

(function () {
  'use strict';

  const SOURCE = 'generator-preview';
  const LAYER_IDS = ['generator-blocks', 'generator-plots', 'generator-streets', 'generator-buildings',
    'generator-excluded', 'generator-excluded-line', 'generator-warning'];
  const HATCH = 'generator-hatch';
  // Typology each style starts from (builtup/calculations/generative.py::STYLES).
  const STYLE_TYPOLOGY = { plain: null, vinex: 'row', garden_city: 'detached', urban_block: 'perimeter', modernist: 'slab' };
  const SEVERITY_ICON = { ok: '✓', info: 'ℹ', warn: '⚠', excluded: '✕', block: '✕' };
  const PREVIEW_DELAY_MS = 250;
  // Inputs sent as generator parameters (builtup/calculations/generative.py::COMMON / TYPOLOGIES).
  const PARAM_INPUTS = ['street_width', 'block_length', 'block_depth', 'plot_width', 'plot_depth',
    'building_depth', 'floors', 'front_setback', 'target_units', 'angle_deg', 'unit_gfa_m2'];
  // Fields that keep their value when the typology changes; the rest fall back to the new typology's defaults.
  const SHARED_INPUTS = new Set(['street_width', 'target_units', 'angle_deg', 'unit_gfa_m2']);
  const RELOAD_AFTER_COMMIT = ['builtup.Street', 'builtup.StreetCanyon', 'builtup.Property',
    'physicalEnv.LandCoverVector', 'housing.HousingProject'];

  function init() {
    const card = document.getElementById('generator-card');
    const openBtn = document.getElementById('generatorToolBtn');
    if (!card || !openBtn) return;

    const $ = (id) => document.getElementById(id);
    const el = {
      close: $('generator-card-close'),
      project: $('generator-project'),
      draw: $('generator-draw'),
      typology: $('generator-typology'),
      style: $('generator-style'),
      pattern: $('generator-street_pattern'),
      dwelling: $('generator-dwelling_mode'),
      variation: $('generator-variation'),
      variationValue: $('generator-variation-value'),
      seed: $('generator-seed'),
      shuffle: $('generator-shuffle'),
      site: $('generator-site'),
      rules: $('generator-rules'),
      ring: $('generator-ring'),
      name: $('generator-name'),
      year: $('generator-year'),
      metrics: $('generator-metrics'),
      commit: $('generator-commit'),
      remove: $('generator-remove'),
      status: $('generator-status'),
    };
    const inputs = Object.fromEntries(PARAM_INPUTS.map(name => [name, $(`generator-${name}`)]));
    const canCommit = card.dataset.canCommit === '1';

    let projects = [];
    let outline = null;           // GeoJSON geometry, WGS84
    let toolDraw = null;          // own MapboxDraw instance, separate from Editing.js
    let timer = null;
    let request = 0;
    let busy = false;
    let blocked = '';             // reason Store is disabled (site check / Bbl), '' when allowed
    let variationTouched = false; // the slider overrides the style's variation only once moved

    const csrfToken = () => card.querySelector('[name=csrfmiddlewaretoken]')?.value || '';

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

    function params() {
      const out = {
        style: el.style.value, typology: el.typology.value, ring_street: el.ring.checked,
        dwelling_mode: el.dwelling.value, seed: Number(el.seed.value) || 1,
      };
      if (el.pattern.value) out.street_pattern = el.pattern.value;
      if (variationTouched) out.variation = Number(el.variation.value) / 100;
      PARAM_INPUTS.forEach(name => {
        const value = inputs[name]?.value.trim();
        if (value) out[name] = Number(value);
      });
      return out;
    }

    function selectedProject() {
      return projects.find(p => String(p.id) === el.project.value) || null;
    }

    // ── map layers ────────────────────────────────────────────
    function hatchImage() {
      // 16 x 16 px diagonal red stripes for protected nature that was cut out
      const size = 16, data = new Uint8Array(size * size * 4);
      for (let y = 0; y < size; y++) {
        for (let x = 0; x < size; x++) {
          const on = (x + y) % 8 < 2;
          data.set(on ? [200, 30, 40, 230] : [200, 30, 40, 40], (y * size + x) * 4);
        }
      }
      return { width: size, height: size, data };
    }

    function ensureLayers() {
      if (map.getSource(SOURCE)) return;
      if (!map.hasImage(HATCH)) map.addImage(HATCH, hatchImage());
      map.addSource(SOURCE, { type: 'geojson', data: { type: 'FeatureCollection', features: [] } });
      map.addLayer({ id: 'generator-excluded', type: 'fill', source: SOURCE, filter: ['==', ['get', 'kind'], 'excluded'],
        paint: { 'fill-pattern': HATCH } });
      map.addLayer({ id: 'generator-excluded-line', type: 'line', source: SOURCE, filter: ['==', ['get', 'kind'], 'excluded'],
        paint: { 'line-color': '#c81e28', 'line-width': 2 } });
      map.addLayer({ id: 'generator-warning', type: 'line', source: SOURCE, filter: ['==', ['get', 'kind'], 'warning'],
        paint: { 'line-color': '#e0a100', 'line-width': 2, 'line-dasharray': [2, 1.5] } });
      map.addLayer({ id: 'generator-blocks', type: 'fill', source: SOURCE, filter: ['==', ['get', 'kind'], 'block'],
        paint: { 'fill-color': '#d9c8a9', 'fill-opacity': 0.25 } });
      map.addLayer({ id: 'generator-plots', type: 'line', source: SOURCE, filter: ['==', ['get', 'kind'], 'plot'],
        paint: { 'line-color': '#8a7a5c', 'line-width': 0.6, 'line-opacity': 0.7 } });
      map.addLayer({ id: 'generator-streets', type: 'line', source: SOURCE, filter: ['==', ['get', 'kind'], 'street'],
        layout: { 'line-cap': 'butt', 'line-join': 'miter' },
        paint: { 'line-color': '#6b6f76',
          // Street width in metres as pixels: 2^zoom / 96 376 px per metre (Web Mercator at ~52° N)
          'line-width': ['interpolate', ['exponential', 2], ['zoom'], 12, ['*', ['get', 'width'], 0.0425], 20, ['*', ['get', 'width'], 10.88]] } });
      map.addLayer({ id: 'generator-buildings', type: 'fill-extrusion', source: SOURCE, filter: ['==', ['get', 'kind'], 'building'],
        paint: { 'fill-extrusion-color': '#e07a5f', 'fill-extrusion-height': ['get', 'height_m'],
          'fill-extrusion-opacity': 0.85 } });
    }

    function showLayout(collection) {
      ensureLayers();
      map.getSource(SOURCE).setData(collection);
    }

    function clearLayers() {
      LAYER_IDS.forEach(id => { if (map.getLayer(id)) map.removeLayer(id); });
      if (map.getSource(SOURCE)) map.removeSource(SOURCE);
    }

    // ── drawing ───────────────────────────────────────────────
    function onDraw() {
      const feature = toolDraw?.getAll().features.find(f => f.geometry.type === 'Polygon');
      if (!feature) return;
      outline = feature.geometry;
      schedulePreview();
    }

    function startDraw() {
      if (typeof isEditing === 'function' && isEditing()) {
        setStatus('Finish or cancel the open map edit first.', 'warn');
        return;
      }
      if (!toolDraw) {
        toolDraw = new MapboxDraw({ displayControlsDefault: false, userProperties: false });
        map.addControl(toolDraw, 'top-left');
        map.on('draw.create', onDraw);
        map.on('draw.update', onDraw);
      }
      toolDraw.deleteAll();
      el.project.value = '';
      outline = null;
      toolDraw.changeMode('draw_polygon');
      setStatus('Click to place the outline corners; double-click to finish. Drag its corners to reshape it.');
      updateButtons();
    }

    function stopDraw() {
      if (!toolDraw) return;
      map.off('draw.create', onDraw);
      map.off('draw.update', onDraw);
      try { map.removeControl(toolDraw); } catch (e) { /* style already gone */ }
      toolDraw = null;
    }

    function editableOutline(geometry) {
      if (!toolDraw) startDraw();
      toolDraw.deleteAll();
      const polygon = geometry.type === 'MultiPolygon'
        ? { type: 'Polygon', coordinates: geometry.coordinates[0] } : geometry;
      const [id] = toolDraw.add({ type: 'Feature', properties: {}, geometry: polygon });
      toolDraw.changeMode('direct_select', { featureId: id });
      outline = polygon;
    }

    // ── preview / metrics ─────────────────────────────────────
    function schedulePreview() {
      clearTimeout(timer);
      timer = setTimeout(preview, PREVIEW_DELAY_MS);
    }

    const fmt = (n, digits = 0) => (n == null ? '–' : Number(n).toLocaleString(undefined, { maximumFractionDigits: digits }));

    function renderMetrics(m) {
      const target = m.target_units ? ` of ${fmt(m.target_units)} wanted (${m.units_vs_target >= 0 ? '+' : ''}${fmt(m.units_vs_target)})` : '';
      const site = m.outline_m2 && m.site_m2 < m.outline_m2 - 1
        ? `${fmt((m.site_m2 || 0) / 10000, 2)} of ${fmt(m.outline_m2 / 10000, 2)} ha buildable`
        : `${fmt((m.site_m2 || 0) / 10000, 2)} ha`;
      el.metrics.replaceChildren(...[
        `${fmt(m.units)} dwellings${target} in ${fmt(m.buildings)} buildings`,
        `${fmt(m.dwellings_per_building, 1)} dwellings per building (max ${fmt(m.max_dwellings_per_building)}) · ` +
          `${fmt(m.single_family)} single-family, ${fmt(m.multi_family)} with flats`,
        `FSI ${fmt(m.far, 2)} · GSI ${fmt(m.gsi, 2)} · ${fmt(m.density_units_ha, 1)} dwellings/ha`,
        `Streets ${fmt(m.street_length_m)} m, ${fmt((m.street_share || 0) * 100, 0)} % of ${site}`,
      ].map(text => { const div = document.createElement('div'); div.textContent = text; return div; }));
    }

    function renderFindings(container, title, findings) {
      const rows = (findings || []).map(f => {
        const row = document.createElement('div');
        row.className = `generator-finding ${f.severity}`;
        row.title = f.source || '';
        const icon = document.createElement('span');
        icon.className = 'generator-finding-icon';
        icon.textContent = SEVERITY_ICON[f.severity] || '•';
        const text = document.createElement('span');
        text.textContent = f.message;
        row.append(icon, text);
        return row;
      });
      const head = document.createElement('div');
      head.className = 'generator-findings-title';
      head.textContent = title;
      container.replaceChildren(head, ...rows);
    }

    function blockingReason(data) {
      const blocks = [...(data.site?.findings || []), ...(data.regulations || [])].filter(f => f.severity === 'block');
      return blocks.map(f => f.message).join(' ');
    }

    function showDefaults(resolved) {
      PARAM_INPUTS.forEach(name => {
        const input = inputs[name];
        if (!input) return;
        const value = resolved[name];
        input.placeholder = value == null ? 'auto' : String(Math.round(value * 100) / 100);
      });
      if (!variationTouched && resolved.variation != null) {
        el.variation.value = Math.round(resolved.variation * 100);
        el.variationValue.textContent = `${el.variation.value} %`;
      }
    }

    async function preview() {
      if (!outline) { updateButtons(); return; }
      const token = ++request;
      setStatus('Generating…', 'working');
      try {
        const data = await readJson(await fetch(card.dataset.previewUrl, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken() },
          body: JSON.stringify({ outline, params: params() }),
        }));
        if (token !== request) return;
        showLayout(data.layout);
        renderMetrics(data.metrics);
        showDefaults(data.params);
        renderFindings(el.site, 'Site check', data.site?.findings);
        renderFindings(el.rules, 'Building rules (indicative)', data.regulations);
        blocked = blockingReason(data);
        setStatus(blocked ? `Cannot be stored: ${blocked}` : 'Preview only: nothing is stored until you press Store.',
          blocked ? 'error' : '');
      } catch (error) {
        if (token !== request) return;
        blocked = '';
        setStatus(error.message, 'error');
      }
      updateButtons();
    }

    // ── projects ──────────────────────────────────────────────
    async function loadProjects() {
      try {
        const data = await readJson(await fetch(card.dataset.projectsUrl));
        projects = data.projects || [];
      } catch (error) {
        setStatus(error.message, 'error');
        return;
      }
      const current = el.project.value;
      el.project.replaceChildren(new Option('New outline (draw it)', ''),
        ...projects.map(p => new Option(`${p.name} · ${p.units} units · ${p.status}`, p.id)));
      el.project.value = projects.some(p => String(p.id) === current) ? current : '';
    }

    function pickProject() {
      const project = selectedProject();
      if (!project) { startDraw(); return; }
      const saved = project.params || {};
      if (saved.style) el.style.value = saved.style;
      if (saved.typology) el.typology.value = saved.typology;
      el.pattern.value = saved.street_pattern || '';
      el.dwelling.value = saved.dwelling_mode || 'auto';
      el.seed.value = saved.seed || 1;
      variationTouched = saved.variation != null;
      if (variationTouched) {
        el.variation.value = Math.round(saved.variation * 100);
        el.variationValue.textContent = `${el.variation.value} %`;
      }
      el.ring.checked = saved.ring_street !== false;
      PARAM_INPUTS.forEach(name => {
        if (inputs[name]) inputs[name].value = saved[name] == null ? '' : saved[name];
      });
      if (!saved.target_units && project.units) inputs.target_units.value = project.units;
      el.name.value = project.name || '';
      el.year.value = project.year_expected_completion || '';
      editableOutline(project.outline);
      el.project.value = String(project.id);
      schedulePreview();
    }

    function updateButtons() {
      const project = selectedProject();
      el.commit.hidden = el.remove.hidden = !canCommit;
      el.commit.disabled = busy || !outline || !!blocked;
      el.commit.title = blocked ? `Cannot be stored: ${blocked}` : '';
      el.commit.textContent = project ? 'Store on this project (completed)' : 'Store as a new completed project';
      el.remove.disabled = busy || !(project && project.status === 'completed' && project.params);
    }

    function afterStore() {
      // Same events as a map edit: reload layers, the DSM and the backup bar.
      document.body.dispatchEvent(new CustomEvent('feature-saved', { detail: { layer: 'builtup.Building' } }));
      RELOAD_AFTER_COMMIT.forEach(key => {
        if (typeof loadedLayers !== 'undefined' && loadedLayers[key] && typeof reloadLayer === 'function') reloadLayer(key);
      });
    }

    async function post(url, body) {
      return readJson(await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken() },
        body: JSON.stringify(body),
      }));
    }

    async function commit() {
      if (busy || !outline) return;
      busy = true;
      updateButtons();
      setStatus('Storing streets, buildings and dwellings…', 'working');
      try {
        const project = selectedProject();
        const data = await post(card.dataset.commitUrl, {
          outline, params: params(), project_id: project?.id || null,
          name: el.name.value.trim(), year_expected_completion: el.year.value || null,
        });
        const r = data.result || {};
        await loadProjects();
        el.project.value = String(data.project.id);
        setStatus(`Stored on "${data.project.name}": ${fmt(r.streets)} streets, ${fmt(r.buildings)} buildings, ` +
          `${fmt(r.dwellings)} dwellings. Restore in the backup bar undoes it.`, 'ok');
        clearLayers();
        afterStore();
      } catch (error) {
        setStatus(error.message, 'error');
      }
      busy = false;
      updateButtons();
    }

    async function remove() {
      const project = selectedProject();
      if (busy || !project) return;
      busy = true;
      updateButtons();
      setStatus('Removing the generated rows…', 'working');
      try {
        await post(card.dataset.removeUrl, { project_id: project.id });
        await loadProjects();
        el.project.value = String(project.id);
        setStatus(`"${project.name}" is planned again; its generated streets and buildings are gone.`, 'ok');
        afterStore();
      } catch (error) {
        setStatus(error.message, 'error');
      }
      busy = false;
      updateButtons();
    }

    // ── open / close ──────────────────────────────────────────
    let styleHooked = false;
    function open() {
      if (!styleHooked) {
        // A basemap switch drops custom sources: draw the last preview again.
        map.on('style.load', () => { if (card.classList.contains('visible') && outline) schedulePreview(); });
        styleHooked = true;
      }
      ['lst-card', 'svf-card', 'solweig-card', 'degurba-card'].forEach(id => $(id)?.classList.remove('visible'));
      card.classList.add('visible');
      if (typeof setActionsMenuOpen === 'function') setActionsMenuOpen(false);
      loadProjects().then(updateButtons);
      if (!outline) setStatus('Draw an outline or pick a housing project.');
    }

    function close() {
      card.classList.remove('visible');
      blocked = '';
      el.site.replaceChildren();
      el.rules.replaceChildren();
      clearTimeout(timer);
      request++;
      stopDraw();
      clearLayers();
      outline = null;
    }

    openBtn.addEventListener('click', open);
    el.close.addEventListener('click', close);
    el.draw.addEventListener('click', startDraw);
    el.project.addEventListener('change', pickProject);
    const resetTypologyFields = () =>
      PARAM_INPUTS.forEach(name => { if (!SHARED_INPUTS.has(name) && inputs[name]) inputs[name].value = ''; });
    el.typology.addEventListener('change', () => { resetTypologyFields(); schedulePreview(); });
    el.style.addEventListener('change', () => {
      // A style brings its own typology, street pattern and variation; typed sizes start over.
      const typology = STYLE_TYPOLOGY[el.style.value];
      if (typology) el.typology.value = typology;
      el.pattern.value = '';
      variationTouched = false;
      resetTypologyFields();
      schedulePreview();
    });
    el.pattern.addEventListener('change', schedulePreview);
    el.dwelling.addEventListener('change', schedulePreview);
    el.seed.addEventListener('input', schedulePreview);
    el.variation.addEventListener('input', () => {
      variationTouched = true;
      el.variationValue.textContent = `${el.variation.value} %`;
      schedulePreview();
    });
    el.shuffle.addEventListener('click', () => {
      // A new seed redraws the variation; the seed is stored with the project, so a layout can be repeated.
      el.seed.value = 1 + Math.floor(Math.random() * 99999);
      schedulePreview();
    });
    el.ring.addEventListener('change', schedulePreview);
    Object.values(inputs).forEach(input => input?.addEventListener('input', schedulePreview));
    el.commit.addEventListener('click', commit);
    el.remove.addEventListener('click', remove);
    // Other tools close this card by removing .visible: drop the preview with it.
    new MutationObserver(() => {
      if (!card.classList.contains('visible') && (toolDraw || map.getSource?.(SOURCE))) close();
    }).observe(card, { attributes: true, attributeFilter: ['class'] });

    if (typeof makeDraggable === 'function' && window.matchMedia('(min-width: 769px)').matches) {
      makeDraggable(card, '.lst-card-header');
    }
  }

  document.addEventListener('DOMContentLoaded', init);
})();
