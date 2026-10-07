// Marginalia: a question is typed, the answer streams in, and gold threads tie each
// citation to its margin note and then to the highlighted line in the source page.
import { splitWords } from './util.js';

const SVG_NS = 'http://www.w3.org/2000/svg';

export function initMarginalia({ gsap, ST, reduce, rtl }) {
  const stage = document.querySelector('[data-demo]');
  if (!stage) return;
  const pin = stage.closest('.demo__pin');
  const svg = stage.querySelector('.threads');
  const margin = stage.querySelector('.folio__margin');
  const composer = stage.querySelector('[data-composer]');
  const question = stage.querySelector('[data-question]');
  const caret = question.querySelector('.caret');
  const stages = [...stage.querySelectorAll('[data-stage]')];
  const cites = [1, 2].map((n) => stage.querySelector(`[data-cite="${n}"]`));
  const notes = [1, 2].map((n) => stage.querySelector(`[data-note="${n}"]`));
  const docs = [1, 2].map((n) => stage.querySelector(`[data-doc="${n}"]`));
  const marks = [1, 2].map((n) => stage.querySelector(`[data-hl="${n}"] mark`));
  const streams = [1, 2].map((n) => splitWords(stage.querySelector(`[data-stream="${n}"]`)));

  // Each answer sentence becomes its own line group so its citation ends a line.
  const answerP = stage.querySelector('.answer p');
  const second = answerP.querySelector('[data-stream="2"]');
  const p2 = document.createElement('p');
  while (second.previousSibling && second.previousSibling.nodeType === Node.TEXT_NODE) second.previousSibling.remove();
  p2.append(second, cites[1]);
  answerP.after(p2);

  // Typing: chips count as one keystroke, like picking a file from the @ menu.
  const segs = [...question.querySelectorAll('[data-seg]')].map((el) => ({ el, full: el.textContent, chip: el.dataset.seg === 'chip' }));
  const units = segs.reduce((n, s) => n + (s.chip ? 1 : s.full.length), 0);
  const fullText = segs.map((s) => s.full).join('');
  const sr = document.createElement('span');
  sr.className = 'visually-hidden';
  sr.textContent = fullText;
  question.prepend(sr);
  segs.forEach((s) => s.el.setAttribute('aria-hidden', 'true'));
  question.style.minHeight = `${question.offsetHeight}px`;

  const typeTo = (n) => {
    let left = Math.round(n);
    for (const s of segs) {
      if (s.chip) {
        s.el.style.display = left > 0 ? '' : 'none';
        left -= 1;
      } else {
        s.el.textContent = s.full.slice(0, Math.max(0, Math.min(s.full.length, left)));
        left -= s.full.length;
      }
    }
  };

  // Threads: citation -> note, note -> highlighted source line.
  const links = [
    [cites[0], notes[0].querySelector('.note__n')],
    [notes[0], marks[0]],
    [cites[1], notes[1].querySelector('.note__n')],
    [notes[1], marks[1]],
  ];
  const paths = links.map(() => {
    const path = document.createElementNS(SVG_NS, 'path');
    path.setAttribute('class', 'thread');
    path.setAttribute('pathLength', '1');
    const dot = document.createElementNS(SVG_NS, 'circle');
    dot.setAttribute('class', 'thread-end');
    dot.setAttribute('r', '3.2');
    svg.append(path, dot);
    return { path, dot };
  });

  const placeNotes = () => {
    const stacked = getComputedStyle(notes[0]).position !== 'absolute';
    if (stacked) {
      notes.forEach((n) => { n.style.top = ''; });
      return;
    }
    const mr = margin.getBoundingClientRect();
    let minTop = 0;
    notes.forEach((note, i) => {
      const cr = cites[i].getBoundingClientRect();
      const top = Math.max(minTop, cr.top - mr.top - 4);
      note.style.top = `${top}px`;
      minTop = top + note.offsetHeight + 16;
    });
  };

  const layoutThreads = () => {
    placeNotes();
    // Stacked (narrow) layout: the source cards sit below, so only the short threads are drawn.
    const stacked = getComputedStyle(notes[0]).position !== 'absolute';
    [1, 3].forEach((i) => {
      paths[i].path.style.display = stacked ? 'none' : '';
      paths[i].dot.style.display = stacked ? 'none' : '';
    });
    const box = stage.getBoundingClientRect();
    svg.setAttribute('viewBox', `0 0 ${box.width} ${box.height}`);
    links.forEach(([from, to], i) => {
      const a = from.getBoundingClientRect();
      const b = to.getBoundingClientRect();
      const ac = { x: (a.left + a.right) / 2 - box.left, y: (a.top + a.bottom) / 2 - box.top };
      const bc = { x: (b.left + b.right) / 2 - box.left, y: (b.top + b.bottom) / 2 - box.top };
      let d;
      let end;
      if (Math.abs(bc.x - ac.x) > Math.abs(bc.y - ac.y) * 0.5) {
        const toRight = bc.x > ac.x;
        const sx = (toRight ? a.right : a.left) - box.left + (toRight ? 3 : -3);
        const ex = (toRight ? b.left : b.right) - box.left + (toRight ? -3 : 3);
        const dx = (ex - sx) * 0.55;
        d = `M${sx},${ac.y} C${sx + dx},${ac.y} ${ex - dx},${bc.y} ${ex},${bc.y}`;
        end = [ex, bc.y];
      } else {
        const down = bc.y > ac.y;
        const sy = (down ? a.bottom : a.top) - box.top + (down ? 3 : -3);
        const ey = (down ? b.top : b.bottom) - box.top + (down ? -3 : 3);
        const dy = (ey - sy) * 0.55;
        d = `M${ac.x},${sy} C${ac.x},${sy + dy} ${bc.x},${ey - dy} ${bc.x},${ey}`;
        end = [bc.x, ey];
      }
      paths[i].path.setAttribute('d', d);
      paths[i].dot.setAttribute('cx', end[0]);
      paths[i].dot.setAttribute('cy', end[1]);
    });
  };

  layoutThreads();
  ST.addEventListener('refresh', layoutThreads);
  // Anything that reflows the page or the sources (late fonts, wrapping) re-routes the threads.
  const ro = new ResizeObserver(() => layoutThreads());
  [stage, stage.querySelector('.folio__main'), ...docs].forEach((node) => ro.observe(node));
  document.fonts?.addEventListener?.('loadingdone', layoutThreads);

  // The whole sequence as one timeline, so scroll can scrub it both ways.
  const typer = { n: 0 };
  const tl = gsap.timeline({ defaults: { ease: 'none' } });
  tl.to(typer, { n: units, duration: 2.4, onUpdate: () => typeTo(typer.n) })
    .to(composer, { '--sent': 1, duration: 0.45 }, '+=0.15')
    .to(caret, { autoAlpha: 0, duration: 0.1 }, '<');

  stages.forEach((li) => {
    tl.fromTo(li, { autoAlpha: 0, y: 6 }, { autoAlpha: 1, y: 0, duration: 0.3 }, '+=0.05')
      .to(li, { '--done': 1, duration: 0.25 }, '+=0.3');
  });

  const shift = rtl ? 10 : -10;
  [0, 1].forEach((i) => {
    tl.fromTo(streams[i], { autoAlpha: 0, filter: 'blur(5px)' }, { autoAlpha: 1, filter: 'blur(0px)', duration: 0.3, stagger: 0.07 }, '+=0.15')
      .fromTo(cites[i], { autoAlpha: 0, scale: 0.3 }, { autoAlpha: 1, scale: 1, duration: 0.25, ease: 'back.out(3)' })
      .fromTo(paths[i * 2].path, { strokeDashoffset: 1 }, { strokeDashoffset: 0, duration: 0.55, ease: 'power1.inOut' })
      .fromTo(paths[i * 2].dot, { opacity: 0 }, { opacity: 1, duration: 0.1 })
      .fromTo(notes[i], { autoAlpha: 0, x: -shift }, { autoAlpha: 1, x: 0, duration: 0.35, ease: 'power2.out' }, '-=0.1')
      .fromTo(paths[i * 2 + 1].path, { strokeDashoffset: 1 }, { strokeDashoffset: 0, duration: 0.9, ease: 'power1.inOut' }, '+=0.05')
      .fromTo(docs[i], { '--lift': 0 }, { '--lift': 1, duration: 0.5, ease: 'power2.out' }, '-=0.45')
      .fromTo(paths[i * 2 + 1].dot, { opacity: 0 }, { opacity: 1, duration: 0.1 }, '-=0.05')
      .fromTo(marks[i], { '--hl': 0 }, { '--hl': 1, duration: 0.5, ease: 'power1.inOut' })
      .to(docs[i], { '--lift': 0.35, duration: 0.3 }, '+=0.2');
  });
  tl.to({}, { duration: 0.8 });

  if (reduce) {
    tl.progress(1);
    requestAnimationFrame(layoutThreads);
    return;
  }

  const mm = gsap.matchMedia();
  mm.add('(min-width: 900px) and (min-height: 620px)', () => {
    ST.create({
      trigger: pin,
      start: () => (stage.offsetHeight < window.innerHeight - 140 ? 'center 52%' : 'top top+=84'),
      end: () => `+=${Math.round(window.innerHeight * 2.8)}`,
      pin: true,
      scrub: 0.7,
      animation: tl,
      anticipatePin: 1,
      invalidateOnRefresh: true,
    });
  });
  mm.add('(max-width: 899.98px), (max-height: 619.98px)', () => {
    ST.create({
      trigger: stage,
      start: 'top 72%',
      end: 'bottom 75%',
      scrub: 0.5,
      animation: tl,
      invalidateOnRefresh: true,
    });
  });
}
