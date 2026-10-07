const { test } = require('node:test');
const assert = require('node:assert/strict');
const React = require('react');
const { renderToStaticMarkup } = require('react-dom/server');
const { linkCitations, citationNumber } = require('./.compiled/core/citations.js');
const { ChatFeed } = require('./.compiled/components/ChatFeed.js');
const { parseSessions } = require('./.compiled/core/state.js');

const noop = () => {};

test('citation markers become links only within the source range', () => {
  assert.equal(linkCitations('A [1]. B [2][3]. C [1, 3]. D [۲]', 3),
    'A [1](#cite-1). B [2](#cite-2)[3](#cite-3). C [1](#cite-1)[3](#cite-3). D [2](#cite-2)');
  assert.equal(linkCitations('out [4] and [0]', 3), 'out [4] and [0]');
  assert.equal(linkCitations('no sources [1]', 0), 'no sources [1]');
  assert.equal(linkCitations('[1](https://x.example) link', 3), '[1](https://x.example) link');
});

test('code and math keep their brackets', () => {
  const markdown = 'array `a[1]`\n\n```\nx = y[2]\n```\n\n$v_{[1]}$ and real [1]';
  assert.equal(linkCitations(markdown, 2), 'array `a[1]`\n\n```\nx = y[2]\n```\n\n$v_{[1]}$ and real [1](#cite-1)');
});

test('citation links are recognized and others are not', () => {
  assert.equal(citationNumber('#cite-12'), 12);
  assert.equal(citationNumber('https://example.com#cite-1'), undefined);
  assert.equal(citationNumber(undefined), undefined);
});

test('answers render citation chips and numbered, foldable sources', () => {
  const html = renderToStaticMarkup(React.createElement(ChatFeed, {
    messages: [{ id: 'a1', role: 'assistant', timestamp: 1, content: 'هدف پروژه ساخت سامانه است [2].',
      sources: [
        { n: 1, filename: 'a.pdf', text: 'متن دیگر', cited: false, location: { kind: 'page', start: 1 } },
        { n: 2, filename: 'report.pdf', text: 'هدف این پروژه ساخت سامانهٔ پرسش و پاسخ است.', cited: true, location: { kind: 'page', start: 4, end: 5 } },
      ] }],
    language: 'fa', isGenerating: false, activeMode: 'strict', onRetry: noop, onEditPrompt: noop,
    onSelectVariant: noop, onRevealComplete: noop, isBusy: false,
  }));
  assert.match(html, /class="cite-chip"[^>]*aria-label="نمایش منبع ۲"[^>]*>۲<\/button>/);
  assert.match(html, /id="source-a1-2"/);
  assert.match(html, /report\.pdf/);
  assert.match(html, /صفحه ۴–۵/);
  assert.match(html, /class="source-more"/);
  assert.match(html, /۱ بخش دیگر هم بررسی شد/);
});

test('stored sources survive a reload and are bounded', () => {
  const [session] = parseSessions(JSON.stringify([{ id: 'session_1', messages: [{ id: 'm', role: 'assistant', content: 'x [1]',
    sources: [{ n: 1, filename: 'a.pdf', text: 'y'.repeat(5000), cited: true, location: { kind: 'page', start: 3 } }, { n: 'bad' }] }] }]));
  const [source] = session.messages[0].sources;
  assert.equal(session.messages[0].sources.length, 1);
  assert.equal(source.text.length, 1600);
  assert.deepEqual(source.location, { kind: 'page', start: 3 });
});
