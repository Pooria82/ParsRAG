import type { Language, RuntimeSettingGroup } from '../types';

type Text = { fa: string; en: string };

/** Label and short explanation of each server setting, by environment name. */
export const SETTING_TEXT: Record<string, { label: Text; hint: Text }> = {
  OLLAMA_CONTEXT_LENGTH: {
    label: { fa: 'اندازهٔ متن Ollama (توکن)', en: 'Ollama context (tokens)' },
    hint: { fa: 'حافظه‌ای که Ollama برای هر پرسش می‌گیرد. روی GPU کوچک کمترش کنید (مثلاً ۴۰۹۶).', en: 'Memory Ollama reserves per question. Lower it on small GPUs (for example 4096).' },
  },
  OLLAMA_THINK: {
    label: { fa: 'اجازهٔ «فکر کردن» به مدل‌های Ollama', en: 'Let Ollama models think first' },
    hint: { fa: 'مدل‌هایی مثل qwen3 پیش از پاسخ استدلال می‌کنند؛ کندتر است و به اندازهٔ متن بزرگ‌تری نیاز دارد.', en: 'Models such as qwen3 reason before answering; slower, and needs a larger context.' },
  },
  MODEL_CONTEXT_WINDOW: {
    label: { fa: 'اندازهٔ متن مدل API (توکن)', en: 'API model context (tokens)' },
    hint: { fa: 'برای سطح‌های رایگان با محدودیت توکن در دقیقه کمترش کنید.', en: 'Lower it for free tiers that limit tokens per minute.' },
  },
  MODEL_API_MAX_RETRIES: {
    label: { fa: 'تلاش دوباره برای خطاهای موقت API', en: 'Retries for temporary API errors' },
    hint: { fa: 'برای خطاهای ۵۰۰ و ۴۲۹ سرویس‌های رایگان.', en: 'For HTTP 500 and 429 errors from free tiers.' },
  },
  LLM_REQUEST_TIMEOUT_SECONDS: {
    label: { fa: 'مهلت هر پاسخ (ثانیه)', en: 'Answer timeout (seconds)' },
    hint: { fa: 'مدل‌های کند روی CPU به مهلت بیشتری نیاز دارند.', en: 'Slow models on a CPU need more time.' },
  },
  CONDENSE_TIMEOUT_SECONDS: {
    label: { fa: 'مهلت بازنویسی پرسش پیگیری (ثانیه)', en: 'Follow-up rewrite timeout (seconds)' },
    hint: { fa: 'اگر تمام شود، پرسش همان‌طور که نوشته شده جست‌وجو می‌شود.', en: 'When it runs out, the question is searched as written.' },
  },
  STRICT_RAG_THRESHOLD: {
    label: { fa: 'آستانهٔ پذیرش شواهد (فقط اسناد)', en: 'Evidence threshold (documents only)' },
    hint: { fa: 'بالاتر یعنی سخت‌گیرتر: پاسخ‌های کمتر ولی مطمئن‌تر. پیش‌فرض ۰٫۷۵.', en: 'Higher is stricter: fewer but surer answers. Default 0.75.' },
  },
  STRICT_RAG_TOP_K: {
    label: { fa: 'تعداد بخش‌ها در حالت فقط اسناد', en: 'Passages in documents-only mode' },
    hint: { fa: '«خودکار» تعداد را بر اساس پرسش تعیین می‌کند و معمولاً بهترین است.', en: 'Automatic picks the number per question and is usually best.' },
  },
  HYBRID_RETRIEVE_TOP_K: {
    label: { fa: 'بخش‌های اولیه در حالت ترکیبی', en: 'Candidates in hybrid mode' },
    hint: { fa: 'بخش‌هایی که پیش از رتبه‌بندی دوباره جست‌وجو می‌شوند.', en: 'Passages searched before reranking.' },
  },
  HYBRID_RERANK_TOP_K: {
    label: { fa: 'بخش‌های نهایی در حالت ترکیبی', en: 'Passages kept in hybrid mode' },
    hint: { fa: '«خودکار» بر اساس پرسش تعیین می‌شود.', en: 'Automatic picks the number per question.' },
  },
  KEYWORD_SEARCH: {
    label: { fa: 'جست‌وجوی واژه‌ای در کنار جست‌وجوی معنایی', en: 'Keyword search next to semantic search' },
    hint: { fa: 'نام‌ها، عددها و کدها را بهتر پیدا می‌کند.', en: 'Finds names, numbers, and codes more reliably.' },
  },
  PARSRAG_MAX_FILES_PER_SESSION: {
    label: { fa: 'بیشترین تعداد سند در هر گفت‌وگو', en: 'Documents per conversation' },
    hint: { fa: 'سندهای بیشتر یعنی بازیابی کندتر.', en: 'More documents make retrieval slower.' },
  },
  PARSRAG_MAX_FILE_BYTES: {
    label: { fa: 'بیشترین حجم هر فایل (مگابایت)', en: 'Largest file (MB)' },
    hint: { fa: 'باید از حجم هر بارگذاری کمتر باشد.', en: 'Must not exceed the upload batch size.' },
  },
  PARSRAG_MAX_BATCH_BYTES: {
    label: { fa: 'بیشترین حجم هر بارگذاری (مگابایت)', en: 'Largest upload batch (MB)' },
    hint: { fa: 'سقف سرور (PARSRAG_MAX_REQUEST_BYTES) فقط از ⁦.env⁩ تغییر می‌کند.', en: 'The server ceiling (PARSRAG_MAX_REQUEST_BYTES) changes only in ⁦.env⁩.' },
  },
  OCR_ENABLED: {
    label: { fa: 'خواندن متن تصویرها و اسکن‌ها (OCR)', en: 'Read images and scans (OCR)' },
    hint: { fa: 'بدون آن، متن داخل تصویرها و PDFهای اسکن‌شده جست‌وجوپذیر نیست.', en: 'Without it, text inside images and scanned PDFs cannot be searched.' },
  },
  OCR_LANGUAGES: {
    label: { fa: 'زبان‌های OCR', en: 'OCR languages' },
    hint: { fa: 'کد زبان‌های Tesseract با + جدا شوند؛ مثلاً fas+eng.', en: 'Tesseract language codes joined with +, for example fas+eng.' },
  },
  OCR_DPI: {
    label: { fa: 'وضوح خواندن صفحه‌های اسکن‌شده (DPI)', en: 'Scan resolution (DPI)' },
    hint: { fa: 'بیشتر یعنی دقیق‌تر ولی کندتر.', en: 'Higher is more accurate but slower.' },
  },
  OCR_ORIENTATION: {
    label: { fa: 'صاف کردن صفحه‌های کج یا وارونه', en: 'Straighten rotated or skewed pages' },
    hint: { fa: 'صفحه‌های چرخیده را پیش از خواندن صاف می‌کند.', en: 'Rotates pages upright before reading them.' },
  },
  OCR_MAX_PAGES: {
    label: { fa: 'بیشترین صفحهٔ اسکن‌شده در هر PDF', en: 'Scanned pages read per PDF' },
    hint: { fa: 'صفحه‌های بعدی خوانده نمی‌شوند و پیام داده می‌شود.', en: 'Later pages are skipped with a notice.' },
  },
  OCR_MAX_IMAGES: {
    label: { fa: 'بیشترین تصویر خوانده‌شده در هر فایل Word یا PowerPoint', en: 'Images read per Word or PowerPoint file' },
    hint: { fa: 'تصویرهای بعدی خوانده نمی‌شوند و پیام داده می‌شود.', en: 'Later images are skipped with a notice.' },
  },
  OCR_TIMEOUT_SECONDS: {
    label: { fa: 'مهلت خواندن هر تصویر (ثانیه)', en: 'Time per image (seconds)' },
    hint: { fa: 'تصویری که بیشتر طول بکشد کنار گذاشته می‌شود.', en: 'An image that takes longer is skipped.' },
  },
  OCR_DOCUMENT_TIMEOUT_SECONDS: {
    label: { fa: 'مهلت کل خواندن یک سند (ثانیه)', en: 'Reading time per document (seconds)' },
    hint: { fa: 'پس از آن، صفحه‌ها و تصویرهای باقی‌مانده با هشدار کنار گذاشته می‌شوند و بقیهٔ سند ایندکس می‌شود.', en: 'After this, the remaining pages and images are skipped with a notice and the rest is indexed.' },
  },
  OCR_MIN_IMAGE_PIXELS: {
    label: { fa: 'کوچک‌ترین تصویر خواندنی (پیکسل)', en: 'Smallest image read (pixels)' },
    hint: { fa: 'آیکون‌ها و تصویرهای خیلی کوچک خوانده نمی‌شوند.', en: 'Icons and tiny pictures are skipped.' },
  },
  SOURCE_IMAGE_PREVIEWS: {
    label: { fa: 'نمایش خود تصویر در منابع پاسخ', en: 'Show the image in answer sources' },
    hint: { fa: 'نسخهٔ کوچکی از هر تصویر کنار سند نگه داشته می‌شود. برای سندهای تازه اعمال می‌شود.', en: 'A small copy of each image is kept with the document. Applies to new uploads.' },
  },
  OCR_WORKERS: {
    label: { fa: 'تصویرهایی که هم‌زمان خوانده می‌شوند', en: 'Images read at the same time' },
    hint: { fa: 'بیشتر یعنی ایندکس سریع‌تر و مصرف CPU بیشتر. «خودکار»: همهٔ هسته‌ها، حداکثر ۸.', en: 'More is faster indexing and more CPU. Automatic: every core, at most 8.' },
  },
  EMBED_BATCH_SIZE: {
    label: { fa: 'اندازهٔ دستهٔ بردارسازی', en: 'Embedding batch size' },
    hint: { fa: '«خودکار»: ۸ روی CPU و ۳۲ روی GPU.', en: 'Automatic: 8 on a CPU, 32 on a GPU.' },
  },
  PARSRAG_CPU_THREADS: {
    label: { fa: 'هسته‌های CPU برای بردارسازی', en: 'CPU threads for embeddings' },
    hint: { fa: 'بیشتر یعنی بردارسازی سریع‌تر؛ تا تعداد هسته‌های واقعی دستگاه.', en: 'More is faster embedding, up to the physical cores.' },
  },
  QDRANT_UPSERT_BATCH_SIZE: {
    label: { fa: 'بخش‌های ذخیره‌شده در هر نوبت', en: 'Chunks saved per write' },
    hint: { fa: 'معمولاً نیازی به تغییر ندارد.', en: 'Rarely needs changing.' },
  },
};

export const GROUP_TEXT: Record<RuntimeSettingGroup, Text> = {
  model: { fa: 'تنظیمات پیشرفتهٔ مدل', en: 'Advanced model settings' },
  retrieval: { fa: 'بازیابی در سرور', en: 'Server retrieval' },
  documents: { fa: 'بارگذاری و OCR', en: 'Uploads and OCR' },
  performance: { fa: 'سرعت ایندکس', en: 'Indexing speed' },
};

export const RUNTIME_TEXT = {
  fa: {
    automatic: 'خودکار', perQuestion: 'بسته به هر پرسش', on: 'روشن', off: 'خاموش', fromEnv: 'مقدار ⁦.env⁩:', resetOne: 'بازگشت به مقدار ⁦.env⁩',
    save: 'ذخیره', saving: 'در حال ذخیره…', saved: 'ذخیره شد و از درخواست بعدی اعمال می‌شود.', resetAll: 'بازگشت همه به ⁦.env⁩',
    loadError: 'تنظیمات سرور خوانده نشد.', saveError: 'تنظیمات ذخیره نشد.', invalid: 'یک مقدار معتبر نیست یا خارج از محدوده است.',
    ceiling: 'حجم بارگذاری از سقف سرور بیشتر است؛ ابتدا PARSRAG_MAX_REQUEST_BYTES را در ⁦.env⁩ بالا ببرید.',
    envOnly: 'درگاه، نشانی‌های مجاز، Qdrant، سقف حافظه و مدل بردارسازی فقط از ⁦.env⁩ و با راه‌اندازی دوباره تغییر می‌کنند.',
    overridden: 'در برنامه تغییر کرده',
  },
  en: {
    automatic: 'Automatic', perQuestion: 'per question', on: 'On', off: 'Off', fromEnv: '⁦.env⁩ value:', resetOne: 'Back to the ⁦.env⁩ value',
    save: 'Save', saving: 'Saving…', saved: 'Saved; applies from the next request.', resetAll: 'Reset all to ⁦.env⁩',
    loadError: 'Could not read the server settings.', saveError: 'The settings were not saved.', invalid: 'A value is invalid or out of range.',
    ceiling: 'The upload size exceeds the server ceiling; raise PARSRAG_MAX_REQUEST_BYTES in ⁦.env⁩ first.',
    envOnly: 'Ports, allowed addresses, Qdrant, memory limits, and the embedding model change only in ⁦.env⁩, with a restart.',
    overridden: 'Changed in the app',
  },
} satisfies Record<Language, Record<string, string>>;
