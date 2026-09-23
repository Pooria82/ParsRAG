import { readFile, mkdir } from 'node:fs/promises';
import { resolve } from 'node:path';
import { chromium } from '@playwright/test';

const root = resolve(import.meta.dirname, '../..');
const output = resolve(root, 'docs/social-preview.png');
const mark = (await readFile(resolve(root, 'frontend/public/brand/parsrag-mark.svg'), 'utf8'))
  .replace('<svg ', '<svg width="132" height="132" ');
const browser = await chromium.launch({ channel: 'chrome' }).catch(() => chromium.launch());
try {
  const page = await browser.newPage({ viewport: { width: 1280, height: 640 }, deviceScaleFactor: 1 });
  await page.setContent(`<!doctype html><html><head><meta charset="utf-8"><style>
    *{box-sizing:border-box}body{margin:0;background:#f7f5ef;color:#1f2f2b;font-family:Arial,sans-serif}
    .card{width:1280px;height:640px;padding:78px 88px;position:relative;overflow:hidden}
    .rule{width:110px;height:7px;border-radius:9px;background:#146a57;margin:0 0 54px}
    .identity{display:flex;align-items:center;gap:24px}.identity svg{flex:none}
    h1{font-size:84px;letter-spacing:-4px;line-height:1;margin:0;font-weight:700}
    p{font-size:30px;line-height:1.38;margin:42px 0 0;max-width:890px;color:#485b53}
    .tags{display:flex;gap:14px;margin-top:46px}.tags span{border:1px solid #becfc4;border-radius:18px;padding:10px 16px;font-size:19px;color:#255d4c}
    .corner{position:absolute;right:-86px;bottom:-160px;width:500px;height:500px;border:1px solid #ccdcd1;border-radius:50%;box-shadow:0 0 0 50px #f7f5ef,0 0 0 51px #dbe6dd,0 0 0 108px #f7f5ef,0 0 0 109px #e2eae2;z-index:-1}
  </style></head><body><main class="card"><div class="rule"></div><div class="identity">${mark}<h1>ParsRAG</h1></div>
    <p>Private document intelligence, designed for Persian.</p>
    <div class="tags"><span>Local OCR</span><span>Cited answers</span><span>Ollama &amp; compatible APIs</span></div><div class="corner"></div>
  </main></body></html>`);
  await mkdir(resolve(root, 'docs'), { recursive: true });
  await page.screenshot({ path: output });
} finally {
  await browser.close();
}
