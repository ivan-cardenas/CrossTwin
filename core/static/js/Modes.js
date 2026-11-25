// ============================================================
// Modes.js — Explore / Plan / Edit (Map simplification step 5).
// One mode at a time, chosen in the bottom bar's #mode-switch:
//   explore  the stored data, read-only (default). Lens panels show Summary
//            and Calculate; no what-if sliders, no population what-if.
//   plan     what-ifs and climate scenarios; nothing is stored. The What-if
//            tab and the population what-if show, and #mode-banner names
//            everything that differs from the stored baseline (one banner
//            instead of per-card badges), with Back to baseline.
//   edit     staff: the feature editor (popup Edit, ＋ in Layers), the
//            restore point, the neighbourhood generator and map settings,
//            all in the Edit banner. Shows the baseline; the time chip is
//            locked so stored edits are never mixed with what-ifs.
// Leaving Plan returns everything to the baseline; leaving Edit closes the
// editor, the generator and the settings card. In Explore a non-baseline
// year or climate (time chip, Scenarios panel) switches to Plan
// (mainMap.js::setTime).
// The mode is window.MAP_MODE and body[data-map-mode] (CSS hides by it).
// Depends on: mainMap.js (setTime, renderTime, climateChipLabel,
// syncPanelBtns, refreshActivePanel, findActiveAdminTool), Panels.js
// (panelTab, syncPanelTabs, loadPopulationPanel), MapUI.js (renderLayerList),
// Editing.js (isEditing).
// ============================================================

const MAP_MODES = ['explore', 'plan', 'edit'];
window.MAP_MODE = 'explore';

/** The baseline year: the first year of the time chip's picker (today). */
function baselineYear() {
  const years = document.getElementById('year-picker')?.dataset.years;
  return years ? parseInt(years.split(',')[0]) : 2025;
}

function isBaselineTime() {
  const year = window.ACTIVE_YEAR || baselineYear();
  return year === baselineYear() && (window.CLIMATE_SCENARIO || 'current') === 'current';
}

function isBaselinePopulation() {
  return (window.POP_SCENARIO || 'prognose') === 'prognose' && !parseFloat(window.POP_GROWTH || 0);
}

/**
 * Has the user moved a what-if control of the open lens panel away from the
 * value the server rendered it with (its HTML default)? Only touched controls
 * count (data-touched, set on input; heat.js's Reset clears it): a range input
 * snaps its value to its step, so an untouched slider can differ slightly
 * from its default. A full panel re-render brings fresh, untouched controls.
 */
function panelWhatifMoved() {
  const controls = document.querySelectorAll('#panel-body .whatif-only input, #panel-body .whatif-only select');
  return [...controls].some(input => {
    if (input.disabled || input.dataset.touched !== '1') return false;
    if (input.type === 'radio' || input.type === 'checkbox') return input.checked !== input.defaultChecked;
    if (input.tagName === 'SELECT') return [...input.options].some(o => o.selected !== o.defaultSelected);
    if (input.type === 'range' || input.type === 'number') {
      return input.value !== '' && input.defaultValue !== '' && Number(input.value) !== Number(input.defaultValue);
    }
    return input.value !== input.defaultValue;
  });
}

const POP_VARIANT_LABELS = { low: 'lower bound', high: 'upper bound', prognose: 'median' };

/** What differs from the stored baseline, as short labels for the Plan banner. */
function planWhatifs() {
  const items = [];
  if (!isBaselineTime()) {
    const climate = typeof climateChipLabel === 'function' ? climateChipLabel() : '';
    items.push(`${window.ACTIVE_YEAR}${climate ? ' · ' + climate : ''}`);
  }
  if (!isBaselinePopulation()) {
    const variant = POP_VARIANT_LABELS[window.POP_SCENARIO] || window.POP_SCENARIO;
    const growth = parseFloat(window.POP_GROWTH || 0);
    items.push(`Population: ${variant}${growth ? `, ${growth > 0 ? '+' : ''}${growth} %/yr` : ''}`);
  }
  if (panelWhatifMoved()) items.push(`${document.getElementById('panel-title')?.textContent || 'Panel'} sliders`);
  return items;
}

function renderModeBanner() {
  const banner = document.getElementById('mode-banner');
  if (!banner) return;
  const mode = window.MAP_MODE;
  const row = banner.querySelector(`[data-banner="${mode}"]`);
  banner.hidden = !row;
  banner.querySelectorAll('[data-banner]').forEach(r => { r.hidden = r !== row; });

  if (mode === 'plan') {
    const items = planWhatifs();
    const text = document.getElementById('plan-banner-text');
    const list = document.getElementById('plan-banner-items');
    text.textContent = items.length
      ? 'These numbers differ from the stored baseline; nothing is stored:'
      : "Change the year, the climate or a panel's sliders: numbers then show as what-ifs on the stored baseline. Nothing is stored.";
    list.replaceChildren(...items.map(label => {
      const chip = document.createElement('span');
      chip.className = 'mode-banner-item';
      chip.textContent = label;
      return chip;
    }));
    document.getElementById('plan-reset').disabled = !items.length;
  }
  syncModeBannerHeight();
}

// Overlays at the top of the map move down by the banner's height.
function syncModeBannerHeight() {
  const banner = document.getElementById('mode-banner');
  const height = banner && !banner.hidden ? Math.ceil(banner.offsetHeight) : 0;
  document.documentElement.style.setProperty('--mode-banner-h', `${height}px`);
}

/**
 * Back to the stored baseline: today's year and climate, the median
 * population forecast, the open panel re-rendered (its sliders at their
 * stored values). Stays in the current mode.
 */
function resetToBaseline() {
  window.POP_SCENARIO = 'prognose';
  window.POP_GROWTH = 0;
  const timeChanged = !isBaselineTime();
  const scenariosOpen = !!document.querySelector('#panel-body #climate-panel');
  if (scenariosOpen && window.MAP_MODE !== 'plan') {
    // Scenarios are Plan only: close the panel rather than re-render it
    document.getElementById('side-panel')?.classList.remove('visible');
    document.getElementById('panel-body').innerHTML = '';
  }
  if (timeChanged) {
    setTime({ year: baselineYear() }, { refreshPanel: !scenariosOpen || window.MAP_MODE === 'plan' });
  }
  if (typeof syncPanelBtns === 'function') syncPanelBtns();
  // setTime already re-rendered the panel when the time moved
  const panelOpen = document.getElementById('side-panel')?.classList.contains('visible');
  if (!timeChanged && panelOpen && typeof findActiveAdminTool === 'function' && findActiveAdminTool()) {
    refreshActivePanel();
  }
  if (typeof loadPopulationPanel === 'function') loadPopulationPanel();
  renderModeBanner();
}

function leaveEdit() {
  if (typeof isEditing === 'function' && isEditing()) {
    // Editing.js's observer sees the form go and removes the drawing tools
    document.getElementById('panel-body').innerHTML =
      '<p class="feature-editor-msg">Left Edit mode. Unsaved changes were dropped.</p>';
  }
  ['generator-card', 'settings-card'].forEach(id => {
    if (document.getElementById(id)?.classList.contains('visible')) {
      document.getElementById(`${id}-close`)?.click();
    }
  });
}

/** Switch mode. Unknown modes (and Edit without the staff button) are ignored. */
function setMapMode(mode) {
  if (!MAP_MODES.includes(mode) || mode === window.MAP_MODE) return;
  if (!document.querySelector(`#mode-switch [data-mode="${mode}"]`)) return;
  const previous = window.MAP_MODE;
  if (previous === 'edit') leaveEdit();

  window.MAP_MODE = mode;
  document.body.dataset.mapMode = mode;
  document.querySelectorAll('#mode-switch [data-mode]').forEach(btn =>
    btn.setAttribute('aria-checked', String(btn.dataset.mode === mode)));

  if (previous === 'plan') resetToBaseline();
  if (mode !== 'plan' && typeof panelTab !== 'undefined' && panelTab === 'whatif') panelTab = 'summary';
  if (typeof syncPanelTabs === 'function') syncPanelTabs();
  if (typeof renderTime === 'function') renderTime();   // the chip is locked in Edit
  // Popup Edit and the ＋ buttons exist in Edit mode only
  if (typeof renderLayerList === 'function' && typeof availableLayers !== 'undefined' && availableLayers.length) {
    renderLayerList();
  }
  renderModeBanner();
  window.dispatchEvent(new CustomEvent('crosstwin:mode-changed', { detail: { mode, previous } }));
}

window.setMapMode = setMapMode;
window.renderModeBanner = renderModeBanner;
window.isBaselineTime = isBaselineTime;

// ── Header Data menu (staff) ─────────────────────────────────────────────
function initDataMenu() {
  const btn = document.getElementById('data-menu-btn');
  const menu = document.getElementById('data-menu');
  if (!btn || !menu) return;
  const setOpen = (open) => {
    menu.hidden = !open;
    btn.setAttribute('aria-expanded', String(open));
  };
  btn.addEventListener('click', () => setOpen(menu.hidden));
  document.addEventListener('click', (evt) => {
    if (!menu.contains(evt.target) && !btn.contains(evt.target)) setOpen(false);
  });
  document.addEventListener('keydown', (evt) => {
    if (evt.key === 'Escape' && !menu.hidden) { setOpen(false); btn.focus(); }
  });
}

document.addEventListener('DOMContentLoaded', () => {
  document.body.dataset.mapMode = window.MAP_MODE;

  document.getElementById('mode-switch')?.addEventListener('click', (evt) => {
    const btn = evt.target.closest('[data-mode]');
    if (btn) setMapMode(btn.dataset.mode);
  });
  // Arrow keys move between the modes (radio group)
  document.getElementById('mode-switch')?.addEventListener('keydown', (evt) => {
    if (!['ArrowLeft', 'ArrowRight'].includes(evt.key)) return;
    const buttons = [...document.querySelectorAll('#mode-switch [data-mode]')];
    const index = buttons.findIndex(b => b.dataset.mode === window.MAP_MODE);
    const next = buttons[(index + (evt.key === 'ArrowRight' ? 1 : buttons.length - 1)) % buttons.length];
    setMapMode(next.dataset.mode);
    next.focus();
  });

  // "All indicators and what-ifs" (and the What-if tab) lead into Plan.
  // Capture phase, so the mode is set before Panels.js picks the tab.
  document.addEventListener('click', (evt) => {
    const tab = evt.target.closest?.('[data-panel-tab="whatif"], .panel-tab[data-tab="whatif"]');
    if (tab && window.MAP_MODE === 'explore') setMapMode('plan');
  }, true);

  document.getElementById('plan-reset')?.addEventListener('click', resetToBaseline);

  // The banner follows the what-if controls and every panel swap
  ['input', 'change'].forEach(name => document.addEventListener(name, (evt) => {
    if (evt.target.closest?.('#panel-body .whatif-only')) evt.target.dataset.touched = '1';
    if (window.MAP_MODE === 'plan' && evt.target.closest?.('#panel-body .whatif-only, #population-panel')) {
      renderModeBanner();
    }
  }));
  document.addEventListener('htmx:afterSettle', () => { if (window.MAP_MODE === 'plan') renderModeBanner(); });

  const banner = document.getElementById('mode-banner');
  if (banner && typeof ResizeObserver !== 'undefined') new ResizeObserver(syncModeBannerHeight).observe(banner);
  window.addEventListener('resize', syncModeBannerHeight);

  initDataMenu();
  renderModeBanner();
});
