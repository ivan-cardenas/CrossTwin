/*
 * Shared popover for every "?" help button (.info-btn, Templates/partials/_info_btn.html).
 *
 * Loaded once per page (mainMap.html, indicators_base.html). The popover is
 * created lazily as a direct child of <body>: inside the map's side panel it
 * would be positioned against the panel (its backdrop-filter makes it the
 * containing block of position: fixed) and clipped by the scrolling panel
 * body, and it would be thrown away by every HTMX swap of the panel.
 * Clicks are delegated from the document, so buttons swapped in later work.
 */
(function () {
  if (window._infoPopoverAttached) return;
  window._infoPopoverAttached = true;

  var GAP = 10;      // px between button and popover
  var MARGIN = 8;    // px kept free at the viewport edges
  var openBtn = null;

  function popover() {
    var el = document.getElementById('info-popover');
    if (!el) {
      el = document.createElement('div');
      el.id = 'info-popover';
      el.setAttribute('role', 'dialog');
      el.innerHTML = '<span class="info-popover-notch" aria-hidden="true"></span>'
                   + '<div class="info-popover-body"></div>';
      document.body.appendChild(el);
    }
    return el;
  }

  function fill(body, btn) {
    body.textContent = '';
    var tpl = btn.querySelector('template.info-btn-content');
    if (tpl) {
      body.appendChild(tpl.content.cloneNode(true));
      return;
    }
    // Legacy markup: data-info-title / data-info-text attributes
    var title = document.createElement('span');
    title.className = 'info-popover-title';
    title.textContent = btn.dataset.infoTitle || '';
    var text = document.createElement('p');
    text.className = 'info-popover-text';
    text.textContent = btn.dataset.infoText || '';
    body.appendChild(title);
    body.appendChild(text);
  }

  function place(el, btn) {
    var b = btn.getBoundingClientRect();
    var r = el.getBoundingClientRect();
    var left = Math.max(MARGIN, Math.min(b.right - r.width, window.innerWidth - r.width - MARGIN));
    var top = b.bottom + GAP;
    var above = top + r.height > window.innerHeight - MARGIN && b.top - GAP - r.height >= MARGIN;
    if (above) top = b.top - GAP - r.height;
    // Neither side fits: keep it on screen; its body scrolls (max-height in CSS)
    top = Math.max(MARGIN, Math.min(top, window.innerHeight - r.height - MARGIN));
    el.style.left = left + 'px';
    el.style.top = top + 'px';
    el.dataset.placement = above ? 'above' : 'below';
    // Notch sits under the button however far the popover shifted
    var notch = Math.max(12, Math.min(r.width - 22, b.left - left + b.width / 2 - 5));
    el.style.setProperty('--notch-offset', notch + 'px');
  }

  function show(btn) {
    var el = popover();
    fill(el.querySelector('.info-popover-body'), btn);
    el.querySelector('.info-popover-body').scrollTop = 0;
    el.classList.add('show');
    place(el, btn);
    btn.setAttribute('aria-expanded', 'true');
    openBtn = btn;
  }

  function hide() {
    var el = document.getElementById('info-popover');
    if (el) el.classList.remove('show');
    if (openBtn) openBtn.setAttribute('aria-expanded', 'false');
    openBtn = null;
  }

  document.addEventListener('click', function (e) {
    var btn = e.target.closest('.info-btn');
    if (btn) {
      e.preventDefault();
      e.stopPropagation();
      var wasOpen = openBtn === btn;
      hide();
      if (!wasOpen) show(btn);
      return;
    }
    if (!e.target.closest('#info-popover')) hide();
  });

  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') hide();
  });

  // The popover is fixed to the viewport: close it when the content under it
  // moves (panel scroll, resize) or is swapped away, rather than leave it
  // pointing at nothing. Scrolling inside the popover itself is fine.
  document.addEventListener('scroll', function (e) {
    if (openBtn && !(e.target.closest && e.target.closest('#info-popover'))) hide();
  }, true);
  window.addEventListener('resize', hide);
  document.addEventListener('htmx:beforeSwap', function () { if (openBtn) hide(); });
})();
