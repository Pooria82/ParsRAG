const { test, afterEach } = require('node:test');
const assert = require('node:assert/strict');
const { ApiError, ParsRagApiClient } = require('./.compiled/services/api.js');

const originalFetch = global.fetch;
afterEach(() => { global.fetch = originalFetch; });

test('API client normalizes base URLs and reports health without leaking fetch details', async () => {
  let requested = '';
  global.fetch = async url => { requested = String(url); return new Response(null, { status: 200 }); };
  const client = new ParsRagApiClient('http://localhost:8000///');
  assert.equal(await client.isHealthy(), true);
  assert.equal(requested, 'http://localhost:8000/health');
});

test('API client classifies scanned PDFs for localized UI handling', async () => {
  global.fetch = async () => new Response(JSON.stringify({ detail: 'Scanned PDFs are not supported' }), {
    status: 422, headers: { 'Content-Type': 'application/json' },
  });
  const client = new ParsRagApiClient('http://localhost:8000');
  await assert.rejects(() => client.ingest(new File(['scan'], 'scan.pdf'), 'session-1'), error => {
    assert.equal(error instanceof ApiError, true);
    assert.equal(error.code, 'scanned_pdf');
    assert.equal(error.status, 422);
    return true;
  });
});

test('API client encodes session identifiers in resource paths', async () => {
  let requested = '';
  global.fetch = async url => { requested = String(url); return new Response('[]', { status: 200 }); };
  const client = new ParsRagApiClient('');
  await client.files('session / فارسی');
  assert.equal(requested, '/sessions/session%20%2F%20%D9%81%D8%A7%D8%B1%D8%B3%DB%8C/files');
});
