const { test } = require('node:test');
const assert = require('node:assert/strict');
const {
  DEFAULT_SETTINGS, MAX_FILE_BYTES, parseSettings, parseSessions, createSession,
  validateUploads, buildQuery, parseAnswer, mergeRemoteDocuments, isLocalEndpoint,
} = require('./.compiled/core/state.js');

test('recovers malformed storage and validates settings without external endpoints', () => {
  assert.deepEqual(parseSettings('{bad'), DEFAULT_SETTINGS);
  assert.deepEqual(parseSessions('{}'), []);
  const settings = parseSettings(JSON.stringify({ language: 'xx', theme: 'neon', topK: 100, backendUrl: 'https://example.com' }));
  assert.equal(settings.language, 'fa');
  assert.equal(settings.theme, 'light');
  assert.equal(settings.topK, 50);
  assert.equal(settings.backendUrl, '');
  assert.equal(isLocalEndpoint('https://localhost.evil.com'), false);
  assert.equal(isLocalEndpoint('http://localhost@evil.com'), false);
  assert.equal(isLocalEndpoint('http://localhost:8000'), true);
  assert.equal(isLocalEndpoint('http://[::1]:8000'), true);
  assert.equal(isLocalEndpoint('http://192.168.1.10:8000', 'http://192.168.1.10:8000'), true);
});

test('preserves old conversations and recovers interrupted uploads', () => {
  const raw = [{ id: 'session_old', title: 'پژوهش', messages: [{ id: 'm', role: 'user', content: 'سلام' }, null],
    documents: [{ name: 'a.pdf', status: 'uploading' }, { name: 'b.pdf', status: 'indexed', enabled: false }], ragMode: 'strict' }];
  const [session] = parseSessions(JSON.stringify([...raw, ...raw, { id: '../invalid' }, null]));
  assert.equal(parseSessions(JSON.stringify([...raw, ...raw])).length, 1);
  assert.equal(session.messages[0].content, 'سلام');
  assert.equal(session.documents[0].status, 'error');
  assert.equal(session.documents[1].enabled, true);
  assert.equal(session.ragMode, 'strict');
});

test('validates formats, size, duplicate names, empty files and five-document limit', () => {
  const files = [
    { name: 'ok.PPTX', size: 100 }, { name: 'old.txt', size: 10 },
    { name: 'huge.pdf', size: MAX_FILE_BYTES + 1 }, { name: 'empty.pdf', size: 0 },
    { name: 'ok.PPTX', size: 100 },
  ];
  const result = validateUploads(files, []);
  assert.deepEqual(result.accepted, [0]);
  assert.deepEqual(result.rejected.map(r => r.reason), ['format', 'size', 'empty', 'duplicate']);
  assert.equal(validateUploads([{ name: 'six.pdf', size: 1 }], Array.from({ length: 5 }, (_, i) => ({ name: `${i}.pdf` }))).rejected[0].reason, 'limit');
});

test('builds all three API modes with scoped documents and clean conversational memory', () => {
  const session = createSession('fa', 'strict');
  session.documents = [{ name: 'a.pdf', status: 'indexed' }, { name: 'b.pdf', status: 'indexed', enabled: false }];
  session.messages = [{ id: '1', role: 'user', content: 'سؤال', timestamp: 1 }, { id: '2', role: 'assistant', content: 'error', error: true, timestamp: 2 }];
  for (const mode of ['strict', 'hybrid', 'llm-only']) {
    const payload = buildQuery({ ...session, ragMode: mode }, { ...DEFAULT_SETTINGS, dynamicDepth: false, topK: 9 }, ' پیگیری ');
    assert.equal(payload.mode, mode);
    assert.equal(payload.prompt, 'پیگیری');
    assert.equal(payload.top_k, 9);
    assert.deepEqual(payload.file_filter, mode === 'llm-only' ? null : ['a.pdf']);
    assert.equal(payload.chat_history.length, 1);
  }
  session.documents[0].enabled = false;
  assert.throws(() => buildQuery(session, DEFAULT_SETTINGS, 'hi'), /Select/);
});

test('rejects invalid answers and accepts nullable citation scores', () => {
  assert.throws(() => parseAnswer({ answer: '' }), /invalid_response/);
  assert.throws(() => parseAnswer(null), /invalid_response/);
  assert.deepEqual(parseAnswer({ answer: 'پاسخ', source_nodes: [{ text: 'متن', score: null, metadata: { filename: 'a.pdf' } }] }), {
    answer: 'پاسخ', citations: [{ title: '1', body: 'متن', filename: 'a.pdf', score: 0 }],
  });
});

test('synchronizes real server documents, preserving choices and partial-upload outcomes', () => {
  const docs = [{ name: 'gone.pdf', status: 'indexed' }, { name: 'retry.pdf', status: 'error' }, { name: 'keep.pdf', status: 'indexed', enabled: false }];
  const merged = mergeRemoteDocuments(docs, ['keep.pdf', 'new.pdf', 'new.pdf']);
  assert.deepEqual(merged.map(d => d.name), ['keep.pdf', 'new.pdf', 'retry.pdf']);
  assert.equal(merged[0].enabled, false);
  assert.deepEqual(mergeRemoteDocuments(docs, []), [{ name: 'retry.pdf', status: 'error' }]);
  assert.equal(mergeRemoteDocuments(docs, {}), docs);
});
