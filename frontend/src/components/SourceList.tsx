import { useEffect, useRef, useState } from 'react';
import { BookOpenCheck, ChevronDown, FileText } from 'lucide-react';
import type { Language, SourcePassage } from '../types';
import { translations } from '../i18n/translations';
import { splitExcerpt } from '../core/excerpt';

interface SourceListProps {
  messageId: string;
  sources: SourcePassage[];
  language: Language;
  /** The question; its distinctive words are highlighted in excerpts. */
  question?: string;
  /** Source number to open and scroll to, e.g. after a citation chip click. */
  focus?: number;
  focusToken?: number;
  /** Address of a cited image's preview; the image is shown above its text. */
  imageUrl?: (filename: string, image: number) => string;
}

export function sourceLocationLabel(source: SourcePassage, language: Language): string {
  const location = source.location;
  if (!location) return '';
  const t = translations[language];
  const start = location.start.toLocaleString(language);
  const end = location.end && location.end !== location.start ? `–${location.end.toLocaleString(language)}` : '';
  const table = location.table ? ` · ${t.tableLabel} ${location.table.toLocaleString(language)}` : '';
  const image = location.image ? ` · ${t.imageLabel} ${location.image.toLocaleString(language)}` : '';
  return `${t.locationLabels[location.kind]} ${start}${end}${table}${image}`;
}

const STOPWORDS = new Set(['این', 'آن', 'که', 'است', 'برای', 'از', 'با', 'در', 'به', 'را', 'چه', 'چیست', 'چطور', 'چگونه', 'کدام', 'هست', 'بود', 'what', 'which', 'how', 'the', 'and', 'for', 'with', 'does', 'this', 'that']);

/** Words of the question worth highlighting (3+ letters, not stopwords). */
export function highlightTerms(question: string): string[] {
  const words = question.toLocaleLowerCase().match(/[\p{L}\p{N}]{3,}/gu) ?? [];
  return [...new Set(words.filter(word => !STOPWORDS.has(word)))].sort((a, b) => b.length - a.length).slice(0, 12);
}

/** Split text into plain and highlighted parts for the question's terms. */
export function highlightParts(text: string, terms: string[]): Array<{ text: string; mark: boolean }> {
  if (!terms.length) return [{ text, mark: false }];
  const escaped = terms.map(term => term.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'));
  const pattern = new RegExp(`(${escaped.join('|')})`, 'giu');
  return text.split(pattern).filter(Boolean).map(part => ({ text: part, mark: terms.includes(part.toLocaleLowerCase()) }));
}

function excerptPreview(text: string): string {
  const line = text.replace(/\[page \d+\]\s*/g, '').replace(/\s+/g, ' ').trim();
  return line.length > 110 ? `${line.slice(0, 110).replace(/\s+\S*$/, '')}…` : line;
}

function Highlighted({ text, terms }: { text: string; terms: string[] }) {
  return <>{highlightParts(text, terms).map((part, index) => part.mark ? <mark key={index}>{part.text}</mark> : part.text)}</>;
}

function SourceImage({ src, alt }: { src: string; alt: string }) {
  const [failed, setFailed] = useState(false);
  // Documents indexed before previews existed have none; show only the text then.
  if (failed) return null;
  return <a className="source-image" href={src} target="_blank" rel="noreferrer noopener">
    <img src={src} alt={alt} loading="lazy" decoding="async" onError={() => setFailed(true)} />
  </a>;
}

function SourceCard({ source, language, messageId, active, terms, showFile, imageUrl }: { source: SourcePassage; language: Language; messageId: string; active: boolean; terms: string[]; showFile: boolean; imageUrl?: (filename: string, image: number) => string }) {
  const ref = useRef<HTMLLIElement>(null);
  const [opened, setOpened] = useState(active);
  useEffect(() => {
    if (!active) return;
    const element = ref.current;
    element?.querySelector('details')?.setAttribute('open', '');
    element?.scrollIntoView({ block: 'nearest', behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'instant' : 'smooth' });
  }, [active]);
  const location = sourceLocationLabel(source, language);
  return <li ref={ref} id={`source-${messageId}-${source.n}`} className={'source-card' + (active ? ' is-active' : '')}>
    <details open={active || undefined} onToggle={event => { if (event.currentTarget.open) setOpened(true); }}>
      <summary>
        <span className="source-number">{source.n.toLocaleString(language)}</span>
        <span className="source-title"><bdi className="source-preview" dir="auto">{excerptPreview(source.text)}</bdi>
          <small>{showFile && <bdi>{source.filename}</bdi>}{showFile && location ? ' · ' : ''}{location}</small></span>
        <ChevronDown size={14} className="source-chevron" aria-hidden="true" />
      </summary>
      {opened && imageUrl && source.location?.image ? <SourceImage src={imageUrl(source.filename, source.location.image)} alt={location} /> : null}
      <blockquote dir="auto">{splitExcerpt(source.text).map((block, index) => block.kind === 'text'
        ? <Highlighted key={index} text={block.text} terms={terms} />
        : <div key={index} className="table-scroll source-table"><table dir="auto">
          {block.header && <thead><tr>{block.header.map((cell, at) => <th key={at}><Highlighted text={cell} terms={terms} /></th>)}</tr></thead>}
          <tbody>{block.rows.map((row, at) => <tr key={at}>{row.map((cell, column) => <td key={column}><Highlighted text={cell} terms={terms} /></td>)}</tr>)}</tbody>
        </table></div>)}</blockquote>
    </details>
  </li>;
}

/** Numbered sources: the passages an answer cites first, the rest folded away. */
export function SourceList({ messageId, sources, language, focus, focusToken, question = '', imageUrl }: SourceListProps) {
  const t = translations[language];
  const terms = highlightTerms(question);
  const files = [...new Set(sources.map(source => source.filename))];
  const showFile = files.length > 1;
  const cited = sources.filter(source => source.cited);
  const primary = cited.length ? cited : sources;
  const others = cited.length ? sources.filter(source => !source.cited) : [];
  const focusInOthers = focus !== undefined && others.some(source => source.n === focus);
  return <section className="source-list" data-tour="sources" aria-label={t.citationsTitle}>
    <header>{cited.length ? <BookOpenCheck size={15} /> : <FileText size={15} />}<span>{cited.length ? t.citationsTitle : t.sourcesConsulted}</span>
      {!showFile && <bdi className="source-file">{files[0]}</bdi>}</header>
    <ol>{primary.map(source => <SourceCard key={`${focusToken ?? 0}-${source.n}`} source={source} language={language} messageId={messageId} active={source.n === focus} terms={terms} showFile={showFile} imageUrl={imageUrl} />)}</ol>
    {others.length > 0 && <details className="source-more" open={focusInOthers || undefined}>
      <summary>{t.moreSources.replace('{count}', others.length.toLocaleString(language))}</summary>
      <ol>{others.map(source => <SourceCard key={`${focusToken ?? 0}-${source.n}`} source={source} language={language} messageId={messageId} active={source.n === focus} terms={terms} showFile={showFile} imageUrl={imageUrl} />)}</ol>
    </details>}
  </section>;
}
