/** A run of excerpt text, or a Markdown table found inside an excerpt. */
export type ExcerptBlock =
  | { kind: 'text'; text: string }
  | { kind: 'table'; header: string[] | null; rows: string[][] };

const SEPARATOR_CELL = /^:?-{3,}:?$/;

function tableCells(line: string): string[] {
  const inner = line.trim().replace(/^\|/, '').replace(/(?<!\\)\|$/, '');
  return inner.split(/(?<!\\)\|/).map(cell => cell.trim().replace(/\\\|/g, '|'));
}

/**
 * Split an excerpt into text and tables. Table rows are lines that start with
 * "|"; a row of dashes marks the header above it. Excerpts cut from the
 * middle of a table have no header, so their rows render without one.
 */
export function splitExcerpt(text: string): ExcerptBlock[] {
  const blocks: ExcerptBlock[] = [];
  let prose: string[] = [];
  let rows: string[][] = [];
  let header: string[] | null = null;
  const flushProse = () => {
    if (prose.length) blocks.push({ kind: 'text', text: prose.join('\n') });
    prose = [];
  };
  const flushTable = () => {
    if (rows.length || header) {
      // A single pipe-led line is more likely prose than a table.
      if (!header && rows.length === 1) prose.push(`| ${rows[0].join(' | ')} |`);
      else { flushProse(); blocks.push({ kind: 'table', header, rows }); }
    }
    rows = [];
    header = null;
  };
  for (const line of text.split('\n')) {
    if (line.trim().startsWith('|')) {
      const cells = tableCells(line);
      if (cells.every(cell => SEPARATOR_CELL.test(cell)) && rows.length && !header) {
        header = rows.pop() ?? null;
        continue;
      }
      rows.push(cells);
      continue;
    }
    flushTable();
    prose.push(line);
  }
  flushTable();
  flushProse();
  return blocks;
}
