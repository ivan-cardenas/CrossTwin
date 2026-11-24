/* Theme toggle + scroll reveals. Safe to re-run after htmx swaps (window.ctReveal). */
(function () {
    'use strict';

    var reduced = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    var SEL = '.reveal, .reveal-mast, .reveal-line';
    var observer = null;

    function reveal(el) { el.setAttribute('data-revealed', ''); }

    function getObserver() {
        if (observer || !('IntersectionObserver' in window)) return observer;
        observer = new IntersectionObserver(function (entries) {
            entries.forEach(function (e) {
                if (e.isIntersecting) {
                    reveal(e.target);
                    observer.unobserve(e.target);
                }
            });
        }, { threshold: 0.08, rootMargin: '0px 0px -5% 0px' });
        return observer;
    }

    // Observe every not-yet-revealed element under `scope`.
    function scan(scope) {
        var nodes = (scope || document).querySelectorAll(SEL + ':not([data-revealed])');
        var io = reduced ? null : getObserver();
        nodes.forEach(function (el) {
            if (io) io.observe(el); else reveal(el);
        });
    }
    window.ctReveal = scan;

    function setTheme(theme) {
        document.documentElement.setAttribute('data-theme', theme);
        try { localStorage.setItem('ct-theme', theme); } catch (e) { /* ignore */ }
        syncToggle();
        document.dispatchEvent(new CustomEvent('ct:themechange', { detail: { theme: theme } }));
    }

    function syncToggle() {
        var dark = document.documentElement.getAttribute('data-theme') !== 'light';
        document.querySelectorAll('[data-theme-toggle]').forEach(function (btn) {
            btn.setAttribute('aria-pressed', dark ? 'false' : 'true');
            btn.setAttribute('title', dark ? 'Switch to light theme' : 'Switch to dark theme');
            var icon = btn.querySelector('i');
            if (icon) icon.className = dark ? 'bi bi-sun' : 'bi bi-moon';
        });
    }

    function syncHeaderHeight() {
        var header = document.querySelector('.app-header');
        if (header) {
            document.documentElement.style.setProperty('--header-height', header.offsetHeight + 'px');
        }
    }

    document.addEventListener('click', function (ev) {
        var btn = ev.target.closest && ev.target.closest('[data-theme-toggle]');
        if (!btn) return;
        var dark = document.documentElement.getAttribute('data-theme') !== 'light';
        setTheme(dark ? 'light' : 'dark');
    });

    document.addEventListener('htmx:afterSwap', function (ev) { scan(ev.target); });

    function init() {
        syncToggle();
        syncHeaderHeight();
        scan(document);
    }
    window.addEventListener('resize', syncHeaderHeight);
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
    else init();
})();
