const { test, afterEach } = require('node:test');
const assert = require('node:assert/strict');
const { ApiError, ParsRagApiClient, errorFromBody } = require('./.compiled/services/api.js');
const { noticeMessage, queryErrorMessage, uploadErrorMessage } = require('./.compiled/i18n/errors.js');

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

test('API client keeps the server error code for localized upload messages', async () => {
  global.XMLHttpRequest = class {
    upload = {}; status = 400; responseText = JSON.stringify({ detail: 'The PDF is password-protected.', code: 'encrypted_document' });
    open() {} abort() { this.onabort?.(); }
    send() { this.onload?.(); }
  };
  const client = new ParsRagApiClient('http://localhost:8000');
  await assert.rejects(() => client.ingest(new File(['scan'], 'scan.pdf'), 'session-1'), error => {
    assert.equal(error instanceof ApiError, true);
    assert.equal(error.code, 'encrypted_document');
    assert.equal(error.status, 400);
    return true;
  });
});

test('error bodies without a code, nested codes, and HTML stay usable', () => {
  assert.equal(errorFromBody(503, JSON.stringify({ detail: { status: 'preparing', code: 'not_ready' } })).code, 'not_ready');
  assert.equal(errorFromBody(500, '<html>boom</html>').code, 'request_failed');
  assert.equal(errorFromBody(502, JSON.stringify({ detail: 'x', code: 'model_auth' })).detail, 'x');
});

test('every error code shown to users has Persian and English text', () => {
  const codes = ['encrypted_document', 'corrupt_file', 'ocr_disabled', 'duplicate_file', 'duplicate_content', 'vector_store_unavailable', 'busy'];
  for (const code of codes) {
    assert.ok(uploadErrorMessage(code, 'fa'));
    assert.ok(uploadErrorMessage(code, 'en'));
  }
  for (const code of ['model_timeout', 'model_auth', 'model_rate_limited', 'model_not_found', 'model_unavailable', 'network', 'not_ready']) {
    assert.ok(queryErrorMessage(code, 'fa'));
    assert.ok(queryErrorMessage(code, 'en'));
  }
  assert.equal(queryErrorMessage('something_new', 'fa'), undefined);
  assert.match(noticeMessage('ocr_page_limit', 'fa'), /OCR/);
});

test('successful uploads return per-file chunks and notices', async () => {
  global.XMLHttpRequest = class {
    upload = {}; status = 200;
    responseText = JSON.stringify({ message: 'ok', files: [{ filename: 'scan.pdf', chunks: 12, sections: 30, notices: ['ocr_page_limit'] }] });
    open() {} abort() { this.onabort?.(); }
    send() { this.onload?.(); }
  };
  const [file] = await new ParsRagApiClient('').ingest(new File(['x'], 'scan.pdf'), 'session-1');
  assert.deepEqual(file, { filename: 'scan.pdf', chunks: 12, sections: 30, notices: ['ocr_page_limit'] });
});

test('unreachable services are reported as network failures', async () => {
  global.fetch = async () => { throw new TypeError('Failed to fetch'); };
  await assert.rejects(() => new ParsRagApiClient('').query({}), error => error.code === 'network');
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
