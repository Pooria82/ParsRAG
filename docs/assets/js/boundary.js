// Trust boundary: an illuminated frame around the workstation. Parsing, embeddings and
// Qdrant never leave it; the gate opens only when the model runs behind an API.
import { rovingGroup } from './util.js';

const NS = 'http://www.w3.org/2000/svg';

const LAYOUTS = {
  wide: {
    vb: [1000, 470],
    frame: { x: 20, y: 50, w: 700, h: 390 },
    gate: { x: 720, y: 240, axis: 'y' },
    nodes: {
      docs: [60, 120, 170, 56], parse: [275, 120, 170, 56], embed: [490, 120, 170, 56],
      ollama: [60, 300, 170, 56], adapter: [275, 300, 170, 56], qdrant: [490, 300, 170, 56],
      private: [790, 140, 190, 56], external: [790, 300, 190, 56],
    },
    routes: {
      pipeline: [[145, 148], [360, 148], [575, 148], [575, 328], [360, 328]],
      local: [[360, 328], [145, 328]],
      private: [[360, 328], [360, 240], [760, 240], [760, 168], [885, 168]],
      external: [[360, 328], [360, 240], [760, 240], [760, 328], [885, 328]],
    },
    packetLabel: [740, 226, 'start'],
  },
  narrow: {
    vb: [400, 750],
    frame: { x: 12, y: 50, w: 376, h: 560 },
    gate: { x: 330, y: 610, axis: 'x' },
    nodes: {
      docs: [100, 90, 200, 50], parse: [100, 170, 200, 50], embed: [100, 250, 200, 50],
      qdrant: [100, 330, 200, 50], adapter: [100, 410, 200, 50], ollama: [100, 520, 200, 50],
      private: [14, 680, 180, 50], external: [206, 680, 180, 50],
    },
    routes: {
      pipeline: [[200, 115], [200, 435]],
      local: [[200, 435], [200, 545]],
      private: [[200, 435], [330, 435], [330, 646], [104, 646], [104, 705]],
      external: [[200, 435], [330, 435], [330, 646], [296, 646], [296, 705]],
    },
    packetLabel: [200, 634, 'middle'],
  },
};

const COLORS = { pipeline: '#79C5AA', local: '#D2B06A', private: '#79C5AA', external: '#7E9BE0' };

const el = (name, attrs = {}, parent) => {
  const node = document.createElementNS(NS, name);
  for (const [k, v] of Object.entries(attrs)) node.setAttribute(k, v);
  parent?.append(node);
  return node;
};

const star = (cx, cy, r) => {
  const pts = [];
  for (let i = 0; i < 16; i++) {
    const a = (Math.PI / 8) * i - Math.PI / 2;
    const rr = i % 2 ? r * 0.55 : r;
    pts.push(`${(cx + Math.cos(a) * rr).toFixed(2)},${(cy + Math.sin(a) * rr).toFixed(2)}`);
  }
  return pts.join(' ');
};

function measure(points) {
  const segs = [];
  let total = 0;
  for (let i = 1; i < points.length; i++) {
    const [x1, y1] = points[i - 1];
    const [x2, y2] = points[i];
    const len = Math.hypot(x2 - x1, y2 - y1);
    segs.push({ x1, y1, x2, y2, len, start: total });
    total += len;
  }
  return { segs, total };
}

function pointAt({ segs, total }, t) {
  const d = t * total;
  const s = segs.find((seg) => d <= seg.start + seg.len) || segs[segs.length - 1];
  const k = s.len ? (d - s.start) / s.len : 0;
  return [s.x1 + (s.x2 - s.x1) * k, s.y1 + (s.y2 - s.y1) * k];
}

export function initBoundary({ gsap, ST, reduce, rtl }) {
  const root = document.querySelector('[data-boundary]');
  if (!root) return;
  const svg = root.querySelector('.boundary__svg');
  const note = root.querySelector('.boundary__note');
  const buttons = [...root.querySelectorAll('[data-provider]')];
  const label = (key) => root.dataset[key];
  let provider = 'local';
  let scene = null;

  function build(name) {
    const L = LAYOUTS[name];
    const [W, H] = L.vb;
    const mx = (x, w = 0) => (rtl ? W - x - w : x);
    const mp = (pts) => pts.map(([x, y]) => [mx(x), y]);
    svg.replaceChildren();
    svg.setAttribute('viewBox', `0 0 ${W} ${H}`);

    const { x, y, w, h } = L.frame;
    const fx = mx(x, w);
    el('rect', { class: 'b-frame', x: fx, y, width: w, height: h, rx: 22 }, svg);
    el('rect', { class: 'b-frame-dots', x: fx + 5, y: y + 5, width: w - 10, height: h - 10, rx: 18 }, svg);
    el('rect', { class: 'b-frame-inner', x: fx + 10, y: y + 10, width: w - 20, height: h - 20, rx: 14 }, svg);
    for (const [cx, cy] of [[fx, y], [fx + w, y], [fx, y + h], [fx + w, y + h]]) {
      el('polygon', { class: 'b-star', points: star(cx, cy, 13) }, svg);
      el('circle', { class: 'b-star-core', cx, cy, r: 2.6 }, svg);
    }

    // Title cartouche on the top edge.
    const titleText = label('frame');
    const cart = el('g', {}, svg);
    const tw = Math.max(150, titleText.length * 12 + 48);
    const tcx = fx + w / 2;
    el('rect', { x: tcx - tw / 2, y: y - 20, width: tw, height: 40, rx: 20, fill: '#0A221C', stroke: '#D2B06A', 'stroke-width': 1.2 }, cart);
    const tt = el('text', { class: 'b-frame-label', x: tcx, y: y + 1, 'text-anchor': 'middle', 'dominant-baseline': 'central' }, cart);
    tt.textContent = titleText;

    // Gate: a gap in the frame, closed by two gilt leaves.
    const g = L.gate;
    const gx = mx(g.x);
    const gate = el('g', {}, svg);
    const vertical = g.axis === 'y';
    if (vertical) el('rect', { class: 'b-gate-gap', x: gx - 14, y: g.y - 30, width: 28, height: 60 }, gate);
    else el('rect', { class: 'b-gate-gap', x: gx - 30, y: g.y - 14, width: 60, height: 28 }, gate);
    const glow = vertical
      ? el('line', { class: 'b-gate-glow', x1: gx, y1: g.y - 26, x2: gx, y2: g.y + 26 }, gate)
      : el('line', { class: 'b-gate-glow', x1: gx - 26, y1: g.y, x2: gx + 26, y2: g.y }, gate);
    const doors = vertical
      ? [el('rect', { class: 'b-door', x: gx - 5, y: g.y - 30, width: 10, height: 30, rx: 3 }, gate), el('rect', { class: 'b-door', x: gx - 5, y: g.y, width: 10, height: 30, rx: 3 }, gate)]
      : [el('rect', { class: 'b-door', x: gx - 30, y: g.y - 5, width: 30, height: 10, rx: 3 }, gate), el('rect', { class: 'b-door', x: gx, y: g.y - 5, width: 30, height: 10, rx: 3 }, gate)];

    // Routes under the nodes; packets travel along them.
    const routes = {};
    const linkLayer = el('g', {}, svg);
    const packetLayer = el('g', {}, svg);
    for (const [key, pts] of Object.entries(L.routes)) {
      const mpts = mp(pts);
      const line = el('polyline', { class: `b-link${key === 'pipeline' ? '' : ` b-link--route b-link--${key}`}`, points: mpts.map((p) => p.join(',')).join(' ') }, linkLayer);
      const packets = Array.from({ length: key === 'pipeline' ? 4 : 3 }, () => el('circle', { class: 'b-packet', r: 4, fill: COLORS[key], opacity: 0 }, packetLayer));
      routes[key] = { line, packets, path: measure(mpts) };
    }

    const nodes = {};
    for (const [key, [nx, ny, nw, nh]] of Object.entries(L.nodes)) {
      const out = key === 'private' || key === 'external';
      const cls = ['b-node', out ? `b-node--out b-node--${key}` : '', key === 'ollama' ? 'b-node--model b-node--ollama' : '', key === 'adapter' ? 'b-node--model' : ''].join(' ');
      const group = el('g', { class: cls }, svg);
      const rx = mx(nx, nw);
      el('rect', { x: rx, y: ny, width: nw, height: nh, rx: 12 }, group);
      const text = el('text', { x: rx + nw / 2, y: ny + nh / 2 }, group);
      text.textContent = label(key === 'parse' ? 'parse' : key);
      nodes[key] = group;
    }

    const [plx, ply, anchor] = L.packetLabel;
    const pl = el('text', { class: 'b-packet-label', x: mx(plx), y: ply, 'text-anchor': anchor === 'middle' ? 'middle' : rtl ? 'end' : 'start' }, svg);
    pl.textContent = label('packet');

    scene = { routes, nodes, doors, glow, vertical, packetLabel: pl };
    apply(true);
  }

  function apply(instant) {
    if (!scene) return;
    const { routes, nodes, doors, glow, vertical, packetLabel } = scene;
    const out = provider !== 'local';
    nodes.ollama.classList.toggle('is-off', out);
    nodes.private.classList.toggle('is-on', provider === 'private');
    nodes.external.classList.toggle('is-on', provider === 'external');
    for (const key of ['local', 'private', 'external']) routes[key].line.classList.toggle('is-on', key === provider);
    packetLabel.classList.toggle('is-on', out);
    const shift = out ? 26 : 0;
    const dur = instant || reduce ? 0 : 0.7;
    const prop = vertical ? 'y' : 'x';
    gsap.to(doors[0], { [prop]: -shift, duration: dur, ease: 'power3.inOut' });
    gsap.to(doors[1], { [prop]: shift, duration: dur, ease: 'power3.inOut' });
    gsap.to(glow, { opacity: out ? 0.9 : 0, stroke: provider === 'external' ? '#4A6FC0' : '#79C5AA', duration: dur });
    note.style.setProperty('--note-c', provider === 'external' ? '#7E9BE0' : provider === 'private' ? '#79C5AA' : '#D2B06A');
  }

  rovingGroup({
    root: root.querySelector('.seg'),
    buttons,
    attr: 'aria-checked',
    rtl,
    gsap,
    thumb: root.querySelector('.seg__thumb'),
    onSelect: (i, fromUser) => {
      provider = buttons[i].dataset.provider;
      apply(!fromUser);
      const text = note.dataset[`note${provider[0].toUpperCase()}${provider.slice(1)}`];
      if (reduce || !fromUser) note.textContent = text;
      else gsap.timeline().to(note, { autoAlpha: 0, y: 6, duration: 0.18 }).add(() => { note.textContent = text; }).to(note, { autoAlpha: 1, y: 0, duration: 0.35 });
    },
  });

  const narrow = matchMedia('(max-width: 640px)');
  build(narrow.matches ? 'narrow' : 'wide');
  narrow.addEventListener('change', (e) => build(e.matches ? 'narrow' : 'wide'));

  // Packets flow while the frame is on screen.
  let visible = false;
  const tick = (time) => {
    if (!scene) return;
    for (const [key, r] of Object.entries(scene.routes)) {
      const on = key === 'pipeline' || key === provider;
      const n = r.packets.length;
      r.packets.forEach((c, i) => {
        if (!on) { c.setAttribute('opacity', 0); return; }
        const t = ((time * 70) / r.path.total + i / n) % 1;
        const [px, py] = pointAt(r.path, t);
        c.setAttribute('cx', px.toFixed(1));
        c.setAttribute('cy', py.toFixed(1));
        c.setAttribute('opacity', Math.min(1, Math.sin(t * Math.PI) * 2.2).toFixed(2));
      });
    }
  };
  if (reduce) {
    tick(0.6);
    return;
  }
  ST.create({
    trigger: root,
    start: 'top bottom',
    end: 'bottom top',
    onToggle: (self) => {
      if (self.isActive === visible) return;
      visible = self.isActive;
      if (visible) gsap.ticker.add(tick);
      else gsap.ticker.remove(tick);
    },
  });
}
