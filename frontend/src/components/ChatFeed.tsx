import { useEffect, useRef, useState } from 'react';
import { AlertCircle, ArrowDown, Check, ChevronLeft, ChevronRight, Copy, FileText, Pencil, RotateCcw, X } from 'lucide-react';
import type { Message, Language, QueryStage, RAGMode } from '../types';
import { translations } from '../i18n/translations';
import { BrandMark } from './BrandMark';
import { ProgressiveMarkdown } from './ProgressiveMarkdown';

interface ChatFeedProps {
  messages: Message[]; language: Language; isGenerating: boolean; activeMode: RAGMode;
  onRetry: (messageId: string) => void; onEditPrompt: (messageId: string, content: string) => void;
  onSelectVariant: (messageId: string, index: number) => void; isBusy: boolean;
  queryStage?: QueryStage; revealingMessageId?: string; onRevealComplete: () => void;
}

export function ChatFeed({ messages, language, isGenerating, activeMode, onRetry, onEditPrompt, onSelectVariant, isBusy, queryStage, revealingMessageId, onRevealComplete }: ChatFeedProps) {
  const t = translations[language];
  const scrollRef = useRef<HTMLDivElement>(null);
  const nearBottom = useRef(true);
  const previousCount = useRef(0);
  const [showJump, setShowJump] = useState(false);
  const [copied, setCopied] = useState<string | null>(null);
  const [copyError, setCopyError] = useState(false);
  const [editing, setEditing] = useState<{ id: string; value: string } | null>(null);
  const copyTimer = useRef<ReturnType<typeof setTimeout>>();
  useEffect(() => () => clearTimeout(copyTimer.current), []);
  const toBottom = () => {
    const element = scrollRef.current;
    element?.scrollTo({ top: element.scrollHeight, behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'instant' : 'smooth' });
  };
  useEffect(() => {
    const latest = messages[messages.length - 1];
    const ownMessage = messages.length > previousCount.current && latest?.role === 'user';
    if (nearBottom.current || ownMessage) {
      const element = scrollRef.current;
      if (element) element.scrollTop = element.scrollHeight;
    } else setShowJump(true);
    previousCount.current = messages.length;
  }, [messages, isGenerating]);
  const copy = async (message: Message) => {
    try {
      await navigator.clipboard.writeText(message.content);
      setCopied(message.id); setCopyError(false); clearTimeout(copyTimer.current);
      copyTimer.current = setTimeout(() => setCopied(null), 2000);
    } catch { setCopyError(true); }
  };
  return <div className="feed-container">
    <div className="chat-feed" ref={scrollRef} onScroll={() => {
      const el = scrollRef.current;
      nearBottom.current = Boolean(el && el.scrollHeight - el.scrollTop - el.clientHeight < 120);
      setShowJump(!nearBottom.current);
    }}>
      <div className="message-list" role="log" aria-label={t.conversations} aria-live="polite" aria-relevant="additions">
        {messages.map(message => message.role === 'system'
          ? <p key={message.id} className="system-message">{message.content}</p>
          : <article key={message.id} className={'message message-' + message.role + (message.error ? ' message-error' : '')} aria-label={message.role === 'user' ? t.you : t.appName}>
            {message.role === 'user' ? <>
              {editing?.id === message.id ? <form className="prompt-edit" onSubmit={event => { event.preventDefault(); const value = editing.value.trim(); if (value && value !== message.content) onEditPrompt(message.id, value); setEditing(null); }}>
                <textarea autoFocus value={editing.value} onChange={event => setEditing({ id: message.id, value: event.target.value })} aria-label={t.editPrompt} />
                <div><button type="button" onClick={() => setEditing(null)}><X size={14} />{t.cancel}</button><button className="save-prompt" disabled={!editing.value.trim() || editing.value.trim() === message.content || isBusy}><Check size={14} />{t.saveAndSubmit}</button></div>
              </form> : <div className="user-bubble" dir="auto">{message.content}</div>}
              <div className="message-actions user-actions">
                <button onClick={() => void copy(message)} title={t.copyPrompt}><span>{copied === message.id ? <Check size={15} /> : <Copy size={15} />}</span>{copied === message.id ? t.copied : t.copyPrompt}</button>
                <button onClick={() => setEditing({ id: message.id, value: message.content })} disabled={isBusy || Boolean(editing)} title={t.editPrompt}><Pencil size={15} />{t.editPrompt}</button>
              </div>
            </> : <>
              <div className="assistant-heading"><span className="assistant-avatar"><BrandMark /></span><strong>{t.appName}</strong><span className="message-time">{new Date(message.timestamp).toLocaleTimeString(language, { hour: '2-digit', minute: '2-digit' })}</span></div>
              {message.error ? <div className="message-error-body" dir="auto"><AlertCircle size={18} /><p>{message.content}</p></div> :
                <div className="prose-content" dir="auto">
                  <ProgressiveMarkdown content={message.content} active={revealingMessageId === message.id}
                    externalImageLabel={t.externalImage} onComplete={onRevealComplete} />
                </div>}
              {Boolean(message.citations?.length) && <section className="citation-summary" aria-label={t.citationsTitle}>
                <header><FileText size={15} /><span>{t.citationsTitle}</span></header>
                <ul>{message.citations!.map(citation => <li key={citation.filename}><bdi>{citation.filename}</bdi>{citation.locations.length > 0 && <span className="source-locations">{citation.locations.map((location, locationIndex) => <span key={`${location.kind}-${location.start}-${location.end ?? ''}`}>{t.locationLabels[location.kind]} {location.start.toLocaleString(language)}{location.end && location.end !== location.start ? `–${location.end.toLocaleString(language)}` : ''}{locationIndex < citation.locations.length - 1 ? '، ' : ''}</span>)}</span>}</li>)}</ul>
              </section>}
              <div className="message-actions">
                {!message.error && <button onClick={() => void copy(message)} title={t.copy}><span>{copied === message.id ? <Check size={15} /> : <Copy size={15} />}</span>{copied === message.id ? t.copied : t.copy}</button>}
                <button onClick={() => onRetry(message.id)} disabled={isBusy}><RotateCcw size={15} />{t.retry}</button>
                {message.variants && message.variants.length > 1 && <span className="variant-navigation" aria-label={t.responseVersions}>
                  <button aria-label={t.previousResponse} disabled={isBusy || (message.activeVariant ?? 0) <= 0} onClick={() => onSelectVariant(message.id, (message.activeVariant ?? 0) - 1)}><ChevronRight size={15} /></button>
                  <output>{((message.activeVariant ?? 0) + 1).toLocaleString(language)} / {message.variants.length.toLocaleString(language)}</output>
                  <button aria-label={t.nextResponse} disabled={isBusy || (message.activeVariant ?? 0) >= message.variants.length - 1} onClick={() => onSelectVariant(message.id, (message.activeVariant ?? 0) + 1)}><ChevronLeft size={15} /></button>
                </span>}
              </div>
            </>}
          </article>)}
        {isGenerating && <QueryProgress language={language} mode={activeMode} stage={queryStage ?? 'understanding'} />}
      </div>
      {copyError && <p role="status" className="copy-error">{t.copyFailed}</p>}
    </div>
    {showJump && <button className="jump-button" onClick={toBottom} aria-label={t.jumpToLatest} title={t.jumpToLatest}><ArrowDown size={18} /></button>}
  </div>;
}

function QueryProgress({ language, mode, stage }: { language: Language; mode: RAGMode; stage: QueryStage }) {
  const t = translations[language];
  const stages: QueryStage[] = mode === 'llm-only' ? ['understanding', 'generating'] : ['understanding', 'retrieving', 'generating'];
  const currentIndex = Math.max(0, stages.indexOf(stage));
  return <section className="query-progress" role="status" aria-live="polite">
    <header><span className="assistant-avatar"><BrandMark /></span><div><strong>{t.queryStages[stages[currentIndex]]}</strong><span>{t.queryProgressHint}</span></div><span className="thinking-dots" aria-hidden="true"><i /><i /><i /></span></header>
    <ol>{stages.map((item, index) => <li key={item} data-state={index < currentIndex ? 'complete' : index === currentIndex ? 'active' : 'pending'}>
      <span>{index < currentIndex ? <Check size={12} /> : index + 1}</span><b>{t.queryStages[item]}</b>
    </li>)}</ol>
  </section>;
}

