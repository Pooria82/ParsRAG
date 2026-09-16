/** Local-only, deterministic browser QA. Never imports or contacts the real backend. */
const http = require('node:http');
const fs = require('node:fs');
const path = require('node:path');
const root = path.resolve(__dirname, '../dist');
const queries = [];
const documents = new Map();
const failures = new Set();
const answer = '## یک نگاه روشن‌تر به سند\n\nاین یک **پاسخ آزمایشی** برای بررسی رابط است. نکته‌های اصلی سند عبارت‌اند از:\n\n1. حفظ حریم خصوصی و پردازش محلی اطلاعات\n2. یافتن بخش‌های مرتبط و ارجاع به منبع\n3. امکان مقایسهٔ اسناد فارسی و انگلیسی\n\n| موضوع | نتیجه |\n| --- | --- |\n| منابع | قابل بررسی |\n| زبان | فارسی و English |\n\n```python\nresult = {"mode": "hybrid", "sources": 2}\nprint(result)\n```\n\n> برای نتیجه‌گیری، متن اصلی سند را نیز بخوانید.';
const types = { '.html': 'text/html; charset=utf-8', '.js': 'text/javascript', '.css': 'text/css', '.svg': 'image/svg+xml', '.woff2': 'font/woff2' };
http.createServer(async (req, res) => {
  const url = new URL(req.url, 'http://127.0.0.1:4318');
  const json = (status, data) => { if (!res.destroyed) { res.writeHead(status, { 'Content-Type': 'application/json' }); res.end(JSON.stringify(data)); } };
  if (url.pathname === '/health') return json(200, { status: 'ok' });
  if (url.pathname === '/_test/requests') return json(200, queries);
  if (req.method === 'POST' && url.pathname === '/query') {
    let body = ''; for await (const chunk of req) body += chunk;
    const payload = JSON.parse(body); queries.push(payload);
    if (payload.prompt === 'failure test' && !failures.has(payload.session_id)) {
      failures.add(payload.session_id); return json(503, { detail: 'Simulated outage' });
    }
    const respond = () => json(200, { answer, source_nodes: [{ text: 'پردازش اطلاعات روی سرویس محلی انجام می‌شود. این متن صرفاً نمونهٔ آزمون رابط است.', metadata: { filename: 'راهنمای پژوهش.pdf' }, score: 0.91 }, { text: 'Document comparison fixture.', metadata: { filename: 'research-notes.docx' }, score: 0.82 }] });
    if (payload.prompt === 'slow test') setTimeout(respond, 30000); else setTimeout(respond, 350);
    return;
  }
  const sessionMatch = url.pathname.match(/^\/sessions\/([^/]+)(\/files)?$/);
  if (sessionMatch) {
    if (req.method === 'DELETE') { documents.delete(sessionMatch[1]); return json(200, { message: 'Deleted test session' }); }
    return json(200, documents.get(sessionMatch[1]) || []);
  }
  if (req.method === 'POST' && url.pathname === '/ingest') {
    const chunks = []; for await (const chunk of req) chunks.push(chunk);
    const body = Buffer.concat(chunks).toString('utf8');
    const filename = body.match(/filename="([^"]+)"/)?.[1];
    const session = body.match(/name="session_id"\r\n\r\n([^\r]+)/)?.[1];
    if (!filename || !session) return json(400, { detail: 'Invalid upload fixture' });
    if (filename.includes('broken')) return json(400, { detail: 'Scanned PDFs are not supported.' });
    documents.set(session, [...new Set([...(documents.get(session) || []), filename])]);
    return json(200, { message: 'Indexed test document' });
  }
  const relative = url.pathname === '/' ? 'index.html' : decodeURIComponent(url.pathname).replace(/^\/+/, '');
  const file = path.resolve(root, relative);
  if (!file.startsWith(root + path.sep) || !fs.existsSync(file) || !fs.statSync(file).isFile()) { res.writeHead(404); return res.end('Not found'); }
  res.writeHead(200, { 'Content-Type': types[path.extname(file)] || 'application/octet-stream' });
  fs.createReadStream(file).pipe(res);
}).listen(4318, '127.0.0.1', () => console.log('Isolated browser fixture: http://127.0.0.1:4318'));
