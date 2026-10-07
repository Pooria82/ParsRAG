// Formats shelf: pulling a book out shows what that family covers.
import { rovingGroup } from './util.js';

export function initShelf({ gsap, reduce, rtl }) {
  const root = document.querySelector('[data-shelf]');
  if (!root) return;
  const books = [...root.querySelectorAll('.book[role="tab"]')];
  const cards = books.map((b) => document.getElementById(b.getAttribute('aria-controls')));

  rovingGroup({
    root: root.querySelector('.books'),
    buttons: books,
    rtl,
    gsap,
    onSelect: (i, fromUser) => {
      cards.forEach((c, j) => { c.hidden = j !== i; });
      if (fromUser && !reduce) {
        gsap.fromTo(cards[i].children, { autoAlpha: 0, y: 12 }, { autoAlpha: 1, y: 0, duration: 0.5, stagger: 0.06, ease: 'power3.out' });
      }
    },
  });
  root.querySelector('.books').classList.remove('no-thumb');
}
