const PROTECTED_MARKDOWN = /(```[\s\S]*?```|`[^`\n]*`)/g;
/** Persian/Arabic letters must never be typeset in math mode. */
const RTL_LETTER = /[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\uFB50-\uFDFF\uFE70-\uFEFF]/;
const TEXT_GROUP = /\\(?:text|mathrm|textrm|operatorname)\s*\{[^{}]*\}/g;

/**
 * Commands that unambiguously start mathematics. A whitelist keeps Windows
 * paths (C:\Users) and escaped characters from being typeset as formulae.
 */
const MATH_COMMANDS = new Set([
  'sin', 'cos', 'tan', 'cot', 'sec', 'csc', 'arcsin', 'arccos', 'arctan', 'sinh', 'cosh', 'tanh',
  'log', 'ln', 'lg', 'exp', 'lim', 'liminf', 'limsup', 'max', 'min', 'sup', 'inf', 'det', 'deg',
  'gcd', 'mod', 'bmod', 'pmod', 'arg', 'dim', 'ker', 'Pr',
  'sum', 'prod', 'int', 'iint', 'iiint', 'oint', 'frac', 'dfrac', 'tfrac', 'sqrt', 'binom',
  'alpha', 'beta', 'gamma', 'delta', 'epsilon', 'varepsilon', 'zeta', 'eta', 'theta', 'vartheta',
  'iota', 'kappa', 'lambda', 'mu', 'nu', 'xi', 'pi', 'varpi', 'rho', 'sigma', 'tau', 'upsilon',
  'phi', 'varphi', 'chi', 'psi', 'omega', 'Gamma', 'Delta', 'Theta', 'Lambda', 'Xi', 'Pi',
  'Sigma', 'Upsilon', 'Phi', 'Psi', 'Omega',
  'infty', 'partial', 'nabla', 'cdot', 'cdots', 'ldots', 'dots', 'times', 'div', 'pm', 'mp',
  'leq', 'le', 'geq', 'ge', 'neq', 'ne', 'approx', 'equiv', 'sim', 'simeq', 'propto', 'cong',
  'to', 'rightarrow', 'leftarrow', 'Rightarrow', 'Leftarrow', 'leftrightarrow', 'Leftrightarrow',
  'implies', 'iff', 'mapsto', 'in', 'notin', 'subset', 'subseteq', 'supset', 'cup', 'cap',
  'forall', 'exists', 'neg', 'land', 'lor', 'oplus', 'otimes', 'circ', 'angle', 'perp',
  'vec', 'hat', 'bar', 'dot', 'ddot', 'overline', 'underline', 'mathbb', 'mathbf', 'mathcal',
  'mathrm', 'operatorname', 'left', 'right', 'quad', 'qquad',
]);
const MATH_COMMAND = /\\([A-Za-z]+)/g;
/**
 * A bare formula: an optional one-character operand and operator, a command,
 * then math tokens (commands, groups, scripts, numbers, single-letter
 * variables, operators). Words of two or more letters end the formula.
 */
const BARE_FORMULA = new RegExp(
  String.raw`(?:(?<![A-Za-z])[A-Za-z0-9]\s*[=+\-*/^_]\s*)?\\[A-Za-z]+`
  + String.raw`(?:\s*(?:\\[A-Za-z]+|\{[^{}\n]*\}|[_^](?:\{[^{}\n]*\}|[A-Za-z0-9])`
  + String.raw`|[A-Za-z]{1,3}[_^](?:\{[^{}\n]*\}|[A-Za-z0-9])`
  + String.raw`|[0-9]+(?:\.[0-9]+)?|(?<![A-Za-z])[A-Za-z](?![A-Za-z])|[()[\]+\-*/=<>|!]))*`,
  'g',
);

function hasRtlOutsideText(expression: string): boolean {
  return RTL_LETTER.test(expression.replace(TEXT_GROUP, ''));
}

function hasMathCommand(expression: string): boolean {
  for (const match of expression.matchAll(MATH_COMMAND)) {
    if (MATH_COMMANDS.has(match[1])) return true;
  }
  return false;
}

function looksLikeFormula(value: string): boolean {
  const expression = value.trim();
  if (expression.length < 3 || expression.length > 600 || expression.includes('\n')) return false;
  if (hasRtlOutsideText(expression)) return false;
  const hasOperand = /[A-Za-z0-9Α-ω]/.test(expression);
  const hasTeX = /\\[A-Za-z]+|[_^](?:\{|[A-Za-z0-9])/.test(expression);
  const hasEquation = /(?:=|≤|≥|≈|≠|<|>)/.test(expression)
    && /(?:[+\-*/^]|\\[A-Za-z]+|[A-Za-z][_{])/.test(expression);
  return hasOperand && (hasTeX || hasEquation);
}

/** Wrap bare LaTeX such as "\sin" or "\frac{a}{b} = 1" in inline math delimiters. */
function wrapBareFormulae(text: string): string {
  if (!text.includes('\\')) return text;
  return text.replace(BARE_FORMULA, (match) => {
    const formula = match.trimEnd();
    const trailing = match.slice(formula.length);
    if (!hasMathCommand(formula) || hasRtlOutsideText(formula)) return match;
    return `$${formula.trim()}$${trailing}`;
  });
}

/**
 * Typeset parenthesized formulae such as "(E = mc^2)" and wrap bare LaTeX in
 * the surrounding text. Parentheses that contain Persian prose stay prose.
 */
function normalizeText(text: string): string {
  let output = '';
  let plain = '';
  let index = 0;
  const flushPlain = () => {
    output += wrapBareFormulae(plain);
    plain = '';
  };
  while (index < text.length) {
    if (text[index] !== '(') {
      plain += text[index];
      index += 1;
      continue;
    }
    let depth = 0;
    let closing = -1;
    for (let cursor = index; cursor < text.length; cursor += 1) {
      if (text[cursor] === '(') depth += 1;
      else if (text[cursor] === ')' && --depth === 0) {
        closing = cursor;
        break;
      }
    }
    if (closing < 0) {
      plain += text.slice(index);
      break;
    }
    flushPlain();
    const inner = text.slice(index + 1, closing);
    output += looksLikeFormula(inner) ? `$${inner.trim()}$` : `(${normalizeText(inner)})`;
    index = closing + 1;
  }
  flushPlain();
  return output;
}

/**
 * Split a line into valid math spans and text, repairing model mistakes:
 * unmatched `$`/`$$` are dropped, and spans that contain Persian words are
 * unwrapped so only their LaTeX parts are typeset.
 */
function normalizeLine(line: string): string {
  let output = '';
  let text = '';
  let index = 0;
  const flushText = () => {
    output += normalizeText(text);
    text = '';
  };
  while (index < line.length) {
    const char = line[index];
    if (char === '\\' && line[index + 1] === '$') {
      text += '\\$';
      index += 2;
      continue;
    }
    if (char !== '$') {
      text += char;
      index += 1;
      continue;
    }
    const marker = line[index + 1] === '$' ? '$$' : '$';
    const closing = line.indexOf(marker, index + marker.length);
    if (closing < 0) {
      // An opener without a partner is a stray delimiter; drop it.
      index += marker.length;
      continue;
    }
    const inner = line.slice(index + marker.length, closing);
    if (inner.trim() && !hasRtlOutsideText(inner)) {
      flushText();
      output += `${marker}${inner}${marker}`;
    } else {
      text += inner;
    }
    index = closing + marker.length;
  }
  flushText();
  return output;
}

/** Converts common model-produced math delimiters into remark-math syntax. */
export function normalizeMathMarkdown(content: string): string {
  return content.split(PROTECTED_MARKDOWN).map((segment, index) => {
    if (index % 2 === 1) return segment;
    const lines = segment
      .replace(/\\\[([\s\S]*?)\\\]/g, (_match, formula: string) => `$$\n${formula.trim()}\n$$`)
      .replace(/\\\((.*?)\\\)/g, (_match, formula: string) => `$${formula.trim()}$`)
      .split('\n');
    const output: string[] = [];
    for (let at = 0; at < lines.length; at += 1) {
      if (lines[at].trim() === '$$') {
        // Multi-line display block: keep it verbatim when it is closed.
        const close = lines.findIndex((value, position) => position > at && value.trim() === '$$');
        if (close > at) {
          output.push(...lines.slice(at, close + 1));
          at = close;
        }
        continue;
      }
      output.push(normalizeLine(lines[at]));
    }
    return output.join('\n')
      .replace(/^\$\$([^\n]+)\$\$$/gm, (_match, formula: string) => `$$\n${formula}\n$$`);
  }).join('');
}
