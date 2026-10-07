// A page's journey: one page morphs through the real ingestion sequence
// (upload, OCR, passages, vectors, Qdrant, cited answer) as the steps advance.
import { localDigits } from './util.js';

const BOX_W = 560;
const PAGE = { x: 150, y: 74, w: 260, h: 346 };
const LINE_W = [196, 216, 168, 208, 216, 118, 204, 216, 184, 214, 196, 132];
const CHUNK_POS = [[36, 64], [304, 64], [36, 262], [304, 262]];
const CHUNK = { w: 220, h: 112 };
const CLUSTER = [[318, 186], [352, 214], [326, 244], [366, 170]];
const OTHERS = [
  [132, 112], [178, 300], [226, 158], [404, 318], [452, 128], [150, 220], [262, 352], [438, 236],
  [206, 92], [480, 300], [116, 330], [290, 118], [392, 96], [244, 262], [470, 192], [174, 168],
];
const SLOT_ORDER = [6, 8, 12, 2]; // where the four passages land inside the collection

const slot = (n) => [190 + (n % 5) * 44, 214 + Math.floor(n / 5) * 40];

export function initJourney({ gsap, ST, reduce, rtl, lang }) {
  const root = document.querySelector('[data-journey]');
  if (!root) return;
  const box = root.querySelector('[data-jstage]');
  const frame = root.querySelector('.jstage');
  const stepsList = root.querySelector('.steps');
  const steps = [...root.querySelectorAll('[data-step]')];
  if (rtl) box.dataset.rtl = '';

  const progressBar = document.createElement('span');
  progressBar.className = 'steps__progress';
  progressBar.setAttribute('aria-hidden', 'true');
  stepsList.prepend(progressBar);

  // Mirror x for right-to-left so lines start at the right edge of the page.
  const mx = (x, w = 0) => (rtl ? BOX_W - x - w : x);
  const make = (cls, x, y, w, h, html = '') => {
    const el = document.createElement('div');
    el.className = cls;
    if (html) el.innerHTML = html;
    box.append(el);
    gsap.set(el, { x: mx(x, w), y, width: w || 'auto', height: h || 'auto' });
    return el;
  };

  const page = make('jp-page', PAGE.x, PAGE.y, PAGE.w, PAGE.h);
  const file = make('jp-file', PAGE.x, 24, 0, 0, `<b>PDF</b><span>${root.dataset.file}</span>`);
  if (rtl) gsap.set(file, { x: BOX_W - PAGE.x - file.offsetWidth });
  const lines = LINE_W.map((w, i) => make('jp-line', PAGE.x + 24, PAGE.y + 32 + i * 24, w - 24, 7));
  const beam = make('jp-beam', PAGE.x - 14, PAGE.y, PAGE.w + 28, 3);
  const langTag = make('jp-label', PAGE.x + PAGE.w + 18, PAGE.y - 10, 0, 0, root.dataset.langTag);
  if (rtl) gsap.set(langTag, { x: BOX_W - (PAGE.x + PAGE.w + 18) - langTag.offsetWidth });

  const pageNo = (a, b) => {
    const p = lang === 'fa' ? 'ص ' : 'p. ';
    return localDigits(b ? `${p}${a}–${b}` : `${p}${a}`, lang);
  };
  const tagText = [pageNo(3), pageNo(3), pageNo(3, 4), pageNo(4)];
  const chunks = CHUNK_POS.map(([x, y], k) => make(`jp-chunk${k === 2 ? ' is-bridge' : ''}`, x, y, CHUNK.w, CHUNK.h));
  const tags = CHUNK_POS.map(([x, y], k) => {
    const t = make('jp-tag', x + 14, y - 12, 0, 0, tagText[k]);
    if (rtl) gsap.set(t, { x: BOX_W - (x + 14) - t.offsetWidth });
    return t;
  });

  const axisX = make('jp-axis', 70, 404, 430, 1);
  const axisY = make('jp-axis', 92, 70, 1, 352);
  const others = OTHERS.map(([x, y]) => make('jp-dot is-other', x, y, 14, 14));

  const cyl = make('jp-cyl', 160, 150, 240, 256);
  const cylTop = make('jp-cyl-top', 160, 116, 240, 68);
  const cylLabel = make('jp-cyl-label', 130, 420, 300, 0, root.dataset.collection);

  const query = make('jp-q', 271, 0, 18, 18);
  const NS = 'http://www.w3.org/2000/svg';
  const svg = document.createElementNS(NS, 'svg');
  svg.setAttribute('class', 'jp-links');
  svg.setAttribute('viewBox', `0 0 ${BOX_W} 520`);
  box.append(svg);
  const RISE = [[180, 92], [372, 92], [276, 150]];
  const linkEls = RISE.map(([x, y]) => {
    const l = document.createElementNS(NS, 'line');
    l.setAttribute('x1', mx(280));
    l.setAttribute('y1', 58);
    l.setAttribute('x2', mx(x + 7));
    l.setAttribute('y2', y + 7);
    l.setAttribute('pathLength', '1');
    svg.append(l);
    return l;
  });
  const answer = make('jp-answer', 90, 196, 380, 0,
    `<strong>${root.dataset.answer}</strong><p style="width:94%"></p><p style="width:82%"></p><p style="width:60%"></p><span>${root.dataset.cite}</span>`);

  // Initial (pre-upload) state.
  gsap.set([page, file], { autoAlpha: 0, y: '-=30' });
  gsap.set(lines, { autoAlpha: 0, backgroundColor: '#7F948C', filter: 'blur(1.6px)' });
  gsap.set([beam, langTag, ...chunks, ...tags, axisX, axisY, ...others, cyl, cylTop, cylLabel, query, answer], { autoAlpha: 0 });
  gsap.set(linkEls, { attr: { 'stroke-dasharray': '1 1', 'stroke-dashoffset': 1 } });
  gsap.set([axisX], { scaleX: 0, transformOrigin: rtl ? '100% 50%' : '0 50%' });
  gsap.set([axisY], { scaleY: 0, transformOrigin: '50% 100%' });

  const tl = gsap.timeline({ defaults: { ease: 'power2.inOut' } });

  // 1 Upload
  tl.addLabel('s0', 0)
    .to([page, file], { autoAlpha: 1, y: '+=30', duration: 0.45, stagger: 0.08, ease: 'power3.out' }, 's0')
    .to(lines, { autoAlpha: 0.75, duration: 0.3, stagger: 0.02 }, 's0+=0.25');

  // 2 OCR: the beam passes and each line turns to crisp ink.
  tl.addLabel('s1', 1)
    .to([beam, langTag], { autoAlpha: 1, duration: 0.1 }, 's1')
    .fromTo(beam, { y: PAGE.y }, { y: PAGE.y + PAGE.h, duration: 0.75, ease: 'none' }, 's1')
    .to(lines, { autoAlpha: 1, backgroundColor: '#173129', filter: 'blur(0px)', duration: 0.12, stagger: 0.055, ease: 'none' }, 's1+=0.04')
    .to(beam, { autoAlpha: 0, duration: 0.12 }, 's1+=0.78');

  // 3 Passages: the page splits into located passages; one bridges two pages.
  tl.addLabel('s2', 2)
    .to([page, file, langTag], { autoAlpha: 0, scale: 0.97, duration: 0.4 }, 's2')
    .to(chunks, { autoAlpha: 1, duration: 0.4, stagger: 0.08 }, 's2+=0.25')
    .to(tags, { autoAlpha: 1, duration: 0.3, stagger: 0.08 }, 's2+=0.45');
  lines.forEach((line, i) => {
    const k = Math.floor(i / 3);
    const [cx, cy] = CHUNK_POS[k];
    const w = Math.min(LINE_W[i] * 0.86, CHUNK.w - 40);
    tl.to(line, { x: mx(cx + 20, w), y: cy + 28 + (i % 3) * 24, width: w, backgroundColor: '#B9D8CB', duration: 0.6 }, `s2+=${0.05 + i * 0.015}`);
  });

  // 4 Vectors: each passage collapses into a point; other documents' points appear around it.
  tl.addLabel('s3', 3)
    .to(tags, { autoAlpha: 0, duration: 0.2 }, 's3');
  chunks.forEach((chunk, k) => {
    const [x, y] = CLUSTER[k];
    tl.to(lines.slice(k * 3, k * 3 + 3), { autoAlpha: 0, width: 0, x: mx(x + 7), y: y + 7, duration: 0.45 }, `s3+=${k * 0.05}`)
      .to(chunk, { x: mx(x, 14), y, width: 14, height: 14, borderRadius: 7, borderWidth: 0, backgroundColor: k === 2 ? '#D2B06A' : '#79C5AA', duration: 0.6 }, `s3+=${0.1 + k * 0.05}`);
  });
  tl.to(axisX, { autoAlpha: 1, scaleX: 1, duration: 0.5 }, 's3+=0.2')
    .to(axisY, { autoAlpha: 1, scaleY: 1, duration: 0.5 }, 's3+=0.2')
    .fromTo(others, { scale: 0 }, { autoAlpha: 1, scale: 1, duration: 0.3, stagger: 0.025, ease: 'back.out(2)' }, 's3+=0.35');

  // 5 Qdrant: every point settles into this conversation's collection.
  tl.addLabel('s4', 4)
    .to([axisX, axisY], { autoAlpha: 0, duration: 0.25 }, 's4')
    .to([cyl, cylTop], { autoAlpha: 1, duration: 0.35 }, 's4+=0.1')
    .to(cylLabel, { autoAlpha: 1, duration: 0.3 }, 's4+=0.35');
  const free = Array.from({ length: 20 }, (_, n) => n).filter((n) => !SLOT_ORDER.includes(n));
  others.forEach((dot, i) => {
    const [x, y] = slot(free[i]);
    tl.to(dot, { x: mx(x, 14), y, duration: 0.55 }, `s4+=${0.15 + i * 0.012}`);
  });
  chunks.forEach((chunk, k) => {
    const [x, y] = slot(SLOT_ORDER[k]);
    tl.to(chunk, { x: mx(x, 14), y, backgroundColor: '#79C5AA', duration: 0.55 }, `s4+=${0.2 + k * 0.03}`);
  });

  // 6 Cited answer: the question finds its nearest passages, and they come back as sources.
  tl.addLabel('s5', 5)
    .to(query, { autoAlpha: 1, y: 40, x: mx(271, 18), duration: 0.35, ease: 'power3.out' }, 's5')
    .to([...others, cyl, cylTop], { autoAlpha: 0.25, duration: 0.3 }, 's5+=0.1');
  [0, 1, 2].forEach((k) => {
    const [x, y] = RISE[k];
    tl.to(chunks[k], { x: mx(x, 14), y, backgroundColor: '#D2B06A', boxShadow: '0 0 16px rgba(210,176,106,.8)', duration: 0.4 }, `s5+=${0.2 + k * 0.05}`)
      .to(linkEls[k], { attr: { 'stroke-dashoffset': 0 }, duration: 0.25 }, `s5+=${0.45 + k * 0.05}`);
  });
  tl.to(answer, { autoAlpha: 1, y: 236, duration: 0.4, ease: 'power3.out' }, 's5+=0.7')
    .to([cylLabel, chunks[3]], { autoAlpha: 0, duration: 0.2 }, 's5+=0.7')
    .to({}, { duration: 0.3 });

  // Keep the 560px drawing scaled to its frame.
  const fit = () => gsap.set(box, { scale: frame.clientWidth / BOX_W });
  fit();
  new ResizeObserver(fit).observe(frame);

  const setActive = (index, progress) => {
    steps.forEach((s, i) => {
      s.classList.toggle('is-active', i === index);
      s.classList.toggle('is-past', i < index);
    });
    stepsList.style.setProperty('--p', progress.toFixed(4));
  };

  if (reduce) {
    tl.progress(1);
    setActive(5, 1);
    return;
  }
  setActive(0, 0);

  // Step labels follow the drawing itself, so they never run ahead of the scrubbed animation.
  tl.eventCallback('onUpdate', () => {
    const t = tl.time();
    setActive(Math.min(5, Math.floor(t + 0.05)), Math.min(1, t / 5.4));
  });
  ST.create({
    trigger: root,
    start: 'top top',
    end: () => `+=${Math.round(window.innerHeight * 4.6)}`,
    pin: true,
    scrub: 0.6,
    animation: tl,
    anticipatePin: 1,
    invalidateOnRefresh: true,
  });
}
