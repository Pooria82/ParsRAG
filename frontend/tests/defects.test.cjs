const { test } = require('node:test');
const assert = require('node:assert/strict');
const React = require('react');
const { renderToStaticMarkup } = require('react-dom/server');
const { answerTo, buildQuery, chatHistory, createSession, DEFAULT_SETTINGS, MAX_PROMPT_CHARS, placeAnswer, prepareTurnRegeneration } = require('./.compiled/core/state.js');
const { normalizeMathMarkdown } = require('./.compiled/core/markdown.js');
const { errorFromBody, parseSseBlock } = require('./.compiled/services/api.js');
const { flushPendingDeletions, hydrateSessions, mergeSavedSessions, parsePendingDeletions } = require('./.compiled/core/storage.js');
const { mergeSessions } = require('./.compiled/core/workspaceTransfer.js');
const { modelSettingsErrorMessage, queryErrorMessage, uploadErrorMessage } = require('./.compiled/i18n/errors.js');
const { ChatFeed, promptDirection } = require('./.compiled/components/ChatFeed.js');

const noop = () => {};
const user = (id, content = 'q ' + id) => ({ id, role: 'user', content, timestamp: 1 });
const answer = (id, parentUserId, extra = {}) => ({ id, role: 'assistant', content: 'a ' + id, parentUserId, timestamp: 2, ...extra });

test('history leaves out failed and unanswered turns and cuts long ones to the API limit', () => {
  const long = 'x'.repeat(MAX_PROMPT_CHARS + 500);
  const messages = [
    user('u1', long), answer('a1', 'u1', { content: long }),
    user('u2'), answer('a2', 'u2', { error: true, content: 'failed' }),
    user('u3'), { id: 's', role: 'system', content: 'stopped', timestamp: 3 },
    user('u4'), answer('a4', 'u4'),
  ];
  const history = chatHistory(messages);
  assert.deepEqual(history.map(turn => turn.role), ['user', 'assistant', 'user', 'assistant']);
  assert.equal(history[0].content.length, MAX_PROMPT_CHARS);
  assert.equal(history[1].content.length, MAX_PROMPT_CHARS);
  assert.equal(history[2].content, 'q u4');
  const session = { ...createSession('en', 'hybrid'), messages };
  assert.deepEqual(buildQuery(session, DEFAULT_SETTINGS, 'next').chat_history, history);
  assert.equal('strictThreshold' in DEFAULT_SETTINGS, false);
});

test('editing an unanswered question does not take a later answer', () => {
  const messages = [user('u1'), { id: 's', role: 'system', content: 'stopped', timestamp: 2 }, user('u2'), answer('a2', 'u2')];
  assert.equal(answerTo(messages, 'u1'), undefined);
  assert.equal(answerTo(messages, 'u2').id, 'a2');
  // Older answers without parentUserId belong to the question right before them.
  assert.equal(answerTo([user('u'), { id: 'old', role: 'assistant', content: 'a', timestamp: 2 }], 'u').id, 'old');

  const prepared = prepareTurnRegeneration(messages, 'u1', undefined, 'edited', true);
  assert.deepEqual(prepared.history, []);
  assert.deepEqual(prepared.visible.map(message => message.id), ['u1', 'u2', 'a2']);
  assert.equal(prepared.visible[0].content, 'edited');
  const placed = placeAnswer(prepared.visible, answer('new', 'u1'));
  assert.deepEqual(placed.map(message => message.id), ['u1', 'new', 'u2', 'a2']);
  assert.deepEqual(placeAnswer([user('u9')], answer('n9', 'u9')).map(message => message.id), ['u9', 'n9']);
});

test('an unanswered question offers a retry; answered ones and a running one do not', () => {
  const props = { language: 'en', activeMode: 'hybrid', onRetry: noop, onEditPrompt: noop, onRetryQuestion: noop, onSelectVariant: noop, isBusy: false };
  const retries = html => (html.match(/<\/svg>Try again/g) ?? []).length;
  assert.equal(retries(renderToStaticMarkup(React.createElement(ChatFeed, { ...props, messages: [user('u1')], isGenerating: false }))), 1);
  assert.equal(retries(renderToStaticMarkup(React.createElement(ChatFeed, { ...props, messages: [user('u1')], isGenerating: true }))), 0);
  // The answer has its own retry; the question gets none.
  assert.equal(retries(renderToStaticMarkup(React.createElement(ChatFeed, { ...props, messages: [user('u1'), answer('a1', 'u1')], isGenerating: false }))), 1);
});

test('answer-version arrows point the reading direction', () => {
  const message = { ...answer('a1', 'u1'), variants: [{ id: 'v1', content: 'one', timestamp: 1 }, { id: 'v2', content: 'two', timestamp: 2 }], activeVariant: 1 };
  const render = language => renderToStaticMarkup(React.createElement(ChatFeed, { messages: [user('u1'), message], language, isGenerating: false, activeMode: 'hybrid', onRetry: noop, onEditPrompt: noop, onRetryQuestion: noop, onSelectVariant: noop, isBusy: false }));
  const previousIcon = html => /aria-label="(?:Previous response|پاسخ قبلی)"[^>]*><svg[^>]*class="lucide lucide-(chevron-\w+)/.exec(html)[1];
  assert.equal(previousIcon(render('en')), 'chevron-left');
  assert.equal(previousIcon(render('fa')), 'chevron-right');
});

test('the math normalizer keeps links, snake_case names and amounts', () => {
  assert.equal(normalizeMathMarkdown('See [docs](https://example.com/my_page).'), 'See [docs](https://example.com/my_page).');
  assert.equal(normalizeMathMarkdown('Set (top_k = 15) and (my_var).'), 'Set (top_k = 15) and (my_var).');
  assert.equal(normalizeMathMarkdown('It costs $5, or $10 for two.'), 'It costs \\$5, or \\$10 for two.');
  assert.equal(normalizeMathMarkdown('$5 or $x$'), '\\$5 or $x$');
  // Formulae still become math.
  assert.equal(normalizeMathMarkdown('Here (x_1 = 5) and (E = mc^2) and $a^2$.'), 'Here $x_1 = 5$ and $E = mc^2$ and $a^2$.');
});

test('validation errors are named, and pings are stream events', () => {
  const tooLong = errorFromBody(422, JSON.stringify({ detail: [{ type: 'string_too_long', loc: ['body', 'prompt'] }] }));
  assert.equal(tooLong.code, 'too_long');
  assert.match(queryErrorMessage(tooLong.code, 'en'), /12,000/);
  assert.equal(errorFromBody(422, JSON.stringify({ detail: [{ type: 'missing' }] })).code, 'invalid_request');
  assert.equal(errorFromBody(400, JSON.stringify({ detail: 'x', code: 'invalid_session' })).code, 'invalid_session');
  assert.deepEqual(parseSseBlock('event: ping\ndata: {}'), { type: 'ping' });
});

test('every backend error code has a message in both languages', () => {
  for (const code of ['not_found', 'conflict', 'upstream_unavailable', 'invalid_session', 'no_file', 'untrusted_host', 'service_error', 'request_failed']) {
    for (const language of ['fa', 'en']) {
      assert.ok(uploadErrorMessage(code, language), `${code} ${language}`);
      assert.ok(queryErrorMessage(code, language), `${code} ${language}`);
    }
  }
  assert.ok(modelSettingsErrorMessage('upstream_unavailable', 'fa'));
  assert.ok(modelSettingsErrorMessage('ollama_unreachable', 'en'));
});

test('a localStorage copy written after IndexedDB failed wins over the older IndexedDB copy', async () => {
  const data = new Map([['sessions', '[{"id":"old"}]']]);
  const store = { get: async key => data.get(key) ?? null, set: async (key, value) => { data.set(key, value); }, remove: async key => { data.delete(key); } };
  let cleared = 0;
  const result = await hydrateSessions(store, 'sessions', '[{"id":"new"}]', () => { cleared += 1; }, true);
  assert.deepEqual(result, { sessions: '[{"id":"new"}]', migrated: true });
  assert.equal(data.get('sessions'), '[{"id":"new"}]');
  assert.equal(cleared, 1);
});

test('another tab\'s save is merged without losing this tab\'s newer changes', () => {
  const session = (id, updatedAt, title = id) => ({ ...createSession('en', 'hybrid'), id, updatedAt, title });
  const local = [session('a', 10, 'mine'), session('b', 5), session('fresh', 50), session('gone', 5)];
  const remote = [session('a', 8, 'theirs'), session('b', 7, 'renamed there'), session('c', 9)];
  const merged = mergeSavedSessions(local, remote, 20);
  assert.deepEqual(merged.map(item => [item.id, item.title]), [['a', 'mine'], ['b', 'renamed there'], ['c', 'c'], ['fresh', 'fresh']]);
});

test('deletions made offline are queued and retried until the server confirms them', async () => {
  assert.deepEqual(parsePendingDeletions('["a","a","b",3]'), ['a', 'b']);
  assert.deepEqual(parsePendingDeletions('not json'), []);
  const remaining = await flushPendingDeletions(['a', 'b', 'c'], async id => { if (id === 'b') throw new Error('offline'); });
  assert.deepEqual(remaining, ['b']);
});

test('imported documents show as missing until this server lists them', () => {
  const imported = { ...createSession('en', 'hybrid'), id: 'imported', updatedAt: 5, messages: [user('u')],
    documents: [{ name: 'a.pdf', status: 'indexed', enabled: true }] };
  const { sessions } = mergeSessions([], [imported]);
  assert.deepEqual(sessions[0].documents, [{ name: 'a.pdf', status: 'error', enabled: true, errorMessage: 'not_on_server' }]);
});

test('a prompt sits on the side its language starts from', () => {
  assert.equal(promptDirection('توکن‌ها چه مدت اعتبار دارند؟', 'ltr'), 'rtl');
  assert.equal(promptDirection('ORM در SQLAlchemy چیست؟', 'ltr'), 'rtl');
  assert.equal(promptDirection('What does the word نیازمندی mean?', 'rtl'), 'ltr');
  assert.equal(promptDirection('`x = 1` @{گزارش.pdf}', 'ltr'), 'ltr');
  const placement = (language, content) => /message message-user (prompt-\w+)/.exec(renderToStaticMarkup(React.createElement(ChatFeed, {
    messages: [user('u1', content)], language, isGenerating: true, activeMode: 'hybrid',
    onRetry: noop, onEditPrompt: noop, onRetryQuestion: noop, onSelectVariant: noop, isBusy: false })))[1];
  // Persian in the Persian interface and English in the English one start at the reading edge.
  assert.equal(placement('fa', 'سلام، این سند دربارهٔ چیست؟'), 'prompt-start');
  assert.equal(placement('en', 'What is this document about?'), 'prompt-start');
  assert.equal(placement('fa', 'What is this document about?'), 'prompt-end');
  assert.equal(placement('en', 'سلام، این سند دربارهٔ چیست؟'), 'prompt-end');
});

test('questions carry the interface language for prompts without words', () => {
  const session = { ...createSession('en', 'llm-only') };
  assert.equal(buildQuery(session, { ...DEFAULT_SETTINGS, language: 'en' }, '2 + 2 = ?').language, 'en');
  assert.equal(buildQuery(session, { ...DEFAULT_SETTINGS, language: 'fa' }, '2 + 2 = ?').language, 'fa');
});


test('model ids split into publisher, name and variant for display', () => {
  const { modelNameParts } = require('./.compiled/core/modelName.js');
  assert.deepEqual(modelNameParts('google/gemma-4-26b-a4b-it'), { vendor: 'google', name: 'gemma-4-26b-a4b-it', tag: '' });
  assert.deepEqual(modelNameParts('gemma3:4b'), { vendor: '', name: 'gemma3', tag: '4b' });
  assert.deepEqual(modelNameParts('hf.co/bartowski/Llama-3.2-3B-Instruct-GGUF:Q4_K_M'), { vendor: 'hf.co/bartowski', name: 'Llama-3.2-3B-Instruct-GGUF', tag: 'Q4_K_M' });
  assert.deepEqual(modelNameParts('gpt-4o'), { vendor: '', name: 'gpt-4o', tag: '' });
});
