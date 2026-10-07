import { useEffect, useRef, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import rehypeKatex from 'rehype-katex';
import remarkGfm from 'remark-gfm';
import remarkMath from 'remark-math';
import { normalizeMathMarkdown } from '../core/markdown';
import { citationNumber, linkCitations } from '../core/citations';

interface ProgressiveMarkdownProps {
  content: string;
  active: boolean;
  externalImageLabel: string;
  onComplete?: () => void;
  /** Text is still arriving from the model: show the caret, no reveal effect. */
  streaming?: boolean;
  /** Number of sources; [n] markers within range become citation chips. */
  sourceCount?: number;
  onCite?: (source: number) => void;
  citeLabel?: (source: number) => string;
  formatNumber?: (source: number) => string;
}

export function ProgressiveMarkdown({ content, active, externalImageLabel, onComplete, streaming = false, sourceCount = 0, onCite, citeLabel, formatNumber }: ProgressiveMarkdownProps) {
  const reduceMotion = typeof window !== 'undefined' && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const [visibleLength, setVisibleLength] = useState(active && !reduceMotion ? 0 : content.length);
  const completeRef = useRef(onComplete);
  completeRef.current = onComplete;

  useEffect(() => {
    if (!active || reduceMotion) {
      setVisibleLength(content.length);
      completeRef.current?.();
      return;
    }
    setVisibleLength(0);
    const targetDuration = Math.min(3600, Math.max(1200, content.length * 7));
    let frame = 0;
    let startedAt: number | undefined;
    let lastUpdate = 0;
    const reveal = (time: number) => {
      startedAt ??= time;
      const elapsed = time - startedAt;
      const cursor = Math.min(content.length, Math.ceil((elapsed / targetDuration) * content.length));
      if (time - lastUpdate < 24 && cursor < content.length) {
        frame = requestAnimationFrame(reveal);
        return;
      }
      lastUpdate = time;
      setVisibleLength(cursor);
      if (cursor < content.length) frame = requestAnimationFrame(reveal);
      else completeRef.current?.();
    };
    frame = requestAnimationFrame(reveal);
    return () => cancelAnimationFrame(frame);
  }, [active, content, reduceMotion]);

  const visibleContent = linkCitations(normalizeMathMarkdown(content.slice(0, visibleLength)), sourceCount);
  const revealing = streaming || (active && visibleLength < content.length);
  return <div className={'progressive-markdown' + (revealing ? ' is-revealing' : '')}>
    <ReactMarkdown remarkPlugins={[remarkGfm, remarkMath]} rehypePlugins={[[rehypeKatex, { throwOnError: false, strict: false }]]} components={{
      a: ({ children, href }) => {
        const source = citationNumber(href);
        if (source !== undefined) {
          return <button type="button" className="cite-chip" onClick={() => onCite?.(source)} aria-label={citeLabel?.(source)}>{formatNumber ? formatNumber(source) : source}</button>;
        }
        return <a href={href} target="_blank" rel="noreferrer noopener">{children}</a>;
      },
      img: ({ alt }) => <span className="external-image-note">[{alt || externalImageLabel}]</span>,
      table: ({ children }) => <div className="table-scroll"><table>{children}</table></div>,
      pre: ({ children }) => <pre tabIndex={0}>{children}</pre>,
    }}>{visibleContent}</ReactMarkdown>
    {revealing ? <span className="response-caret" aria-hidden="true" /> : null}
  </div>;
}
