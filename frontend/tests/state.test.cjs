const { test } = require('node:test');
const assert = require('node:assert/strict');
const {
  DEFAULT_SETTINGS, MAX_FILE_BYTES, parseSettings, parseSessions, createSession,
  validateUploads, buildQuery, parseAnswer, mergeRemoteDocuments, isLocalEndpoint, appendResponseVariant, selectResponseVariant, prepareTurnRegeneration, selectConversationBranch, fallbackConversationTitle,
} = require('./.compiled/core/state.js');

test('recovers malformed storage and validates settings without external endpoints', () => {
  assert.deepEqual(parseSettings('{bad'), DEFAULT_SETTINGS);
  assert.deepEqual(parseSessions('{}'), []);
  const settings = parseSettings(JSON.stringify({ language: 'xx', theme: 'neon', topK: 100, backendUrl: 'https://example.com' }));
  assert.equal(settings.language, 'fa');
  assert.equal(settings.theme, 'light');
  assert.equal(settings.palette, 'evergreen');
  assert.equal(parseSettings(JSON.stringify({ palette: 'ocean' })).palette, 'ocean');
  assert.equal(parseSettings(JSON.stringify({ palette: 'unsafe' })).palette, 'evergreen');
  assert.equal(settings.topK, 50);
  assert.equal(settings.backendUrl, '');
  assert.equal(settings.apiModelName, 'google/gemma-4-26b-a4b-it');
  assert.equal(settings.ollamaModelName, 'gemma3:12b');
  assert.equal(settings.apiBaseUrl, 'https://openrouter.ai/api/v1');
  assert.equal(settings.ollamaBaseUrl, 'http://localhost:11434');
  assert.equal(isLocalEndpoint('https://localhost.evil.com'), false);
  assert.equal(isLocalEndpoint('http://localhost@evil.com'), false);
  assert.equal(isLocalEndpoint('http://localhost:8000'), true);
  assert.equal(isLocalEndpoint('http://[::1]:8000'), true);
  assert.equal(isLocalEndpoint('http://192.168.1.10:8000', 'http://192.168.1.10:8000'), true);
});

test('builds a clean local title while generated naming is pending', () => {
  assert.equal(fallbackConversationTitle('  **تحلیل   ساختار فیستل**  '), 'تحلیل ساختار فیستل');
  assert.match(fallbackConversationTitle('این یک پرسش بسیار طولانی درباره ساختار و کاربرد الگوریتم‌های رمزنگاری مدرن است'), /…$/);
});

test('keeps regenerated answers as navigable response variants', () => {
  const original = { id: 'a1', role: 'assistant', content: 'first', timestamp: 1 };
  const next = { id: 'v2', content: 'second', timestamp: 2 };
  const message = appendResponseVariant(original, next);
  assert.equal(message.variants.length, 2);
  assert.equal(message.activeVariant, 1);
  assert.equal(message.content, 'second');
  assert.equal(selectResponseVariant(message, 0).content, 'first');
  assert.equal(selectResponseVariant(message, 99), message);
});

test('editing a prompt branches from that turn and removes later conversation state', () => {
  const messages = [
    { id: 'u0', role: 'user', content: 'before', timestamp: 1 },
    { id: 'a0', role: 'assistant', content: 'before answer', timestamp: 2 },
    { id: 'u1', role: 'user', content: 'old prompt', timestamp: 3 },
    { id: 'a1', role: 'assistant', content: 'old answer', timestamp: 4 },
    { id: 'u2', role: 'user', content: 'later prompt', timestamp: 5 },
  ];
  const branch = prepareTurnRegeneration(messages, 'u1', 'a1', 'edited prompt', true);
  assert.deepEqual(branch.history.map(message => message.id), ['u0', 'a0']);
  assert.deepEqual(branch.visible.map(message => message.id), ['u0', 'a0', 'u1', 'a1']);
  assert.equal(branch.visible[2].content, 'edited prompt');
  assert.deepEqual(branch.visible[3].variants[0].continuation.map(message => message.id), ['u2']);
});

test('switching an answer restores its prompt and the matching conversation branch', () => {
  const original = [
    { id: 'u1', role: 'user', content: 'old prompt', timestamp: 1 },
    { id: 'a1', role: 'assistant', parentUserId: 'u1', content: 'old answer', timestamp: 2,
      variants: [{ id: 'v1', content: 'old answer', prompt: 'old prompt', timestamp: 2 }], activeVariant: 0 },
    { id: 'u2', role: 'user', content: 'old continuation', timestamp: 3 },
    { id: 'a2', role: 'assistant', parentUserId: 'u2', content: 'old follow-up', timestamp: 4 },
  ];
  const prepared = prepareTurnRegeneration(original, 'u1', 'a1', 'edited prompt', true);
  const editedAnswer = appendResponseVariant(prepared.visible[1], {
    id: 'v2', content: 'edited answer', prompt: 'edited prompt', continuation: [], timestamp: 5,
  });
  const editedBranch = [prepared.visible[0], editedAnswer,
    { id: 'u3', role: 'user', content: 'new continuation', timestamp: 6 },
    { id: 'a3', role: 'assistant', parentUserId: 'u3', content: 'new follow-up', timestamp: 7 }];

  const restoredOriginal = selectConversationBranch(editedBranch, 'a1', 0);
  assert.deepEqual(restoredOriginal.map(message => message.id), ['u1', 'a1', 'u2', 'a2']);
  assert.equal(restoredOriginal[0].content, 'old prompt');
  assert.equal(restoredOriginal[1].content, 'old answer');

  const restoredEdit = selectConversationBranch(restoredOriginal, 'a1', 1);
  assert.deepEqual(restoredEdit.map(message => message.id), ['u1', 'a1', 'u3', 'a3']);
  assert.equal(restoredEdit[0].content, 'edited prompt');
  assert.equal(restoredEdit[1].content, 'edited answer');
});

test('stored conversation branches recover nested prompts and continuations', () => {
  const stored = [{ id: 'session_1', title: 'branch', createdAt: 1, updatedAt: 2, ragMode: 'hybrid', documents: [], messages: [
    { id: 'u1', role: 'user', content: 'visible prompt', timestamp: 1 },
    { id: 'a1', role: 'assistant', parentUserId: 'u1', content: 'visible answer', timestamp: 2, activeVariant: 1, variants: [
      { id: 'v1', prompt: 'old prompt', content: 'old answer', timestamp: 2,
        continuation: [{ id: 'u2', role: 'user', content: 'old follow-up', timestamp: 3 }] },
      { id: 'v2', prompt: 'visible prompt', content: 'visible answer', timestamp: 4, continuation: [] },
    ] },
  ] }];
  const parsed = parseSessions(JSON.stringify(stored))[0];
  assert.equal(parsed.messages[1].variants[0].prompt, 'old prompt');
  assert.equal(parsed.messages[1].variants[0].continuation[0].content, 'old follow-up');
});

test('preserves old conversations and recovers interrupted uploads', () => {
  const raw = [{ id: 'session_old', title: 'پژوهش', messages: [{ id: 'm', role: 'user', content: 'سلام', citations: [{ filename: 'a.pdf', body: 'old' }, { filename: 'a.pdf', body: 'old 2' }] }, null],
    documents: [{ name: 'a.pdf', status: 'uploading' }, { name: 'b.pdf', status: 'indexed', enabled: false }], ragMode: 'strict' }];
  const [session] = parseSessions(JSON.stringify([...raw, ...raw, { id: '../invalid' }, null]));
  assert.equal(parseSessions(JSON.stringify([...raw, ...raw])).length, 1);
  assert.equal(session.messages[0].content, 'سلام');
  assert.equal(session.messages[0].citations.length, 1);
  assert.equal(session.documents[0].status, 'error');
  assert.equal(session.documents[1].enabled, false);
  assert.equal(session.ragMode, 'strict');
});

test('validates broad formats, size, duplicate names, empty files and ten-document limit', () => {
  const files = [
    { name: 'ok.PPTX', size: 100 }, { name: 'notes.md', size: 10 }, { name: 'scan.PNG', size: 20 },
    { name: 'malware.exe', size: 10 },
    { name: 'huge.pdf', size: MAX_FILE_BYTES + 1 }, { name: 'empty.pdf', size: 0 },
    { name: 'ok.PPTX', size: 100 },
  ];
  const result = validateUploads(files, []);
  assert.deepEqual(result.accepted, [0, 1, 2]);
  assert.deepEqual(result.rejected.map(r => r.reason), ['format', 'size', 'empty', 'duplicate']);
  assert.equal(validateUploads([{ name: 'eleven.pdf', size: 1 }], Array.from({ length: 10 }, (_, i) => ({ name: `${i}.pdf` }))).rejected[0].reason, 'limit');
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
  assert.deepEqual(buildQuery(session, DEFAULT_SETTINGS, 'hi').file_filter, []);
});

test('rejects invalid answers and deduplicates compact source locations', () => {
  assert.throws(() => parseAnswer({ answer: '' }), /invalid_response/);
  assert.throws(() => parseAnswer(null), /invalid_response/);
  assert.deepEqual(parseAnswer({ answer: 'پاسخ', source_nodes: [{ text: 'متن', metadata: { filename: 'a.pdf', page: 2 } }, { text: 'بیشتر', metadata: { filename: 'a.pdf', page: 2 } }] }), {
    answer: 'پاسخ', citations: [{ filename: 'a.pdf', locations: [{ kind: 'page', start: 2 }] }],
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
