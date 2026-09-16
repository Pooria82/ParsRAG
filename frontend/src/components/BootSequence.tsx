import { useEffect, useState } from 'react';
import type { Language } from '../types';
import { BrandMark } from './BrandMark';

export function BootSequence({ language }: { language: Language }) {
  const [visible, setVisible] = useState(true);

  useEffect(() => {
    const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    const timeout = window.setTimeout(() => setVisible(false), reducedMotion ? 80 : 1380);
    return () => window.clearTimeout(timeout);
  }, []);

  if (!visible) return null;

  return <div className="boot-sequence" role="status" aria-live="polite" aria-label={language === 'fa' ? 'در حال آماده‌سازی پارس‌رگ' : 'Preparing ParsRAG'}>
    <div className="boot-lockup">
      <span className="boot-mark"><BrandMark /></span>
      <span className="boot-wordmark">{language === 'fa' ? 'پارس‌رگ' : 'ParsRAG'}</span>
      <span className="boot-trace" aria-hidden="true"><i /><i /><i /></span>
    </div>
  </div>;
}
