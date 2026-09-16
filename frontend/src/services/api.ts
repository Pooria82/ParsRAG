export type ApiErrorCode = 'request_failed' | 'scanned_pdf';

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

  async ingest(file: File, sessionId: string, signal?: AbortSignal): Promise<void> {
    const body = new FormData();
    body.append('files', file);
    body.append('session_id', sessionId);
    const response = await fetch(this.url('/ingest'), { method: 'POST', body, signal });
    if (response.ok) return;

    const payload: unknown = await response.json().catch(() => null);
    const detail = typeof payload === 'object' && payload !== null && 'detail' in payload && typeof payload.detail === 'string'
      ? payload.detail : '';
    throw new ApiError(detail.includes('Scanned PDFs') ? 'scanned_pdf' : 'request_failed', response.status);
  }

  async deleteSession(sessionId: string, signal?: AbortSignal): Promise<void> {
    const response = await fetch(this.url(`/sessions/${encodeURIComponent(sessionId)}`), { method: 'DELETE', signal });
    if (!response.ok) throw new ApiError('request_failed', response.status);
  }
}
