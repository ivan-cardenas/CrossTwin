// ============================================================
// Advisors.js — the advisor tray (Map simplification step 6)
// One flag in the status strip collects what needs attention: stale
// SVF / thermal-comfort results, homes without water, site warnings of the
// generator, a population year beyond the CBS projection. Each entry names
// the problem and links to the place to act.
//
// API (window.Advisors), called by the owners of each signal:
//   Advisors.set(id, { severity: 'warn'|'info'|'block', title, detail?, action?, actionLabel? })
//   Advisors.clear(id)
// action = { lens, tab, tool }  open that lens, its tab, a Calculate tool card
//        | { time: true }       open the time chip's menu
//        | { card: 'generator-card' }  show a card that is already in the page
//        | a function
// Depends on: the #advisor-flag / #advisor-tray markup in mainMap.html.
// Load before every script that reports to it.
// ============================================================
(function () {
  'use strict';

  const entries = new Map();   // id -> entry, in insertion order
  const ICON = { warn: 'bi-exclamation-triangle', block: 'bi-x-octagon', info: 'bi-info-circle' };
  const RANK = { block: 0, warn: 1, info: 2 };
  let flag = null, count = null, tray = null, list = null;

  function bind() {
    flag = document.getElementById('advisor-flag');
    count = document.getElementById('advisor-count');
    tray = document.getElementById('advisor-tray');
    list = document.getElementById('advisor-list');
    if (!flag || !tray) return;
    flag.addEventListener('click', () => setOpen(!tray.classList.contains('visible')));
    document.addEventListener('click', (evt) => {
      if (!tray.contains(evt.target) && !flag.contains(evt.target)) setOpen(false);
    });
    document.addEventListener('keydown', (evt) => {
      if (evt.key === 'Escape' && tray.classList.contains('visible')) { setOpen(false); flag.focus(); }
    });
    window.addEventListener('resize', position);
    render();
  }

  function position() {
    const wrap = tray?.offsetParent;     // .map-wrapper; null while hidden
    if (!wrap) return;
    const w = wrap.getBoundingClientRect();
    const f = flag.getBoundingClientRect();
    const left = f.right - w.left - tray.offsetWidth;
    tray.style.left = `${Math.max(8, Math.min(left, wrap.clientWidth - tray.offsetWidth - 8))}px`;
    tray.style.top = `${f.bottom - w.top + 8}px`;
  }

  function setOpen(open) {
    if (!tray) return;
    tray.classList.toggle('visible', open);
    flag.classList.toggle('active', open);
    flag.setAttribute('aria-expanded', String(open));
    if (open) position();
  }

  // ---- actions -----------------------------------------------------------
  function click(selector) {
    const node = document.querySelector(selector);
    if (node) node.click();
    return !!node;
  }

  function run(action) {
    setOpen(false);
    if (typeof action === 'function') { action(); return; }
    if (!action) return;
    if (action.time) { click('#time-chip'); return; }
    if (action.card) {
      // a card of the Edit banner (generator, map settings): its own opener
      const opener = { 'generator-card': '#generatorToolBtn', 'settings-card': '#map-settings-btn' }[action.card];
      if (opener) click(opener);
      return;
    }
    if (action.lens) {
      click(`#toolbar .tool-button[data-tool="${action.lens}"]`);
      if (action.tab) {
        // the lens panel arrives through htmx; its tabs exist once it has loaded
        const open = () => {
          click(`#panel-tabs .panel-tab[data-tab="${action.tab}"]`);
          if (action.tool) click(`#${action.tool}ToolBtn`);
        };
        const body = document.getElementById('panel-body');
        if (body && window.MutationObserver) {
          const done = () => { observer.disconnect(); clearTimeout(timer); open(); };
          const observer = new MutationObserver(() => { if (body.querySelector('.lens-panel')) done(); });
          const timer = setTimeout(done, 3000);
          observer.observe(body, { childList: true });
          if (body.querySelector('.lens-panel')) done();
        } else {
          setTimeout(open, 600);
        }
      }
    }
  }

  // ---- rendering ---------------------------------------------------------
  function render() {
    if (!flag) return;
    const items = [...entries.entries()].sort((a, b) => RANK[a[1].severity] - RANK[b[1].severity]);
    flag.hidden = !items.length;
    count.textContent = String(items.length);
    const worst = items[0]?.[1].severity || 'info';
    flag.dataset.severity = worst;
    flag.setAttribute('aria-label', `${items.length} ${items.length === 1 ? 'item needs' : 'items need'} attention`);
    if (!items.length) setOpen(false);

    list.replaceChildren(...items.map(([id, e]) => {
      const li = document.createElement('li');
      li.className = `advisor-item is-${e.severity}`;
      li.dataset.advisor = id;
      const icon = document.createElement('span');
      icon.className = `bi ${ICON[e.severity] || ICON.info}`;
      icon.setAttribute('aria-hidden', 'true');
      const text = document.createElement('div');
      text.className = 'advisor-text';
      const title = document.createElement('strong');
      title.textContent = e.title;
      text.append(title);
      if (e.detail) {
        const detail = document.createElement('span');
        detail.textContent = e.detail;
        text.append(detail);
      }
      li.append(icon, text);
      if (e.action && e.actionLabel) {
        const btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'advisor-action';
        btn.textContent = e.actionLabel;
        btn.addEventListener('click', () => run(e.action));
        li.append(btn);
      }
      return li;
    }));
    if (tray.classList.contains('visible')) position();
  }

  window.Advisors = {
    set(id, entry) {
      const old = entries.get(id);
      if (old && JSON.stringify({ ...old, action: 0 }) === JSON.stringify({ ...entry, action: 0 })) return;
      entries.set(id, { severity: 'warn', ...entry });
      render();
    },
    clear(id) {
      if (entries.delete(id)) render();
    },
    has: (id) => entries.has(id),
    get count() { return entries.size; },
  };

  document.addEventListener('DOMContentLoaded', bind);
})();
