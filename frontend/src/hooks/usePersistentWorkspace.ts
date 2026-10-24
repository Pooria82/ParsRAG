import { useCallback, useEffect, useRef, useState, type SetStateAction } from 'react';
import type { AppSettings, Session } from '../types';
import { createSession, parseSessions, parseSettings, STORAGE } from '../core/state';
import { hydrateSessions, mergeSavedSessions, openIndexedDbStore, type KeyValueStore } from '../core/storage';

function readStorage(key: string): string | null {
  try { return localStorage.getItem(key); } catch { return null; }
}

const SAVE_DELAY_MS = 250;
const CHANNEL = 'parsrag_workspace';

type SavedMessage = { savedAt: number; sessions: string };

/**
 * Conversations live in IndexedDB (localStorage as a fallback); preferences
 * and the active conversation stay in localStorage for a synchronous start.
 * Each save is announced to the app's other open tabs, which merge it, so two
 * tabs do not overwrite each other's conversations.
 */
export function usePersistentWorkspace() {
  const [settings, setSettings] = useState<AppSettings>(() => parseSettings(readStorage(STORAGE.settings), window.location.origin));
  const [sessions, setSessionsState] = useState<Session[]>(() => {
    const stored = parseSessions(readStorage(STORAGE.sessions));
    return stored.length ? stored : [createSession(settings.language, settings.defaultMode)];
  });
  // Read once: the first render may show a blank conversation whose id must
  // not replace the one that was open before the reload.
  const [storedActive] = useState(() => readStorage(STORAGE.active));
  const [activeId, setActiveId] = useState(() =>
    sessions.some(session => session.id === storedActive) ? storedActive! : sessions[0].id);
  const [storageError, setStorageError] = useState(false);
  const [hydrated, setHydrated] = useState(false);
  const storeRef = useRef<KeyValueStore | null>(null);
  const hydratedRef = useRef(false);
  const editedRef = useRef(false);
  const channelRef = useRef<BroadcastChannel | null>(null);
  /** Conversations taken from another tab; they are already saved. */
  const receivedRef = useRef<Session[] | null>(null);
  const sessionsRef = useRef(sessions);
  sessionsRef.current = sessions;
  /** Conversations changed or deleted here since the last save, kept in a merge. */
  const changedRef = useRef(new Set<string>());
  const deletedRef = useRef(new Set<string>());
  const previousRef = useRef(sessions);
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
            try { localStorage.removeItem(STORAGE.sessions); localStorage.removeItem(STORAGE.sessionsFallback); } catch { /* Nothing to free. */ }
          }, readStorage(STORAGE.sessionsFallback) !== null);
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
              setActiveId(loaded.some(session => session.id === storedActive) ? storedActive! : loaded[0].id);
            }
          }
        } catch { storeRef.current = null; }
      }
      if (!cancelled) { hydratedRef.current = true; setHydrated(true); }
    })();
    return () => { cancelled = true; };
  }, []);

  useEffect(() => {
    if (typeof BroadcastChannel === 'undefined') return;
    const channel = new BroadcastChannel(CHANNEL);
    channelRef.current = channel;
    channel.onmessage = (event: MessageEvent<SavedMessage>) => {
      const remote = parseSessions(event.data?.sessions ?? null);
      if (!remote.length || typeof event.data.savedAt !== 'number') return;
      setSessionsState(current => {
        const merged = mergeSavedSessions(current, remote, event.data.savedAt, changedRef.current, deletedRef.current);
        if (!merged.length) return current;
        // Only a copy with nothing newer from this tab is already saved; a
        // merged one is saved and announced back.
        const unchanged = merged.length === remote.length && merged.every((session, index) => session === remote[index]);
        receivedRef.current = unchanged ? merged : null;
        return merged;
      });
    };
    return () => { channel.close(); channelRef.current = null; };
  }, []);

  useEffect(() => {
    try {
      localStorage.setItem(STORAGE.settings, JSON.stringify(settings));
      // Until stored conversations load, the open one is still unknown.
      if (hydrated) localStorage.setItem(STORAGE.active, activeId);
    } catch { setStorageError(true); }
  }, [settings, activeId, hydrated]);

  // Note what this tab changed, so another tab's save cannot undo it.
  useEffect(() => {
    const previous = new Map(previousRef.current.map(session => [session.id, session]));
    previousRef.current = sessions;
    if (sessions === receivedRef.current) return;
    for (const session of sessions) {
      if (previous.get(session.id) !== session) changedRef.current.add(session.id);
      previous.delete(session.id);
    }
    for (const id of previous.keys()) deletedRef.current.add(id);
  }, [sessions]);

  /** Write the conversations now (before a reload, or when the page is hidden). */
  const persist = useCallback(async (): Promise<void> => {
    const serialized = JSON.stringify(sessionsRef.current);
    changedRef.current = new Set();
    deletedRef.current = new Set();
    const store = storeRef.current;
    const announce = () => channelRef.current?.postMessage({ savedAt: Date.now(), sessions: serialized } satisfies SavedMessage);
    const fallback = () => {
      try {
        localStorage.setItem(STORAGE.sessions, serialized);
        // The next start prefers this copy over an older one in IndexedDB,
        // also when IndexedDB was unavailable for this whole page load.
        localStorage.setItem(STORAGE.sessionsFallback, '1');
        setStorageError(false); announce();
      } catch { setStorageError(true); }
    };
    if (!store) { fallback(); return; }
    try {
      await store.set(STORAGE.sessions, serialized);
      setStorageError(false); announce();
      if (readStorage(STORAGE.sessionsFallback) !== null) {
        try { localStorage.removeItem(STORAGE.sessions); localStorage.removeItem(STORAGE.sessionsFallback); } catch { /* Kept until the next start. */ }
      }
    } catch { fallback(); }
  }, []);

  /** Save immediately; resolves when written. Safe to call before a reload. */
  const saveNow = useCallback(async (): Promise<void> => {
    if (hydratedRef.current) await persist();
  }, [persist]);

  // A hidden page may be closed or discarded without another chance to save.
  useEffect(() => {
    const onHide = () => { if (document.visibilityState === 'hidden') void saveNow(); };
    window.addEventListener('pagehide', onHide);
    document.addEventListener('visibilitychange', onHide);
    return () => { window.removeEventListener('pagehide', onHide); document.removeEventListener('visibilitychange', onHide); };
  }, [saveNow]);

  useEffect(() => {
    // Never overwrite stored conversations with the blank first render, and do
    // not save again (or echo back) what another tab just saved.
    if (!hydrated || sessions === receivedRef.current) return;
    const timer = window.setTimeout(() => { void persist(); }, SAVE_DELAY_MS);
    return () => window.clearTimeout(timer);
  }, [sessions, hydrated, persist]);

  return { settings, setSettings, sessions, setSessions, activeId, setActiveId, storageError, hydrated, saveNow };
}
