import { ArrowUpLeft, BookOpenText, Layers2, Lightbulb, LockKeyhole } from 'lucide-react';
import type { ReactNode } from 'react';
import type { Language } from '../types';
import { translations } from '../i18n/translations';
import { BrandMark } from './BrandMark';

export function Welcome({ language, composer, onSelectStarter }: { language: Language; composer: ReactNode; onSelectStarter: (text: string, index: number) => void }) {
  const t = translations[language];
  const icons = [BookOpenText, Layers2, Lightbulb];
  return <div className="welcome-scroll">
    <section className="welcome">
      <div className="welcome-intro">
        <div className="welcome-emblem"><span className="emblem-orbit" /><BrandMark /><span className="emblem-dot" /></div>
        <p className="greeting">{t.greeting}</p>
        <h1>{t.heroGreeting}</h1>
        <p className="welcome-description">{t.heroDescription}</p>
      </div>
      {composer}
      <section className="starters" aria-label={t.starterLabel}>
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

