const { test } = require('node:test');
const assert = require('node:assert/strict');
const { hydrateSessions, openIndexedDbStore } = require('./.compiled/core/storage.js');

function memoryStore(initial = {}) {
  const data = new Map(Object.entries(initial));
  return { data, get: async key => data.get(key) ?? null, set: async (key, value) => { data.set(key, value); }, remove: async key => { data.delete(key); } };
}

test('conversations left in localStorage move to IndexedDB once', async () => {
  const store = memoryStore();
  let cleared = 0;
  const result = await hydrateSessions(store, 'sessions', '[{"id":"s1"}]', () => { cleared += 1; });
  assert.deepEqual(result, { sessions: '[{"id":"s1"}]', migrated: true });
  assert.equal(store.data.get('sessions'), '[{"id":"s1"}]');
  assert.equal(cleared, 1);
});

test('IndexedDB wins over a stale localStorage copy, which is cleared', async () => {
  const store = memoryStore({ sessions: '[{"id":"new"}]' });
  let cleared = 0;
  const result = await hydrateSessions(store, 'sessions', '[{"id":"old"}]', () => { cleared += 1; });
  assert.deepEqual(result, { sessions: '[{"id":"new"}]', migrated: false });
  assert.equal(cleared, 1);
});

test('a first visit has nothing to load', async () => {
  const result = await hydrateSessions(memoryStore(), 'sessions', null, () => assert.fail('nothing to clear'));
  assert.deepEqual(result, { sessions: null, migrated: false });
});

test('environments without IndexedDB fall back to localStorage', async () => {
  assert.equal(await openIndexedDbStore(undefined), null);
  const throwing = { open() { throw new Error('blocked'); } };
  assert.equal(await openIndexedDbStore(throwing), null);
});
