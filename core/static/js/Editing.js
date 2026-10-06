// ============================================================
// Editing.js — visual editing of layer objects (docs/MAP_EDITING.md)
// The attribute form is an HTMX partial in #panel-body (mainMap/editing.py);
// this file adds the Mapbox GL Draw tools for its geometry, keeps the hidden
// geometry input in sync, and reloads layers after a save, delete or restore.
// Depends on: Config.js (map), Layers.js (loadedLayers, featurePopup,
// reloadLayer), the mapbox-gl-draw plugin, htmx.
// ============================================================

let draw = null;
// { key, pk, geomType, input, editor, hidden: [{ id, filter }] } while the editor is open
let editState = null;
let drawEventsBound = false;

function isEditing() {
  return editState !== null;
}

function _featureUrl(key, pk) {
  const [app, model] = key.split('.');
  return `/api/layers/${app}/${model}/features/${pk === null || pk === undefined ? 'new' : pk}/`;
}

function _openEditorPanel(url) {
  featurePopup?.remove();
  htmx.ajax('GET', url, { target: '#panel-body', swap: 'innerHTML' });
}

/** Popup "Edit" button: form in the side panel, shape editable on the map. */
function startEdit(key, pk) {
  if (editState) stopEdit();
  _openEditorPanel(_featureUrl(key, pk));
}

/** Layers panel "＋" button: draw a new shape, then fill in the form. */
function startCreate(key) {
  if (editState) stopEdit();
  _openEditorPanel(_featureUrl(key, null));
}

// Draw mode for a new shape, from the model field's geometry type (MULTIPOLYGON, POINT, ...)
function _drawModeFor(geomType) {
  if (geomType.includes('POINT')) return 'draw_point';
  if (geomType.includes('LINE')) return 'draw_line_string';
  return 'draw_polygon';
}

function _bindDrawEvents() {
  if (drawEventsBound) return;
  drawEventsBound = true;
  // Map-level listeners survive setStyle(), so bind them once.
  map.on('draw.create', _writeGeometry);
  map.on('draw.update', _writeGeometry);
}

/**
 * Copy the drawn shape into the form's hidden geometry input as GeoJSON,
 * wrapping Polygon -> MultiPolygon etc. when the model field is a Multi*
 * type (Draw produces single geometries; the server checks the type).
 */
function _writeGeometry() {
  if (!editState || !draw) return;
  const feature = draw.getAll().features[0];
  if (!feature) return;
  let geometry = feature.geometry;
  if (editState.geomType.startsWith('MULTI') && !geometry.type.startsWith('Multi')) {
    geometry = { type: `Multi${geometry.type}`, coordinates: [geometry.coordinates] };
  }
  editState.input.value = JSON.stringify(geometry);
}

/**
 * Hide the object being edited on its own layer, so the original (an
 * extruded building in particular) doesn't cover the edit handles.
 */
function _hideOriginal(key, pk) {
  const entry = loadedLayers[key];
  if (!entry || pk === null) return [];
  return entry.layerIds.filter(id => map.getLayer(id)).map(id => {
    const filter = map.getFilter(id) || null;
    const notThis = ['!=', ['get', 'id'], Number(pk)];
    map.setFilter(id, filter ? ['all', filter, notThis] : notThis);
    return { id, filter };
  });
}

function _restoreOriginal() {
  for (const { id, filter } of editState?.hidden || []) {
    if (map.getLayer(id)) map.setFilter(id, filter);
  }
}

function _removeDrawControl() {
  if (!draw) return;
  // A basemap switch removes Draw's layers with the style; don't let that throw.
  try { map.removeControl(draw); } catch (e) { /* style already gone */ }
  draw = null;
}

/** Called when a #feature-editor appears in #panel-body (first load or after a save). */
function _attachEditor(editor) {
  const key = editor.dataset.layerKey;
  const pk = editor.dataset.pk === '' ? null : editor.dataset.pk;
  const geomType = editor.dataset.geomType;
  const input = editor.querySelector(`[name="${editor.dataset.geomField}"]`);
  const geojsonEl = editor.querySelector('#feature-editor-geojson');
  const geometry = geojsonEl ? JSON.parse(geojsonEl.textContent) : null;

  if (editState) _restoreOriginal();
  _removeDrawControl();
  _bindDrawEvents();

  draw = new MapboxDraw({ displayControlsDefault: false, userProperties: false });
  map.addControl(draw, 'top-left');
  // Draw only wires up its mouse handlers once map.loaded() is true, which
  // needs a rendered frame; ask for one in case nothing else is moving.
  map.triggerRepaint();
  editState = { key, pk, geomType, input, editor, hidden: _hideOriginal(key, pk) };

  document.getElementById('panel-title').textContent = 'EDIT FEATURE';
  if (map.getPitch() > 0) map.easeTo({ pitch: 0, duration: 400 });

  if (geometry) {
    const [id] = draw.add({ type: 'Feature', properties: {}, geometry });
    // direct_select drags vertices; points have none, so they move in simple_select
    if (geomType.includes('POINT')) draw.changeMode('simple_select', { featureIds: [id] });
    else draw.changeMode('direct_select', { featureId: id });
  } else {
    draw.changeMode(_drawModeFor(geomType));
  }
}

/**
 * Leave edit mode: remove the drawing tools and show the original again.
 * Called on cancel, after a delete, when the panel is closed or its content
 * replaced, and before a basemap switch.
 */
function stopEdit() {
  if (!editState) return;
  _restoreOriginal();
  _removeDrawControl();
  editState = null;
}

function _cancelEdit() {
  stopEdit();
  document.getElementById('panel-body').innerHTML = '<p class="feature-editor-msg">Edit cancelled. Nothing was saved.</p>';
}

document.addEventListener('DOMContentLoaded', () => {
  const panelBody = document.getElementById('panel-body');
  if (!panelBody) return;

  // Whatever replaces the panel content (an htmx swap, a toolbar click that
  // sets innerHTML, a save that re-renders the form) goes through here.
  new MutationObserver(() => {
    const editor = panelBody.querySelector('#feature-editor');
    if (editor && editor !== editState?.editor) _attachEditor(editor);
    else if (!editor && editState) stopEdit();
  }).observe(panelBody, { childList: true });

  document.getElementById('panel-close')?.addEventListener('click', stopEdit);

  // Buttons in the editor form and the backup bar (no inline handlers)
  document.addEventListener('click', (evt) => {
    const btn = evt.target.closest('[data-editor-action]');
    if (!btn) return;
    const box = btn.closest('form');
    const confirm = box?.querySelector('.feature-editor-confirm, .edit-backup-confirm');
    switch (btn.dataset.editorAction) {
      case 'cancel': _cancelEdit(); break;
      case 'ask-delete':
      case 'ask-restore': if (confirm) confirm.hidden = false; break;
      case 'keep': if (confirm) confirm.hidden = true; break;
    }
  });

  // HX-Trigger events from mainMap/editing.py
  document.body.addEventListener('feature-saved', (evt) => {
    const key = evt.detail?.layer;
    if (!key) return;
    if (loadedLayers[key]) {
      reloadLayer(key);
    } else if (!evt.detail.deleted) {
      // Created with ＋ on a layer that isn't shown yet: show it, so the new object appears
      const toggle = document.getElementById(`toggle-${key}`);
      if (toggle) toggle.checked = true;
      toggleLayerVisibility(key, true);
    }
  });
  document.body.addEventListener('backup-restored', (evt) => {
    // The object in the form may have just been reverted or deleted
    if (editState) _cancelEdit();
    (evt.detail?.layers || []).forEach(reloadLayer);
  });
});

window.isEditing = isEditing;
window.startEdit = startEdit;
window.startCreate = startCreate;
window.stopEdit = stopEdit;
