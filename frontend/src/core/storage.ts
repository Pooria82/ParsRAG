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
 */
export async function hydrateSessions(store: KeyValueStore, key: string, legacy: string | null, clearLegacy: () => void): Promise<Hydration> {
  const stored = await store.get(key);
  if (stored !== null) {
    if (legacy !== null) clearLegacy();
    return { sessions: stored, migrated: false };
  }
  if (legacy === null) return { sessions: null, migrated: false };
  await store.set(key, legacy);
  clearLegacy();
  return { sessions: legacy, migrated: true };
}
