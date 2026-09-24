const { test, afterEach } = require('node:test');
const assert = require('node:assert/strict');
const { ApiError, ParsRagApiClient } = require('./.compiled/services/api.js');

const originalFetch = global.fetch;
const originalXhr = global.XMLHttpRequest;
afterEach(() => { global.fetch = originalFetch; global.XMLHttpRequest = originalXhr; });

test('API client normalizes base URLs and reports health without leaking fetch details', async () => {
  let requested = '';
  global.fetch = async url => { requested = String(url); return new Response(null, { status: 200 }); };
  const client = new ParsRagApiClient('http://localhost:8000///');
  assert.equal(await client.isHealthy(), true);
  assert.equal(requested, 'http://localhost:8000/health/ready');
});

test('API client distinguishes model preparation from an offline service', async () => {
  global.fetch = async () => new Response(JSON.stringify({ status: 'preparing' }), {
    status: 503, headers: { 'Content-Type': 'application/json' },
  });
  assert.equal(await new ParsRagApiClient('').healthStatus(), 'preparing');
});

test('API client discovers ingestion capabilities from the backend', async () => {
  global.fetch = async () => new Response(JSON.stringify({ ingestion: {
    max_files_per_session: 10, max_file_size_bytes: 104857600,
    max_batch_size_bytes: 524288000, supported_extensions: ['.pdf', '.png'], ocr_enabled: true,
  } }), { status: 200, headers: { 'Content-Type': 'application/json' } });

  const capabilities = await new ParsRagApiClient('').capabilities();

  assert.equal(capabilities.ingestion.max_files_per_session, 10);
  assert.deepEqual(capabilities.ingestion.supported_extensions, ['.pdf', '.png']);
});

test('API client classifies OCR failures for localized UI handling', async () => {
  global.XMLHttpRequest = class {
    upload = {}; status = 422; responseText = JSON.stringify({ detail: 'Scanned PDFs are not supported' });
    open() {} abort() { this.onabort?.(); }
    send() { this.onload?.(); }
  };
  const client = new ParsRagApiClient('http://localhost:8000');
  await assert.rejects(() => client.ingest(new File(['scan'], 'scan.pdf'), 'session-1'), error => {
    assert.equal(error instanceof ApiError, true);
    assert.equal(error.code, 'ocr_unavailable');
    assert.equal(error.status, 422);
    return true;
  });
});

test('upload reports byte progress and reaches 100 percent', async () => {
  global.XMLHttpRequest = class {
    upload = {}; status = 200; responseText = '';
    open() {} abort() { this.onabort?.(); }
    send() { this.upload.onprogress?.({ lengthComputable: true, loaded: 3, total: 4 }); this.onload?.(); }
  };
  const values = [];
  await new ParsRagApiClient('').ingest(new File(['data'], 'file.pdf'), 'session-1', undefined, value => values.push(value));
  assert.deepEqual(values, [75, 100]);
});

test('API client encodes session identifiers in resource paths', async () => {
  let requested = '';
  global.fetch = async url => { requested = String(url); return new Response('[]', { status: 200 }); };
  const client = new ParsRagApiClient('');
  await client.files('session / فارسی');
  assert.equal(requested, '/sessions/session%20%2F%20%D9%81%D8%A7%D8%B1%D8%B3%DB%8C/files');
});

test('deletes one document with a JSON filename payload', async () => {
  let body = '';
  global.fetch = async (_url, init) => { body = String(init.body); return new Response(null, { status: 200 }); };
  await new ParsRagApiClient('').deleteDocument('session-1', 'راهنما.pdf');
  assert.deepEqual(JSON.parse(body), { filename: 'راهنما.pdf' });
});

test('reuses a document by referencing its source session without uploading bytes', async () => {
  let request;
  global.fetch = async (url, init) => {
    request = { url: String(url), init };
    return new Response(JSON.stringify({ filename: 'راهنما.pdf', chunks: 4 }), { status: 200 });
  };
  await new ParsRagApiClient('').reuseDocument('new-session', 'old-session', 'راهنما.pdf');
  assert.equal(request.url, '/sessions/new-session/files/reuse');
  assert.equal(request.init.method, 'POST');
  assert.deepEqual(JSON.parse(request.init.body), { source_session_id: 'old-session', filename: 'راهنما.pdf' });
});

test('reads and saves model configuration without exposing API credentials', async () => {
  const requests = [];
  global.fetch = async (url, init = {}) => {
    requests.push({ url: String(url), init });
    return new Response(JSON.stringify({ provider: 'ollama', model_name: 'gemma3:12b', base_url: 'http://localhost:11434', api_key_configured: false }), { status: 200, headers: { 'Content-Type': 'application/json' } });
  };
  const client = new ParsRagApiClient('http://localhost:8000');
  assert.equal((await client.modelConfiguration()).model_name, 'gemma3:12b');
  const saved = await client.configureModel({ provider: 'ollama', model_name: 'gemma3:12b', base_url: 'http://localhost:11434' });
  assert.equal(saved.provider, 'ollama');
  assert.equal(requests[1].init.method, 'PUT');
  assert.deepEqual(JSON.parse(requests[1].init.body), { provider: 'ollama', model_name: 'gemma3:12b', base_url: 'http://localhost:11434' });
});

test('requests a generated conversation title after the first prompt', async () => {
  let request;
  global.fetch = async (url, init) => {
    request = { url: String(url), init };
    return new Response(JSON.stringify({ title: 'ساختار رمزنگاری فیستل' }), { status: 200, headers: { 'Content-Type': 'application/json' } });
  };
  const title = await new ParsRagApiClient('').conversationTitle('فیستل چیست؟', 'fa');
  assert.equal(title, 'ساختار رمزنگاری فیستل');
  assert.equal(request.url, '/conversations/title');
  assert.deepEqual(JSON.parse(request.init.body), { prompt: 'فیستل چیست؟', language: 'fa' });
});
