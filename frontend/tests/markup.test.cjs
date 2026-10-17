const { test } = require('node:test');
const assert = require('node:assert/strict');
const { normalizeMathMarkdown, repairModelMarkup } = require('./.compiled/core/markdown.js');
const { splitExcerpt } = require('./.compiled/core/excerpt.js');

test('leaked [extract_itex] math becomes inline math', () => {
  const answer = 'تعداد تجمعی خرابی‌ها: **45** [extract_itex]n = 45[/extract_itex] [۳]';
  assert.equal(repairModelMarkup(answer), 'تعداد تجمعی خرابی‌ها: **45** $n = 45$ [۳]');
  assert.match(normalizeMathMarkdown(answer), /\$n = 45\$/);
  assert.doesNotMatch(normalizeMathMarkdown(answer), /extract_itex/);
  assert.equal(repairModelMarkup('a [extract_itex][/extract_itex] b'), 'a  b');
  assert.equal(repairModelMarkup('stray [/extract_itex] tag'), 'stray  tag');
});

test('a half-streamed [extract_itex] tag stays hidden until it closes', () => {
  assert.equal(repairModelMarkup('مقدار [extract_itex]t = 3'), 'مقدار ');
  assert.equal(repairModelMarkup('مقدار [extr'), 'مقدار ');
  assert.equal(repairModelMarkup('see [1]'), 'see [1]');
  assert.equal(repairModelMarkup('list ['), 'list [');
});

test('table rows inside an excerpt become a table', () => {
  const blocks = splitExcerpt('جدول ۳-۱:\n| تاریخ | n | t |\n| :--- | :--- | :--- |\n| 03/24 | 44 | 352 |\n| 03/25 | 45 | 360 |\nپایان');
  assert.deepEqual(blocks, [
    { kind: 'text', text: 'جدول ۳-۱:' },
    { kind: 'table', header: ['تاریخ', 'n', 't'], rows: [['03/24', '44', '352'], ['03/25', '45', '360']] },
    { kind: 'text', text: 'پایان' },
  ]);
});

test('rows cut from the middle of a table render without a header', () => {
  const blocks = splitExcerpt('| 02/26 | 9 | 0.144 |\n| 02/27 | 1 | 0.143 |');
  assert.deepEqual(blocks, [{ kind: 'table', header: null, rows: [['02/26', '9', '0.144'], ['02/27', '1', '0.143']] }]);
});

test('escaped pipes stay inside a cell and a single pipe line stays prose', () => {
  assert.deepEqual(splitExcerpt('| a \\| b | c |\n| d | e |')[0].rows[0], ['a | b', 'c']);
  assert.deepEqual(splitExcerpt('متن | ادامه\n| فقط یک خط |'), [{ kind: 'text', text: 'متن | ادامه\n| فقط یک خط |' }]);
});
