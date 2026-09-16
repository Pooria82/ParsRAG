import { useEffect, useRef, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { AlertCircle, ArrowDown, Check, ChevronDown, Copy, FileText, RotateCcw } from 'lucide-react';
import type { Message, Language, RAGMode } from '../types';
import { translations } from '../i18n/translations';
import { BrandMark } from './BrandMark';

interface ChatFeedProps {
  messages: Message[]; language: Language; isGenerating: boolean; activeMode: RAGMode;
  onRetry: (messageId: string) => void; isBusy: boolean;
}

export function ChatFeed({ messages, language, isGenerating, activeMode, onRetry, isBusy }: ChatFeedProps) {
  const t = translations[language];
  const scrollRef = useRef<HTMLDivElement>(null);
  const nearBottom = useRef(true);
  const previousCount = useRef(0);
  const [showJump, setShowJump] = useState(false);
  const [copied, setCopied] = useState<string | null>(null);
  const [copyError, setCopyError] = useState(false);
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
        {messages.map((message, index) => message.role === 'system'
          ? <p key={message.id} className="system-message">{message.content}</p>
          : <article key={message.id} className={'message message-' + message.role + (message.error ? ' message-error' : '')} aria-label={message.role === 'user' ? t.you : t.appName}>
            {message.role === 'user' ? <div className="user-bubble" dir="auto">{message.content}</div> : <>
              <div className="assistant-heading"><span className="assistant-avatar"><BrandMark /></span><strong>{t.appName}</strong><span className="message-time">{new Date(message.timestamp).toLocaleTimeString(language, { hour: '2-digit', minute: '2-digit' })}</span></div>
              {message.error ? <div className="message-error-body"><AlertCircle size={18} /><p>{message.content}</p></div> :
                <div className="prose-content">
                  <ReactMarkdown remarkPlugins={[remarkGfm]} components={{
                    a: ({ children, href }) => <a href={href} target="_blank" rel="noreferrer noopener">{children}</a>,
                    img: ({ alt }) => <span className="external-image-note">[{alt || t.externalImage}]</span>,
                    table: ({ children }) => <div className="table-scroll"><table>{children}</table></div>,
                    pre: ({ children }) => <pre tabIndex={0}>{children}</pre>,
                  }}>{message.content}</ReactMarkdown>
                </div>}
              {Boolean(message.citations?.length) && <details className="citation-group">
                <summary><FileText size={16} /><span>{t.citationsTitle}</span><span className="citation-count">{message.citations!.length.toLocaleString(language)}</span><ChevronDown size={15} /></summary>
                <div className="citation-list">{message.citations!.map((citation, citationIndex) => <details className="citation" key={citationIndex}>
                  <summary><span className="source-number">{(citationIndex + 1).toLocaleString(language)}</span><bdi>{citation.filename}</bdi><ChevronDown size={14} /></summary>
                  <div className="citation-body">{citation.score > 0 && <span className="relevance">{t.similarityScore}: {citation.score.toLocaleString(language, { maximumFractionDigits: 3 })}</span>}<p dir="auto">{citation.body}</p></div>
                </details>)}</div>
              </details>}
              <div className="message-actions">
                {!message.error && <button onClick={() => void copy(message)} title={t.copy}><span>{copied === message.id ? <Check size={15} /> : <Copy size={15} />}</span>{copied === message.id ? t.copied : t.copy}</button>}
                {message.error && index === messages.length - 1 && <button onClick={() => onRetry(message.id)} disabled={isBusy}><RotateCcw size={15} />{t.retry}</button>}
              </div>
            </>}
          </article>)}
        {isGenerating && <div className="thinking-row" role="status"><span className="assistant-avatar"><BrandMark /></span><span>{activeMode === 'llm-only' ? t.thinking : t.searchingDocs}</span><span className="thinking-dots" aria-hidden="true"><i /><i /><i /></span></div>}
      </div>
      {copyError && <p role="status" className="copy-error">{t.copyFailed}</p>}
    </div>
    {showJump && <button className="jump-button" onClick={toBottom} aria-label={t.jumpToLatest} title={t.jumpToLatest}><ArrowDown size={18} /></button>}
  </div>;
}

