const PROTECTED_MARKDOWN = /(```[\s\S]*?```|`[^`\n]*`)/g;

function looksLikeFormula(value: string): boolean {
  const expression = value.trim();
  if (expression.length < 3 || expression.length > 600 || expression.includes('\n')) return false;
  const hasOperand = /[A-Za-z0-9Α-ω]/.test(expression);
  const hasTeX = /\\[A-Za-z]+|[_^](?:\{|[A-Za-z0-9])/.test(expression);
  const hasEquation = /(?:=|≤|≥|≈|≠|<|>)/.test(expression)
    && /(?:[+\-*/^]|\\[A-Za-z]+|[A-Za-z][_{])/.test(expression);
  return hasOperand && (hasTeX || hasEquation);
}

function normalizeParenthesizedFormulae(line: string): string {
  let output = '';
  let index = 0;
  while (index < line.length) {
    if (line[index] === '$') {
      const marker = line[index + 1] === '$' ? '$$' : '$';
      const closing = line.indexOf(marker, index + marker.length);
      if (closing >= 0) {
        output += line.slice(index, closing + marker.length);
        index = closing + marker.length;
        continue;
      }
    }
    if (line[index] !== '(') {
      output += line[index];
      index += 1;
      continue;
    }
    let depth = 0;
    let closing = -1;
    for (let cursor = index; cursor < line.length; cursor += 1) {
      if (line[cursor] === '(') depth += 1;
      else if (line[cursor] === ')' && --depth === 0) {
        closing = cursor;
        break;
      }
    }
    if (closing < 0) {
      output += line.slice(index);
      break;
    }
    const inner = line.slice(index + 1, closing);
    output += looksLikeFormula(inner) ? `$${inner.trim()}$` : line.slice(index, closing + 1);
    index = closing + 1;
  }
  return output;
}

/** Converts common model-produced math delimiters into remark-math syntax. */
export function normalizeMathMarkdown(content: string): string {
  return content.split(PROTECTED_MARKDOWN).map((segment, index) => {
    if (index % 2 === 1) return segment;
    return segment
      .replace(/\\\[([\s\S]*?)\\\]/g, (_match, formula: string) => `$$\n${formula.trim()}\n$$`)
      .replace(/\\\((.*?)\\\)/g, (_match, formula: string) => `$${formula.trim()}$`)
      .split('\n')
      .map(normalizeParenthesizedFormulae)
      .join('\n')
      .replace(/^\$\$([^\n]+)\$\$$/gm, (_match, formula: string) => `$$\n${formula}\n$$`);
  }).join('');
}
