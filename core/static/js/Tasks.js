// ============================================================
// Tasks.js — task starts (Map simplification step 7)
// The "Start here" card offers three questions (Config.js::TASKS). Picking one
// runs its steps on the live map: a step does its action when it opens and
// highlights the next control (the .tour-highlight style of the classic tour).
// Depends on: Config.js (TASKS), Modes.js (setMapMode), mainMap.js (setTime).
// ============================================================
(function () {
  'use strict';

  let task = null;
  let index = 0;
  const $ = (id) => document.getElementById(id);

  function clearHighlight() {
    document.querySelectorAll('.tour-highlight').forEach(node => node.classList.remove('tour-highlight'));
  }

  function render() {
    const step = task.steps[index];
    $('task-guide-title').textContent = task.title;
    $('task-guide-count').textContent = `${index + 1} / ${task.steps.length}`;
    $('task-guide-text').textContent = step.text;
    $('task-guide-prev').disabled = index === 0;
    $('task-guide-next').textContent = index === task.steps.length - 1 ? 'Done ✓' : 'Next →';
    clearHighlight();
    // the control may appear a moment after the action (htmx panel, a card)
    if (step.target) {
      setTimeout(() => {
        if (task) document.querySelector(step.target)?.classList.add('tour-highlight');
      }, 250);
    }
  }

  function enter(i) {
    index = i;
    try { task.steps[i].run?.(); } catch (error) { console.warn('Task step:', error); }
    render();
  }

  function end() {
    task = null;
    clearHighlight();
    $('task-guide').hidden = true;
    localStorage.setItem('crosstwin_tour_seen', '1');
  }

  function start(id) {
    const def = TASKS[id];
    if (!def) return;
    const hint = $('onboarding-hint');
    if (hint) hint.style.display = 'none';
    $('demo-tour')?.classList.add('hidden');
    task = def;
    $('task-guide').hidden = false;
    enter(0);
  }

  document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('.onboarding-task').forEach(btn =>
      btn.addEventListener('click', () => start(btn.dataset.task)));
    $('task-guide-next')?.addEventListener('click', () => {
      if (task && index < task.steps.length - 1) enter(index + 1); else end();
    });
    $('task-guide-prev')?.addEventListener('click', () => { if (task && index > 0) { index -= 1; render(); } });
    $('task-guide-close')?.addEventListener('click', end);
  });

  window.Tasks = { start, end };
})();
