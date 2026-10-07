import type { AppCapabilities, IngestedFile, ModelConfiguration, ModelProvider, OllamaModel, QueryStage } from '../types';

/** A failed request with the server's stable error code ('network' when unreachable). */
export class ApiError extends Error {
  constructor(public readonly code: string, public readonly status?: number, public readonly detail?: string) {
    super(code);
    this.name = 'ApiError';
  }
}

/** Read `{ detail, code }` (or FastAPI's `{ detail: { code } }`) from an error body. */
export function errorFromBody(status: number, body: string): ApiError {
  let code = 'request_failed';
  let detail: string | undefined;
  try {
    const value: unknown = JSON.parse(body);
    if (typeof value === 'object' && value !== null) {
      const record = value as Record<string, unknown>;
      if (typeof record.code === 'string') code = record.code;
      if (typeof record.detail === 'string') detail = record.detail;
      else if (typeof record.detail === 'object' && record.detail !== null) {
        const nested = record.detail as Record<string, unknown>;
        if (typeof nested.code === 'string') code = nested.code;
      }
    }
  } catch { /* Non-JSON bodies keep the generic code. */ }
  return new ApiError(code, status, detail);
}

async function failure(response: Response): Promise<ApiError> {
  return errorFromBody(response.status, await response.text().catch(() => ''));
}

function parseIngested(body: string): IngestedFile[] {
  try {
    const value: unknown = JSON.parse(body);
    const files = typeof value === 'object' && value !== null ? (value as { files?: unknown }).files : undefined;
    if (!Array.isArray(files)) return [];
    return files.filter((file): file is Record<string, unknown> => typeof file === 'object' && file !== null && typeof (file as { filename?: unknown }).filename === 'string')
      .map(file => ({
        filename: file.filename as string,
        chunks: typeof file.chunks === 'number' ? file.chunks : undefined,
        sections: typeof file.sections === 'number' ? file.sections : undefined,
        notices: Array.isArray(file.notices) ? file.notices.filter((notice): notice is string => typeof notice === 'string') : [],
      }));
  } catch { return []; }
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
    return (await this.healthStatus(signal)) === 'online';
  }

  async healthStatus(signal?: AbortSignal): Promise<'online' | 'preparing' | 'offline'> {
    try {
      const response = await fetch(this.url('/health/ready'), { signal });
      if (response.ok) return 'online';
      if (response.status === 503) {
        const payload: unknown = await response.json();
        if (typeof payload === 'object' && payload !== null && 'status' in payload && payload.status === 'preparing') return 'preparing';
      }
      return 'offline';
    } catch {
      return 'offline';
    }
  }

  async files(sessionId: string, signal?: AbortSignal): Promise<unknown> {
    const response = await fetch(this.url(`/sessions/${encodeURIComponent(sessionId)}/files`), { signal });
    if (!response.ok) throw await failure(response);
    return response.json() as Promise<unknown>;
  }

  async capabilities(signal?: AbortSignal): Promise<AppCapabilities> {
    const response = await fetch(this.url('/capabilities'), { signal });
    if (!response.ok) throw await failure(response);
    return response.json() as Promise<AppCapabilities>;
  }

  async query(payload: unknown, signal?: AbortSignal): Promise<unknown> {
    let response: Response;
    try {
      response = await fetch(this.url('/query'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
        signal,
      });
    } catch (error) {
      if (signal?.aborted) throw error;
      throw new ApiError('network');
    }
    if (!response.ok) throw await failure(response);
    return response.json() as Promise<unknown>;
  }

  async conversationTitle(prompt: string, language: 'fa' | 'en', signal?: AbortSignal): Promise<string> {
    const response = await fetch(this.url('/conversations/title'), {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ prompt, language }), signal,
    });
    if (!response.ok) throw new ApiError('request_failed', response.status);
    const payload: unknown = await response.json();
    if (typeof payload !== 'object' || payload === null || !('title' in payload)
      || typeof payload.title !== 'string' || !payload.title.trim()) throw new ApiError('request_failed');
    return payload.title.trim();
  }

  async queryProgress(requestId: string, signal?: AbortSignal): Promise<QueryStage | null> {
    const response = await fetch(this.url(`/queries/${encodeURIComponent(requestId)}/progress`), { signal });
    if (response.status === 404) return null;
    if (!response.ok) throw new ApiError('request_failed', response.status);
    const payload: unknown = await response.json();
    if (typeof payload !== 'object' || payload === null || !('stage' in payload)) return null;
    const stage = payload.stage;
    return stage === 'understanding' || stage === 'retrieving' || stage === 'generating' || stage === 'complete' || stage === 'failed' ? stage : null;
  }

  async modelConfiguration(signal?: AbortSignal): Promise<ModelConfiguration> {
    const response = await fetch(this.url('/models/configuration'), { signal });
    if (!response.ok) throw new ApiError('request_failed', response.status);
    return response.json() as Promise<ModelConfiguration>;
  }

  async configureModel(payload: { provider: ModelProvider; model_name: string; base_url: string; api_key?: string; disclosure_acknowledged?: boolean }, signal?: AbortSignal): Promise<ModelConfiguration> {
    const response = await fetch(this.url('/models/configuration'), { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload), signal });
    if (!response.ok) throw new ApiError('request_failed', response.status);
    return response.json() as Promise<ModelConfiguration>;
  }

  async ollamaModels(baseUrl: string, signal?: AbortSignal): Promise<OllamaModel[]> {
    const response = await fetch(this.url(`/models/ollama?base_url=${encodeURIComponent(baseUrl)}`), { signal });
    if (!response.ok) throw new ApiError('request_failed', response.status);
    return response.json() as Promise<OllamaModel[]>;
  }

  async ingest(file: File, sessionId: string, signal?: AbortSignal, onProgress?: (percent: number) => void): Promise<IngestedFile[]> {
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
        if (request.status >= 200 && request.status < 300) { onProgress?.(100); resolve(parseIngested(request.responseText)); return; }
        reject(errorFromBody(request.status, request.responseText));
      };
      request.onerror = () => reject(new ApiError('network'));
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

  async reuseDocument(sessionId: string, sourceSessionId: string, filename: string, signal?: AbortSignal): Promise<void> {
    const response = await fetch(this.url(`/sessions/${encodeURIComponent(sessionId)}/files/reuse`), {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ source_session_id: sourceSessionId, filename }), signal,
    });
    if (!response.ok) throw new ApiError('request_failed', response.status);
  }

  async deleteSession(sessionId: string, signal?: AbortSignal): Promise<void> {
    const response = await fetch(this.url(`/sessions/${encodeURIComponent(sessionId)}`), { method: 'DELETE', signal });
    if (!response.ok) throw new ApiError('request_failed', response.status);
  }
}
