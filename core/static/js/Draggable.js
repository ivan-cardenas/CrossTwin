// ============================================================
// Draggable.js — generic drag-by-handle for floating map overlays
// Depends on: nothing (pure DOM). Loaded before layers.js/events.js so
// both can call makeDraggable() on the elements they create.
// ============================================================

/**
 * Make `el` draggable within `.map-wrapper` by pointer-dragging anything
 * matching `handleSelector` inside it. Listeners are bound to `el` itself
 * and delegate via `evt.target.closest(handleSelector)`, so this keeps
 * working for handle elements added after the call (e.g. `.legend-title` —
 * #legend-stack gets a new one per legend Layers.js adds).
 *
 * On first drag, `el` is reparented directly into `.map-wrapper` (so its
 * drag bounds and its `position: absolute` coordinate frame always agree —
 * some overlays, like the WMS time scrubber, otherwise sit inside a smaller
 * centering wrapper that would badly cramp the drag range) and switched
 * from its CSS-positioned layout (top/left/right/bottom/transform, e.g. the
 * toolbar's translateY(-50%) centering or the population dock's `right`
 * rule that reacts to the side panel) to explicit inline `left`/`top`
 * pixels. Reparenting preserves the element's on-screen position exactly,
 * since getBoundingClientRect() is read before the move and inline
 * left/top are computed from it. Double-clicking a handle clears those
 * inline styles so the element goes back to its original parent and normal
 * CSS-driven position.
 *
 * Clicks on interactive descendants (buttons, inputs, selects, links —
 * close buttons, checkboxes, the tour's step dots, etc.) never start a drag
 * or trigger the reset, so they keep working normally.
 *
 * @param {HTMLElement} el - the element to move.
 * @param {string} handleSelector - selector (matched via closest()) for drag grips inside el.
 * @param {Object} [opts]
 * @param {Function} [opts.onDragEnd] - called after a drag completes.
 * @param {Function} [opts.onReset] - called after a double-click reset.
 */
function makeDraggable(el, handleSelector, opts = {}) {
  if (!el) return;
  const container = el.closest('.map-wrapper');
  if (!container) return;
  const originalParent = el.parentElement;
  const originalNextSibling = el.nextSibling;
  const INTERACTIVE = 'button, a, input, select, textarea, [contenteditable]';

  let dragging = false;
  let startX = 0, startY = 0;
  let startLeft = 0, startTop = 0;
  let activePointerId = null;

  el.addEventListener('pointerdown', (evt) => {
    if (!evt.target.closest(handleSelector)) return;
    if (evt.target.closest(INTERACTIVE)) return;
    if (evt.button !== undefined && evt.button !== 0) return;

    const containerRect = container.getBoundingClientRect();
    const elRect = el.getBoundingClientRect();

    // Freeze current on-screen position into explicit left/top (computed
    // before any DOM change) then move el straight into .map-wrapper so its
    // absolute-positioning frame matches the bounds we clamp against below.
    startLeft = elRect.left - containerRect.left;
    startTop = elRect.top - containerRect.top;
    if (el.parentElement !== container) container.appendChild(el);
    el.style.position = 'absolute';
    el.style.left = `${startLeft}px`;
    el.style.top = `${startTop}px`;
    el.style.right = 'auto';
    el.style.bottom = 'auto';
    el.style.transform = 'none';

    startX = evt.clientX;
    startY = evt.clientY;
    dragging = true;
    activePointerId = evt.pointerId;
    el.setPointerCapture(evt.pointerId);
    el.classList.add('dragging');
    evt.preventDefault();
  });

  el.addEventListener('pointermove', (evt) => {
    if (!dragging || evt.pointerId !== activePointerId) return;

    const containerRect = container.getBoundingClientRect();
    const elRect = el.getBoundingClientRect();

    let newLeft = startLeft + (evt.clientX - startX);
    let newTop = startTop + (evt.clientY - startY);

    const maxLeft = containerRect.width - elRect.width;
    const maxTop = containerRect.height - elRect.height;
    newLeft = Math.min(Math.max(newLeft, 0), Math.max(maxLeft, 0));
    newTop = Math.min(Math.max(newTop, 0), Math.max(maxTop, 0));

    el.style.left = `${newLeft}px`;
    el.style.top = `${newTop}px`;
  });

  const endDrag = (evt) => {
    if (!dragging || evt.pointerId !== activePointerId) return;
    dragging = false;
    activePointerId = null;
    el.classList.remove('dragging');
    el.dataset.dragged = '1';
    try { el.releasePointerCapture(evt.pointerId); } catch (e) { /* noop */ }
    if (typeof opts.onDragEnd === 'function') opts.onDragEnd();
  };
  el.addEventListener('pointerup', endDrag);
  el.addEventListener('pointercancel', endDrag);

  el.addEventListener('dblclick', (evt) => {
    if (!evt.target.closest(handleSelector)) return;
    if (evt.target.closest(INTERACTIVE)) return;
    if (originalParent && el.parentElement !== originalParent) {
      originalParent.insertBefore(el, originalNextSibling);
    }
    el.style.position = '';
    el.style.left = '';
    el.style.top = '';
    el.style.right = '';
    el.style.bottom = '';
    el.style.transform = '';
    delete el.dataset.dragged;
    if (typeof opts.onReset === 'function') opts.onReset();
  });
}

window.makeDraggable = makeDraggable;
