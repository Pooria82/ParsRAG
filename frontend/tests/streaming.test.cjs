const { test, afterEach } = require('node:test');
const assert = require('node:assert/strict');
const React = require('react');
const { renderToStaticMarkup } = require('react-dom/server');
const { ParsRagApiClient, parseSseBlock } = require('./.compiled/services/api.js');
const { ChatFeed } = require('./.compiled/components/ChatFeed.js');
const { citedNumbers } = require('./.compiled/core/citations.js');
const { parseAnswer } = require('./.compiled/core/state.js');

const originalFetch = global.fetch;
afterEach(() => { global.fetch = originalFetch; });
const noop = () => {};

function streamResponse(chunks, status = 200) {
  const encoder = new TextEncoder();
  const body = new ReadableStream({ start(controller) { for (const chunk of chunks) controller.enqueue(encoder.encode(chunk)); controller.close(); } });
  return new Response(body, { status, headers: { 'Content-Type': 'text/event-stream' } });
}
const sse = (kind, data) => `event: ${kind}\ndata: ${JSON.stringify(data)}\n\n`;

test('SSE blocks become typed events and errors become coded failures', () => {
  assert.deepEqual(parseSseBlock('event: stage\ndata: {"stage":"retrieving"}'), { type: 'stage', stage: 'retrieving' });
  assert.deepEqual(parseSseBlock('event: token\ndata: {"text":"سلام\\n"}'), { type: 'token', text: 'سلام\n' });
  assert.equal(parseSseBlock('event: stage\ndata: {"stage":"hacked"}'), undefined);
  assert.equal(parseSseBlock(': keep-alive'), undefined);
  assert.throws(() => parseSseBlock('event: error\ndata: {"detail":"x","code":"model_auth"}'), error => error.code === 'model_auth');
});

test('the client streams events across chunk boundaries and returns the result', async () => {
  const body = sse('stage', { stage: 'understanding' }) + sse('sources', { source_nodes: [{ text: 'a', metadata: { filename: 'a.pdf' } }] })
    + sse('token', { text: 'هدف ' }) + sse('token', { text: 'پروژه [1]' })
    + sse('done', { answer: 'هدف پروژه [1]', source_nodes: [{ text: 'a', metadata: { filename: 'a.pdf' } }], cited: [1] });
  const chunks = [body.slice(0, 17), body.slice(17, 90), body.slice(90).replace(/\n\n/g, '\r\n\r\n')];
  let requested;
  global.fetch = async (url, init) => { requested = { url: String(url), init }; return streamResponse(chunks); };
  const events = [];

  const result = await new ParsRagApiClient('').queryStream({ prompt: 'x' }, undefined, event => events.push(event));

  assert.equal(requested.url, '/query/stream');
  assert.equal(requested.init.headers.Accept, 'text/event-stream');
  assert.deepEqual(events.map(event => event.type), ['stage', 'sources', 'token', 'token', 'done']);
  assert.equal(events.filter(event => event.type === 'token').map(event => event.text).join(''), 'هدف پروژه [1]');
  assert.deepEqual(parseAnswer(result).sources.map(source => source.cited), [true]);
});

test('a stream that ends early or reports an error rejects with a code', async () => {
  global.fetch = async () => streamResponse([sse('token', { text: 'half' })]);
  await assert.rejects(() => new ParsRagApiClient('').queryStream({}, undefined, noop), error => error.code === 'stream_interrupted');
  global.fetch = async () => streamResponse([sse('token', { text: 'half' }), sse('error', { detail: 'slow', code: 'model_timeout' })]);
  await assert.rejects(() => new ParsRagApiClient('').queryStream({}, undefined, noop), error => error.code === 'model_timeout');
  global.fetch = async () => new Response(JSON.stringify({ detail: 'busy', code: 'busy' }), { status: 429 });
  await assert.rejects(() => new ParsRagApiClient('').queryStream({}, undefined, noop), error => error.code === 'busy' && error.status === 429);
});

test('streamed text renders live with a caret instead of the progress card', () => {
  const html = renderToStaticMarkup(React.createElement(ChatFeed, {
    messages: [{ id: 'u', role: 'user', timestamp: 1, content: 'پرسش' }], language: 'fa', isGenerating: true,
    activeMode: 'hybrid', onRetry: noop, onEditPrompt: noop, onSelectVariant: noop, onRevealComplete: noop, isBusy: true,
    streamingDraft: { content: 'پاسخ در حال **نوشتن**' },
  }));
  assert.match(html, /class="message message-assistant is-streaming"[^>]*aria-busy="true"/);
  assert.match(html, /<strong>نوشتن<\/strong>/);
  assert.match(html, /response-caret/);
  assert.doesNotMatch(html, /query-progress/);
});

test('partial answers keep the numbers they already cite', () => {
  assert.deepEqual(citedNumbers('a [2] b [1][2] c [9]', 3), [2, 1]);
});

test('refusals carry an outcome the interface can explain', () => {
  assert.equal(parseAnswer({ answer: 'x', outcome: 'no_evidence' }).outcome, 'no_evidence');
  assert.equal(parseAnswer({ answer: 'x', outcome: 'surprise' }).outcome, 'answered');
});
