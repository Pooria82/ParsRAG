export type ApiErrorCode = 'request_failed' | 'scanned_pdf';
import type { ModelConfiguration, ModelProvider, OllamaModel } from '../types';

export class ApiError extends Error {
  constructor(public readonly code: ApiErrorCode, public readonly status?: number) {
    super(code);
    this.name = 'ApiError';
  }
}

export class ParsRagApiClient {
  private readonly baseUrl: string;

  constructor(baseUrl: string) {
    this.baseUrl = baseUrl.replace(/\/+$/, '');
  }

  private url(path: string): string {
    return `${this.baseUrl}${path}`;
  }

  async isHealthy(signal?: AbortSignal): Promise<boolean> {
    try {
      const response = await fetch(this.url('/health'), { signal });
      return response.ok;
    } catch {
      return false;
    }
  }

  async files(sessionId: string, signal?: AbortSignal): Promise<unknown> {
    const response = await fetch(this.url(`/sessions/${encodeURIComponent(sessionId)}/files`), { signal });
    if (!response.ok) throw new ApiError('request_failed', response.status);
    return response.json() as Promise<unknown>;
  }

  async query(payload: unknown, signal?: AbortSignal): Promise<unknown> {
    const response = await fetch(this.url('/query'), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
      signal,
    });
    if (!response.ok) throw new ApiError('request_failed', response.status);
    return response.json() as Promise<unknown>;
  }

  async modelConfiguration(signal?: AbortSignal): Promise<ModelConfiguration> {
    const response = await fetch(this.url('/models/configuration'), { signal });
    if (!response.ok) throw new ApiError('request_failed', response.status);
    return response.json() as Promise<ModelConfiguration>;
  }

  async configureModel(payload: { provider: ModelProvider; model_name: string; base_url: string; api_key?: string }, signal?: AbortSignal): Promise<ModelConfiguration> {
    const response = await fetch(this.url('/models/configuration'), { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload), signal });
    if (!response.ok) throw new ApiError('request_failed', response.status);
    return response.json() as Promise<ModelConfiguration>;
  }

  async ollamaModels(baseUrl: string, signal?: AbortSignal): Promise<OllamaModel[]> {
    const response = await fetch(this.url(`/models/ollama?base_url=${encodeURIComponent(baseUrl)}`), { signal });
    if (!response.ok) throw new ApiError('request_failed', response.status);
    return response.json() as Promise<OllamaModel[]>;
  }

  async ingest(file: File, sessionId: string, signal?: AbortSignal, onProgress?: (percent: number) => void): Promise<void> {
    const body = new FormData();
    body.append('files', file);
    body.append('session_id', sessionId);
    return new Promise((resolve, reject) => {
      const request = new XMLHttpRequest();
      const abort = () => request.abort();
      request.open('POST', this.url('/ingest'));
      request.upload.onprogress = event => {
        if (event.lengthComputable) onProgress?.(Math.min(100, Math.round((event.loaded / event.total) * 100)));
      };
      request.onload = () => {
        signal?.removeEventListener('abort', abort);
        if (request.status >= 200 && request.status < 300) { onProgress?.(100); resolve(); return; }
        let detail = '';
        try { const value: unknown = JSON.parse(request.responseText); if (typeof value === 'object' && value !== null && 'detail' in value && typeof value.detail === 'string') detail = value.detail; } catch { /* invalid server body */ }
        reject(new ApiError(detail.includes('Scanned PDFs') ? 'scanned_pdf' : 'request_failed', request.status));
      };
      request.onerror = () => reject(new ApiError('request_failed'));
      request.onabort = () => reject(new DOMException('Aborted', 'AbortError'));
      signal?.addEventListener('abort', abort, { once: true });
      if (signal?.aborted) abort(); else request.send(body);
    });
  }

  async deleteDocument(sessionId: string, filename: string, signal?: AbortSignal): Promise<void> {
    const response = await fetch(this.url(`/sessions/${encodeURIComponent(sessionId)}/files`), {
      method: 'DELETE', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ filename }), signal,
    });
    if (!response.ok) throw new ApiError('request_failed', response.status);
  }

  async deleteSession(sessionId: string, signal?: AbortSignal): Promise<void> {
    const response = await fetch(this.url(`/sessions/${encodeURIComponent(sessionId)}`), { method: 'DELETE', signal });
    if (!response.ok) throw new ApiError('request_failed', response.status);
  }
}
