const { test, afterEach } = require('node:test');
const assert = require('node:assert/strict');
const { changedValues, displayValue, storedValue } = require('./.compiled/components/ServerSettings.js');
const { ParsRagApiClient } = require('./.compiled/services/api.js');
const { SETTING_TEXT } = require('./.compiled/i18n/runtimeSettings.js');

const originalFetch = global.fetch;
afterEach(() => { global.fetch = originalFetch; });

test('sizes are edited in MB and stored in bytes', () => {
  const size = { kind: 'bytes' };
  assert.equal(displayValue(size, String(100 * 1024 * 1024)), '100');
  assert.equal(storedValue(size, '250'), String(250 * 1024 * 1024));
  assert.equal(displayValue({ kind: 'int' }, '200'), '200');
  assert.equal(storedValue({ kind: 'float' }, ' 0.8 '), '0.8');
});

test('only fields that differ from the active value are sent', () => {
  const settings = [
    { key: 'OCR_DPI', value: '200' },
    { key: 'OCR_ENABLED', value: '1' },
    { key: 'STRICT_RAG_TOP_K', value: '' },
  ];
  assert.deepEqual(changedValues(settings, { OCR_DPI: '300', OCR_ENABLED: '1', STRICT_RAG_TOP_K: '' }), { OCR_DPI: '300' });
});

test('runtime settings are read and changed through the API', async () => {
  const calls = [];
  global.fetch = async (url, init = {}) => {
    calls.push({ url: String(url), method: init.method ?? 'GET', body: init.body });
    return new Response(JSON.stringify({ settings: [], upload_ceiling_bytes: 1 }), { status: 200 });
  };
  const client = new ParsRagApiClient('http://localhost:8000');
  await client.runtimeSettings();
  await client.updateRuntimeSettings({ OCR_DPI: '300', OCR_WORKERS: null });
  assert.deepEqual(calls.map(call => call.method), ['GET', 'PUT']);
  assert.equal(calls[1].url, 'http://localhost:8000/settings/runtime');
  assert.deepEqual(JSON.parse(calls[1].body), { values: { OCR_DPI: '300', OCR_WORKERS: null } });

  global.fetch = async () => new Response(JSON.stringify({ detail: 'x', code: 'upload_ceiling' }), { status: 400 });
  await assert.rejects(client.updateRuntimeSettings({ PARSRAG_MAX_BATCH_BYTES: '1' }), error => error.code === 'upload_ceiling');
});

test('every server setting has a Persian and English label and hint', () => {
  const keys = ['OLLAMA_CONTEXT_LENGTH', 'OLLAMA_THINK', 'MODEL_CONTEXT_WINDOW', 'MODEL_API_MAX_RETRIES', 'LLM_REQUEST_TIMEOUT_SECONDS',
    'CONDENSE_TIMEOUT_SECONDS', 'STRICT_RAG_THRESHOLD', 'STRICT_RAG_TOP_K', 'HYBRID_RETRIEVE_TOP_K', 'HYBRID_RERANK_TOP_K', 'KEYWORD_SEARCH',
    'PARSRAG_MAX_FILES_PER_SESSION', 'PARSRAG_MAX_FILE_BYTES', 'PARSRAG_MAX_BATCH_BYTES', 'OCR_ENABLED', 'OCR_LANGUAGES', 'OCR_DPI',
    'OCR_ORIENTATION', 'OCR_MAX_PAGES', 'OCR_MAX_IMAGES', 'OCR_TIMEOUT_SECONDS', 'OCR_DOCUMENT_TIMEOUT_SECONDS', 'OCR_MIN_IMAGE_PIXELS', 'SOURCE_IMAGE_PREVIEWS',
    'OCR_WORKERS', 'EMBED_BATCH_SIZE', 'PARSRAG_CPU_THREADS', 'QDRANT_UPSERT_BATCH_SIZE'];
  assert.equal(Object.keys(SETTING_TEXT).length, keys.length);
  for (const key of keys) {
    for (const part of ['label', 'hint']) {
      assert.ok(SETTING_TEXT[key][part].fa, `${key} ${part} fa`);
      assert.ok(SETTING_TEXT[key][part].en, `${key} ${part} en`);
    }
  }
});

test('automatic fields show the value in use and start from it when switched off', () => {
  const { automaticText, manualStart } = require('./.compiled/components/ServerSettings.js');
  assert.equal(automaticText({ automatic_value: '4' }, 'en'), '4');
  assert.equal(automaticText({ automatic_value: '8-30' }, 'en'), '8–30 (per question)');
  assert.equal(automaticText({ automatic_value: '8-30' }, 'fa'), '8–30 (بسته به هر پرسش)');
  assert.equal(automaticText({ automatic_value: null }, 'en'), 'Automatic');
  assert.equal(manualStart({ key: 'OCR_WORKERS', automatic_value: '10', env_value: '', minimum: 1 }), '10');
  assert.equal(manualStart({ key: 'STRICT_RAG_TOP_K', automatic_value: '8-30', env_value: '', minimum: 1 }), '15');
  assert.equal(manualStart({ key: 'STRICT_RAG_TOP_K', automatic_value: '8-30', env_value: '12', minimum: 1 }), '12');
});
