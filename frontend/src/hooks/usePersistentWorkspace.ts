import { useCallback, useEffect, useRef, useState, type SetStateAction } from 'react';
import type { AppSettings, Session } from '../types';
import { createSession, parseSessions, parseSettings, STORAGE } from '../core/state';
import { hydrateSessions, openIndexedDbStore, type KeyValueStore } from '../core/storage';

function readStorage(key: string): string | null {
  try { return localStorage.getItem(key); } catch { return null; }
}

const SAVE_DELAY_MS = 250;

/**
 * Conversations live in IndexedDB (localStorage as a fallback); preferences
 * and the active conversation stay in localStorage for a synchronous start.
 */
export function usePersistentWorkspace() {
  const [settings, setSettings] = useState<AppSettings>(() => parseSettings(readStorage(STORAGE.settings), window.location.origin));
  const [sessions, setSessionsState] = useState<Session[]>(() => {
    const stored = parseSessions(readStorage(STORAGE.sessions));
    return stored.length ? stored : [createSession(settings.language, settings.defaultMode)];
  });
  const [activeId, setActiveId] = useState(() => {
    const stored = readStorage(STORAGE.active);
    return sessions.some(session => session.id === stored) ? stored! : sessions[0].id;
  });
  const [storageError, setStorageError] = useState(false);
  const [hydrated, setHydrated] = useState(false);
  const storeRef = useRef<KeyValueStore | null>(null);
  const hydratedRef = useRef(false);
  const editedRef = useRef(false);
  /** Record edits made before stored conversations finish loading. */
  const setSessions = useCallback((value: SetStateAction<Session[]>) => {
    if (!hydratedRef.current) editedRef.current = true;
    setSessionsState(value);
  }, []);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      const store = await openIndexedDbStore();
      if (cancelled) return;
      if (store) {
        try {
          const result = await hydrateSessions(store, STORAGE.sessions, readStorage(STORAGE.sessions), () => {
            try { localStorage.removeItem(STORAGE.sessions); } catch { /* Nothing to free. */ }
          });
          if (cancelled) return;
          storeRef.current = store;
          const loaded = parseSessions(result.sessions);
          // A migration loads what the first render already showed.
          if (loaded.length && !result.migrated) {
            if (editedRef.current) {
              // Keep edits made while loading; add conversations not on screen.
              setSessionsState(current => [...current, ...loaded.filter(session => !current.some(item => item.id === session.id))]);
            } else {
              setSessionsState(loaded);
              const active = readStorage(STORAGE.active);
              setActiveId(loaded.some(session => session.id === active) ? active! : loaded[0].id);
            }
          }
        } catch { storeRef.current = null; }
      }
      if (!cancelled) { hydratedRef.current = true; setHydrated(true); }
    })();
    return () => { cancelled = true; };
  }, []);

  useEffect(() => {
    try {
      localStorage.setItem(STORAGE.settings, JSON.stringify(settings));
      localStorage.setItem(STORAGE.active, activeId);
    } catch { setStorageError(true); }
  }, [settings, activeId]);

  useEffect(() => {
    // Never overwrite stored conversations with the blank first render.
    if (!hydrated) return;
    const timer = window.setTimeout(() => {
      const serialized = JSON.stringify(sessions);
      const store = storeRef.current;
      const fallback = () => {
        try { localStorage.setItem(STORAGE.sessions, serialized); setStorageError(false); } catch { setStorageError(true); }
      };
      if (!store) { fallback(); return; }
      store.set(STORAGE.sessions, serialized).then(() => setStorageError(false)).catch(fallback);
    }, SAVE_DELAY_MS);
    return () => window.clearTimeout(timer);
  }, [sessions, hydrated]);

  return { settings, setSettings, sessions, setSessions, activeId, setActiveId, storageError, hydrated };
}
