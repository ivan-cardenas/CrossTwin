// ============================================================
// ConsoleFeed.js — the server's console lines under the map loader
//
// While the page waits on the Django server (any fetch() or HTMX request),
// it polls /api/console/ (core/console.py: the server's print() lines and
// project log records) and shows the newest lines under #map-loader, so the
// user can follow an import, a COG export or an analysis run. Requests that
// print nothing show nothing. TiTiler tiles are not requests of this page
// (Mapbox loads them in its workers) and TiTiler is not captured anyway.
// The feed is open in DEBUG or for staff; on a 403 polling stops for good.
// ============================================================
(function () {
  'use strict';

  const FEED_URL = '/api/console/';
  const POLL_MS = 700;          // while a request is running
  const TAIL_MS = 1500;         // keep polling this long after the last one ends
  const LINGER_MS = 4000;       // keep the lines visible this long afterwards
  const MAX_SHOWN = 6;
  const STALE_REQUEST_MS = 15 * 60 * 1000;  // forget a request that never ended

  const nativeFetch = window.fetch.bind(window);
  const pending = new Map();    // token -> start time
  let lastSeq = null;           // null until the first poll returned the start
  let enabled = true;
  let pollTimer = null;
  let polling = false;
  let idleSince = 0;
  let hideTimer = null;
  let shown = [];

  const wrap = () => document.getElementById('map-loader-wrap');
  const logBox = () => document.getElementById('map-loader-log');

  function busy() {
    const now = Date.now();
    for (const [token, start] of pending) {
      if (now - start > STALE_REQUEST_MS) pending.delete(token);
    }
    return pending.size > 0;
  }

  // ---- request tracking ----------------------------------------------

  function begin(token) {
    if (!enabled) return;
    pending.set(token, Date.now());
    schedule(0);
  }

  function end(token) {
    if (!pending.delete(token)) return;
    if (!busy()) idleSince = Date.now();
  }

  window.fetch = function (input, init) {
    const url = typeof input === 'string' ? input : (input && input.url) || '';
    if (!enabled || url.includes(FEED_URL)) return nativeFetch(input, init);
    const token = {};
    begin(token);
    return nativeFetch(input, init).finally(() => end(token));
  };

  document.addEventListener('htmx:beforeRequest', (e) => begin(e.detail.xhr));
  ['htmx:afterRequest', 'htmx:sendError', 'htmx:timeout', 'htmx:abort'].forEach((name) =>
    document.addEventListener(name, (e) => e.detail && end(e.detail.xhr)));

  // ---- polling --------------------------------------------------------

  function schedule(delay) {
    if (!enabled || pollTimer !== null || polling) return;
    pollTimer = setTimeout(poll, delay);
  }

  async function poll() {
    pollTimer = null;
    polling = true;
    try {
      const query = lastSeq === null ? '' : `?after=${lastSeq}`;
      const response = await nativeFetch(FEED_URL + query, { credentials: 'same-origin' });
      if (response.status === 403 || response.status === 404) {
        enabled = false;
        return;
      }
      if (response.ok) {
        const data = await response.json();
        if (lastSeq !== null && data.lines.length) render(data.lines);
        lastSeq = data.last;
      }
    } catch (err) {
      // Server restarting or offline: try again on the next request
    } finally {
      polling = false;
    }
    if (busy() || Date.now() - idleSince < TAIL_MS) {
      schedule(POLL_MS);
    } else {
      settle();
    }
  }

  // ---- display --------------------------------------------------------

  function render(lines) {
    const box = logBox();
    const container = wrap();
    if (!box || !container) return;

    shown = shown.concat(lines).slice(-MAX_SHOWN);
    box.replaceChildren(...shown.map((line) => {
      const div = document.createElement('div');
      div.className = `log-line ${line.level || 'info'}`;
      div.textContent = line.text;
      div.title = line.text;
      return div;
    }));

    clearTimeout(hideTimer);
    box.hidden = false;
    box.classList.remove('fading');
    if (!container.classList.contains('busy')) {
      container.classList.add('busy');
      const loader = document.getElementById('map-loader');
      const text = document.getElementById('map-loader-text');
      if (text && loader && !loader.classList.contains('visible')) text.textContent = 'Working...';
    }
  }

  function settle() {
    const container = wrap();
    const box = logBox();
    if (!container || !box || box.hidden) return;
    container.classList.remove('busy');
    const text = document.getElementById('map-loader-text');
    if (text) text.textContent = 'Loading features...';

    clearTimeout(hideTimer);
    hideTimer = setTimeout(() => {
      if (busy()) return;
      box.classList.add('fading');
      hideTimer = setTimeout(() => {
        if (busy()) return;
        box.hidden = true;
        box.classList.remove('fading');
        box.replaceChildren();
        shown = [];
      }, 400);
    }, LINGER_MS);
  }

  // Learn where the feed stands now, so lines printed before the page
  // loaded are never shown (also turns the feed off early when forbidden).
  schedule(0);
})();
