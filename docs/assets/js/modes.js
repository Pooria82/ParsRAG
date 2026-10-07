// Answer modes: one question, three answers. Switching re-streams the answer
// so the difference between cited, model-written, and declined text is visible.
import { splitWords, rovingGroup } from './util.js';

export function initModes({ gsap, ST, reduce, rtl }) {
  const root = document.querySelector('[data-modes]');
  if (!root) return;
  const seg = root.querySelector('.seg');
  const tabs = [...seg.querySelectorAll('[role="tab"]')];
  const panels = tabs.map((t) => document.getElementById(t.getAttribute('aria-controls')));

  const stream = (panel) => {
    if (reduce) return;
    const spans = [...panel.querySelectorAll('[data-stream]')];
    const words = spans.flatMap((el) => splitWords(el));
    const chips = panel.querySelectorAll('.cite-chip');
    const facts = panel.querySelectorAll('.facts > div');
    gsap.killTweensOf([...spans, ...words, ...chips, ...facts]);
    const tl = gsap.timeline();
    tl.fromTo(words, { autoAlpha: 0, filter: 'blur(5px)' }, { autoAlpha: 1, filter: 'blur(0px)', duration: 0.35, stagger: 0.028, ease: 'power1.out' });
    // Each underline follows its own words.
    let offset = 0;
    spans.forEach((span) => {
      const n = span.querySelectorAll('.w').length;
      tl.fromTo(span, { '--u': 0 }, { '--u': 1, duration: n * 0.028 + 0.3, ease: 'none' }, offset * 0.028 + 0.05);
      offset += n;
    });
    tl.fromTo(facts, { autoAlpha: 0, y: 8 }, { autoAlpha: 1, y: 0, duration: 0.4, stagger: 0.08, ease: 'power2.out' }, 0.15);
    chips.forEach((chip) => {
      // Each citation lands right after the sentence it supports.
      const prev = chip.previousElementSibling;
      const index = prev ? words.indexOf([...prev.querySelectorAll('.w')].pop()) : 0;
      tl.fromTo(chip, { autoAlpha: 0, scale: 0.6 }, { autoAlpha: 1, scale: 1, duration: 0.3, ease: 'back.out(2.5)' }, Math.max(0, index) * 0.028 + 0.3);
    });
  };

  rovingGroup({
    root: seg,
    buttons: tabs,
    rtl,
    gsap,
    thumb: seg.querySelector('.seg__thumb'),
    onSelect: (i, fromUser) => {
      panels.forEach((p, j) => { p.hidden = j !== i; });
      if (fromUser) stream(panels[i]);
    },
  });

  if (!reduce) {
    // Hide the first answer until the sheet scrolls into view, then stream it once.
    const first = panels[0];
    const spans = [...first.querySelectorAll('[data-stream]')];
    const words = spans.flatMap((el) => splitWords(el));
    gsap.set([...words, ...first.querySelectorAll('.cite-chip, .facts > div')], { autoAlpha: 0 });
    gsap.set(spans, { '--u': 0 });
    ST.create({ trigger: root.querySelector('.sheet'), start: 'top 70%', once: true, onEnter: () => stream(panels[tabs.findIndex((t) => t.getAttribute('aria-selected') === 'true')]) });
  }
}
