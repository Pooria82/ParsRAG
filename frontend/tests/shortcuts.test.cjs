const { test } = require('node:test');
const assert = require('node:assert/strict');
const { isApplePlatform, resolveShortcut, shortcutLabel } = require('./.compiled/core/shortcuts.js');

function key(key, options = {}) {
  return { key, ctrlKey: false, metaKey: false, shiftKey: false, altKey: false, isComposing: false, ...options };
}

test('shows and accepts Command on Apple platforms and Control on Windows and Linux', () => {
  assert.equal(isApplePlatform('MacIntel'), true);
  assert.equal(isApplePlatform('Win32'), false);
  assert.equal(isApplePlatform('Linux x86_64'), false);
  assert.equal(shortcutLabel('newChat', true), '⌘⇧O');
  assert.equal(shortcutLabel('newChat', false), 'Ctrl+Shift+O');
  assert.equal(resolveShortcut(key('O', { metaKey: true, shiftKey: true }), true, false), 'newChat');
  assert.equal(resolveShortcut(key('O', { ctrlKey: true, shiftKey: true }), false, false), 'newChat');
  assert.equal(resolveShortcut(key('O', { ctrlKey: true, shiftKey: true }), true, false), null);
  assert.equal(resolveShortcut(key('O', { metaKey: true, shiftKey: true }), false, false), null);
});

test('shortcuts avoid unmodified text entry and unsupported modifier combinations', () => {
  assert.equal(resolveShortcut(key('/'), false, false), 'composer');
  assert.equal(resolveShortcut(key('/'), false, true), null);
  assert.equal(resolveShortcut(key('K', { ctrlKey: true, shiftKey: true }), false, true), 'searchChats');
  assert.equal(resolveShortcut(key('K', { ctrlKey: true, shiftKey: true, altKey: true }), false, false), null);
  assert.equal(resolveShortcut(key('h', { ctrlKey: true, shiftKey: true, isComposing: true }), false, false), null);
});
