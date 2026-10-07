import type { AppSettings, Citation, IngestionCapabilities, Language, Message, RAGMode, ResponseVariant, Session, SessionDocument, SourceLocation, SourcePassage } from '../types';
import { summarizeSources } from './citations';

/** Longest excerpt kept per source in the browser (characters). */
export const MAX_SOURCE_TEXT = 1600;

export const STORAGE = {
  sessions: 'parsrag_sessions_v1',
  active: 'parsrag_active_session_id_v1',
  settings: 'parsrag_settings_v1',
};

export const DEFAULT_SETTINGS: AppSettings = {
  language: 'fa', theme: 'light', palette: 'evergreen', defaultMode: 'hybrid', strictThreshold: 0.8,
  dynamicDepth: true, topK: 15, selectedModel: 'gemma3:12b',
  apiModelName: 'google/gemma-4-26b-a4b-it', ollamaModelName: 'gemma3:12b',
  apiBaseUrl: 'https://openrouter.ai/api/v1', ollamaBaseUrl: 'http://localhost:11434', backendUrl: '',
};

export const DEFAULT_INGESTION_CAPABILITIES: IngestionCapabilities = {
  max_files_per_session: 10,
  max_file_size_bytes: 100 * 1024 * 1024,
  max_batch_size_bytes: 500 * 1024 * 1024,
  supported_extensions: [
    '.pdf', '.docx', '.pptx', '.png', '.jpg', '.jpeg', '.webp', '.bmp', '.tif', '.tiff',
    '.txt', '.md', '.markdown', '.json', '.csv', '.tsv', '.html', '.htm', '.xml', '.yaml', '.yml',
    '.log', '.py', '.js', '.jsx', '.ts', '.tsx', '.css', '.sql', '.toml', '.ini', '.cfg',
  ],
  ocr_enabled: true,
};
export const MAX_DOCUMENTS = DEFAULT_INGESTION_CAPABILITIES.max_files_per_session;
export const MAX_FILE_BYTES = DEFAULT_INGESTION_CAPABILITIES.max_file_size_bytes;
export const FILE_ACCEPT = DEFAULT_INGESTION_CAPABILITIES.supported_extensions.join(',');
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
      palette: ['evergreen', 'ocean', 'indigo', 'sienna'].includes(String(value.palette))
        ? value.palette as AppSettings['palette'] : 'evergreen',
      defaultMode: isMode(value.defaultMode) ? value.defaultMode : 'hybrid',
      dynamicDepth: typeof value.dynamicDepth === 'boolean' ? value.dynamicDepth : true,
      topK: typeof value.topK === 'number' && Number.isInteger(value.topK)
        ? Math.max(1, Math.min(50, value.topK)) : 15,
      selectedModel: typeof value.selectedModel === 'string' && value.selectedModel.trim() ? value.selectedModel : DEFAULT_SETTINGS.selectedModel,
      apiModelName: typeof value.apiModelName === 'string' && value.apiModelName.trim() ? value.apiModelName : DEFAULT_SETTINGS.apiModelName,
      ollamaModelName: typeof value.ollamaModelName === 'string' && value.ollamaModelName.trim() ? value.ollamaModelName : DEFAULT_SETTINGS.ollamaModelName,
      apiBaseUrl: typeof value.apiBaseUrl === 'string' && value.apiBaseUrl.trim() ? value.apiBaseUrl : DEFAULT_SETTINGS.apiBaseUrl,
      ollamaBaseUrl: typeof value.ollamaBaseUrl === 'string' && value.ollamaBaseUrl.trim() ? value.ollamaBaseUrl : DEFAULT_SETTINGS.ollamaBaseUrl,
      backendUrl: typeof value.backendUrl === 'string' && isLocalEndpoint(value.backendUrl, origin)
        ? value.backendUrl.trim().replace(/\/+$/, '') : '',
    };
  } catch { return { ...DEFAULT_SETTINGS }; }
}

function parseCitations(value: unknown): Citation[] {
  if (!Array.isArray(value)) return [];
  const sources = new Map<string, Citation>();
  for (const c of value.filter(isRecord).filter(c => typeof c.filename === 'string')) {
    const filename = c.filename as string;
    const locations = Array.isArray(c.locations) ? c.locations.filter(isRecord).filter(location =>
      ['page', 'slide', 'paragraph', 'section'].includes(String(location.kind)) && typeof location.start === 'number'
    ).map(location => ({ kind: location.kind as Citation['locations'][number]['kind'], start: location.start as number, end: typeof location.end === 'number' ? location.end : undefined })) : [];
    const current = sources.get(filename) ?? { filename, locations: [] };
    for (const location of locations) if (!current.locations.some(item => item.kind === location.kind && item.start === location.start && item.end === location.end)) current.locations.push(location);
    sources.set(filename, current);
  }
  return [...sources.values()];
}

function finite(value: unknown): number | undefined {
  return typeof value === 'number' && Number.isFinite(value) ? value : undefined;
}

function parseLocation(value: unknown): SourceLocation | undefined {
  if (!isRecord(value) || !['page', 'slide', 'paragraph', 'section'].includes(String(value.kind))) return undefined;
  const start = finite(value.start);
  if (start === undefined) return undefined;
  const end = finite(value.end);
  return { kind: value.kind as SourceLocation['kind'], start, ...(end !== undefined && end > start ? { end } : {}) };
}

function parseSources(value: unknown): SourcePassage[] | undefined {
  if (!Array.isArray(value)) return undefined;
  const sources = value.filter(isRecord).filter(source => finite(source.n) !== undefined
    && typeof source.filename === 'string' && typeof source.text === 'string').map(source => ({
    n: source.n as number, filename: source.filename as string, text: (source.text as string).slice(0, MAX_SOURCE_TEXT),
    cited: source.cited === true, score: finite(source.score), location: parseLocation(source.location),
  }));
  return sources.length ? sources : undefined;
}

/** Map server chunk metadata to one citable location. */
export function sourceLocation(metadata: Record<string, unknown>): SourceLocation | undefined {
  const range = (kind: SourceLocation['kind'], start: number | undefined, end: number | undefined): SourceLocation | undefined =>
    start === undefined ? undefined : { kind, start, ...(end !== undefined && end > start ? { end } : {}) };
  return range('page', finite(metadata.page), finite(metadata.page_end))
    ?? range('slide', finite(metadata.slide), undefined)
    ?? range('paragraph', finite(metadata.paragraph_start ?? metadata.paragraph), finite(metadata.paragraph_end))
    ?? range('section', finite(metadata.section), undefined);
}

function parseMessages(value: unknown, depth = 0): Message[] {
  if (!Array.isArray(value) || depth > 12) return [];
  return value.filter(isRecord).filter(m => typeof m.id === 'string'
    && typeof m.content === 'string' && ['user', 'assistant', 'system'].includes(String(m.role)))
    .map(m => {
      const variants = Array.isArray(m.variants) ? m.variants.filter(isRecord).filter(variant => typeof variant.id === 'string' && typeof variant.content === 'string').map(variant => ({
        id: variant.id as string, content: variant.content as string,
        timestamp: typeof variant.timestamp === 'number' ? variant.timestamp : 0,
        error: variant.error === true, citations: parseCitations(variant.citations), sources: parseSources(variant.sources),
        prompt: typeof variant.prompt === 'string' ? variant.prompt : undefined,
        continuation: Array.isArray(variant.continuation) ? parseMessages(variant.continuation, depth + 1) : undefined,
      })) : [];
      const activeVariant = variants.length ? Math.max(0, Math.min(variants.length - 1, typeof m.activeVariant === 'number' ? m.activeVariant : variants.length - 1)) : undefined;
      const active = activeVariant === undefined ? undefined : variants[activeVariant];
      return {
        id: m.id as string, role: m.role as Message['role'], content: active?.content ?? m.content as string,
        timestamp: active?.timestamp ?? (typeof m.timestamp === 'number' ? m.timestamp : 0),
        error: active?.error ?? m.error === true, citations: active?.citations ?? parseCitations(m.citations),
        sources: active ? active.sources : parseSources(m.sources),
        variants: variants.length ? variants : undefined, activeVariant,
        parentUserId: typeof m.parentUserId === 'string' ? m.parentUserId : undefined,
      };
    });
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
      chunks: typeof doc.chunks === 'number' ? doc.chunks : undefined,
      sections: typeof doc.sections === 'number' ? doc.sections : undefined,
      notices: Array.isArray(doc.notices) ? doc.notices.filter((notice): notice is string => typeof notice === 'string') : undefined,
      errorMessage: doc.status === 'uploading' || doc.status === 'processing' ? 'interrupted'
        : typeof doc.errorMessage === 'string' ? doc.errorMessage : undefined,
    });
  }
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

/** Builds a readable local fallback while model-generated naming runs. */
export function fallbackConversationTitle(prompt: string): string {
  const cleaned = prompt.replace(/[`*_#>\[\]()]/g, ' ').replace(/\s+/g, ' ').trim();
  if (cleaned.length <= 48) return cleaned;
  const shortened = cleaned.slice(0, 48).replace(/\s+\S*$/, '').trim();
  return `${shortened || cleaned.slice(0, 48)}…`;
}

export type UploadIssue = 'format' | 'size' | 'empty' | 'duplicate' | 'limit';
export function validateUploads(
  files: Pick<File, 'name' | 'size'>[],
  documents: SessionDocument[],
  capabilities = DEFAULT_INGESTION_CAPABILITIES,
) {
  const accepted: number[] = [];
  const rejected: { name: string; reason: UploadIssue }[] = [];
  const names = new Set(documents.map(d => d.name));
  files.forEach((file, index) => {
    let reason: UploadIssue | undefined;
    const lowerName = file.name.toLocaleLowerCase('en-US');
    if (!capabilities.supported_extensions.some(extension => lowerName.endsWith(extension))) reason = 'format';
    else if (file.size > capabilities.max_file_size_bytes) reason = 'size';
    else if (file.size === 0) reason = 'empty';
    else if (names.has(file.name)) reason = 'duplicate';
    else if (documents.length + accepted.length >= capabilities.max_files_per_session) reason = 'limit';
    if (reason) rejected.push({ name: file.name, reason });
    else { accepted.push(index); names.add(file.name); }
  });
  return { accepted, rejected };
}

export function buildQuery(session: Session, settings: AppSettings, prompt: string) {
  const indexed = session.documents.filter(d => d.status === 'indexed');
  const selected = indexed.filter(d => d.enabled !== false).map(d => d.name);
  return {
    prompt: prompt.trim(), mode: session.ragMode, session_id: session.id,
    top_k: settings.dynamicDepth ? null : settings.topK,
    file_filter: session.ragMode === 'llm-only' || !indexed.length ? null : selected,
    chat_history: session.messages.filter(m => !m.error && m.role !== 'system').slice(-10)
      .map(({ role, content }) => ({ role, content })),
  };
}

/** Read an answer: numbered sources (cited ones flagged) and a per-file summary. */
export function parseAnswer(value: unknown): { answer: string; citations: Citation[]; sources: SourcePassage[] } {
  if (!isRecord(value) || typeof value.answer !== 'string' || !value.answer.trim()) {
    throw new Error('invalid_response');
  }
  const nodes = Array.isArray(value.source_nodes) ? value.source_nodes : [];
  const cited = new Set(Array.isArray(value.cited) ? value.cited.filter(number => Number.isInteger(number)) : []);
  const sources: SourcePassage[] = [];
  nodes.forEach((node, index) => {
    if (!isRecord(node)) return;
    const metadata = isRecord(node.metadata) ? node.metadata : {};
    sources.push({
      n: index + 1,
      filename: typeof metadata.filename === 'string' ? metadata.filename : 'Document',
      location: sourceLocation(metadata),
      text: typeof node.text === 'string' ? node.text.slice(0, MAX_SOURCE_TEXT) : '',
      cited: cited.has(index + 1),
      score: finite(node.score),
    });
  });
  const used = sources.filter(source => source.cited);
  return { answer: value.answer, citations: summarizeSources(used.length ? used : sources), sources };
}

export function mergeRemoteDocuments(current: SessionDocument[], remote: unknown): SessionDocument[] {
  if (!Array.isArray(remote) || !remote.every(name => typeof name === 'string')) return current;
  const names = [...new Set(remote as string[])];
  const merged: SessionDocument[] = names.map(name => ({
    ...current.find(doc => doc.name === name), name, status: 'indexed', errorMessage: undefined,
  }));
  merged.push(...current.filter(doc => doc.status !== 'indexed' && !names.includes(doc.name)));
  return merged;
}

export function appendResponseVariant(message: Message, variant: ResponseVariant): Message {
  const variants = message.variants?.length ? [...message.variants, variant] : [
    { id: `${message.id}-original`, content: message.content, citations: message.citations, sources: message.sources, error: message.error, timestamp: message.timestamp, prompt: variant.prompt },
    variant,
  ];
  return { ...message, content: variant.content, citations: variant.citations, sources: variant.sources, error: variant.error, timestamp: variant.timestamp, variants, activeVariant: variants.length - 1 };
}

export function selectResponseVariant(message: Message, index: number): Message {
  const variant = message.variants?.[index];
  return variant ? { ...message, content: variant.content, citations: variant.citations, sources: variant.sources, error: variant.error, timestamp: variant.timestamp, activeVariant: index } : message;
}

export function prepareTurnRegeneration(messages: Message[], userId: string, assistantId: string | undefined, prompt: string, edit: boolean) {
  const userIndex = messages.findIndex(message => message.id === userId);
  if (userIndex < 0) return { history: messages, visible: messages };
  const assistantIndex = assistantId ? messages.findIndex(message => message.id === assistantId) : -1;
  const lastKept = assistantIndex > userIndex ? assistantIndex : userIndex;
  const currentPrompt = messages[userIndex].content;
  const assistant = assistantIndex > userIndex
    ? snapshotActiveBranch(messages[assistantIndex], currentPrompt, messages.slice(assistantIndex + 1))
    : undefined;
  return {
    history: messages.slice(0, userIndex),
    visible: messages.slice(0, lastKept + 1).map(message => {
      if (message.id === userId && edit) return { ...message, content: prompt.trim(), timestamp: Date.now() };
      if (assistant && message.id === assistant.id) return assistant;
      return message;
    }),
  };
}

function snapshotActiveBranch(message: Message, prompt: string, continuation: Message[]): Message {
  const variants: ResponseVariant[] = message.variants?.length ? message.variants.map(variant => ({
    ...variant, prompt: variant.prompt ?? prompt,
  })) : [{
    id: `${message.id}-original`, content: message.content, timestamp: message.timestamp,
    citations: message.citations, sources: message.sources, error: message.error, prompt,
  }];
  const activeVariant = Math.max(0, Math.min(variants.length - 1, message.activeVariant ?? variants.length - 1));
  variants[activeVariant] = { ...variants[activeVariant], prompt, continuation };
  return { ...message, variants, activeVariant };
}

/** Switches one answer branch together with its originating prompt and continuation. */
export function selectConversationBranch(messages: Message[], assistantId: string, index: number): Message[] {
  const assistantIndex = messages.findIndex(message => message.id === assistantId && message.role === 'assistant');
  if (assistantIndex < 0) return messages;
  const assistant = messages[assistantIndex];
  let userIndex = assistant.parentUserId
    ? messages.findIndex(message => message.id === assistant.parentUserId) : -1;
  if (userIndex < 0) {
    for (let cursor = assistantIndex - 1; cursor >= 0; cursor -= 1) {
      if (messages[cursor].role === 'user') { userIndex = cursor; break; }
    }
  }
  if (userIndex < 0) return messages;
  const snapshotted = snapshotActiveBranch(assistant, messages[userIndex].content, messages.slice(assistantIndex + 1));
  const target = snapshotted.variants?.[index];
  if (!target) return messages;
  const prefix = messages.slice(0, assistantIndex + 1).map(message => {
    if (message.id === messages[userIndex].id) return { ...message, content: target.prompt ?? message.content };
    if (message.id === assistantId) return {
      ...snapshotted, content: target.content, citations: target.citations, sources: target.sources, error: target.error,
      timestamp: target.timestamp, activeVariant: index,
    };
    return message;
  });
  return [...prefix, ...(target.continuation ?? [])];
}
