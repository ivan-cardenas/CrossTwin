// ============================================================
// MapSettings.js — the map's settings panel (staff only).
// Opened from the header's "Map settings" button (#map-settings-btn); the
// body is an HTMX partial from mainMap/settings_views.py with two tabs:
// which layers are editable, and the layer styles. A save answers with an
// HX-Trigger, which this file turns into a map update without a reload:
//   editable-changed {key, enabled} -> the catalog entry's editable flag (popup Edit, ＋)
//   style-changed {kind, key}       -> the restyled layer is removed and added again
// Paint inputs (colours, opacity, width) preview live on the map before saving.
// Depends on: Config.js (CONFIG, map, availableLayers, loadedLayers, layerVisibility),
// Layers.js (addLayer, removeLayer), MapUI.js (renderLayerList), Draggable.js, htmx.
// ============================================================

(function () {
  'use strict';

  async function catalogEntry(key, appLabel) {
    const response = await fetch(`${CONFIG.layersApiUrl}?app_labels=${encodeURIComponent(appLabel)}`);
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const data = await response.json();
    return data.layers.find(l => l.key === key) || null;
  }

  // ---- editable-changed ------------------------------------------------

  async function applyEditable({ key }) {
    const existing = availableLayers.find(l => l.key === key);
    if (!existing) return;   // its app's catalog is not loaded yet; it arrives with the flag
    try {
      const fresh = await catalogEntry(key, existing.app_label);
      if (!fresh) return;
      if (fresh.editable) {
        existing.editable = true;
        existing.edit_geom_type = fresh.edit_geom_type;
      } else {
        delete existing.editable;
        delete existing.edit_geom_type;
      }
      renderLayerList();
    } catch (error) {
      console.error(`Could not refresh the editable flag of "${key}":`, error);
    }
  }

  // ---- style-changed ---------------------------------------------------

  // Remove a layer and add its new catalog entry back, shown again if it was.
  async function readdLayer(oldConfig, newConfig) {
    const key = oldConfig.key;
    const wasLoaded = Boolean(loadedLayers[key]);
    const wasVisible = layerVisibility[key] !== false;
    removeLayer(key);   // also drops its catalog entry and legend
    availableLayers.push(newConfig);
    layerVisibility[key] = wasVisible;
    renderLayerList();
    if (wasLoaded && wasVisible) await addLayer(newConfig, { fit: false });
  }

  async function applyStyle({ kind, key }) {
    try {
      if (kind === 'vector') {
        const existing = availableLayers.find(l => l.key === key);
        if (!existing) return;   // not in the catalog yet: it will arrive with the new style
        const fresh = await catalogEntry(key, existing.app_label);
        if (fresh) await readdLayer(existing, fresh);
      } else {
        // A raster style applies to every raster sharing it: re-add the loaded
        // ones, whose tile URL then carries the new colormap / range.
        const rasters = Object.values(loadedLayers)
          .map(entry => entry.config)
          .filter(config => config && config.layer_type === 'raster');
        for (const config of rasters) await readdLayer(config, config);
      }
    } catch (error) {
      console.error(`Could not apply the new style of "${key}":`, error);
    }
  }

  // ---- live preview ----------------------------------------------------

  function preview(input) {
    const form = input.closest('.settings-style');
    if (!form || form.dataset.kind !== 'vector' || !input.dataset.prop) return;
    const layerId = `${form.dataset.key}-custom-${input.dataset.layerIndex}`;
    if (!map.getLayer(layerId)) return;
    const value = input.type === 'number' ? Number(input.value) : input.value;
    if (input.type === 'number' && (input.value === '' || Number.isNaN(value))) return;
    try {
      map.setPaintProperty(layerId, input.dataset.prop, value);
    } catch (error) {
      console.warn(`Preview of ${input.dataset.prop} failed:`, error);
    }
  }

  // ---- open / close / tabs ---------------------------------------------

  function init() {
    const card = document.getElementById('settings-card');
    const openBtn = document.getElementById('map-settings-btn');
    if (!card || !openBtn) return;
    const body = document.getElementById('settings-card-body');

    function setOpen(open) {
      card.classList.toggle('visible', open);
      openBtn.setAttribute('aria-expanded', String(open));
      // Reloaded on each open, so it shows what other staff changed meanwhile
      if (open) htmx.ajax('GET', card.dataset.url, { target: body, swap: 'innerHTML' });
    }

    openBtn.addEventListener('click', () => setOpen(!card.classList.contains('visible')));
    document.getElementById('settings-card-close')?.addEventListener('click', () => setOpen(false));

    card.addEventListener('click', event => {
      const tab = event.target.closest('[data-settings-tab]');
      if (!tab) return;
      card.querySelectorAll('[data-settings-tab]').forEach(t => t.classList.toggle('active', t === tab));
      card.querySelectorAll('[data-settings-pane]').forEach(pane => {
        pane.hidden = pane.dataset.settingsPane !== tab.dataset.settingsTab;
      });
    });
    card.addEventListener('input', event => preview(event.target));

    document.body.addEventListener('editable-changed', event => applyEditable(event.detail));
    document.body.addEventListener('style-changed', event => applyStyle(event.detail));

    if (typeof makeDraggable === 'function' && window.matchMedia('(min-width: 769px)').matches) {
      makeDraggable(card, '.lst-card-header');
    }
  }

  document.addEventListener('DOMContentLoaded', init);
})();
