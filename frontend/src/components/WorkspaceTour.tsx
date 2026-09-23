import { useEffect, useRef, useState } from 'react';
import { ArrowLeft, ArrowRight, Sparkles } from 'lucide-react';
import type { Language } from '../types';

const STEPS = [
  { target: '[data-tour="brand"]', fa: ['گفت‌وگوی تازه', 'با انتخاب نام برنامه، هر زمان می‌توانید گفت‌وگوی تازه‌ای شروع کنید.'], en: ['A fresh conversation', 'Select the app name whenever you want a new conversation.'] },
  { target: '[data-tour="documents"]', fa: ['اسناد گفت‌وگو', 'فایل‌ها را بارگذاری کنید یا سندی از گفت‌وگوهای قبلی بیاورید.'], en: ['Your documents', 'Upload files or bring in a document from an earlier conversation.'] },
  { target: '[data-tour="composer"]', fa: ['پرسش شما', 'با @ سند خاصی را نام ببرید؛ با / دستورهای آماده را ببینید.'], en: ['Your question', 'Use @ to mention a document and / to explore quick commands.'] },
  { target: '[data-tour="mode"]', fa: ['شیوهٔ پاسخ', 'بین پاسخ فقط بر اساس اسناد، حالت ترکیبی و گفت‌وگوی آزاد جابه‌جا شوید.'], en: ['Answer mode', 'Switch between documents only, hybrid answers, and open conversation.'] },
] as const;

interface TourProps { open: boolean; language: Language; onClose: () => void }
type Highlight = { top: number; left: number; width: number; height: number };

export function WorkspaceTour({ open, language, onClose }: TourProps) {
  const [index, setIndex] = useState(0);
  const [highlight, setHighlight] = useState<Highlight | null>(null);
  const cardRef = useRef<HTMLDivElement>(null);
  useEffect(() => { if (open) setIndex(0); }, [open]);
  useEffect(() => {
    if (!open) return;
    const update = () => {
      const target = document.querySelector<HTMLElement>(STEPS[index].target);
      if (!target) { setHighlight(null); return; }
      const bounds = target.getBoundingClientRect();
      setHighlight({ top: Math.max(8, bounds.top - 6), left: Math.max(8, bounds.left - 6),
        width: bounds.width + 12, height: bounds.height + 12 });
    };
    const frame = requestAnimationFrame(update);
    window.addEventListener('resize', update);
    window.addEventListener('scroll', update, true);
    return () => { cancelAnimationFrame(frame); window.removeEventListener('resize', update); window.removeEventListener('scroll', update, true); };
  }, [index, open]);
  useEffect(() => { if (open) cardRef.current?.querySelector<HTMLButtonElement>('.tour-next')?.focus(); }, [open, index]);
  if (!open) return null;
  const [title, description] = STEPS[index][language];
  const screenWidth = window.innerWidth;
  const screenHeight = window.innerHeight;
  const cardWidth = Math.min(340, screenWidth - 32);
  const cardLeft = Math.max(16, Math.min((highlight?.left ?? 16), screenWidth - cardWidth - 16));
  const cardTop = highlight ? (highlight.top + highlight.height + 186 < screenHeight
    ? highlight.top + highlight.height + 16 : Math.max(16, highlight.top - 196)) : Math.max(16, (screenHeight - 190) / 2);
  return <div className="tour-layer" role="dialog" aria-modal="true" aria-label={language === 'fa' ? 'راهنمای پارس‌رگ' : 'ParsRAG tour'}
    onKeyDown={event => {
      if (event.key === 'Escape') { event.preventDefault(); onClose(); }
      if (event.key === 'Tab') {
        const buttons = [...(cardRef.current?.querySelectorAll<HTMLButtonElement>('button') ?? [])];
        if (!buttons.length) return;
        const position = buttons.indexOf(document.activeElement as HTMLButtonElement);
        if (event.shiftKey && position === 0) { event.preventDefault(); buttons[buttons.length - 1].focus(); }
        else if (!event.shiftKey && position === buttons.length - 1) { event.preventDefault(); buttons[0].focus(); }
      }
    }}>
    {highlight ? <>
      <div className="tour-shade" style={{ top: 0, left: 0, right: 0, height: highlight.top }} />
      <div className="tour-shade" style={{ top: highlight.top, left: 0, width: highlight.left, height: highlight.height }} />
      <div className="tour-shade" style={{ top: highlight.top, left: highlight.left + highlight.width, right: 0, height: highlight.height }} />
      <div className="tour-shade" style={{ top: highlight.top + highlight.height, left: 0, right: 0, bottom: 0 }} />
      <div className="tour-highlight" style={highlight} />
    </> : <div className="tour-shade" style={{ inset: 0 }} />}
    <div ref={cardRef} className="tour-card" style={{ top: cardTop, left: cardLeft, width: cardWidth }} dir={language === 'fa' ? 'rtl' : 'ltr'}>
      <div className="tour-card-heading"><Sparkles size={18} /><span>{String(index + 1).padStart(2, '0')} / {String(STEPS.length).padStart(2, '0')}</span></div>
      <h2>{title}</h2><p>{description}</p>
      <div className="tour-actions">
        <button onClick={onClose}>{language === 'fa' ? 'رد کردن' : 'Skip'}</button>
        <span />
        {index > 0 && <button onClick={() => setIndex(current => current - 1)}>{language === 'fa' ? <ArrowRight size={15} /> : <ArrowLeft size={15} />}{language === 'fa' ? 'قبلی' : 'Back'}</button>}
        <button className="button primary tour-next" onClick={() => index + 1 === STEPS.length ? onClose() : setIndex(current => current + 1)}>
          {index + 1 === STEPS.length ? language === 'fa' ? 'شروع کنیم' : 'Get started' : language === 'fa' ? 'بعدی' : 'Next'}
        </button>
      </div>
    </div>
  </div>;
}
