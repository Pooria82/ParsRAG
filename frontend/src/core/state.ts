import type { AppSettings, Citation, Language, Message, RAGMode, Session, SessionDocument } from '../types';

export const STORAGE = {
  sessions: 'parsrag_sessions_v1',
  active: 'parsrag_active_session_id_v1',
  settings: 'parsrag_settings_v1',
};

export const DEFAULT_SETTINGS: AppSettings = {
  language: 'fa', theme: 'light', defaultMode: 'hybrid', strictThreshold: 0.8,
  dynamicDepth: true, topK: 15, selectedModel: 'llama3.1:8b', backendUrl: '',
};

export const MAX_DOCUMENTS = 5;
export const MAX_FILE_BYTES = 50 * 1024 * 1024;
export const FILE_ACCEPT = '.pdf,.docx,.pptx';
export const MODES: RAGMode[] = ['hybrid', 'strict', 'llm-only'];

export function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

export function isMode(value: unknown): value is RAGMode {
  return MODES.includes(value as RAGMode);
}

/** Endpoints stay on the current origin or a local loopback service. */
export function isLocalEndpoint(value: string, origin = 'http://localhost:3000'): boolean {
  if (!value.trim()) return true;
  try {
    const url = new URL(value);
    return ['http:', 'https:'].includes(url.protocol) && !url.username && !url.password
      && !url.search && !url.hash && (url.origin === new URL(origin).origin
        || ['localhost', '127.0.0.1', '[::1]'].includes(url.hostname));
  } catch { return false; }
}

export function parseSettings(raw: string | null, origin?: string): AppSettings {
  try {
    const value: unknown = JSON.parse(raw ?? 'null');
    if (!isRecord(value)) return { ...DEFAULT_SETTINGS };
    return {
      ...DEFAULT_SETTINGS,
      language: value.language === 'en' ? 'en' : 'fa',
      theme: value.theme === 'dark' ? 'dark' : 'light',
      defaultMode: isMode(value.defaultMode) ? value.defaultMode : 'hybrid',
      dynamicDepth: typeof value.dynamicDepth === 'boolean' ? value.dynamicDepth : true,
      topK: typeof value.topK === 'number' && Number.isInteger(value.topK)
        ? Math.max(1, Math.min(50, value.topK)) : 15,
      backendUrl: typeof value.backendUrl === 'string' && isLocalEndpoint(value.backendUrl, origin)
        ? value.backendUrl.trim().replace(/\/+$/, '') : '',
    };
  } catch { return { ...DEFAULT_SETTINGS }; }
}

function parseCitations(value: unknown): Citation[] {
  if (!Array.isArray(value)) return [];
  return value.filter(isRecord).filter(c => typeof c.body === 'string').map(c => ({
    title: typeof c.title === 'string' ? c.title : '',
    filename: typeof c.filename === 'string' ? c.filename : 'Document',
    body: c.body as string,
    score: typeof c.score === 'number' && Number.isFinite(c.score) ? c.score : 0,
  }));
}

function parseMessages(value: unknown): Message[] {
  if (!Array.isArray(value)) return [];
  return value.filter(isRecord).filter(m => typeof m.id === 'string'
    && typeof m.content === 'string' && ['user', 'assistant', 'system'].includes(String(m.role)))
    .map(m => ({
      id: m.id as string, role: m.role as Message['role'], content: m.content as string,
      timestamp: typeof m.timestamp === 'number' ? m.timestamp : 0,
      error: m.error === true, citations: parseCitations(m.citations),
    }));
}

function parseDocuments(value: unknown): SessionDocument[] {
  if (!Array.isArray(value)) return [];
  const seen = new Set<string>();
  const docs: SessionDocument[] = [];
  for (const doc of value) {
    if (!isRecord(doc) || typeof doc.name !== 'string' || seen.has(doc.name)) continue;
    seen.add(doc.name);
    docs.push({
      name: doc.name, size: typeof doc.size === 'number' ? doc.size : undefined,
      status: doc.status === 'indexed' ? 'indexed' : 'error',
      enabled: doc.enabled !== false,
      errorMessage: doc.status === 'uploading' ? 'interrupted'
        : typeof doc.errorMessage === 'string' ? doc.errorMessage : undefined,
    });
  }
  // An empty file_filter means "all files" to the API, so retain one selection.
  const indexed = docs.filter(d => d.status === 'indexed');
  if (indexed.length && indexed.every(d => d.enabled === false)) indexed[0].enabled = true;
  return docs;
}

export function parseSessions(raw: string | null): Session[] {
  try {
    const value: unknown = JSON.parse(raw ?? 'null');
    if (!Array.isArray(value)) return [];
    const seen = new Set<string>();
    return value.filter(isRecord).filter(s => {
      if (typeof s.id !== 'string' || !/^[a-zA-Z0-9_-]{1,64}$/.test(s.id) || seen.has(s.id)) return false;
      seen.add(s.id);
      return true;
    }).map(s => ({
      id: s.id as string, title: typeof s.title === 'string' ? s.title : '',
      createdAt: typeof s.createdAt === 'number' ? s.createdAt : 0,
      updatedAt: typeof s.updatedAt === 'number' ? s.updatedAt : 0,
      ragMode: isMode(s.ragMode) ? s.ragMode : 'hybrid',
      messages: parseMessages(s.messages), documents: parseDocuments(s.documents),
      draft: typeof s.draft === 'string' ? s.draft : '',
    }));
  } catch { return []; }
}

export function createSession(language: Language, mode: RAGMode): Session {
  return {
    id: `session_${crypto.randomUUID()}`,
    title: language === 'fa' ? 'گفت‌وگوی تازه' : 'New conversation',
    createdAt: Date.now(), updatedAt: Date.now(), documents: [], messages: [], ragMode: mode, draft: '',
  };
}

export type UploadIssue = 'format' | 'size' | 'empty' | 'duplicate' | 'limit';
export function validateUploads(files: Pick<File, 'name' | 'size'>[], documents: SessionDocument[]) {
  const accepted: number[] = [];
  const rejected: { name: string; reason: UploadIssue }[] = [];
  const names = new Set(documents.map(d => d.name));
  files.forEach((file, index) => {
    let reason: UploadIssue | undefined;
    if (!/\.(pdf|docx|pptx)$/i.test(file.name)) reason = 'format';
    else if (file.size > MAX_FILE_BYTES) reason = 'size';
    else if (file.size === 0) reason = 'empty';
    else if (names.has(file.name)) reason = 'duplicate';
    else if (documents.length + accepted.length >= MAX_DOCUMENTS) reason = 'limit';
    if (reason) rejected.push({ name: file.name, reason });
    else { accepted.push(index); names.add(file.name); }
  });
  return { accepted, rejected };
}

export function buildQuery(session: Session, settings: AppSettings, prompt: string) {
  const indexed = session.documents.filter(d => d.status === 'indexed');
  const selected = indexed.filter(d => d.enabled !== false).map(d => d.name);
  if (session.ragMode !== 'llm-only' && indexed.length && !selected.length) {
    throw new Error('Select at least one document.');
  }
  return {
    prompt: prompt.trim(), mode: session.ragMode, session_id: session.id,
    top_k: settings.dynamicDepth ? null : settings.topK,
    file_filter: session.ragMode === 'llm-only' || !selected.length ? null : selected,
    chat_history: session.messages.filter(m => !m.error && m.role !== 'system').slice(-10)
      .map(({ role, content }) => ({ role, content })),
  };
}

export function parseAnswer(value: unknown): { answer: string; citations: Citation[] } {
  if (!isRecord(value) || typeof value.answer !== 'string' || !value.answer.trim()) {
    throw new Error('invalid_response');
  }
  const nodes = Array.isArray(value.source_nodes) ? value.source_nodes : [];
  return { answer: value.answer, citations: nodes.filter(isRecord).map((node, index) => ({
    title: String(index + 1),
    filename: isRecord(node.metadata) && typeof node.metadata.filename === 'string'
      ? node.metadata.filename : 'Document',
    body: typeof node.text === 'string' ? node.text : '',
    score: typeof node.score === 'number' && Number.isFinite(node.score) ? node.score : 0,
  })) };
}

export function mergeRemoteDocuments(current: SessionDocument[], remote: unknown): SessionDocument[] {
  if (!Array.isArray(remote) || !remote.every(name => typeof name === 'string')) return current;
  const names = [...new Set(remote as string[])];
  const merged: SessionDocument[] = names.map(name => ({
    ...current.find(doc => doc.name === name), name, status: 'indexed', errorMessage: undefined,
  }));
  merged.push(...current.filter(doc => doc.status !== 'indexed' && !names.includes(doc.name)));
  if (merged.some(d => d.status === 'indexed') && !merged.some(d => d.status === 'indexed' && d.enabled !== false)) {
    merged.find(d => d.status === 'indexed')!.enabled = true;
  }
  return merged;
}
