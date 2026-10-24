import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import type { Language } from '../types';

/** Release notes as Markdown: no raw HTML, links open outside the app. */
export function ReleaseNotesText({ text, language }: { text: string; language: Language }) {
  return <div className="release-notes prose-content" dir={language === 'fa' ? 'rtl' : 'ltr'}>
    <ReactMarkdown remarkPlugins={[remarkGfm]} components={{
      a: ({ href, children }) => <a href={href} target="_blank" rel="noopener noreferrer">{children}</a>,
      img: () => null,
    }}>{text}</ReactMarkdown>
  </div>;
}
