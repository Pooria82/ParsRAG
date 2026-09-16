const { test } = require('node:test');
const assert = require('node:assert/strict');
const React = require('react');
const { renderToStaticMarkup } = require('react-dom/server');
const { ChatFeed } = require('./.compiled/components/ChatFeed.js');
const { Composer } = require('./.compiled/components/Composer.js');
const { DocumentCenter } = require('./.compiled/components/DocumentCenter.js');
const { SettingsModal } = require('./.compiled/components/SettingsModal.js');
const { BootSequence } = require('./.compiled/components/BootSequence.js');
const { ChoiceMenu } = require('./.compiled/components/ui/ChoiceMenu.js');
const { BrandMark } = require('./.compiled/components/BrandMark.js');
const { DEFAULT_SETTINGS } = require('./.compiled/core/state.js');
const render = (Component, props) => renderToStaticMarkup(React.createElement(Component, props));
const noop = () => {};

test('model markdown cannot execute HTML or fetch a tracking image', () => {
  const html = render(ChatFeed, { messages: [{ id: 'm1', role: 'assistant', timestamp: 1,
    content: '<script>alert(1)</script>\n\n![tracker](https://outside.invalid/pixel)\n\n[unsafe](javascript:alert(1))' }],
    language: 'fa', isGenerating: false, activeMode: 'hybrid', onRetry: noop, isBusy: false });
  assert.doesNotMatch(html, /<script|<img|href="javascript:/);
  assert.match(html, /tracker/);
});

test('citation filenames and excerpts are escaped, with keyboard-operable disclosure', () => {
  const html = render(ChatFeed, { messages: [{ id: 'm2', role: 'assistant', content: 'پاسخ', timestamp: 1,
    citations: [{ filename: '<img src=x onerror=alert(1)>', body: '<script>source</script>', score: 0.8 }] }],
    language: 'fa', isGenerating: false, activeMode: 'strict', onRetry: noop, isBusy: false });
  assert.match(html, /<details class="citation"/);
  assert.match(html, /&lt;script&gt;source&lt;\/script&gt;/);
  assert.doesNotMatch(html, /<img/);
});

test('empty Persian composer uses RTL, has a real label and disables empty submission', () => {
  const html = render(Composer, { value: '', onChange: noop, onSendMessage: noop, onStopGenerating: noop,
    isGenerating: false, isBusy: false, activeMode: 'hybrid', onChangeMode: noop, language: 'fa',
    onOpenDocuments: noop, documentCount: 0, focusToken: 0 });
  assert.match(html, /<textarea[^>]*aria-label="پیام شما"[^>]*dir="rtl"/);
  assert.match(html, /<button[^>]*disabled=""[^>]*aria-label="ارسال پیام"/);
});

test('stop control replaces submission during a pending answer', () => {
  const html = render(Composer, { value: 'next draft', onChange: noop, onSendMessage: noop, onStopGenerating: noop,
    isGenerating: true, isBusy: true, activeMode: 'llm-only', onChangeMode: noop, language: 'en',
    onOpenDocuments: noop, documentCount: 0, focusToken: 0 });
  assert.match(html, /aria-label="Stop receiving answer"/);
  assert.doesNotMatch(html, /aria-label="Send message"/);
  assert.doesNotMatch(html, /<textarea[^>]*disabled/);
});

test('document controls match API formats and protect the final selected source', () => {
  const html = render(DocumentCenter, { isOpen: false, onClose: noop, documents: [{ name: 'a.pdf', status: 'indexed' }],
    onUploadFiles: noop, onRemoveFailed: noop, onToggleDocument: noop, language: 'en', isUploading: false, activeMode: 'strict', error: null });
  assert.match(html, /accept=".pdf,.docx,.pptx"/);
  assert.match(html, /type="checkbox"[^>]*disabled=""/);
  assert.doesNotMatch(html, /Delete document/);
});

test('settings render labeled native choices and modal semantics in both languages', () => {
  for (const language of ['fa', 'en']) {
    const html = render(SettingsModal, { onClose: noop, settings: { ...DEFAULT_SETTINGS, language }, onUpdateSettings: noop, onClearAllData: noop, busy: false });
    assert.match(html, /<dialog[^>]*aria-labelledby=/);
    assert.match(html, /role="tablist"/);
    assert.equal((html.match(/type="radio"/g) || []).length, 4);
  }
});

test('startup sequence exposes a quiet branded status before the workspace appears', () => {
  const html = render(BootSequence, { language: 'fa' });
  assert.match(html, /class="boot-sequence"/);
  assert.match(html, /role="status"/);
  assert.match(html, /پارس‌رگ/);
  assert.match(html, /boot-trace/);
});

test('brand mark is a reusable project-owned vector asset', () => {
  const html = render(BrandMark, {});
  assert.match(html, /data-brand="parsrag-mark"/);
  assert.equal((html.match(/<path/g) || []).length >= 4, true);
  assert.doesNotMatch(html, /linearGradient|radialGradient|filter=/);
});

test('settings mode selector is a keyboard-ready custom menu rather than a native select', () => {
  const html = render(ChoiceMenu, { label: 'Answer mode', value: 'hybrid', onChange: noop,
    options: [{ value: 'hybrid', label: 'Hybrid' }, { value: 'strict', label: 'Strict' }] });
  assert.match(html, /aria-haspopup="menu"/);
  assert.match(html, /class="choice-menu-trigger"/);
  assert.doesNotMatch(html, /<select/);
});
