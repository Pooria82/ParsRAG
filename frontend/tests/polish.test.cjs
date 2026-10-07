const { test, afterEach } = require('node:test');
const assert = require('node:assert/strict');
const React = require('react');
const { renderToStaticMarkup } = require('react-dom/server');
const { Welcome } = require('./.compiled/components/Welcome.js');
const { ChatFeed } = require('./.compiled/components/ChatFeed.js');
const { highlightParts, highlightTerms } = require('./.compiled/components/SourceList.js');
const { ErrorBoundary } = require('./.compiled/components/ErrorBoundary.js');
const { answerGrounding, suggestionKey, parseSessions } = require('./.compiled/core/state.js');
const { ParsRagApiClient } = require('./.compiled/services/api.js');

const originalFetch = global.fetch;
afterEach(() => { global.fetch = originalFetch; });
const noop = () => {};
const render = (Component, props) => renderToStaticMarkup(React.createElement(Component, props));

test('the welcome screen offers questions written from the documents', () => {
  const html = render(Welcome, { language: 'fa', composer: null, onSelectStarter: noop,
    documentQuestions: ['بودجهٔ پروژه چقدر بود؟', 'از چه ابزاری استفاده شد؟'], onSelectQuestion: noop });
  assert.match(html, /پرسش‌هایی که اسناد شما پاسخ می‌دهند/);
  assert.equal((html.match(/class="document-question"/g) ?? []).length, 2);
  const loading = render(Welcome, { language: 'en', composer: null, onSelectStarter: noop, documentQuestionsLoading: true });
  assert.equal((loading.match(/document-question is-loading/g) ?? []).length, 3);
  assert.doesNotMatch(render(Welcome, { language: 'en', composer: null, onSelectStarter: noop }), /document-questions/);
});

test('answers show where their content came from', () => {
  const sources = [{ n: 1, filename: 'a.pdf', text: 'x', cited: true }, { n: 2, filename: 'a.pdf', text: 'y', cited: false }];
  const html = render(ChatFeed, { messages: [
    { id: 'a', role: 'assistant', timestamp: 1, content: 'ok [1]', grounding: 'documents', sources },
    { id: 'b', role: 'assistant', timestamp: 1, content: 'general', grounding: 'general' },
    { id: 'c', role: 'assistant', timestamp: 1, content: 'none', grounding: 'not_found' },
  ], language: 'en', isGenerating: false, activeMode: 'strict', onRetry: noop, onEditPrompt: noop, onSelectVariant: noop, onRevealComplete: noop, isBusy: false });
  assert.match(html, /grounding-documents[^>]*>.*Documents only.*1 sources/s);
  assert.match(html, /grounding-general/);
  assert.match(html, /grounding-not_found[^>]*>.*Not found in documents/s);
  assert.equal(answerGrounding('strict', 'answered'), 'documents');
  assert.equal(answerGrounding('hybrid', 'answered'), 'hybrid');
  assert.equal(answerGrounding('llm-only', 'answered'), 'general');
  assert.equal(answerGrounding('strict', 'no_evidence'), 'not_found');
});

test('excerpts highlight the distinctive words of the question', () => {
  const terms = highlightTerms('بودجهٔ پروژه Odoo چقدر است؟');
  assert.ok(terms.includes('odoo') && terms.includes('پروژه') && !terms.includes('است'));
  const parts = highlightParts('ماژول‌های Odoo در پروژه ارتقا یافت', ['odoo', 'پروژه']);
  assert.deepEqual(parts.filter(part => part.mark).map(part => part.text), ['Odoo', 'پروژه']);
  assert.deepEqual(highlightParts('بدون واژه', []), [{ text: 'بدون واژه', mark: false }]);
});

test('suggestions follow the selected documents and survive reloads', () => {
  const session = { id: 's', documents: [{ name: 'b.pdf', status: 'indexed' }, { name: 'a.pdf', status: 'indexed' }, { name: 'off.pdf', status: 'indexed', enabled: false }, { name: 'up.pdf', status: 'uploading' }] };
  assert.equal(suggestionKey(session, 'fa'), 'fa:a.pdf\u0000b.pdf');
  assert.equal(suggestionKey({ documents: [] }, 'fa'), '');
  const [restored] = parseSessions(JSON.stringify([{ id: 'session_1', messages: [], suggestions: { key: 'fa:a.pdf', questions: ['q1?', 7, 'q2?', 'q3?', 'q4?'] } }]));
  assert.deepEqual(restored.suggestions, { key: 'fa:a.pdf', questions: ['q1?', 'q2?', 'q3?'] });
});

test('the client requests suggestions for the selected files', async () => {
  let body;
  global.fetch = async (url, init) => { body = { url: String(url), payload: JSON.parse(init.body) }; return new Response(JSON.stringify({ questions: ['a?', '', 'b?'] }), { status: 200 }); };
  assert.deepEqual(await new ParsRagApiClient('').suggestions('s1', 'en', ['a.pdf']), ['a?', 'b?']);
  assert.deepEqual(body, { url: '/sessions/s1/suggestions', payload: { language: 'en', files: ['a.pdf'] } });
});

test('a rendering failure shows a way to recover instead of a blank page', () => {
  assert.deepEqual(ErrorBoundary.getDerivedStateFromError(), { failed: true });
  const boundary = new ErrorBoundary({ children: null });
  boundary.state = { failed: true };
  const html = renderToStaticMarkup(boundary.render());
  assert.match(html, /role="alert"/);
  assert.match(html, /بارگذاری دوباره/);
});
