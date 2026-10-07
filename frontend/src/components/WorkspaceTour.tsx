import { useEffect, useRef, useState } from 'react';
import { ArrowLeft, ArrowRight, Sparkles } from 'lucide-react';
import type { Language, ModelProvider } from '../types';

export interface TourStage {
  surface?: 'documents' | 'settings';
  menu?: 'mode' | 'document' | 'command';
  settingsTab?: 'general' | 'rag' | 'connection';
  provider?: ModelProvider;
}

type TourStep = TourStage & {
  target: string;
  fallback?: string;
  fa: [string, string];
  en: [string, string];
};

const STEPS: TourStep[] = [
  { target: '[data-tour="brand"]', fa: ['گفت‌وگوی تازه', 'با انتخاب نام پارس‌رگ، گفت‌وگوی تازه‌ای شروع می‌شود. هر گفت‌وگو پرسش‌ها و اسناد خودش را دارد.'], en: ['A fresh conversation', 'Select ParsRAG to start a new conversation. Each conversation has its own questions and documents.'] },
  { target: '[data-tour="new-chat"]', fallback: '[data-tour="sidebar-toggle"]', fa: ['فضای گفت‌وگوها', 'در نوار کناری گفت‌وگوی تازه بسازید، گفت‌وگوهای قبلی را باز کنید یا نامشان را تغییر دهید و حذف کنید.'], en: ['Conversation space', 'Use the sidebar to start a conversation, revisit earlier ones, or rename and delete them.'] },
  { target: '[data-tour="history-search"]', fallback: '[data-tour="sidebar-toggle"]', fa: ['پیداکردن گفت‌وگو', 'عنوان و متن گفت‌وگوها را اینجا جست‌وجو کنید. میانبر جست‌وجو در تنظیمات آمده است.'], en: ['Find a conversation', 'Search conversation titles and messages here. Its keyboard shortcut is listed in Settings.'] },
  { target: '[data-tour="documents"]', fa: ['اسناد این گفت‌وگو', 'بخش اسناد را برایتان باز می‌کنیم تا بارگذاری، استفادهٔ دوباره و انتخاب سندها را در جای واقعی‌شان ببینید.'], en: ['Conversation documents', 'We will open the document panel so you can see upload, reuse, and selection where they actually happen.'] },
  { surface: 'documents', target: '[data-tour="document-upload"]', fa: ['بارگذاری سند', 'فایل‌ها را اینجا انتخاب یا رها کنید. محدودیت تعداد و اندازه زیر دکمه نوشته شده و پیشرفت بارگذاری و پردازش برای هر فایل نمایش داده می‌شود.'], en: ['Upload a document', 'Select or drop files here. The file count and size limits appear below, and each file shows upload and processing progress.'] },
  { surface: 'documents', target: '[data-tour="document-reuse"]', fallback: '[data-tour="document-upload"]', fa: ['استفادهٔ دوباره از سند', 'فایل‌های نمایه‌شدهٔ گفت‌وگوهای قبلی در این فهرست قرار می‌گیرند و بدون بارگذاری دوباره به گفت‌وگوی تازه اضافه می‌شوند.'], en: ['Reuse a document', 'Indexed files from earlier conversations appear here and can be added to a new conversation without uploading again.'] },
  { surface: 'documents', target: '[data-tour="document-selection"]', fallback: '[data-tour="document-upload"]', fa: ['انتخاب و حذف سند', 'پس از بارگذاری، سندها اینجا ظاهر می‌شوند. تیک هر سند تعیین می‌کند در پاسخ به کار رود یا نه؛ حذف سند نیز از همین فهرست انجام می‌شود.'], en: ['Select or remove documents', 'Uploaded files appear here. Each checkbox controls whether a file informs answers; you can also delete it from this list.'] },
  { target: '[data-tour="composer"]', fa: ['نوشتن پرسش', 'پرسش را اینجا بنویسید. در چند مرحلهٔ بعد، فهرست‌های @ و / را بدون تغییر متن پرسش باز می‌کنیم.'], en: ['Write your question', 'Write here. Next, we will open the @ and / menus without changing your draft.'] },
  { menu: 'document', target: '[data-tour="mention-menu"]', fallback: '[data-tour="composer"]', fa: ['اشاره به سند با @', 'وقتی @ را در پرسش بنویسید، نام سندهای همین گفت‌وگو پیشنهاد می‌شود. می‌توانید چند سند را در بخش‌های مختلف یک پرسش نام ببرید.'], en: ['Mention a document with @', 'Typing @ suggests documents in this conversation. You can mention different documents in different parts of one question.'] },
  { menu: 'command', target: '[data-tour="command-menu"]', fallback: '[data-tour="composer"]', fa: ['دستورهای آماده با /', 'با / دستورهایی مثل خلاصه‌سازی، مقایسه، ترجمه، تغییر حالت پاسخ، مدیریت اسناد و نمایش همین راهنما ظاهر می‌شوند.'], en: ['Quick commands with /', 'Typing / offers commands for summaries, comparisons, translation, answer modes, documents, and this tour.'] },
  { menu: 'mode', target: '[data-tour="mode-menu"]', fallback: '[data-tour="mode"]', fa: ['سه شیوهٔ پاسخ', '«فقط اسناد» به شواهد فایل‌ها محدود است؛ «ترکیبی» اسناد را با دانش مدل همراه می‌کند؛ «گفت‌وگوی آزاد» اسناد را جست‌وجو نمی‌کند.'], en: ['Three answer modes', 'Documents only stays grounded in sources; Hybrid combines sources with model knowledge; Free chat does not search documents.'] },
  { target: '[data-tour="send"]', fa: ['ارسال و توقف', 'Enter پرسش را می‌فرستد و Shift+Enter خط تازه می‌سازد. هنگام تولید پاسخ، همین دکمه برای توقف به کار می‌رود.'], en: ['Send and stop', 'Enter sends your question; Shift+Enter adds a line. During generation, this button stops the response.'] },
  { target: '[data-tour="starters"]', fallback: '[data-tour="composer"]', fa: ['شروع سریع', 'کارت‌های پیشنهادی در گفت‌وگوی خالی به شروع خلاصه‌سازی، مقایسه یا پرسش آزاد کمک می‌کنند.'], en: ['Quick starts', 'On an empty conversation, starter cards help you begin a summary, comparison, or open question.'] },
  { target: '[data-tour="prompt-actions"]', fallback: '[data-tour="composer"]', fa: ['ویرایش پرسش', 'پس از ارسال، پرسش را کپی یا ویرایش کنید. ویرایش، شاخهٔ تازه‌ای می‌سازد و می‌توانید میان نسخه‌های پرسش و پاسخ جابه‌جا شوید.'], en: ['Edit your question', 'After sending, copy or edit a prompt. Editing creates a new branch so you can switch between prompt and answer versions.'] },
  { target: '[data-tour="sources"]', fallback: '[data-tour="composer"]', fa: ['منابع پاسخ', 'در پاسخ‌های مبتنی بر سند، نام فایل‌های استفاده‌شده و جایگاه‌هایی مانند صفحه یا بند، در صورت تشخیص، کنار پاسخ دیده می‌شود.'], en: ['Answer sources', 'Document-grounded answers show source filenames and, when available, locations such as pages or paragraphs.'] },
  { target: '[data-tour="response-actions"]', fallback: '[data-tour="composer"]', fa: ['کنترل پاسخ', 'پاسخ را کپی یا دوباره تولید کنید. اگر چند نسخه وجود داشته باشد، میان آن‌ها جابه‌جا شوید.'], en: ['Control an answer', 'Copy or regenerate an answer. If several versions exist, move between them.'] },
  { target: '[data-tour="connection"]', fallback: '[data-tour="sidebar-toggle"]', fa: ['وضعیت سرویس', 'پایین نوار کناری، آماده‌بودن سرویس و مدل فعال را ببینید.'], en: ['Service status', 'The sidebar shows whether the service is ready and which model is active.'] },
  { target: '[data-tour="theme"]', fallback: '[data-tour="sidebar-toggle"]', fa: ['تغییر سریع ظاهر', 'با این دکمه حالت روشن و تیره را تغییر دهید. گزینه‌های بیشتر را در تنظیمات می‌بینید.'], en: ['Quick appearance switch', 'Switch light and dark here. More appearance options are in Settings.'] },
  { target: '[data-tour="settings"]', fallback: '[data-tour="sidebar-toggle"]', fa: ['تنظیمات برنامه', 'اکنون تنظیمات را باز می‌کنیم و بخش‌های ظاهر، بازیابی اسناد، مدل و داده‌ها را روی خود پنجره نشان می‌دهیم.'], en: ['App settings', 'We will open Settings and walk through appearance, document retrieval, model connection, and data controls in the panel.'] },
  { surface: 'settings', settingsTab: 'general', target: '[data-tour="settings-theme"]', fa: ['روشن یا تیره', 'نمای روشن یا تیره را اینجا انتخاب کنید. تور هیچ‌کدام را تغییر نمی‌دهد.'], en: ['Light or dark', 'Choose a light or dark appearance here. The tour does not change your choice.'] },
  { surface: 'settings', settingsTab: 'general', target: '[data-tour="settings-palette"]', fa: ['رنگ‌بندی', 'چند رنگ‌بندی هماهنگ در این بخش قرار دارد؛ رنگ پیش‌فرض پارس‌رگ نیز حفظ می‌شود.'], en: ['Color palette', 'Choose among coordinated palettes; the original ParsRAG palette remains available.'] },
  { surface: 'settings', settingsTab: 'general', target: '[data-tour="settings-language"]', fa: ['زبان رابط', 'زبان فارسی یا انگلیسی را از اینجا انتخاب کنید. جهت هر پاسخ بر اساس زبان خود پاسخ تعیین می‌شود.'], en: ['Interface language', 'Choose Persian or English here. Each answer follows the direction of its own language.'] },
  { surface: 'settings', settingsTab: 'general', target: '[data-tour="settings-shortcuts"]', fa: ['میانبرهای صفحه‌کلید', 'میانبرهای مخصوص سیستم‌عامل شما اینجا نمایش داده می‌شوند؛ در مک کلید Command و در ویندوز و لینوکس Control به کار می‌رود.'], en: ['Keyboard shortcuts', 'This list uses your operating system’s keys: Command on Mac, Control on Windows and Linux.'] },
  { surface: 'settings', settingsTab: 'general', target: '[data-tour="settings-guide"]', fa: ['نمایش دوبارهٔ راهنما', 'هر زمان خواستید، این تور را از این دکمه دوباره آغاز کنید؛ ردکردن تور مانع اجرای دوباره نمی‌شود.'], en: ['Replay this tour', 'Start the tour again from here at any time, even if you skipped it earlier.'] },
  { surface: 'settings', settingsTab: 'general', target: '[data-tour="settings-pwa"]', fa: ['نصب برنامه (PWA)', 'اگر مرورگر و سیستم‌عامل شما پشتیبانی کنند، دکمهٔ نصب اینجا ظاهر می‌شود. نسخهٔ نصب‌شده همان محیط پارس‌رگ را باز می‌کند و سرویس محلی باید در دسترس باشد.'], en: ['Install the app (PWA)', 'When your browser and operating system support it, an Install button appears here. The installed app opens the same ParsRAG workspace and still needs the local service.'] },
  { surface: 'settings', settingsTab: 'rag', target: '[data-tour="settings-default-mode"]', fa: ['حالت پیش‌فرض پاسخ', 'در زبانهٔ بازیابی، شیوهٔ پاسخ پیش‌فرض گفت‌وگوهای تازه را از میان سه حالت انتخاب کنید.'], en: ['Default answer mode', 'In the retrieval tab, choose the default answer mode for new conversations.'] },
  { surface: 'settings', settingsTab: 'rag', target: '[data-tour="settings-depth"]', fa: ['عمق جست‌وجو', 'عمق پویا تعداد قطعه‌های بازیابی‌شده را بر اساس پرسش تعیین می‌کند. با خاموش‌کردنش، کنترل دستی تعداد قطعه‌ها نمایان می‌شود.'], en: ['Retrieval depth', 'Dynamic depth adjusts retrieved chunks to the question. Turning it off reveals a manual chunk-count control.'] },
  { surface: 'settings', settingsTab: 'connection', provider: 'ollama', target: '[data-tour="settings-provider"]', fa: ['روش اجرای مدل', 'مدل محلی Ollama یا API سازگار را اینجا انتخاب کنید. تور فقط هر دو حالت را نمایش می‌دهد و روش فعلی را ذخیره نمی‌کند.'], en: ['Model provider', 'Choose local Ollama or a compatible API here. The tour only previews both choices; it does not save a provider.'] },
  { surface: 'settings', settingsTab: 'connection', provider: 'ollama', target: '[data-tour="settings-model-actions"]', fa: ['اتصال به Ollama', 'آدرس سرویس و نام مدل را در همین فرم وارد کنید؛ دکمهٔ یافتن مدل‌ها، مدل‌های نصب‌شدهٔ Ollama را می‌خواند و «اعمال» تنظیم را ذخیره می‌کند.'], en: ['Connect to Ollama', 'Enter the service address and model name here. Find models reads installed Ollama models, and Apply saves the configuration.'] },
  { surface: 'settings', settingsTab: 'connection', provider: 'api', target: '[data-tour="settings-api-key"]', fa: ['کلید API', 'برای API سازگار، آدرس و نام مدل را وارد کنید. این بخش نشان می‌دهد کلید در حافظهٔ سرویس موجود است یا باید وارد شود؛ کلید در مرورگر ذخیره نمی‌شود.'], en: ['API key', 'For a compatible API, enter its URL and model name. This section shows whether a key is already held by the service; it is not stored in the browser.'] },
  { surface: 'settings', settingsTab: 'connection', provider: 'api', target: '[data-tour="settings-api-disclosure"]', fa: ['مرز حریم خصوصی API', 'پیش از استفاده از API بیرونی باید آگاهانه تأیید کنید که پرسش و بخش‌های بازیابی‌شدهٔ سند به همان API ارسال می‌شوند.'], en: ['API privacy boundary', 'Before using an external API, you must acknowledge that your prompt and retrieved document excerpts are sent to that API.'] },
  { surface: 'settings', settingsTab: 'connection', provider: 'api', target: '[data-tour="settings-backend"]', fa: ['نشانی سرویس برنامه', 'نشانی بک‌اند محلی را از این بخش تنظیم کنید. این نشانی با آدرس API مدل فرق دارد.'], en: ['App service address', 'Configure the local backend address here. It is separate from the model API address.'] },
  { surface: 'settings', settingsTab: 'connection', provider: 'api', target: '[data-tour="settings-data"]', fa: ['پاک‌کردن داده‌ها', 'پاک‌کردن همهٔ گفت‌وگوها و اسناد از این بخش انجام می‌شود و به تأیید جداگانه نیاز دارد. تور هیچ داده‌ای را پاک نمی‌کند.'], en: ['Clear your data', 'Delete all conversations and documents here with a separate confirmation. The tour never deletes data.'] },
];

interface TourProps { open: boolean; language: Language; onClose: () => void; onStageChange: (stage: TourStage) => void; activeStage: TourStage }
type Highlight = { top: number; left: number; width: number; height: number };

export function WorkspaceTour({ open, language, onClose, onStageChange, activeStage }: TourProps) {
  const [index, setIndex] = useState(0);
  const [highlight, setHighlight] = useState<Highlight | null>(null);
  const cardRef = useRef<HTMLDivElement>(null);
  useEffect(() => { if (open) setIndex(0); }, [open]);
  useEffect(() => {
    if (!open) return;
    const { surface, menu, settingsTab, provider } = STEPS[index];
    onStageChange({ surface, menu, settingsTab, provider });
  }, [index, open, onStageChange]);
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
      const find = (selector: string) => [...document.querySelectorAll<HTMLElement>(selector)].find(element => {
        const bounds = element.getBoundingClientRect();
        return bounds.width > 0 && bounds.height > 0 && !element.closest('[aria-hidden="true"]');
      });
      const target = find(step.target) || (step.fallback ? find(step.fallback) : undefined);
      if (!target) { setHighlight(null); return; }
      let bounds = target.getBoundingClientRect();
      if (bounds.top < 8 || bounds.bottom > innerHeight - 8) {
        target.scrollIntoView({ block: 'center', behavior: 'instant' });
        bounds = target.getBoundingClientRect();
      }
      const next = { top: Math.max(8, bounds.top - 6), left: Math.max(8, bounds.left - 6), width: Math.min(innerWidth - 16, bounds.width + 12), height: Math.min(innerHeight - 16, bounds.height + 12) };
      setHighlight(current => current && Object.keys(next).every(key => current[key as keyof Highlight] === next[key as keyof Highlight]) ? current : next);
    };
    const frame = requestAnimationFrame(update);
    // The document drawer animates for 340 ms; follow its target until it settles.
    const tracker = window.setInterval(update, 50);
    const timer = window.setTimeout(() => window.clearInterval(tracker), 750);
    window.addEventListener('resize', update);
    window.addEventListener('scroll', update, true);
    return () => { cancelAnimationFrame(frame); window.clearTimeout(timer); window.clearInterval(tracker); window.removeEventListener('resize', update); window.removeEventListener('scroll', update, true); };
  }, [index, open, activeStage]);
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
