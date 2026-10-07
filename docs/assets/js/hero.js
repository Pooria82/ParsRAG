// Hero: Persian letters drift like ink dust, then gather into the ParsRAG mark.
// The pointer stirs them; scrolling away lets them fall toward the page below.
import { splitWords, clamp } from './util.js';

const MARK = {
  left: 'M23.9 12.2C18.2 6.8 10.7 7.5 7.4 10.6v23.8c5.2-2.8 10.7-1.5 16.5 4.1V12.2Z',
  right: 'M24.1 12.2c5.7-5.4 13.2-4.7 16.5-1.6v23.8c-5.2-2.8-10.7-1.5-16.5 4.1V12.2Z',
  lines: 'M24 37.8V14.2M11.8 16c3-.8 5.7-.1 8 1.7m-8 5c3-.8 5.7-.1 8 1.7m8.4-6.7c2.3-1.8 5-2.5 8-1.7m-8 8.4c2.3-1.8 5-2.5 8-1.7',
  spark: 'M24 2.2c.35 2.2 1.7 3.55 3.9 3.9C25.7 6.45 24.35 7.8 24 10c-.35-2.2-1.7-3.55-3.9-3.9 2.2-.35 3.55-1.7 3.9-3.9Z',
  spark2: 'M39.7 6.8c.2 1.2.95 1.95 2.15 2.15-1.2.2-1.95.95-2.15 2.15-.2-1.2-.95-1.95-2.15-2.15 1.2-.2 1.95-.95 2.15-2.15Z',
};

const LETTERS = [...'ابپتثجچحخدذرزژسشصضطظعغفقکگلمنوهی'];
const LATIN = [...'aeinorstRAG'];
const DIGITS = [...'۰۱۲۳۴۵۶۷۸۹'];
const COLORS = { left: '#5DA68D', right: '#8FD3BA', lines: '#EEF2EA', spark: '#E2C27E', ambient: '#79C5AA' };
const SPRITE_FONT = 20; // px the sprite glyph is drawn at
const SPRITE_BOX = 30; // px of the sprite canvas

const pick = (list) => list[(Math.random() * list.length) | 0];
const rand = (a, b) => a + Math.random() * (b - a);
const easeInOut = (t) => (t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2);

export function initHero({ gsap, ST, reduce }) {
  const hero = document.querySelector('.hero');
  const canvas = hero?.querySelector('.hero__field');
  const slot = hero?.querySelector('.hero__slot');
  const title = hero?.querySelector('[data-words]');
  if (!hero || !canvas || !slot) return;
  const c2d = canvas.getContext('2d');
  if (!c2d) return;

  const state = { intro: reduce ? 1 : 0, gather: reduce ? 1 : 0, scatter: 0 };
  const pointer = { x: 0, y: 0, active: false };
  const sprites = new Map();
  let parts = [];
  let W = 0;
  let H = 0;
  let dpr = 1;
  let lastWidth = 0;

  function sprite(ch, color) {
    const key = ch + color;
    let cv = sprites.get(key);
    if (cv) return cv;
    cv = document.createElement('canvas');
    cv.width = cv.height = Math.ceil(SPRITE_BOX * dpr);
    const g = cv.getContext('2d');
    g.scale(dpr, dpr);
    g.fillStyle = color;
    g.font = `500 ${SPRITE_FONT}px Vazirmatn, "Markazi Text", sans-serif`;
    g.textAlign = 'center';
    g.textBaseline = 'middle';
    g.fillText(ch, SPRITE_BOX / 2, SPRITE_BOX / 2 + 1);
    sprites.set(key, cv);
    return cv;
  }

  // Render the mark with a flat color per part, then sample it on a staggered grid.
  function sampleMark(size) {
    const off = document.createElement('canvas');
    off.width = off.height = size;
    const g = off.getContext('2d', { willReadFrequently: true });
    g.scale(size / 48, size / 48);
    g.fillStyle = '#f00';
    g.fill(new Path2D(MARK.left));
    g.fillStyle = '#0f0';
    g.fill(new Path2D(MARK.right));
    g.strokeStyle = '#00f';
    g.lineWidth = 2.4;
    g.lineCap = 'round';
    g.stroke(new Path2D(MARK.lines));
    g.fillStyle = '#ff0';
    g.fill(new Path2D(MARK.spark));
    g.fill(new Path2D(MARK.spark2));
    const data = g.getImageData(0, 0, size, size).data;
    const step = Math.max(5, Math.round(size / 34));
    const points = [];
    for (let y = 0, row = 0; y < size; y += step * 0.88, row++) {
      for (let x = (row % 2) * (step / 2); x < size; x += step) {
        const px = Math.round(x);
        const py = Math.round(y);
        const i = (py * size + px) * 4;
        if (data[i + 3] < 140) continue;
        const [r, gr, b] = [data[i], data[i + 1], data[i + 2]];
        let kind;
        if (b > 120) kind = 'lines';
        else if (r > 170 && gr > 170) kind = 'spark';
        else if (r > gr) kind = 'left';
        else kind = 'right';
        if (kind === 'left' && Math.random() < 0.3) continue;
        points.push({ x: px / size - 0.5, y: py / size - 0.5, kind });
      }
    }
    // The spark is tiny; give it a few more glyphs so it reads as a star.
    for (let k = 0; k < 10; k++) {
      const a = (k / 10) * Math.PI * 2;
      const rr = k % 2 ? 0.035 : 0.065;
      // The large spark is centered at (24, 6.1) in the 48-unit mark.
      points.push({ x: Math.cos(a) * rr, y: 6.1 / 48 - 0.5 + Math.sin(a) * rr, kind: 'spark' });
    }
    return points;
  }

  function build() {
    const hr = hero.getBoundingClientRect();
    const sr = slot.getBoundingClientRect();
    W = hr.width;
    H = hr.height;
    lastWidth = W;
    dpr = Math.min(window.devicePixelRatio || 1, 2);
    canvas.width = Math.round(W * dpr);
    canvas.height = Math.round(H * dpr);
    c2d.setTransform(dpr, 0, 0, dpr, 0, 0);
    sprites.clear();

    const size = Math.round(sr.width);
    const cx = sr.left - hr.left + sr.width / 2;
    const cy = sr.top - hr.top + sr.height / 2;
    const small = W < 700;
    const glyphScale = clamp(size / 230, 0.7, 1.25);

    parts = sampleMark(size).map((pt) => {
      const tx = cx + pt.x * size;
      const ty = cy + pt.y * size;
      const dist = Math.hypot(pt.x, pt.y);
      return {
        kind: pt.kind,
        tx,
        ty,
        hx: rand(-0.05, 1.05) * W,
        hy: rand(-0.05, 1.05) * H,
        ch: pt.kind === 'spark' ? pick(['٭', '✦', '*']) : pt.kind === 'lines' ? pick([...LETTERS, ...LATIN]) : pick(LETTERS),
        color: COLORS[pt.kind],
        size: (pt.kind === 'lines' ? 11 : pt.kind === 'spark' ? 12 : rand(11, 15)) * glyphScale,
        alpha: pt.kind === 'left' ? 0.55 : pt.kind === 'right' ? 0.92 : 1,
        delay: Math.random() * 0.35 + dist * 0.5,
        ph: Math.random() * Math.PI * 2,
        sp: rand(0.15, 0.45),
        fall: rand(120, 520),
        drift: rand(-90, 90),
        ox: 0,
        oy: 0,
      };
    });

    const ambient = small ? 50 : 130;
    for (let k = 0; k < ambient; k++) {
      parts.push({
        kind: 'ambient',
        hx: Math.random() * W,
        hy: Math.random() * H,
        ch: pick([...LETTERS, ...DIGITS]),
        color: COLORS.ambient,
        size: rand(8, 15),
        alpha: rand(0.06, 0.2),
        ph: Math.random() * Math.PI * 2,
        sp: rand(0.08, 0.25),
        fall: rand(60, 260),
        drift: rand(-40, 40),
        ox: 0,
        oy: 0,
      });
    }
  }

  function draw(now) {
    const t = now * 0.001;
    c2d.clearRect(0, 0, W, H);
    const { gather, scatter, intro } = state;
    const R = 120;
    for (const p of parts) {
      let x;
      let y;
      let a;
      const fx = p.hx + Math.sin(t * p.sp + p.ph) * 22;
      const fy = p.hy + Math.cos(t * p.sp * 0.8 + p.ph) * 16;
      if (p.kind === 'ambient') {
        x = fx;
        y = fy;
        a = p.alpha * intro;
      } else {
        const e = easeInOut(clamp((gather * 1.6 - p.delay) / 0.75, 0, 1));
        const bx = p.tx + Math.sin(t * 1.4 + p.ph) * 0.7;
        const by = p.ty + Math.cos(t * 1.2 + p.ph) * 0.7;
        x = fx + (bx - fx) * e;
        y = fy + (by - fy) * e;
        a = p.alpha * (0.22 + 0.78 * e) * intro;
        if (p.kind === 'spark') a *= 0.72 + 0.28 * Math.sin(t * 2.6 + p.ph);
      }
      if (scatter > 0) {
        const s = scatter * scatter;
        x += p.drift * s;
        y += p.fall * s;
        a *= 1 - scatter * 0.9;
      }
      let tox = 0;
      let toy = 0;
      if (pointer.active) {
        const dx = x - pointer.x;
        const dy = y - pointer.y;
        const d2 = dx * dx + dy * dy;
        if (d2 < R * R) {
          const d = Math.sqrt(d2) || 1;
          const f = (1 - d / R) ** 2 * 34;
          tox = (dx / d) * f;
          toy = (dy / d) * f;
        }
      }
      p.ox += (tox - p.ox) * 0.1;
      p.oy += (toy - p.oy) * 0.1;
      x += p.ox;
      y += p.oy;
      if (a < 0.01 || y < -20 || y > H + 20) continue;
      const box = (p.size * SPRITE_BOX) / SPRITE_FONT;
      c2d.globalAlpha = a;
      c2d.drawImage(sprite(p.ch, p.color), x - box / 2, y - box / 2, box, box);
    }
    c2d.globalAlpha = 1;
  }

  build();

  // Static composition for reduced motion: the gathered mark, no loop.
  if (reduce) {
    draw(0);
    let timer;
    window.addEventListener('resize', () => {
      clearTimeout(timer);
      timer = setTimeout(() => { build(); draw(0); }, 150);
    });
    return;
  }

  // Render loop, paused when the hero is off screen.
  let running = false;
  const tick = () => draw(performance.now());
  const setRunning = (on) => {
    if (on === running) return;
    running = on;
    if (on) gsap.ticker.add(tick);
    else gsap.ticker.remove(tick);
  };
  new IntersectionObserver(([entry]) => setRunning(entry.isIntersecting)).observe(hero);

  hero.addEventListener('pointermove', (e) => {
    const r = hero.getBoundingClientRect();
    pointer.x = e.clientX - r.left;
    pointer.y = e.clientY - r.top;
    pointer.active = true;
  });
  hero.addEventListener('pointerleave', () => { pointer.active = false; });

  let resizeTimer;
  window.addEventListener('resize', () => {
    clearTimeout(resizeTimer);
    resizeTimer = setTimeout(() => {
      if (Math.abs(hero.getBoundingClientRect().width - lastWidth) > 2) build();
    }, 180);
  });

  // The one orchestrated moment: ink gathers, then the words arrive.
  const words = title ? splitWords(title) : [];
  const intro = gsap.timeline({ delay: 0.1 });
  intro
    .to(state, { intro: 1, duration: 1.1, ease: 'power1.out' }, 0)
    .to(state, { gather: 1, duration: 2.8, ease: 'none' }, 0.2)
    .fromTo('[data-hero="pill"]', { opacity: 0, y: 14 }, { opacity: 1, y: 0, duration: 0.9, ease: 'power3.out' }, 1.0)
    .fromTo(title, { opacity: 0 }, { opacity: 1, duration: 0.01 }, 1.1)
    .fromTo(words, { opacity: 0, y: '0.38em', filter: 'blur(12px)' }, { opacity: 1, y: 0, filter: 'blur(0px)', duration: 1.1, stagger: 0.075, ease: 'power3.out' }, 1.1)
    .fromTo('[data-hero="lead"]', { opacity: 0, y: 16 }, { opacity: 1, y: 0, duration: 1, ease: 'power3.out' }, 1.7)
    .fromTo('[data-hero="actions"]', { opacity: 0, y: 16 }, { opacity: 1, y: 0, duration: 1, ease: 'power3.out' }, 1.9)
    .fromTo('[data-hero="cue"]', { opacity: 0 }, { opacity: 1, duration: 1 }, 2.6)
    .add(() => words.forEach((w) => { w.style.willChange = 'auto'; w.style.filter = ''; }));

  // Leaving the hero: the letters fall toward the page below and the copy lifts away.
  ST.create({
    trigger: hero,
    start: 'top top',
    end: 'bottom top',
    scrub: true,
    onUpdate: (self) => { state.scatter = self.progress; },
  });
  gsap.to('.hero__content', {
    yPercent: -14,
    opacity: 0,
    ease: 'none',
    scrollTrigger: { trigger: hero, start: 'top top', end: 'bottom 15%', scrub: true },
  });
}
