import { useEffect, useState } from 'react';
import type { AppSettings, Session } from '../types';
import { createSession, parseSessions, parseSettings, STORAGE } from '../core/state';

function readStorage(key: string): string | null {
  try { return localStorage.getItem(key); } catch { return null; }
}

export function usePersistentWorkspace() {
  const [settings, setSettings] = useState<AppSettings>(() => parseSettings(readStorage(STORAGE.settings), window.location.origin));
  const [sessions, setSessions] = useState<Session[]>(() => {
    const stored = parseSessions(readStorage(STORAGE.sessions));
    return stored.length ? stored : [createSession(settings.language, settings.defaultMode)];
  });
  const [activeId, setActiveId] = useState(() => {
    const stored = readStorage(STORAGE.active);
    return sessions.some(session => session.id === stored) ? stored! : sessions[0].id;
  });
  const [storageError, setStorageError] = useState(false);

  useEffect(() => {
    try {
      localStorage.setItem(STORAGE.settings, JSON.stringify(settings));
      localStorage.setItem(STORAGE.sessions, JSON.stringify(sessions));
      localStorage.setItem(STORAGE.active, activeId);
      setStorageError(false);
    } catch { setStorageError(true); }
  }, [settings, sessions, activeId]);

  return { settings, setSettings, sessions, setSessions, activeId, setActiveId, storageError };
}
