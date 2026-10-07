// Boots the page: smooth scrolling, then one module per section.
import { initHero } from './hero.js';
import { initMarginalia } from './marginalia.js';
import { initJourney } from './journey.js';
import { initModes } from './modes.js';
import { initBoundary } from './boundary.js';
import { initShelf } from './shelf.js';
import { initCompare } from './compare.js';
import { initTerminal } from './terminal.js';
import { initCoda } from './coda.js';

const html = document.documentElement;

function markReady(isStatic) {
  clearTimeout(window.__revealFailsafe);
  html.classList.add('is-ready');
  if (isStatic) html.classList.add('is-static');
}

async function boot() {
  const { gsap, ScrollTrigger, Lenis } = window;
  const ctx = {
    gsap,
    ST: ScrollTrigger,
    rtl: html.dir === 'rtl',
    lang: html.lang,
    reduce: matchMedia('(prefers-reduced-motion: reduce)').matches,
  };

  if (!gsap || !ScrollTrigger) {
    markReady(true);
    return;
  }
  gsap.registerPlugin(ScrollTrigger);

  const topbar = document.querySelector('[data-topbar]');
  ScrollTrigger.create({
    start: 24,
    end: 'max',
    onToggle: (self) => topbar.classList.toggle('is-solid', self.isActive),
  });

  if (!ctx.reduce && Lenis) {
    const lenis = new Lenis({ lerp: 0.1, smoothWheel: true, anchors: { offset: -8 }, autoRaf: false });
    lenis.on('scroll', ScrollTrigger.update);
    gsap.ticker.add((time) => lenis.raf(time * 1000));
    gsap.ticker.lagSmoothing(0);
    ctx.lenis = lenis;
  }

  // Glyphs are drawn with Vazirmatn; wait for it, but never longer than a moment.
  await Promise.race([document.fonts.ready, new Promise((r) => setTimeout(r, 1500))]);

  for (const init of [initHero, initMarginalia, initJourney, initModes, initBoundary, initShelf, initCompare, initTerminal, initCoda]) {
    try {
      init(ctx);
    } catch (error) {
      console.error(`[ParsRAG] ${init.name} failed`, error);
    }
  }
  markReady(ctx.reduce);
  ScrollTrigger.refresh();
}

boot();
