import { useCallback, useRef } from 'react';
import { flushSync } from 'react-dom';
import type { Language } from '../types';

interface ViewTransition {
  finished: Promise<void>;
  skipTransition: () => void;
}

type TransitionDocument = Document & {
  startViewTransition?: (update: () => void) => ViewTransition;
};

export function useLanguageTransition(onChange: (language: Language) => void) {
  const activeTransition = useRef<ViewTransition>();
  return useCallback((language: Language) => {
    const root = document.documentElement;
    const transitionDocument = document as TransitionDocument;
    if (!transitionDocument.startViewTransition || window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
      onChange(language); return;
    }
    activeTransition.current?.skipTransition();
    root.dataset.languageTransition = language;
    const transition = transitionDocument.startViewTransition(() => flushSync(() => onChange(language)));
    activeTransition.current = transition;
    void transition.finished.finally(() => {
      if (activeTransition.current === transition) activeTransition.current = undefined;
      delete root.dataset.languageTransition;
    });
  }, [onChange]);
}
