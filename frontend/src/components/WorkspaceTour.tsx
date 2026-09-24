import { useEffect, useRef, useState } from 'react';
import { ArrowLeft, ArrowRight, Sparkles } from 'lucide-react';
import type { Language } from '../types';

const STEPS = [
  { target: '[data-tour="brand"]', fa: ['گفت‌وگوی تازه', 'با انتخاب نام پارس‌رگ، گفت‌وگوی تازه‌ای شروع کنید. هر گفت‌وگو، پرسش‌ها و اسناد خودش را دارد.'], en: ['A fresh conversation', 'Select the ParsRAG name to start again. Each conversation keeps its own questions and documents.'] },
  { target: '[data-tour="new-chat"]', fallback: '[data-tour="sidebar-toggle"]', fa: ['فضای گفت‌وگوها', 'از نوار کناری گفت‌وگوی تازه بسازید، گفت‌وگوهای قبلی را باز کنید یا نامشان را تغییر دهید و حذف کنید.'], en: ['Conversation space', 'Use the sidebar to start a conversation, revisit earlier ones, or rename and delete them.'] },
  { target: '[data-tour="history-search"]', fallback: '[data-tour="sidebar-toggle"]', fa: ['پیداکردن گفت‌وگو', 'در نوار کناری، عنوان و متن گفت‌وگوها را جست‌وجو کنید. میانبر جست‌وجو در تنظیمات نمایش داده می‌شود.'], en: ['Find a conversation', 'Search conversation titles and messages in the sidebar. Its keyboard shortcut is listed in Settings.'] },
  { target: '[data-tour="documents"]', fa: ['اسناد این گفت‌وگو', 'اینجا فایل تازه بارگذاری کنید یا سند ایندکس‌شدهٔ گفت‌وگوی قبلی را بدون بارگذاری دوباره بیاورید.'], en: ['Conversation documents', 'Upload new files here or reuse an indexed document from an earlier conversation without uploading it again.'] },
  { target: '[data-tour="attach"]', fa: ['مدیریت سندها', 'از گیره هم به اسناد برسید. پیشرفت بارگذاری و پردازش را ببینید؛ سندها را برای پاسخ انتخاب یا از انتخاب خارج کنید و در صورت نیاز حذفشان کنید.'], en: ['Manage documents', 'The paperclip opens documents too. Watch upload and processing progress, choose which files inform answers, and remove files when needed.'] },
  { target: '[data-tour="composer"]', fa: ['پرسش دقیق‌تر', 'پرسش را اینجا بنویسید. با @ یک یا چند سند مشخص را نام ببرید و با / دستورهای آماده و حالت‌های پاسخ را پیدا کنید.'], en: ['Ask precisely', 'Write here. Use @ to mention one or more specific documents and / to discover quick commands and answer modes.'] },
  { target: '[data-tour="mode"]', fa: ['سه شیوهٔ پاسخ', '«فقط اسناد» به شواهد محدود است؛ «ترکیبی» اسناد را با دانش مدل همراه می‌کند؛ «گفت‌وگوی آزاد» اسناد را جست‌وجو نمی‌کند.'], en: ['Three answer modes', 'Documents only stays grounded in sources; Hybrid combines sources and model knowledge; Free chat does not search documents.'] },
  { target: '[data-tour="send"]', fa: ['ارسال و توقف', 'Enter پرسش را می‌فرستد و Shift+Enter خط تازه می‌سازد. هنگام تولید پاسخ، همین دکمه توقف را نشان می‌دهد.'], en: ['Send and stop', 'Enter sends your question; Shift+Enter adds a line. During generation, this button becomes Stop.'] },
  { target: '[data-tour="starters"]', fallback: '[data-tour="composer"]', fa: ['شروع سریع', 'کارت‌های پیشنهادی در گفت‌وگوی خالی به شما کمک می‌کنند خلاصه‌سازی، مقایسه یا یک پرسش آزاد را شروع کنید.'], en: ['Quick starts', 'On an empty conversation, starter cards help you begin a summary, comparison, or open-ended question.'] },
  { target: '[data-tour="prompt-actions"]', fallback: '[data-tour="composer"]', fa: ['ویرایش پرسش', 'پس از ارسال، می‌توانید پرسش خود را کپی یا ویرایش کنید. ویرایش، شاخهٔ تازه‌ای می‌سازد تا میان نسخه‌های پرسش و پاسخ جابه‌جا شوید.'], en: ['Edit your question', 'After sending, copy or edit your prompt. Editing creates a new branch so you can switch between prompt and answer versions.'] },
  { target: '[data-tour="sources"]', fallback: '[data-tour="composer"]', fa: ['منابع پاسخ', 'در پاسخ‌های مبتنی بر سند، نام فایل‌های استفاده‌شده و جایگاه‌هایی مانند صفحه یا بند، در صورت تشخیص، کنار پاسخ دیده می‌شود.'], en: ['Answer sources', 'Document-grounded answers show source filenames and, when available, locations such as pages or paragraphs.'] },
  { target: '[data-tour="response-actions"]', fallback: '[data-tour="composer"]', fa: ['کنترل پاسخ', 'پاسخ را کپی کنید یا دوباره تولیدش کنید. اگر چند نسخه وجود داشته باشد، با دکمه‌های کناری میان آن‌ها حرکت کنید.'], en: ['Control an answer', 'Copy or regenerate an answer. When several versions exist, use the adjacent controls to move between them.'] },
  { target: '[data-tour="connection"]', fallback: '[data-tour="sidebar-toggle"]', fa: ['وضعیت سرویس', 'پایین نوار کناری، آماده‌بودن سرویس و مدل فعال را ببینید. اگر سرویس در دسترس نبود، اتصال را دوباره بررسی کنید.'], en: ['Service status', 'The sidebar shows whether the service is ready and which model is active. Retry the connection if it is unavailable.'] },
  { target: '[data-tour="theme"]', fallback: '[data-tour="sidebar-toggle"]', fa: ['ظاهر دلخواه', 'حالت روشن و تیره را سریع عوض کنید. در تنظیمات، چهار رنگ هماهنگ و زبان فارسی یا انگلیسی نیز در دسترس است.'], en: ['Your preferred look', 'Switch light and dark quickly. Settings also offers four coordinated color palettes and Persian or English.'] },
  { target: '[data-tour="settings"]', fallback: '[data-tour="sidebar-toggle"]', fa: ['تنظیمات پاسخ و مدل', 'در تنظیمات، شیوهٔ پیش‌فرض و عمق جست‌وجو را تغییر دهید؛ مدل Ollama محلی یا API سازگار را با آدرس، نام مدل و در صورت نیاز کلید تنظیم کنید.'], en: ['Answers and model settings', 'Settings controls the default mode and retrieval depth, plus local Ollama or an OpenAI-compatible API with its URL, model name, and optional key.'] },
  { target: '[data-tour="settings"]', fallback: '[data-tour="sidebar-toggle"]', fa: ['حریم خصوصی و راهنما', 'تنظیمات مرز ارسال داده به API را روشن می‌کند، فهرست میانبرهای همین سیستم‌عامل را نشان می‌دهد و اجازه می‌دهد این راهنما را دوباره اجرا کنید.'], en: ['Privacy and help', 'Settings explains what an API receives, lists shortcuts for this operating system, and lets you replay this tour.'] },
  { target: '[data-tour="settings"]', fallback: '[data-tour="sidebar-toggle"]', fa: ['داده‌های شما', 'در تنظیمات می‌توانید همهٔ داده‌های گفت‌وگو و اسناد را با تأیید پاک کنید. اگر مرورگر پشتیبانی کند، نصب برنامه نیز همان‌جا پیشنهاد می‌شود.'], en: ['Your data', 'Settings lets you delete all conversations and indexed documents with confirmation. If supported, you can also install the app there.'] },
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
    const layer = cardRef.current?.parentElement;
    const previousFocus = document.activeElement;
    const siblings = [...(layer?.parentElement?.children ?? [])]
      .filter((element): element is HTMLElement => element instanceof HTMLElement && element !== layer)
      .map(element => ({ element, inert: element.inert }));
    for (const { element } of siblings) element.inert = true;
    return () => {
      for (const { element, inert } of siblings) element.inert = inert;
      if (previousFocus instanceof HTMLElement && previousFocus.isConnected && previousFocus !== document.body) previousFocus.focus();
      else document.querySelector<HTMLElement>('[data-tour="brand"]')?.focus();
    };
  }, [open]);
  useEffect(() => {
    if (!open) return;
    const update = () => {
      const step = STEPS[index];
      const visible = (selector: string) => [...document.querySelectorAll<HTMLElement>(selector)].find(element => {
        const bounds = element.getBoundingClientRect();
        return bounds.width > 0 && bounds.height > 0 && bounds.bottom > 0 && bounds.top < innerHeight
          && bounds.right > 0 && bounds.left < innerWidth && !element.closest('[aria-hidden="true"]');
      });
      const target = visible(step.target) || ('fallback' in step ? visible(step.fallback) : undefined);
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
  const cardHeight = Math.min(cardRef.current?.getBoundingClientRect().height ?? 220, screenHeight - 32);
  const below = (highlight?.top ?? 0) + (highlight?.height ?? 0) + 16;
  const preferredTop = highlight
    ? below + cardHeight + 16 <= screenHeight ? below : highlight.top - cardHeight - 16
    : (screenHeight - cardHeight) / 2;
  const cardTop = Math.max(16, Math.min(preferredTop, screenHeight - cardHeight - 16));
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
      <div className="tour-progress" aria-hidden="true"><i style={{ width: `${((index + 1) / STEPS.length) * 100}%` }} /></div>
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
