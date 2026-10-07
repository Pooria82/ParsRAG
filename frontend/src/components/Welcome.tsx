import { ArrowUpLeft, BookOpenText, Layers2, Lightbulb, LockKeyhole, Sparkles } from 'lucide-react';
import type { ReactNode } from 'react';
import type { Language } from '../types';
import { translations } from '../i18n/translations';
import { BrandMark } from './BrandMark';

interface WelcomeProps {
  language: Language; composer: ReactNode; onSelectStarter: (text: string, index: number) => void;
  /** Questions written from the conversation's own documents. */
  documentQuestions?: string[]; documentQuestionsLoading?: boolean;
  onSelectQuestion?: (question: string) => void;
}

export function Welcome({ language, composer, onSelectStarter, documentQuestions, documentQuestionsLoading = false, onSelectQuestion }: WelcomeProps) {
  const t = translations[language];
  const icons = [BookOpenText, Layers2, Lightbulb];
  const showQuestions = documentQuestionsLoading || Boolean(documentQuestions?.length);
  return <div className="welcome-scroll">
    <section className="welcome">
      <div className="welcome-intro">
        <div className="welcome-emblem"><span className="emblem-orbit" /><BrandMark /><span className="emblem-dot" /></div>
        <p className="greeting">{t.greeting}</p>
        <h1>{t.heroGreeting}</h1>
        <p className="welcome-description">{t.heroDescription}</p>
      </div>
      {composer}
      {showQuestions && <section className="document-questions" aria-label={t.documentQuestionsLabel} aria-busy={documentQuestionsLoading || undefined}>
        <p className="starters-label"><Sparkles size={13} aria-hidden="true" />{t.documentQuestionsLabel}</p>
        <div className="document-question-list">
          {documentQuestionsLoading && !documentQuestions?.length
            ? [0, 1, 2].map(index => <span className="document-question is-loading" key={index} aria-hidden="true" />)
            : documentQuestions?.map(question => <button type="button" className="document-question" key={question} dir="auto" onClick={() => onSelectQuestion?.(question)}>
              <span>{question}</span><ArrowUpLeft size={14} className="starter-arrow" />
            </button>)}
        </div>
      </section>}
      <section className="starters" data-tour="starters" aria-label={t.starterLabel}>
        <p className="starters-label">{t.starterLabel}</p>
        <div className="starter-grid">
          {t.starterPrompts.map((starter, index) => {
            const Icon = icons[index];
            return <button className="starter-card" key={starter.title} onClick={() => onSelectStarter(starter.prompt, index)}>
              <div className="starter-top"><span className={'starter-icon tone-' + index}><Icon size={19} /></span><ArrowUpLeft size={15} className="starter-arrow" /></div>
              <strong>{starter.title}</strong><span>{starter.desc}</span>
            </button>;
          })}
        </div>
      </section>
      <p className="welcome-signature"><LockKeyhole size={12} />{t.localStorage}</p>
    </section>
  </div>;
}

