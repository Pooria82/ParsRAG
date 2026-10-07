import type { Citation, SourcePassage } from '../types';

// Code and math are never rewritten; the capture group keeps them in split().
const PROTECTED = /(```[\s\S]*?```|`[^`\n]*`|\$\$[\s\S]*?\$\$|\$[^$\n]+\$)/g;
// [2], [1, 3], [۲]، [1][2]; not an existing Markdown link such as [1](url).
const CITATION = /\[\s*([0-9۰-۹٠-٩]{1,3}(?:\s*[,،]\s*[0-9۰-۹٠-٩]{1,3})*)\s*\](?!\()/g;

function asciiDigits(value: string): string {
  return value.replace(/[۰-۹]/g, digit => String(digit.charCodeAt(0) - 0x06F0))
    .replace(/[٠-٩]/g, digit => String(digit.charCodeAt(0) - 0x0660));
}

/** Turn [n] citation markers into `#cite-n` links the renderer shows as chips. */
export function linkCitations(markdown: string, sourceCount: number): string {
  if (!sourceCount) return markdown;
  return markdown.split(PROTECTED).map((part, index) => index % 2 ? part : part.replace(CITATION, (whole: string, list: string) => {
    const numbers = list.split(/\s*[,،]\s*/).map(value => Number(asciiDigits(value)));
    if (!numbers.every(number => Number.isInteger(number) && number >= 1 && number <= sourceCount)) return whole;
    return numbers.map(number => `[${number}](#cite-${number})`).join('');
  })).join('');
}

/** Read the source number from a citation link, or undefined for other links. */
export function citationNumber(href: string | undefined): number | undefined {
  const match = /^#cite-(\d{1,3})$/.exec(href ?? '');
  return match ? Number(match[1]) : undefined;
}

/** Group passages by file for the compact per-file source summary. */
export function summarizeSources(sources: SourcePassage[]): Citation[] {
  const files = new Map<string, Citation>();
  for (const source of sources) {
    const citation = files.get(source.filename) ?? { filename: source.filename, locations: [] };
    const location = source.location;
    if (location && !citation.locations.some(item => item.kind === location.kind && item.start === location.start && item.end === location.end)) {
      citation.locations.push(location);
    }
    files.set(source.filename, citation);
  }
  return [...files.values()];
}
