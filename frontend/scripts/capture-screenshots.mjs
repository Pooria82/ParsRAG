// Capture the README screenshots from the built app with synthetic data.
//
//   npm run build && node scripts/capture-screenshots.mjs
//
// The API is simulated in the browser, so no backend, model, or private
// document is involved; every name and number below is made up.
import { mkdir } from 'node:fs/promises';
import { resolve } from 'node:path';
import { chromium } from '@playwright/test';
import { preview } from 'vite';

const root = resolve(import.meta.dirname, '../..');
const output = resolve(root, 'docs/screenshots');
const MB = 1024 * 1024;

const TEXT = {
  en: {
    title: 'Load test results',
    question: 'How many failures did the last load test record, and how long did it run?',
    answer: [
      'The last run of the load test, on **03/25**, recorded **45** cumulative failures over **360** test hours [1]. The reliability calculator reports the same totals in its results panel [2].',
      '',
      '**Reliability estimate**',
      '',
      '- Failure rate: $\\lambda = 45 / 360 = 0.125$ failures per hour [1]',
      '- Mean time between failures: $\\mathrm{MTBF} = 1/\\lambda = 8$ hours [2]',
      '',
      'The test plan required at most **50** failures, so this run passes [3].',
    ].join('\n'),
    files: ['test-report.docx', 'test-plan.pdf'],
    tableCaption: 'Table 3-1: Cumulative test data',
    tableHead: ['Date', 'Failures (n)', 'Hours (t)'],
    imageCaption: 'Figure 3-5: Reliability calculator results',
    imageText: 'Total failures 45 · Test hours 360 · MTBF 8.00 h',
    plan: 'Acceptance criteria: the system passes when a 360-hour run records at most 50 failures.',
    panelTitle: 'Reliability calculator',
    panelRows: [['Total failures', '45'], ['Test hours', '360'], ['Failure rate', '0.125 / h'], ['MTBF', '8.00 h']],
  },
  fa: {
    title: 'نتیجهٔ آزمون بار',
    question: 'در آخرین اجرای آزمون بار چند خرابی ثبت شد و آزمون چند ساعت طول کشید؟',
    answer: [
      'در آخرین اجرای آزمون بار، در تاریخ **03/25**، روی هم **45** خرابی در **360** ساعت آزمون ثبت شده است [1]. پنل نتایج محاسبه‌گر قابلیت اطمینان هم همین مقدارها را نشان می‌دهد [2].',
      '',
      '**برآورد قابلیت اطمینان**',
      '',
      '- نرخ خرابی: $\\lambda = 45 / 360 = 0.125$ در ساعت [1]',
      '- میانگین زمان بین خرابی‌ها: $\\mathrm{MTBF} = 1/\\lambda = 8$ ساعت [2]',
      '',
      'طبق طرح آزمون، حداکثر **50** خرابی مجاز است؛ پس این اجرا پذیرفته می‌شود [3].',
    ].join('\n'),
    files: ['گزارش-آزمون.docx', 'طرح-آزمون.pdf'],
    tableCaption: 'جدول ۳-۱: داده‌های تجمعی آزمون',
    tableHead: ['تاریخ', 'خرابی‌ها (n)', 'ساعت‌ها (t)'],
    imageCaption: 'شکل ۳-۵: نتیجهٔ محاسبه‌گر قابلیت اطمینان',
    imageText: 'تعداد کل خرابی‌ها 45 · ساعت‌های آزمون 360 · MTBF 8.00',
    plan: 'معیار پذیرش: سامانه وقتی پذیرفته می‌شود که در اجرای ۳۶۰ ساعته حداکثر ۵۰ خرابی ثبت شود.',
    panelTitle: 'محاسبه‌گر قابلیت اطمینان',
    panelRows: [['تعداد کل خرابی‌ها', '45'], ['ساعت‌های آزمون', '360'], ['نرخ خرابی', '0.125'], ['MTBF', '8.00']],
  },
};

const SETTINGS = [
  ['OLLAMA_CONTEXT_LENGTH', 'model', 'int', '4096', '4096', 2048, 131072],
  ['OLLAMA_THINK', 'model', 'bool', '0', '0'],
  ['MODEL_CONTEXT_WINDOW', 'model', 'int', '32768', '32768', 2048, 1048576],
  ['MODEL_API_MAX_RETRIES', 'model', 'int', '4', '4', 0, 8],
  ['LLM_REQUEST_TIMEOUT_SECONDS', 'model', 'int', '120', '120', 10, 600],
  ['CONDENSE_TIMEOUT_SECONDS', 'model', 'int', '30', '30', 5, 120],
  ['STRICT_RAG_THRESHOLD', 'retrieval', 'float', '0.75', '0.75', 0, 1],
  ['STRICT_RAG_TOP_K', 'retrieval', 'int', '', '', 1, 50, true, '8-30'],
  ['HYBRID_RETRIEVE_TOP_K', 'retrieval', 'int', '25', '25', 1, 50],
  ['HYBRID_RERANK_TOP_K', 'retrieval', 'int', '', '', 1, 50, true, '8-30'],
  ['KEYWORD_SEARCH', 'retrieval', 'bool', '1', '1'],
  ['PARSRAG_MAX_FILES_PER_SESSION', 'documents', 'int', '10', '10', 1, 50],
  ['PARSRAG_MAX_FILE_BYTES', 'documents', 'bytes', String(100 * MB), String(100 * MB), MB, 1024 * MB],
  ['PARSRAG_MAX_BATCH_BYTES', 'documents', 'bytes', String(500 * MB), String(500 * MB), MB, 2048 * MB],
  ['OCR_ENABLED', 'documents', 'bool', '1', '1'],
  ['OCR_LANGUAGES', 'documents', 'text', 'fas+eng', 'fas+eng'],
  ['OCR_DPI', 'documents', 'int', '200', '200', 150, 600],
  ['OCR_ORIENTATION', 'documents', 'bool', '1', '1'],
  ['OCR_MAX_PAGES', 'documents', 'int', '30', '30', 1, 200],
  ['OCR_MAX_IMAGES', 'documents', 'int', '200', '200', 1, 1000],
  ['OCR_TIMEOUT_SECONDS', 'documents', 'int', '45', '45', 1, 300],
  ['OCR_MIN_IMAGE_PIXELS', 'documents', 'int', '10000', '10000', 1, 1000000],
  ['SOURCE_IMAGE_PREVIEWS', 'documents', 'bool', '1', '1'],
  ['OCR_WORKERS', 'performance', 'int', '', '', 1, 16, true, '10'],
  ['EMBED_BATCH_SIZE', 'performance', 'int', '8', '8', 1, 128, true, '8'],
  ['PARSRAG_CPU_THREADS', 'performance', 'int', '8', '4', 1, 64, true, '4'],
  ['QDRANT_UPSERT_BATCH_SIZE', 'performance', 'int', '64', '64', 1, 512],
].map(([key, group, kind, value, env_value, minimum = null, maximum = null, automatic = false, automatic_value = null]) => ({
  key, group, kind, value, env_value, overridden: value !== env_value, minimum, maximum, automatic, automatic_value,
}));

function session(language) {
  const t = TEXT[language];
  const [report, plan] = t.files;
  const rows = [['03/23', '43', '344'], ['03/24', '44', '352'], ['03/25', '45', '360']];
  const table = [`[${language === 'fa' ? 'جدول' : 'Table'} 6] ${t.tableCaption}`, `| ${t.tableHead.join(' | ')} |`, '| :--- | :--- | :--- |',
    ...rows.map(row => `| ${row.join(' | ')} |`)].join('\n');
  return {
    id: 'sample', title: t.title, createdAt: Date.now() - 60000, updatedAt: Date.now(), ragMode: 'strict', draft: '',
    documents: t.files.map(name => ({ name, status: 'indexed', chunks: 120, sections: 64 })),
    messages: [
      { id: 'q1', role: 'user', content: t.question, timestamp: Date.now() - 50000 },
      {
        id: 'a1', role: 'assistant', content: t.answer, timestamp: Date.now() - 40000, grounding: 'documents',
        sources: [
          { n: 1, filename: report, cited: true, location: { kind: 'paragraph', start: 812, table: 6 }, text: table },
          { n: 2, filename: report, cited: true, location: { kind: 'paragraph', start: 845, image: 15 },
            text: `[${language === 'fa' ? 'تصویر' : 'Image'} 15] ${t.imageCaption}\n${t.imageText}` },
          { n: 3, filename: plan, cited: true, location: { kind: 'page', start: 4 }, text: t.plan },
        ],
      },
    ],
  };
}

async function panelImage(browser, language) {
  const t = TEXT[language];
  const page = await browser.newPage({ viewport: { width: 880, height: 440 } });
  await page.setContent(`<html dir="${language === 'fa' ? 'rtl' : 'ltr'}"><body style="margin:0;font:22px Tahoma,sans-serif;background:#eef3f7">
    <div style="margin:28px;background:#fff;border-radius:14px;box-shadow:0 4px 18px #0002;overflow:hidden">
      <div style="background:#1f6feb;color:#fff;padding:18px 26px;font-weight:bold">${t.panelTitle}</div>
      <table style="width:100%;border-collapse:collapse">${t.panelRows.map(([label, value], index) =>
        `<tr style="background:${index % 2 ? '#f6f8fa' : '#fff'}"><td style="padding:16px 26px">${label}</td><td dir="ltr" style="padding:16px 26px;text-align:end;font-weight:bold">${value}</td></tr>`).join('')}</table>
    </div></body></html>`);
  const image = await page.screenshot();
  await page.close();
  return image;
}

async function open(browser, { language, theme, sessions, image, height = 900 }) {
  const context = await browser.newContext({ viewport: { width: 1440, height }, reducedMotion: 'reduce', locale: language === 'fa' ? 'fa-IR' : 'en-US' });
  const page = await context.newPage();
  await page.addInitScript(([settings, stored]) => {
    localStorage.setItem('parsrag_settings_v1', JSON.stringify(settings));
    localStorage.setItem('parsrag_tour_v1', 'done');
    if (stored.length) {
      localStorage.setItem('parsrag_sessions_v1', JSON.stringify(stored));
      localStorage.setItem('parsrag_active_session_id_v1', stored[0].id);
    }
  }, [{ language, theme, ollamaBaseUrl: 'http://host.docker.internal:11434', ollamaModelName: 'qwen3.5:4b', selectedModel: 'qwen3.5:4b' }, sessions]);
  await page.route('**/health/ready', route => route.fulfill({ json: { status: 'ready' } }));
  await page.route('**/capabilities', route => route.fulfill({ json: { ingestion: {
    max_files_per_session: 10, max_file_size_bytes: 100 * MB, max_batch_size_bytes: 500 * MB,
    supported_extensions: ['.pdf', '.docx', '.pptx', '.txt', '.md', '.png', '.jpg'], ocr_enabled: true } } }));
  await page.route('**/models/configuration', route => route.fulfill({ json: {
    provider: 'ollama', model_name: 'qwen3.5:4b', base_url: 'http://host.docker.internal:11434',
    api_key_configured: false, disclosure_acknowledged: false, ollama_base_url: 'http://host.docker.internal:11434' } }));
  await page.route('**/models/ollama**', route => route.fulfill({ json: [
    { name: 'qwen3.5:4b', size: 3324173934 }, { name: 'qwen2.5:7b', size: 4683087332 }, { name: 'gemma3:12b', size: 8149190253 }] }));
  await page.route('**/settings/runtime', route => route.fulfill({ json: { settings: SETTINGS, upload_ceiling_bytes: 500 * MB } }));
  await page.route('**/sessions/*/files', route => route.fulfill({ json: sessions[0]?.documents.map(document => document.name) ?? [] }));
  await page.route('**/sessions/*/images/**', route => route.fulfill({ body: image, contentType: 'image/png' }));
  await page.goto(server.resolvedUrls.local[0]);
  await page.waitForSelector('.boot-sequence', { state: 'detached', timeout: 15000 }).catch(() => undefined);
  await page.waitForTimeout(600);
  return { context, page };
}

async function settingsDialog(page, tab) {
  await page.locator('[data-tour="settings"]').first().click();
  await page.getByRole('tab', { name: tab }).click();
  await page.waitForTimeout(500);
  return page.locator('.settings-dialog');
}

await mkdir(output, { recursive: true });
const server = await preview({ root: resolve(import.meta.dirname, '..'), preview: { host: '127.0.0.1', port: 4182, strictPort: true } });
const browser = await chromium.launch({ channel: 'chrome' }).catch(() => chromium.launch());
try {
  for (const language of ['en', 'fa']) {
    const image = await panelImage(browser, language);
    const shot = name => resolve(output, `${name}-${language}`);

    let { context, page } = await open(browser, { language, theme: 'light', sessions: [], image });
    await page.screenshot({ path: `${shot('home')}-light.png` });
    let dialog = await settingsDialog(page, language === 'fa' ? 'مدل و اتصال' : 'Model & connection');
    await dialog.locator('[data-tour="settings-model-name"] .choice-menu-trigger').click();
    await page.waitForTimeout(300);
    await dialog.screenshot({ path: `${shot('model')}-light.png` });
    await page.keyboard.press('Escape');
    await page.waitForTimeout(200);
    if (await dialog.isVisible()) await page.keyboard.press('Escape');
    await page.waitForTimeout(400);
    dialog = await settingsDialog(page, language === 'fa' ? 'اسناد و سرعت' : 'Documents & speed');
    await dialog.locator('.server-settings-group').nth(1).scrollIntoViewIfNeeded();
    await dialog.screenshot({ path: `${shot('settings')}-light.png` });
    await context.close();

    ({ context, page } = await open(browser, { language, theme: 'light', sessions: [session(language)], image, height: 1300 }));
    const sources = page.locator('[data-tour="sources"]').last();
    await sources.locator('.source-card').nth(0).locator('summary').click();
    await sources.locator('.source-card').nth(1).locator('summary').click();
    await page.waitForTimeout(500);
    await page.locator('.grounding-badge').last().evaluate(element => element.scrollIntoView({ block: 'start' }));
    await page.waitForTimeout(300);
    // The scroll shortcut would cover the sources in a still image.
    await page.addStyleTag({ content: '.jump-button{display:none!important}' });
    await page.screenshot({ path: `${shot('sources')}-light.png` });
    await context.close();

    ({ context, page } = await open(browser, { language, theme: 'dark', sessions: [session(language)], image }));
    await page.screenshot({ path: `${shot('workspace')}-dark.png` });
    await context.close();
  }
} finally {
  await browser.close();
  await new Promise(done => server.httpServer.close(done));
}
console.log(`Screenshots written to ${output}`);
