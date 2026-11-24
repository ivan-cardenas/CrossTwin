/* Runs in <head>, before first paint: applies the saved theme (default dark) and
   flags JS so scroll-reveal elements may start hidden. */
(function () {
    var root = document.documentElement;
    var theme = 'dark';
    try {
        var saved = localStorage.getItem('ct-theme');
        if (saved === 'light' || saved === 'dark') theme = saved;
    } catch (e) { /* storage blocked: stay on default */ }
    root.setAttribute('data-theme', theme);
    root.classList.add('js');
})();
