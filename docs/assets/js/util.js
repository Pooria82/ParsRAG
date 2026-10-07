// Shared helpers.

/** Wraps each whitespace-separated word in a span. Persian words stay whole, so letters keep joining. */
export function splitWords(el, className = 'w') {
  if (el.dataset.split) return [...el.querySelectorAll(`.${className}`)];
  const words = [];
  for (const node of [...el.childNodes]) {
    if (node.nodeType !== Node.TEXT_NODE) continue;
    const frag = document.createDocumentFragment();
    for (const part of node.textContent.split(/(\s+)/)) {
      if (!part) continue;
      if (/^\s+$/.test(part)) {
        frag.append(part);
      } else {
        const span = document.createElement('span');
        span.className = className;
        span.textContent = part;
        frag.append(span);
        words.push(span);
      }
    }
    node.replaceWith(frag);
  }
  el.dataset.split = '1';
  return words;
}

export const clamp = (v, min, max) => Math.min(max, Math.max(min, v));

/** Persian digits for the fa page. */
export const localDigits = (value, lang) =>
  lang === 'fa' ? String(value).replace(/\d/g, (d) => '۰۱۲۳۴۵۶۷۸۹'[d]) : String(value);

/**
 * Accessible tabs / radio group with roving tabindex and an optional sliding thumb.
 * `buttons` are the controls; `onSelect(index, fromUser)` runs on change.
 */
export function rovingGroup({ root, buttons, attr = 'aria-selected', rtl, gsap, onSelect, thumb }) {
  let current = Math.max(0, buttons.findIndex((b) => b.getAttribute(attr) === 'true'));

  const moveThumb = (instant) => {
    if (!thumb) return;
    const b = buttons[current];
    const props = { x: b.offsetLeft, y: b.offsetTop, width: b.offsetWidth, height: b.offsetHeight };
    if (instant) gsap.set(thumb, props);
    else gsap.to(thumb, { ...props, duration: 0.55, ease: 'power3.out' });
  };

  const select = (i, fromUser = false, focus = false) => {
    current = (i + buttons.length) % buttons.length;
    buttons.forEach((b, j) => {
      b.setAttribute(attr, String(j === current));
      b.tabIndex = j === current ? 0 : -1;
    });
    if (focus) buttons[current].focus();
    moveThumb(!fromUser);
    onSelect?.(current, fromUser);
  };

  buttons.forEach((b, i) => {
    b.addEventListener('click', () => i !== current && select(i, true));
    b.addEventListener('keydown', (e) => {
      const next = rtl ? 'ArrowLeft' : 'ArrowRight';
      const prev = rtl ? 'ArrowRight' : 'ArrowLeft';
      let to = null;
      if (e.key === next || e.key === 'ArrowDown') to = current + 1;
      else if (e.key === prev || e.key === 'ArrowUp') to = current - 1;
      else if (e.key === 'Home') to = 0;
      else if (e.key === 'End') to = buttons.length - 1;
      if (to === null) return;
      e.preventDefault();
      select(to, true, true);
    });
  });

  if (thumb) {
    moveThumb(true);
    new ResizeObserver(() => moveThumb(true)).observe(root);
  } else {
    root.classList.add('no-thumb');
  }
  return { select, get index() { return current; } };
}
