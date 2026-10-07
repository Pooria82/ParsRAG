import { useEffect, useRef } from 'react';
import { BookOpenCheck, ChevronDown, FileText } from 'lucide-react';
import type { Language, SourcePassage } from '../types';
import { translations } from '../i18n/translations';

interface SourceListProps {
  messageId: string;
  sources: SourcePassage[];
  language: Language;
  /** Source number to open and scroll to, e.g. after a citation chip click. */
  focus?: number;
  focusToken?: number;
}

export function sourceLocationLabel(source: SourcePassage, language: Language): string {
  const location = source.location;
  if (!location) return '';
  const t = translations[language];
  const start = location.start.toLocaleString(language);
  const end = location.end && location.end !== location.start ? `–${location.end.toLocaleString(language)}` : '';
  return `${t.locationLabels[location.kind]} ${start}${end}`;
}

function SourceCard({ source, language, messageId, active }: { source: SourcePassage; language: Language; messageId: string; active: boolean }) {
  const ref = useRef<HTMLLIElement>(null);
  useEffect(() => {
    if (!active) return;
    const element = ref.current;
    element?.querySelector('details')?.setAttribute('open', '');
    element?.scrollIntoView({ block: 'nearest', behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'instant' : 'smooth' });
  }, [active]);
  const location = sourceLocationLabel(source, language);
  return <li ref={ref} id={`source-${messageId}-${source.n}`} className={'source-card' + (active ? ' is-active' : '')}>
    <details open={active || undefined}>
      <summary>
        <span className="source-number">{source.n.toLocaleString(language)}</span>
        <span className="source-title"><bdi>{source.filename}</bdi>{location && <small>{location}</small>}</span>
        <ChevronDown size={14} className="source-chevron" aria-hidden="true" />
      </summary>
      <blockquote dir="auto">{source.text}</blockquote>
    </details>
  </li>;
}

/** Numbered sources: the passages an answer cites first, the rest folded away. */
export function SourceList({ messageId, sources, language, focus, focusToken }: SourceListProps) {
  const t = translations[language];
  const cited = sources.filter(source => source.cited);
  const primary = cited.length ? cited : sources;
  const others = cited.length ? sources.filter(source => !source.cited) : [];
  const focusInOthers = focus !== undefined && others.some(source => source.n === focus);
  return <section className="source-list" data-tour="sources" aria-label={t.citationsTitle}>
    <header>{cited.length ? <BookOpenCheck size={15} /> : <FileText size={15} />}<span>{cited.length ? t.citationsTitle : t.sourcesConsulted}</span></header>
    <ol>{primary.map(source => <SourceCard key={`${focusToken ?? 0}-${source.n}`} source={source} language={language} messageId={messageId} active={source.n === focus} />)}</ol>
    {others.length > 0 && <details className="source-more" open={focusInOthers || undefined}>
      <summary>{t.moreSources.replace('{count}', others.length.toLocaleString(language))}</summary>
      <ol>{others.map(source => <SourceCard key={`${focusToken ?? 0}-${source.n}`} source={source} language={language} messageId={messageId} active={source.n === focus} />)}</ol>
    </details>}
  </section>;
}
