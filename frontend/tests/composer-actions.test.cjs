const { test } = require('node:test');
const assert = require('node:assert/strict');
const { activeComposerTrigger, insertDocumentMention, applyComposerCommand } = require('./.compiled/core/composerActions.js');

test('mention insertion preserves Persian filenames and surrounding text', () => {
  const text = 'از @گزارش دربارهٔ هزینه و از سند دیگر دربارهٔ زمان بگو';
  const cursor = 'از @گزارش'.length;
  const trigger = activeComposerTrigger(text, cursor);
  assert.equal(trigger.kind, 'document');
  const inserted = insertDocumentMention(text, trigger, 'گزارش نهایی.pdf');
  assert.equal(inserted.text, 'از @{گزارش نهایی.pdf} دربارهٔ هزینه و از سند دیگر دربارهٔ زمان بگو');
  assert.equal(activeComposerTrigger('email@example.com', 17), null);
  const braces = insertDocumentMention('@گزارش', activeComposerTrigger('@گزارش', '@گزارش'.length), 'گزارش {نهایی}.pdf');
  assert.equal(braces.text, '@{گزارش \\{نهایی\\}.pdf} ');
});

test('slash commands apply only known prompt and mode actions', () => {
  const trigger = activeComposerTrigger('/strict', 7);
  assert.equal(trigger.kind, 'command');
  assert.deepEqual(applyComposerCommand('strict', 'en', '/strict', trigger), { text: '', mode: 'strict' });
  assert.match(applyComposerCommand('summary', 'fa', '/summary', activeComposerTrigger('/summary', 8)).text, /منبع/);
  assert.deepEqual(applyComposerCommand('documents', 'en', '/documents', activeComposerTrigger('/documents', 10)), { text: '', action: 'documents' });
  assert.deepEqual(applyComposerCommand('help', 'en', '/help', activeComposerTrigger('/help', 5)), { text: '', action: 'help' });
  assert.deepEqual(applyComposerCommand('hybrid', 'en', '/hybrid', activeComposerTrigger('/hybrid', 7)), { text: '', mode: 'hybrid' });
  assert.deepEqual(applyComposerCommand('free', 'en', '/free', activeComposerTrigger('/free', 5)), { text: '', mode: 'llm-only' });
  for (const command of ['summary', 'compare', 'translate', 'outline']) {
    const token = `/${command}`;
    const result = applyComposerCommand(command, 'en', token, activeComposerTrigger(token, token.length));
    assert.ok(result.text.length > 10);
    assert.equal(result.mode, undefined);
    assert.equal(result.action, undefined);
  }
});
