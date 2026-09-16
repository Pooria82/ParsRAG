import { useCallback, useRef } from 'react';
import { flushSync } from 'react-dom';
import type { Theme } from '../types';

interface ThemeTransition {
  finished: Promise<void>;
  skipTransition: () => void;
}

type TransitionDocument = Document & {
  startViewTransition?: (update: () => void) => ThemeTransition;
};

export interface ThemeOrigin {
  x: number;
  y: number;
}

export function useThemeTransition(onChange: (theme: Theme) => void) {
  const activeTransition = useRef<ThemeTransition>();

  return useCallback((theme: Theme, origin?: ThemeOrigin) => {
    const root = document.documentElement;
    const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    const x = origin?.x ?? window.innerWidth / 2;
    const y = origin?.y ?? window.innerHeight / 2;
    root.style.setProperty('--theme-x', `${x}px`);
    root.style.setProperty('--theme-y', `${y}px`);

    const transitionDocument = document as TransitionDocument;
    if (!transitionDocument.startViewTransition || reducedMotion) {
      onChange(theme);
      return;
    }

    activeTransition.current?.skipTransition();
    root.dataset.themeDirection = theme;
    const transition = transitionDocument.startViewTransition(() => flushSync(() => onChange(theme)));
    activeTransition.current = transition;
    void transition.finished.finally(() => {
      if (activeTransition.current === transition) activeTransition.current = undefined;
      delete root.dataset.themeDirection;
    });
  }, [onChange]);
}
