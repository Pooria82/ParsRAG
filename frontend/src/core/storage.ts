import type { Session } from '../types';

/** Minimal asynchronous key-value storage for the conversation workspace. */
export interface KeyValueStore {
  get(key: string): Promise<string | null>;
  set(key: string, value: string): Promise<void>;
  remove(key: string): Promise<void>;
}

const DATABASE = 'parsrag';
const STORE = 'workspace';

function settle<T>(request: IDBRequest<T>): Promise<T> {
  return new Promise((resolve, reject) => {
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error ?? new Error('indexeddb_error'));
  });
}

function committed(transaction: IDBTransaction): Promise<void> {
  return new Promise((resolve, reject) => {
    transaction.oncomplete = () => resolve();
    transaction.onabort = () => reject(transaction.error ?? new Error('indexeddb_abort'));
    transaction.onerror = () => reject(transaction.error ?? new Error('indexeddb_error'));
  });
}

/**
 * Open the workspace database. Resolves to null where IndexedDB is missing
 * or blocked (some private windows), so callers can keep localStorage.
 */
export async function openIndexedDbStore(factory: IDBFactory | undefined = globalThis.indexedDB): Promise<KeyValueStore | null> {
  if (!factory) return null;
  try {
    const opening = factory.open(DATABASE, 1);
    opening.onupgradeneeded = () => { opening.result.createObjectStore(STORE); };
    const database = await settle(opening);
    return {
      async get(key) {
        const value: unknown = await settle(database.transaction(STORE, 'readonly').objectStore(STORE).get(key));
        return typeof value === 'string' ? value : null;
      },
      async set(key, value) {
        const transaction = database.transaction(STORE, 'readwrite');
        transaction.objectStore(STORE).put(value, key);
        await committed(transaction);
      },
      async remove(key) {
        const transaction = database.transaction(STORE, 'readwrite');
        transaction.objectStore(STORE).delete(key);
        await committed(transaction);
      },
    };
  } catch { return null; }
}

export interface Hydration {
  /** Serialized sessions to load, or null to keep the initial state. */
  sessions: string | null;
  /** True when localStorage sessions were copied into the store. */
  migrated: boolean;
}

/**
 * Read conversations from the store, moving any left in localStorage there
 * first. localStorage keeps only small preferences afterwards, which frees its
 * ~5 MB quota for nothing else and keeps large histories off the main thread.
 * `legacyIsNewer` marks a localStorage copy written because saving to the
 * store failed; it replaces the older copy in the store.
 */
export async function hydrateSessions(store: KeyValueStore, key: string, legacy: string | null, clearLegacy: () => void, legacyIsNewer = false): Promise<Hydration> {
  const stored = await store.get(key);
  if (stored !== null && !(legacyIsNewer && legacy !== null)) {
    if (legacy !== null) clearLegacy();
    return { sessions: stored, migrated: false };
  }
  if (legacy === null) return { sessions: null, migrated: false };
  await store.set(key, legacy);
  clearLegacy();
  return { sessions: legacy, migrated: true };
}

/**
 * Combine conversations another tab saved at `savedAt` with this tab's. The
 * other tab's copy wins unless this tab changed a conversation later; one
 * missing there was deleted there, unless this tab changed it after that save.
 */
export function mergeSavedSessions(local: Session[], remote: Session[], savedAt: number): Session[] {
  const mine = new Map(local.map(session => [session.id, session]));
  const theirs = new Set(remote.map(session => session.id));
  const merged = remote.map(session => {
    const current = mine.get(session.id);
    return current && current.updatedAt > session.updatedAt ? current : session;
  });
  merged.push(...local.filter(session => !theirs.has(session.id) && session.updatedAt > savedAt));
  return merged;
}

/** Read the queue of conversations still to delete on the server. */
export function parsePendingDeletions(raw: string | null): string[] {
  try {
    const value: unknown = JSON.parse(raw ?? '[]');
    return Array.isArray(value) ? [...new Set(value.filter((id): id is string => typeof id === 'string'))] : [];
  } catch { return []; }
}

/** Delete each queued conversation; the ones whose deletion failed stay queued. */
export async function flushPendingDeletions(ids: string[], remove: (id: string) => Promise<void>): Promise<string[]> {
  const remaining: string[] = [];
  for (const id of ids) {
    try { await remove(id); } catch { remaining.push(id); }
  }
  return remaining;
}
