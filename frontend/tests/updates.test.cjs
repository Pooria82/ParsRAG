const { test, afterEach } = require('node:test');
const assert = require('node:assert/strict');
const { isNewerVersion, notesToShow, offeredUpdate, releaseNotesText, updateCommand } = require('./.compiled/core/updates.js');
const { ParsRagApiClient } = require('./.compiled/services/api.js');

const originalFetch = global.fetch;
afterEach(() => { global.fetch = originalFetch; });

test('versions compare numerically and ignore pre-releases', () => {
  assert.equal(isNewerVersion('1.10.0', '1.9.3'), true);
  assert.equal(isNewerVersion('v1.1.2', '1.1.1'), true);
  assert.equal(isNewerVersion('1.1.1', '1.1.1'), false);
  assert.equal(isNewerVersion('1.0.9', '1.1.0'), false);
  assert.equal(isNewerVersion('1.2.0-rc1', '1.1.0'), false);
});

test('notes show after an update, for every version since the last one seen', () => {
  assert.deepEqual(notesToShow('1.1.1', '1.3.0', true), { since: '1.1.1' });
  assert.equal(notesToShow('1.3.0', '1.3.0', true), undefined);
  // Someone with conversations but no record used an older version: show this one.
  assert.deepEqual(notesToShow(null, '1.1.2', true), { since: null });
  // A first visit has nothing to compare with.
  assert.equal(notesToShow(null, '1.1.2', false), undefined);
});

test('the badge offers the latest release unless it was skipped', () => {
  const status = { enabled: true, current_version: '1.1.1', latest_version: '1.3.0', update_available: true, releases: [] };
  assert.equal(offeredUpdate(status, null), '1.3.0');
  assert.equal(offeredUpdate(status, '1.3.0'), undefined);
  // Skipping 1.2.0 does not hide a later release.
  assert.equal(offeredUpdate(status, '1.2.0'), '1.3.0');
  assert.equal(offeredUpdate({ ...status, update_available: false }, null), undefined);
});

test('the update command fits the system, and notes fall back to English', () => {
  assert.match(updateCommand('Win32'), /powershell .*scripts\/update\.ps1/);
  assert.equal(updateCommand('MacIntel'), 'sh scripts/update.sh');
  assert.equal(releaseNotesText({ notes_fa: '', notes_en: 'Fixed' }, 'fa'), 'Fixed');
  assert.equal(releaseNotesText({ notes_fa: 'رفع شد', notes_en: 'Fixed' }, 'fa'), 'رفع شد');
});

test('the client reads update status and release notes', async () => {
  const urls = [];
  global.fetch = async url => {
    urls.push(String(url));
    if (String(url).includes('/updates')) return new Response(JSON.stringify({ enabled: true, current_version: '1.1.2', update_available: false, releases: [] }));
    return new Response(JSON.stringify({ current_version: '1.1.2', notes: [{ version: '1.1.2', notes: 'تازه‌ها' }, { version: 3 }] }));
  };
  const api = new ParsRagApiClient('');
  assert.equal((await api.updates(true)).current_version, '1.1.2');
  assert.deepEqual(await api.releaseNotes('1.1.1', 'fa'), [{ version: '1.1.2', notes: 'تازه‌ها' }]);
  assert.deepEqual(urls, ['/updates?refresh=true', '/release-notes?language=fa&since=1.1.1']);
});
