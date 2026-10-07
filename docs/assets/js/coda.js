// Coda: the mark is drawn by a single gold thread, then filled in.
export function initCoda({ gsap, ST, reduce }) {
  const mark = document.querySelector('[data-coda-mark] .mark');
  if (!mark || reduce) return;
  const shapes = [...mark.querySelectorAll('path')];
  shapes.forEach((p) => {
    p.setAttribute('pathLength', '1');
  });
  const fills = shapes.filter((p) => !p.classList.contains('mark__lines'));
  const lines = mark.querySelector('.mark__lines');

  gsap.set(shapes, { strokeDasharray: 1, strokeDashoffset: 1, stroke: '#D2B06A', strokeWidth: 0.6 });
  gsap.set(fills, { fillOpacity: 0 });
  gsap.set(lines, { opacity: 0 });

  const tl = gsap.timeline({ paused: true });
  tl.to(shapes, { strokeDashoffset: 0, duration: 1.6, stagger: 0.12, ease: 'power2.inOut' })
    .to(fills, { fillOpacity: 1, duration: 0.8, ease: 'power1.out' }, '-=0.5')
    .to(lines, { opacity: 1, stroke: '#0F2E27', strokeWidth: 1.9, duration: 0.6 }, '<')
    .to(fills, { strokeWidth: 0, duration: 0.6 }, '<');

  ST.create({ trigger: mark, start: 'top 80%', once: true, onEnter: () => tl.play() });
}
