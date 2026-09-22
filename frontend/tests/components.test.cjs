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
const { Header } = require('./.compiled/components/Header.js');
const { Sidebar } = require('./.compiled/components/Sidebar.js');
const { DEFAULT_SETTINGS } = require('./.compiled/core/state.js');
const { normalizeMathMarkdown } = require('./.compiled/core/markdown.js');
const render = (Component, props) => renderToStaticMarkup(React.createElement(Component, props));
const noop = () => {};

test('model markdown cannot execute HTML or fetch a tracking image', () => {
  const html = render(ChatFeed, { messages: [{ id: 'm1', role: 'assistant', timestamp: 1,
    content: '<script>alert(1)</script>\n\n![tracker](https://outside.invalid/pixel)\n\n[unsafe](javascript:alert(1))' }],
    language: 'fa', isGenerating: false, activeMode: 'hybrid', onRetry: noop, isBusy: false });
  assert.doesNotMatch(html, /<script|<img|href="javascript:/);
  assert.match(html, /tracker/);
});

test('assistant response direction follows its content instead of interface language', () => {
  const englishInPersian = render(ChatFeed, { messages: [{ id: 'en', role: 'assistant', timestamp: 1, content: 'This answer is in English.' }], language: 'fa', isGenerating: false, activeMode: 'hybrid', onRetry: noop, onEditPrompt: noop, onSelectVariant: noop, isBusy: false });
  const persianInEnglish = render(ChatFeed, { messages: [{ id: 'fa', role: 'assistant', timestamp: 1, content: 'این پاسخ فارسی است.' }], language: 'en', isGenerating: false, activeMode: 'hybrid', onRetry: noop, onEditPrompt: noop, onSelectVariant: noop, isBusy: false });
  assert.match(englishInPersian, /class="prose-content" dir="auto"/);
  assert.match(persianInEnglish, /class="prose-content" dir="auto"/);
});

test('assistant markdown renders inline and display mathematics with KaTeX', () => {
  const html = render(ChatFeed, { messages: [{ id: 'math', role: 'assistant', timestamp: 1,
    content: 'رابطه $L_i = R_{i-1}$ است.\n\n$$R_i = L_{i-1} \\oplus F(R_{i-1}, K_i)$$' }],
    language: 'fa', isGenerating: false, activeMode: 'strict', onRetry: noop, onEditPrompt: noop,
    onSelectVariant: noop, onRevealComplete: noop, isBusy: false });
  assert.match(html, /class="katex"/);
  assert.match(html, /class="katex-display"/);
  assert.match(html, /<math/);
});

test('assistant markdown repairs model-produced parenthesized and escaped formulae', () => {
  const html = render(ChatFeed, { messages: [{ id: 'math-loose', role: 'assistant', timestamp: 1,
    content: 'حد: ( \\lim_{n \\to \\infty} P(|X_n-X| > \\epsilon) = 0 )\n\nانرژی: \\(E_k = \\frac{1}{2}mv^2\\)\n\n`(F = ma)`' }],
    language: 'fa', isGenerating: false, activeMode: 'strict', onRetry: noop, onEditPrompt: noop,
    onSelectVariant: noop, onRevealComplete: noop, isBusy: false });
  assert.match(html, /class="katex"/);
  assert.match(html, /mfrac/);
  assert.match(html, /<code>\(F = ma\)<\/code>/);
  assert.equal(normalizeMathMarkdown('حد: ( \\lim_{n \\to \\infty} n = 0 )'), 'حد: $\\lim_{n \\to \\infty} n = 0$');
  assert.equal(normalizeMathMarkdown('`(F = ma)`'), '`(F = ma)`');
});

test('query progress identifies the real active pipeline stage', () => {
  const html = render(ChatFeed, { messages: [], language: 'fa', isGenerating: true,
    activeMode: 'hybrid', queryStage: 'retrieving', onRetry: noop, onEditPrompt: noop,
    onSelectVariant: noop, onRevealComplete: noop, isBusy: true });
  assert.match(html, /یافتن شواهد مرتبط در اسناد/);
  assert.match(html, /class="query-loader"/);
  assert.match(html, /class="query-progress-label"/);
  assert.doesNotMatch(html, /<ol>/);
});

test('sources are compact, unique, escaped and show traceable locations', () => {
  const html = render(ChatFeed, { messages: [{ id: 'm2', role: 'assistant', content: 'پاسخ', timestamp: 1,
    citations: [{ filename: '<img src=x onerror=alert(1)>', locations: [{ kind: 'page', start: 3 }] }] }],
    language: 'fa', isGenerating: false, activeMode: 'strict', onRetry: noop, isBusy: false });
  assert.match(html, /class="citation-summary"/);
  assert.match(html, /صفحه ۳/);
  assert.doesNotMatch(html, /<img/);
  assert.doesNotMatch(html, /<details|امتیاز ارتباط/);
});

test('message actions include prompt editing, copying, retry and response navigation', () => {
  const html = render(ChatFeed, { messages: [
    { id: 'u1', role: 'user', content: 'original prompt', timestamp: 1 },
    { id: 'a1', role: 'assistant', content: 'second answer', timestamp: 3, activeVariant: 1, variants: [
      { id: 'v1', content: 'first answer', timestamp: 2 }, { id: 'v2', content: 'second answer', timestamp: 3 },
    ] },
  ], language: 'en', isGenerating: false, activeMode: 'hybrid', onRetry: noop, onEditPrompt: noop, onSelectVariant: noop, isBusy: false });
  assert.match(html, /Copy prompt/);
  assert.match(html, /Edit prompt/);
  assert.match(html, /Try again/);
  assert.match(html, /aria-label="Response versions"/);
  assert.match(html, />2 \/ 2</);
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

test('document controls allow clearing the final source and deleting an indexed document', () => {
  const html = render(DocumentCenter, { isOpen: false, onClose: noop, documents: [{ name: 'a.pdf', status: 'indexed' }],
    onUploadFiles: noop, onRemoveFailed: noop, onToggleDocument: noop, onDeleteDocument: noop, language: 'en', isUploading: false, activeMode: 'strict', error: null });
  assert.match(html, /accept=".pdf,.docx,.pptx"/);
  assert.match(html, /type="checkbox"/);
  assert.doesNotMatch(html, /type="checkbox"[^>]*disabled=""/);
  assert.match(html, /Delete document: a.pdf/);
});

test('document processing shows transfer, extraction and ready stages', () => {
  const html = render(DocumentCenter, { isOpen: true, onClose: noop,
    documents: [{ name: 'scan.pdf', status: 'processing', size: 1000 }], onUploadFiles: noop,
    onRemoveFailed: noop, onToggleDocument: noop, onDeleteDocument: noop, language: 'fa',
    isUploading: true, activeMode: 'strict', error: null });
  assert.match(html, /انتقال فایل/);
  assert.match(html, /استخراج و ایندکس/);
  assert.match(html, /آمادهٔ پرسش/);
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

test('brand controls are real buttons that start a new conversation', () => {
  const header = render(Header, { title: 'Thread', language: 'en', isSidebarOpen: true, isEmpty: false, documentCount: 0, onToggleSidebar: noop, onOpenDocuments: noop, onNewChat: noop });
  const sidebar = render(Sidebar, { sessions: [], activeSessionId: '', onSelectSession: noop, onNewChat: noop, onDeleteSession: async () => true, onRenameSession: noop, language: 'en', theme: 'light', onToggleTheme: noop, onOpenSettings: noop, isOpen: true, isMobile: false, onClose: noop, connection: 'online', onRetryConnection: noop });
  assert.match(header, /<button class="header-brand"[^>]*title="New conversation"/);
  assert.match(sidebar, /<button class="sidebar-brand"[^>]*title="New conversation"/);
});

test('sidebar replaces the generic local note with active model runtime details', () => {
  const html = render(Sidebar, { sessions: [], activeSessionId: '', onSelectSession: noop,
    onNewChat: noop, onDeleteSession: async () => true, onRenameSession: noop, language: 'fa',
    theme: 'light', onToggleTheme: noop, onOpenSettings: noop, isOpen: true, isMobile: false,
    onClose: noop, connection: 'online', modelRuntime: { provider: 'ollama', model_name: 'qwen2.5:7b',
      base_url: 'http://ollama:11434', api_key_configured: false }, onRetryConnection: noop });
  assert.match(html, /Ollama محلی/);
  assert.match(html, /qwen2.5:7b/);
  assert.doesNotMatch(html, /فضای کار محلی|تاریخچه در این مرورگر/);
});

test('settings mode selector is a keyboard-ready custom menu rather than a native select', () => {
  const html = render(ChoiceMenu, { label: 'Answer mode', value: 'hybrid', onChange: noop,
    options: [{ value: 'hybrid', label: 'Hybrid' }, { value: 'strict', label: 'Strict' }] });
  assert.match(html, /aria-haspopup="menu"/);
  assert.match(html, /class="choice-menu-trigger"/);
  assert.doesNotMatch(html, /<select/);
});

test('model settings keep provider-specific endpoints and require API disclosure', () => {
  const source = require('node:fs').readFileSync('src/components/SettingsModal.tsx', 'utf8');
  assert.match(source, /apiModelUrl/);
  assert.match(source, /ollamaModelUrl/);
  assert.match(source, /apiDisclosureAccepted/);
  assert.match(source, /remoteApiDisclosure/);
  assert.match(source, /localized-placeholder/);
  assert.match(source, /modelNamePlaceholder/);
  assert.match(source, /apiKeyAvailable/);
  assert.match(source, /apiKeyMissing/);
});

test('clear-all waits for backend deletion and preserves browser state on failure', () => {
  const settingsSource = require('node:fs').readFileSync('src/components/SettingsModal.tsx', 'utf8');
  const appSource = require('node:fs').readFileSync('src/App.tsx', 'utf8');
  assert.match(settingsSource, /onClearAllData\(\)\.then\(onClose\)\.catch/);
  assert.match(appSource, /await api\.deleteSession\(session\.id/);
  assert.match(appSource, /if \(failures\.length\) throw/);
});
