// Quick start terminal: setup tabs, copy, and one typed pass the first time it is seen.
import { rovingGroup } from './util.js';

export function initTerminal({ gsap, ST, reduce, rtl }) {
  const root = document.querySelector('[data-term]');
  if (!root) return;
  const tabs = [...root.querySelectorAll('[role="tab"]')];
  const panels = tabs.map((t) => document.getElementById(t.getAttribute('aria-controls')));
  const copyBtn = root.querySelector('[data-copy-btn]');
  const copyLabel = root.querySelector('[data-copy-label]');
  let current = 0;

  rovingGroup({
    root: root.querySelector('.term__tabs'),
    buttons: tabs,
    rtl,
    gsap,
    onSelect: (i) => {
      current = i;
      panels.forEach((p, j) => { p.hidden = j !== i; });
    },
  });
  root.querySelector('.term__tabs').classList.remove('no-thumb');

  let resetTimer;
  copyBtn.addEventListener('click', async () => {
    const text = [...panels[current].querySelectorAll('.l, .c')].map((l) => l.textContent).join('\n');
    try {
      await navigator.clipboard.writeText(text);
      copyLabel.textContent = root.dataset.copied;
    } catch {
      const sel = getSelection();
      const r = document.createRange();
      r.selectNodeContents(panels[current]);
      sel.removeAllRanges();
      sel.addRange(r);
    }
    clearTimeout(resetTimer);
    resetTimer = setTimeout(() => { copyLabel.textContent = root.dataset.copy; }, 1800);
  });

  if (reduce) return;
  const lines = [...panels[0].querySelectorAll('.l')];
  gsap.set(lines, { clipPath: 'inset(0 100% 0 0)' });
  ST.create({
    trigger: root,
    start: 'top 75%',
    once: true,
    onEnter: () => {
      const tl = gsap.timeline();
      lines.forEach((line) => {
        const n = line.textContent.length + 2;
        tl.to(line, { clipPath: 'inset(0 0% 0 0)', duration: Math.min(0.9, n * 0.014), ease: `steps(${n})` }, '+=0.12');
      });
    },
  });
}
