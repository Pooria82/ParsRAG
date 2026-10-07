// Two directions: a divider between the Persian and English workspaces.
export function initCompare({ gsap, ST, reduce }) {
  const root = document.querySelector('[data-compare]');
  if (!root) return;
  const range = root.querySelector('.compare__range');
  const set = (v) => root.style.setProperty('--pos', `${v}%`);
  range.addEventListener('input', () => set(range.value));
  set(range.value);

  if (reduce) return;
  // A single hint that the divider moves, the first time it comes into view.
  const proxy = { v: 50 };
  ST.create({
    trigger: root,
    start: 'top 65%',
    once: true,
    onEnter: () => {
      gsap.to(proxy, {
        keyframes: [{ v: 68, duration: 0.9 }, { v: 34, duration: 1.1 }, { v: 50, duration: 0.8 }],
        ease: 'power2.inOut',
        onUpdate: () => {
          range.value = Math.round(proxy.v);
          set(proxy.v.toFixed(2));
        },
      });
    },
  });
}
