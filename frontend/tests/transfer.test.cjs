const { test } = require('node:test');
const assert = require('node:assert/strict');
const { createBackup, parseBackup, mergeSessions, conversationMarkdown, exportFilename } = require('./.compiled/core/workspaceTransfer.js');
const { DEFAULT_SETTINGS } = require('./.compiled/core/state.js');

const session = (id, updatedAt, extra = {}) => ({
  id, title: 'گزارش فاز اول', createdAt: 1, updatedAt, ragMode: 'strict', draft: '',
  documents: [{ name: 'report.pdf', status: 'indexed', enabled: true }],
  messages: [
    { id: `${id}-u`, role: 'user', content: 'هدف پروژه چیست؟', timestamp: 2 },
    { id: `${id}-a`, role: 'assistant', content: 'ساخت سامانهٔ پرسش و پاسخ.', timestamp: 3,
      citations: [{ filename: 'report.pdf', locations: [{ kind: 'page', start: 2 }, { kind: 'page', start: 4, end: 5 }] }] },
  ],
  ...extra,
});

test('a backup round-trips conversations without the local endpoint', () => {
  const text = createBackup([session('session_a', 10), { ...session('session_empty', 5), messages: [], documents: [] }],
    { ...DEFAULT_SETTINGS, language: 'en', backendUrl: 'http://localhost:8000' }, Date.UTC(2026, 9, 7));
  const raw = JSON.parse(text);
  assert.equal(raw.format, 'parsrag-workspace');
  assert.equal(raw.version, 1);
  assert.equal('backendUrl' in raw.settings, false);
  assert.equal(raw.sessions.length, 1);

  const restored = parseBackup(text);
  assert.equal(restored.sessions[0].messages[1].citations[0].locations.length, 2);
  assert.equal(restored.settings.language, 'en');
});

test('invalid, foreign, newer, and empty backups are rejected with a reason', () => {
  assert.throws(() => parseBackup('{oops'), /invalid_backup/);
  assert.throws(() => parseBackup(JSON.stringify({ format: 'other', version: 1 })), /invalid_backup/);
  assert.throws(() => parseBackup(JSON.stringify({ format: 'parsrag-workspace', version: 99, sessions: [] })), /unsupported_version/);
  assert.throws(() => parseBackup(JSON.stringify({ format: 'parsrag-workspace', version: 1, sessions: [{ id: '../bad' }] })), /empty_backup/);
});

test('import adds new conversations and replaces only older local copies', () => {
  const local = [session('session_a', 10), session('session_b', 30, { documents: [] })];
  const incoming = [
    session('session_a', 20, { title: 'newer', documents: [] }),
    session('session_b', 5, { title: 'older' }),
    session('session_c', 15),
  ];
  const merged = mergeSessions(local, incoming);
  assert.equal(merged.added, 1);
  assert.equal(merged.updated, 1);
  assert.deepEqual(merged.sessions.map(item => item.id), ['session_b', 'session_a', 'session_c']);
  const a = merged.sessions.find(item => item.id === 'session_a');
  assert.equal(a.title, 'newer');
  assert.equal(a.documents.length, 1, 'documents stay as indexed on this machine');
});

test('Markdown export keeps turns and sources in the reader language', () => {
  const markdown = conversationMarkdown(session('session_a', 10), 'fa', Date.UTC(2026, 9, 7));
  assert.match(markdown, /^# گزارش فاز اول/);
  assert.match(markdown, /### شما\n\nهدف پروژه چیست؟/);
  assert.match(markdown, /\*\*منابع:\*\*\n- report\.pdf \(صفحه 2، صفحه 4–5\)/);
  assert.match(conversationMarkdown(session('session_a', 10), 'en'), /### You/);
});

test('export file names are safe on every operating system', () => {
  assert.equal(exportFilename('a/b:c*?', 'md', Date.UTC(2026, 9, 7)), 'a b c 2026-10-07.md');
  assert.equal(exportFilename('   ', 'json', Date.UTC(2026, 9, 7)), 'parsrag 2026-10-07.json');
});
