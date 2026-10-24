import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { AlertCircle, FileText, X } from 'lucide-react';
import { Sidebar } from './components/Sidebar';
import { Header } from './components/Header';
import { DocumentCenter } from './components/DocumentCenter';
import { ChatFeed } from './components/ChatFeed';
import { Composer } from './components/Composer';
import { SettingsModal } from './components/SettingsModal';
import { Welcome } from './components/Welcome';
import { BootSequence } from './components/BootSequence';
import { WorkspaceTour, type TourStage } from './components/WorkspaceTour';
import { useMediaQuery } from './hooks/useMediaQuery';
import { useThemeTransition } from './hooks/useThemeTransition';
import { useLanguageTransition } from './hooks/useLanguageTransition';
import { usePersistentWorkspace } from './hooks/usePersistentWorkspace';
import { usePwa } from './hooks/usePwa';
import { ApiError, ParsRagApiClient } from './services/api';
import type { AppSettings, IngestionCapabilities, Message, ModelConfiguration, ModelConnectionState, QueryStage, ReleaseNote, UpdateStatus, ResponseVariant, Session, SessionDocument } from './types';
import { translations } from './i18n/translations';
import { queryErrorMessage, uploadErrorMessage } from './i18n/errors';
import { answerGrounding, answerTo, suggestionKey, appendResponseVariant, buildQuery, createSession, DEFAULT_INGESTION_CAPABILITIES, fallbackConversationTitle, mergeRemoteDocuments, parseAnswer, placeAnswer, placeNote, prepareTurnRegeneration, selectConversationBranch, STORAGE, validateUploads } from './core/state';
import { flushPendingDeletions, parsePendingDeletions } from './core/storage';
import { isApplePlatform, resolveShortcut } from './core/shortcuts';
import { createBackup, downloadText, mergeSessions, parseBackup } from './core/workspaceTransfer';
import { citedNumbers } from './core/citations';
import { APP_VERSION } from './core/appVersion';
import { isNewerVersion, notesToShow, offeredUpdate, UPDATE_STORAGE } from './core/updates';
import { UpdateDialog } from './components/UpdateDialog';
import { WhatsNewDialog } from './components/WhatsNewDialog';

/**
 * Longest wait for any stream event. The server sends a ping every 15 seconds
 * while it works, so this only ends a connection that has really gone quiet.
 */
const STREAM_IDLE_MS = 60000;

/** The service could not be reached (as opposed to answering with an error). */
function unreachable(error: unknown): boolean {
  return (error instanceof ApiError && error.code === 'network')
    || (error instanceof DOMException && ['TimeoutError', 'AbortError'].includes(error.name));
}

function readStored(key: string, storage: () => Storage = () => localStorage): string | null {
  try { return storage().getItem(key); } catch { return null; }
}

function writeStored(key: string, value: string, storage: () => Storage = () => localStorage): void {
  try { storage().setItem(key, value); } catch { /* Shown again next time; nothing breaks. */ }
}

function readPendingDeletions(): string[] {
  try { return parsePendingDeletions(localStorage.getItem(STORAGE.pendingDeletions)); } catch { return []; }
}

function writePendingDeletions(ids: string[]): void {
  try {
    if (ids.length) localStorage.setItem(STORAGE.pendingDeletions, JSON.stringify(ids));
    else localStorage.removeItem(STORAGE.pendingDeletions);
  } catch { /* The server copy stays until the conversation is deleted again. */ }
}

export function App() {
  const { settings, setSettings, sessions, setSessions, activeId, setActiveId, storageError, saveNow } = usePersistentWorkspace();
  const pwa = usePwa();
  const isMobile = useMediaQuery('(max-width: 760px)');
  const [sidebarOpen, setSidebarOpen] = useState(!isMobile);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [documentsOpen, setDocumentsOpen] = useState(false);
  const [generatingId, setGeneratingId] = useState<string>();
  const [uploadingId, setUploadingId] = useState<string>();
  const [connection, setConnection] = useState<'checking' | 'preparing' | 'online' | 'offline'>('checking');
  const [notice, setNotice] = useState<string | null>(null);
  const [uploadError, setUploadError] = useState<{ sessionId: string; text: string } | null>(null);
  const [queryProgress, setQueryProgress] = useState<{ sessionId: string; stage: QueryStage }>();
  const [streamDraft, setStreamDraft] = useState<{ sessionId: string; messageId?: string; afterUserId?: string; content: string; sourceCount?: number }>();
  const [deletingDocuments, setDeletingDocuments] = useState<ReadonlySet<string>>(new Set());
  const suggestionRunRef = useRef<object | null>(null);
  const [suggesting, setSuggesting] = useState<string>();
  const [revealingMessageId, setRevealingMessageId] = useState<string>();
  const [modelRuntime, setModelRuntime] = useState<ModelConfiguration>();
  const [modelState, setModelState] = useState<ModelConnectionState | null>(null);
  const [updateStatus, setUpdateStatus] = useState<UpdateStatus | null>(null);
  const [updateOpen, setUpdateOpen] = useState(false);
  const [skippedUpdate, setSkippedUpdate] = useState(() => readStored(UPDATE_STORAGE.skippedUpdate));
  const [whatsNew, setWhatsNew] = useState<{ version: string; notes: ReleaseNote[] } | null>(null);
  const [ingestionCapabilities, setIngestionCapabilities] = useState<IngestionCapabilities>(DEFAULT_INGESTION_CAPABILITIES);
  const [focusToken, setFocusToken] = useState(0);
  const [searchFocusToken, setSearchFocusToken] = useState(0);
  const [guideOpen, setGuideOpen] = useState(false);
  const [tourStage, setTourStage] = useState<TourStage>({});
  const [guideEligible] = useState(() => { try { return localStorage.getItem('parsrag_tour_v1') !== 'done'; } catch { return true; } });
  const queryRef = useRef<{ controller: AbortController; sessionId: string } | null>(null);
  const progressRef = useRef<AbortController | undefined>(undefined);
  const uploadRef = useRef(false);
  const healthRef = useRef<AbortController | undefined>(undefined);
  const sessionsRef = useRef(sessions);
  sessionsRef.current = sessions;
  const active = sessions.find(s => s.id === activeId) ?? sessions[0];
  const t = translations[settings.language];
  const endpoint = settings.backendUrl.replace(/\/+$/, '');
  const api = useMemo(() => new ParsRagApiClient(endpoint), [endpoint]);
  const busy = Boolean(generatingId || uploadingId);

  const updateSession = useCallback((id: string, update: (session: Session) => Session) => {
    setSessions(previous => previous.map(session => session.id === id ? update(session) : session));
  }, []);

  useEffect(() => { setSidebarOpen(!isMobile); }, [isMobile]);
  useEffect(() => {
    if (!guideEligible) return;
    const timeout = window.setTimeout(() => setGuideOpen(true), 1200);
    return () => window.clearTimeout(timeout);
  }, [guideEligible]);
  const closeGuide = () => { setGuideOpen(false); setDocumentsOpen(false); setSettingsOpen(false); setTourStage({}); try { localStorage.setItem('parsrag_tour_v1', 'done'); } catch { /* The tour remains dismissible when storage is unavailable. */ } };
  const changeTourStage = useCallback((stage: TourStage) => {
    setTourStage(stage);
    setDocumentsOpen(stage.surface === 'documents');
    setSettingsOpen(stage.surface === 'settings');
  }, []);
  useEffect(() => {
    document.documentElement.dir = settings.language === 'fa' ? 'rtl' : 'ltr';
    document.documentElement.lang = settings.language;
    document.documentElement.dataset.theme = settings.theme;
    document.documentElement.dataset.palette = settings.palette;
    document.title = settings.language === 'fa' ? 'پارس‌رگ — از پرسش، به بینش' : 'ParsRAG — A clearer perspective';
    const themeColor = getComputedStyle(document.documentElement).getPropertyValue('--canvas').trim();
    document.querySelector<HTMLMetaElement>('meta[name="theme-color"]')?.setAttribute('content', themeColor);
  }, [settings.language, settings.theme, settings.palette]);

  const checkHealth = useCallback(async () => {
    healthRef.current?.abort();
    const controller = new AbortController();
    healthRef.current = controller;
    const timeout = setTimeout(() => controller.abort(), 5000);
    try {
      const status = await api.healthStatus(controller.signal);
      if (healthRef.current === controller) {
        setConnection(status);
        if (status === 'online') {
          try {
            const [configuration, capabilities] = await Promise.all([
              api.modelConfiguration(controller.signal), api.capabilities(controller.signal),
            ]);
            setModelRuntime(configuration);
            setIngestionCapabilities(capabilities.ingestion);
            // The app can be ready while Ollama is stopped or the API refuses
            // the key. The server waits up to 5 s for the model, so this waits
            // longer; a check that still fails keeps the last known state.
            const model = await api.modelStatus(AbortSignal.timeout(9000)).catch(() => undefined);
            if (model !== undefined && healthRef.current === controller) setModelState(model);
            // Served from the server's daily check; offline it simply stays unknown.
            void api.updates(false, controller.signal).then(setUpdateStatus).catch(() => undefined);
          } catch { setModelRuntime(undefined); setModelState(null); }
        }
      }
    } catch {
      if (healthRef.current === controller) setConnection('offline');
    } finally { clearTimeout(timeout); }
  }, [api]);

  useEffect(() => {
    setConnection('checking'); void checkHealth();
    const interval = setInterval(() => void checkHealth(), 30000);
    return () => { clearInterval(interval); healthRef.current?.abort(); healthRef.current = undefined; };
  }, [checkHealth]);

  // Cancel stale synchronization when changing conversations, endpoints, or uploading.
  useEffect(() => {
    if (connection !== 'online' || uploadingId === active.id) return;
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 10000);
    void (async () => {
      try {
        const remote = await api.files(active.id, controller.signal);
        if (!controller.signal.aborted) updateSession(active.id, s => ({ ...s, documents: mergeRemoteDocuments(s.documents, remote) }));
      } catch { /* Keep the last known documents when the service is unavailable. */ }
      finally { clearTimeout(timeout); }
    })();
    return () => { controller.abort(); clearTimeout(timeout); };
  }, [active.id, api, connection, uploadingId, updateSession]);
  useEffect(() => () => { queryRef.current?.controller.abort(); progressRef.current?.abort(); }, []);

  const serverVersion = updateStatus?.current_version;
  // The server was updated while this page was open: load the new interface.
  // A tab reloads once per version, so a mismatch can never loop.
  useEffect(() => {
    if (!serverVersion || !isNewerVersion(serverVersion, APP_VERSION) || busy) return;
    const session = () => sessionStorage;
    if (readStored(UPDATE_STORAGE.reloadedFor, session) === serverVersion) return;
    writeStored(UPDATE_STORAGE.reloadedFor, serverVersion, session);
    // The answer that just finished may not be saved yet.
    void saveNow().finally(() => window.location.reload());
  }, [serverVersion, busy, saveNow]);
  // A new interface is ready in the background: switch to it when idle, so
  // nobody has to clear the cache. The page already runs it after an update.
  useEffect(() => {
    if (!pwa.updateReady || busy) return;
    // Reload only for a server known to run another version; save first.
    const reload = serverVersion !== undefined && serverVersion !== APP_VERSION;
    void saveNow().finally(() => pwa.activateUpdate(reload));
  }, [pwa.updateReady, busy, serverVersion, saveNow]);
  // After an update, show once what changed in every version since the last one seen.
  useEffect(() => {
    if (!serverVersion || serverVersion !== APP_VERSION) return;
    const seen = readStored(UPDATE_STORAGE.seenVersion);
    const show = notesToShow(seen, serverVersion, sessionsRef.current.some(session => session.messages.length > 0));
    if (!show) { if (seen !== serverVersion) writeStored(UPDATE_STORAGE.seenVersion, serverVersion); return; }
    const controller = new AbortController();
    void api.releaseNotes(show.since, settings.language, controller.signal).then(notes => {
      if (notes.length) setWhatsNew({ version: serverVersion, notes });
      else writeStored(UPDATE_STORAGE.seenVersion, serverVersion);
    }).catch(() => undefined);
    return () => controller.abort();
  }, [serverVersion, api, settings.language]);
  const closeWhatsNew = () => {
    if (whatsNew) writeStored(UPDATE_STORAGE.seenVersion, whatsNew.version);
    setWhatsNew(null);
  };
  const exportBackup = () => downloadText(`parsrag-backup-${new Date().toISOString().slice(0, 10)}.json`, createBackup(sessionsRef.current, settings), 'application/json');

  // Delete on the server what was deleted here while it was unreachable.
  useEffect(() => {
    if (connection !== 'online') return;
    const pending = readPendingDeletions();
    if (!pending.length) return;
    void flushPendingDeletions(pending, async id => {
      try { await api.deleteSession(id, AbortSignal.timeout(15000)); } catch (error) {
        // A refusal (for example 404: already gone) will not change by retrying.
        if (!(error instanceof ApiError && error.status !== undefined && error.status < 500)) throw error;
      }
    }).then(remaining => writePendingDeletions([...remaining, ...readPendingDeletions().filter(id => !pending.includes(id))]));
  }, [api, connection]);

  // Suggest questions from the documents of an empty conversation, once per document set.
  const activeSuggestionKey = suggestionKey(active, settings.language);
  useEffect(() => {
    if (connection !== 'online' || active.messages.length || !activeSuggestionKey
      || active.suggestions?.key === activeSuggestionKey || uploadingId === active.id) return;
    const sessionId = active.id;
    const files = active.documents.filter(doc => doc.status === 'indexed' && doc.enabled !== false).map(doc => doc.name);
    const controller = new AbortController();
    const run = {};
    suggestionRunRef.current = run;
    setSuggesting(sessionId);
    void api.suggestions(sessionId, settings.language, files, controller.signal).then(questions => {
      updateSession(sessionId, s => ({ ...s, suggestions: { key: activeSuggestionKey, questions } }));
    }).catch(() => { /* Generic starters remain when suggestions are unavailable. */ })
      .finally(() => { if (suggestionRunRef.current === run) setSuggesting(undefined); });
    return () => controller.abort();
  }, [active.id, activeSuggestionKey, active.messages.length, connection, uploadingId, api, settings.language, updateSession]);

  const newChat = useCallback(() => {
    const blank = sessionsRef.current.find(s => !s.messages.length && !s.documents.length && !s.draft?.trim());
    const session = blank ?? createSession(settings.language, settings.defaultMode);
    if (!blank) setSessions(previous => [session, ...previous]);
    setActiveId(session.id); setNotice(null); setDocumentsOpen(false);
    if (isMobile) setSidebarOpen(false);
    setFocusToken(value => value + 1);
  }, [settings.language, settings.defaultMode, isMobile]);

  const stop = () => {
    const current = queryRef.current;
    if (!current) return;
    // send() keeps any streamed text and records the stop in order.
    current.controller.abort('user');
    queryRef.current = null; setGeneratingId(undefined);
    setQueryProgress(undefined);
  };

  /** Store an answer as a new message (after its question) or as another version of the retried one. */
  const commitAnswer = (sessionId: string, variant: ResponseVariant, parentUserId: string, assistantId?: string) => {
    const messageId = assistantId ?? crypto.randomUUID();
    updateSession(sessionId, s => {
      if (assistantId && s.messages.some(message => message.id === assistantId)) {
        return { ...s, messages: s.messages.map(message => message.id === assistantId ? appendResponseVariant(message, variant) : message), updatedAt: Date.now() };
      }
      const assistant: Message = { id: messageId, role: 'assistant', parentUserId, content: variant.content, citations: variant.citations, sources: variant.sources, grounding: variant.grounding, error: variant.error, timestamp: variant.timestamp, variants: [variant], activeVariant: 0 };
      return { ...s, messages: placeAnswer(s.messages, assistant), updatedAt: Date.now() };
    });
  };

  /** Keep the text that already streamed as the answer, as Stop does. */
  const commitPartial = (sessionId: string, partial: string, sourceNodes: unknown[], prompt: string, parentUserId: string, assistantId?: string) => {
    const data = parseAnswer({ answer: partial, source_nodes: sourceNodes, cited: citedNumbers(partial, sourceNodes.length) });
    commitAnswer(sessionId, { id: crypto.randomUUID(), content: partial, citations: data.citations, sources: data.sources, timestamp: Date.now(), prompt: prompt.trim(), continuation: [] }, parentUserId, assistantId);
  };
  const addNote = (sessionId: string, content: string, userId: string) => updateSession(sessionId, s => ({
    ...s, messages: placeNote(s.messages, { id: crypto.randomUUID(), role: 'system', content, timestamp: Date.now() }, userId),
  }));

  const send = async (session: Session, prompt: string, target?: { userId: string; assistantId?: string; edit?: boolean }) => {
    if (!prompt.trim() || queryRef.current || uploadRef.current) return;
    if (session.ragMode === 'strict' && !session.documents.some(d => d.status === 'indexed')) {
      setNotice(t.uploadFirst); setDocumentsOpen(true); return;
    }
    if (session.ragMode === 'strict' && !session.documents.some(d => d.status === 'indexed' && d.enabled !== false)) {
      setNotice(t.selectDocumentFirst); setDocumentsOpen(true); return;
    }
    const prepared = target ? prepareTurnRegeneration(session.messages, target.userId, target.assistantId, prompt, Boolean(target.edit)) : null;
    const firstTurn = !target && session.messages.length === 0;
    // The first question moves the message box from the welcome screen to the
    // conversation; keep the keyboard in it.
    if (firstTurn && document.activeElement?.id === 'message-input') setFocusToken(value => value + 1);
    const fallbackTitle = fallbackConversationTitle(prompt);
    const historySession = prepared ? { ...session, messages: prepared.history } : session;
    const payload = buildQuery(historySession, settings, prompt);
    const controller = new AbortController();
    const requestId = crypto.randomUUID();
    queryRef.current = { controller, sessionId: session.id };
    setGeneratingId(session.id); setQueryProgress({ sessionId: session.id, stage: 'understanding' }); setNotice(null);
    const userMessage: Message = { id: target?.userId ?? crypto.randomUUID(), role: 'user', content: prompt.trim(), timestamp: Date.now() };
    updateSession(session.id, s => ({
      ...s, messages: target ? prepareTurnRegeneration(s.messages, target.userId, target.assistantId, prompt, Boolean(target.edit)).visible : [...s.messages, userMessage],
      draft: target ? s.draft : '',
      title: s.messages.length ? s.title : fallbackTitle,
      updatedAt: Date.now(),
    }));
    // Any event, pings included, shows the connection is alive.
    let idle: ReturnType<typeof setTimeout> | undefined;
    const touch = () => { clearTimeout(idle); idle = setTimeout(() => controller.abort('timeout'), STREAM_IDLE_MS); };
    touch();
    let streamed = '';
    let streamedSources: unknown[] = [];
    let frame = 0;
    const showDraft = () => { frame = 0; setStreamDraft({ sessionId: session.id, messageId: target?.assistantId, afterUserId: target && !target.assistantId ? target.userId : undefined, content: streamed, sourceCount: streamedSources.length }); };
    try {
      const raw = await api.queryStream({ ...payload, request_id: requestId }, controller.signal, event => {
        touch();
        if (event.type === 'stage') setQueryProgress({ sessionId: session.id, stage: event.stage });
        else if (event.type === 'sources') streamedSources = event.sourceNodes;
        else if (event.type === 'token') {
          streamed += event.text;
          if (!frame) frame = requestAnimationFrame(showDraft);
        }
      });
      if (controller.signal.aborted) return;
      const data = parseAnswer(raw);
      const content = data.outcome === 'answered' ? data.answer : t.answerOutcomes[data.outcome];
      const variant: ResponseVariant = { id: crypto.randomUUID(), content, citations: data.citations, sources: data.sources, grounding: answerGrounding(session.ragMode, data.outcome), timestamp: Date.now(), prompt: prompt.trim(), continuation: [] };
      commitAnswer(session.id, variant, userMessage.id, target?.assistantId);
      setConnection('online');
      if (firstTurn) {
        void api.conversationTitle(prompt.trim(), settings.language, AbortSignal.timeout(120000)).then(title => {
          updateSession(session.id, current => current.title === fallbackTitle
            ? { ...current, title, updatedAt: Date.now() } : current);
        }).catch(() => { /* The local fallback remains valid when title generation is unavailable. */ });
      }
    } catch (error: unknown) {
      const reason = controller.signal.reason;
      const partial = streamed.trim();
      if (controller.signal.aborted && reason === 'user') {
        // Keep what was already written; the reader asked to stop, not to discard.
        if (partial) commitPartial(session.id, partial, streamedSources, prompt, userMessage.id, target?.assistantId);
        addNote(session.id, t.stopped, userMessage.id);
        return;
      }
      if (controller.signal.aborted && reason !== 'timeout') return;
      const content = reason === 'timeout' ? t.timeout
        : error instanceof ApiError ? queryErrorMessage(error.code, settings.language) ?? t.queryFailed
          : error instanceof Error && error.message === 'invalid_response' ? t.invalidResponse : t.queryFailed;
      if (partial) {
        // A timeout or a dropped connection keeps the text that arrived, with the reason after it.
        commitPartial(session.id, partial, streamedSources, prompt, userMessage.id, target?.assistantId);
        addNote(session.id, content, userMessage.id);
      } else {
        commitAnswer(session.id, { id: crypto.randomUUID(), content, error: true, timestamp: Date.now(), prompt: prompt.trim(), continuation: [] }, userMessage.id, target?.assistantId);
      }
      void checkHealth();
    } finally {
      clearTimeout(idle);
      if (frame) cancelAnimationFrame(frame);
      setStreamDraft(current => current?.sessionId === session.id ? undefined : current);
      setQueryProgress(current => current?.sessionId === session.id ? undefined : current);
      if (queryRef.current?.controller === controller) { queryRef.current = null; setGeneratingId(undefined); }
    }
  };

  const upload = async (files: File[]) => {
    if (uploadRef.current || queryRef.current) return;
    const sessionId = active.id;
    const validation = validateUploads(files, active.documents, ingestionCapabilities);
    setUploadError(validation.rejected.length ? {
      sessionId, text: validation.rejected.map(issue => issue.name + ': ' + t.uploadErrors[issue.reason]).join('\n'),
    } : null);
    if (!validation.accepted.length) return;
    const acceptedFiles = validation.accepted.map(index => files[index]);
    uploadRef.current = true; setUploadingId(sessionId);
    const optimistic: SessionDocument[] = acceptedFiles.map(file => ({ name: file.name, size: file.size, status: 'uploading', uploadProgress: 0, enabled: true }));
    updateSession(sessionId, s => ({ ...s, documents: [...s.documents, ...optimistic], updatedAt: Date.now() }));
    try {
      for (const file of acceptedFiles) {
        const controller = new AbortController();
        const timeout = setTimeout(() => controller.abort(), 600000);
        try {
          const [indexed] = await api.ingest(file, sessionId, controller.signal, uploadProgress => updateSession(sessionId, s => ({ ...s, documents: s.documents.map(d => d.name === file.name ? uploadProgress >= 100
            ? { ...d, status: 'processing', uploadProgress: undefined }
            : { ...d, status: 'uploading', uploadProgress } : d) })));
          updateSession(sessionId, s => ({ ...s, documents: s.documents.map(d => d.name === file.name ? {
            ...d, status: 'indexed', uploadProgress: undefined, errorMessage: undefined,
            chunks: indexed?.chunks, sections: indexed?.sections, notices: indexed?.notices.length ? indexed.notices : undefined,
          } : d) }));
        } catch (error: unknown) {
          const reason = error instanceof ApiError ? uploadErrorMessage(error.code, settings.language) : undefined;
          updateSession(sessionId, s => ({ ...s, documents: s.documents.map(d => d.name === file.name ? {
            ...d, status: 'error', errorMessage: reason ?? t.uploadFailed,
          } : d) }));
        } finally { clearTimeout(timeout); }
      }
    } finally { uploadRef.current = false; setUploadingId(undefined); }
  };

  const reuseDocument = async (sourceSessionId: string, name: string) => {
    if (uploadRef.current || queryRef.current || active.documents.some(doc => doc.name === name)
      || active.documents.length >= ingestionCapabilities.max_files_per_session) return;
    const sessionId = active.id;
    uploadRef.current = true; setUploadingId(sessionId); setUploadError(null);
    updateSession(sessionId, session => ({ ...session, documents: [...session.documents,
      { name, status: 'processing', enabled: true }], updatedAt: Date.now() }));
    try {
      await api.reuseDocument(sessionId, sourceSessionId, name, AbortSignal.timeout(60000));
      updateSession(sessionId, session => ({ ...session, documents: session.documents.map(doc =>
        doc.name === name ? { ...doc, status: 'indexed' } : doc) }));
    } catch (error: unknown) {
      updateSession(sessionId, session => ({ ...session, documents: session.documents.filter(doc => doc.name !== name) }));
      const reason = error instanceof ApiError && error.code !== 'request_failed' ? uploadErrorMessage(error.code, settings.language) : undefined;
      setUploadError({ sessionId, text: reason ?? t.reuseDocumentFailed });
    } finally { uploadRef.current = false; setUploadingId(undefined); }
  };

  const deleteDocument = async (name: string) => {
    if (busy || deletingDocuments.has(name)) return;
    const sessionId = active.id;
    setDeletingDocuments(current => new Set(current).add(name));
    try {
      await api.deleteDocument(sessionId, name, AbortSignal.timeout(15000));
      updateSession(sessionId, s => ({ ...s, documents: s.documents.filter(d => d.name !== name), updatedAt: Date.now() }));
    } catch (error: unknown) {
      const reason = error instanceof ApiError && error.code !== 'request_failed' ? uploadErrorMessage(error.code, settings.language) : undefined;
      setUploadError({ sessionId, text: reason ?? t.documentDeleteFailed });
    } finally {
      setDeletingDocuments(current => { const next = new Set(current); next.delete(name); return next; });
    }
  };

  /**
   * Delete a conversation on the server. Only documents live there; while the
   * server is unreachable the deletion is queued and done when it is back.
   */
  const deleteOnServer = async (session: Session): Promise<void> => {
    if (!session.documents.length) return;
    try {
      await api.deleteSession(session.id, AbortSignal.timeout(15000));
    } catch (error) {
      if (!unreachable(error)) throw error;
      writePendingDeletions([...readPendingDeletions().filter(id => id !== session.id), session.id]);
    }
  };

  const deleteSession = async (id: string): Promise<boolean> => {
    if (uploadingId === id) return false;
    const session = sessionsRef.current.find(s => s.id === id);
    if (!session) return true;
    try {
      await deleteOnServer(session);
      if (queryRef.current?.sessionId === id) { queryRef.current.controller.abort('deleted'); progressRef.current?.abort(); queryRef.current = null; setGeneratingId(undefined); setQueryProgress(undefined); }
      const remaining = sessionsRef.current.filter(s => s.id !== id);
      if (!remaining.length) remaining.push(createSession(settings.language, settings.defaultMode));
      setSessions(remaining);
      if (activeId === id) setActiveId(remaining[0].id);
      return true;
    } catch { return false; }
  };

  const clearAllData = async (): Promise<void> => {
    if (busy) throw new Error('busy');
    const current = [...sessionsRef.current];
    const failures: string[] = [];
    for (const session of current) {
      try {
        await deleteOnServer(session);
      } catch {
        failures.push(session.id);
      }
    }
    if (failures.length) throw new Error('backend_delete_failed');
    const fresh = createSession(settings.language, settings.defaultMode);
    setSessions([fresh]); setActiveId(fresh.id); setNotice(null);
  };

  const updateSettings = useCallback((updated: Partial<AppSettings>) => setSettings(current => ({ ...current, ...updated })), []);
  const transitionTheme = useThemeTransition(theme => updateSettings({ theme }));
  const transitionLanguage = useLanguageTransition(language => updateSettings({ language }));
  useEffect(() => {
    const onShortcut = (event: KeyboardEvent) => {
      if (guideOpen || document.querySelector('dialog[open]')) return;
      const element = event.target instanceof HTMLElement ? event.target : null;
      const editable = Boolean(element?.isContentEditable || element?.closest('input,textarea,select,[contenteditable="true"]'));
      const action = resolveShortcut(event, isApplePlatform(navigator.platform || navigator.userAgent), editable);
      if (!action) return;
      event.preventDefault();
      switch (action) {
        case 'newChat': newChat(); break;
        case 'searchChats':
          setSidebarOpen(true);
          setSearchFocusToken(value => value + 1);
          break;
        case 'documents': setDocumentsOpen(true); break;
        case 'settings': setSettingsOpen(true); break;
        case 'composer': setFocusToken(value => value + 1); break;
        case 'guide': setGuideOpen(true); break;
        case 'theme': transitionTheme(settings.theme === 'dark' ? 'light' : 'dark'); break;
      }
    };
    window.addEventListener('keydown', onShortcut);
    return () => window.removeEventListener('keydown', onShortcut);
  }, [guideOpen, newChat, settings.theme, transitionTheme]);
  const selectedDocuments = active.documents.filter(d => d.status === 'indexed' && d.enabled !== false);
  const composer = <Composer key={active.id} value={active.draft ?? ''} onChange={draft => updateSession(active.id, s => ({ ...s, draft }))}
    onSendMessage={() => void send(active, active.draft ?? '')} onStopGenerating={stop}
    isGenerating={generatingId === active.id} isBusy={busy} isUploading={Boolean(uploadingId)} activeMode={active.ragMode}
    onChangeMode={ragMode => updateSession(active.id, s => ({ ...s, ragMode }))}
    language={settings.language} onOpenDocuments={() => setDocumentsOpen(true)} documentCount={selectedDocuments.length} focusToken={focusToken}
    documentNames={active.documents.filter(doc => doc.status === 'indexed').map(doc => doc.name)}
    onSelectMention={name => updateSession(active.id, session => ({ ...session, documents: session.documents.map(doc => doc.name === name ? { ...doc, enabled: true } : doc) }))}
    onOpenGuide={() => setGuideOpen(true)} guidedMenu={guideOpen ? tourStage.menu : null} />;

  return <div className="app-shell">
    <BootSequence language={settings.language} />
    <a href="#message-input" className="skip-link">{t.messageLabel}</a>
    <Sidebar sessions={sessions} activeSessionId={active.id} generatingSessionId={generatingId}
      searchFocusToken={searchFocusToken}
      onSelectSession={id => { setActiveId(id); setNotice(null); setDocumentsOpen(false); if (isMobile) setSidebarOpen(false); }}
      onNewChat={newChat} onDeleteSession={deleteSession}
      onRenameSession={(id, title) => updateSession(id, s => ({ ...s, title, updatedAt: Date.now() }))}
      language={settings.language} theme={settings.theme}
      onToggleTheme={origin => transitionTheme(settings.theme === 'dark' ? 'light' : 'dark', origin)}
      onOpenSettings={() => setSettingsOpen(true)} isOpen={sidebarOpen} isMobile={isMobile} onClose={() => setSidebarOpen(false)}
      connection={connection} modelRuntime={modelRuntime} modelState={modelState} onRetryConnection={checkHealth}
      updateVersion={offeredUpdate(updateStatus, skippedUpdate)} onOpenUpdate={() => setUpdateOpen(true)} uploadingSessionId={uploadingId} />
    <main className="workspace">
      <Header title={active.title} language={settings.language} isSidebarOpen={sidebarOpen} isEmpty={!active.messages.length} onNewChat={newChat}
        documentCount={active.documents.length} onToggleSidebar={() => setSidebarOpen(value => !value)} onOpenDocuments={() => setDocumentsOpen(true)} />
      {(notice || storageError) && <div className="notice" role="status"><AlertCircle size={17} /><span>{storageError ? t.storageFailed : notice}</span>{!storageError && <button className="icon-button" onClick={() => setNotice(null)} aria-label={t.dismiss}><X size={16} /></button>}</div>}
      {pwa.updateReady && <div className="notice pwa-update" role="status"><span>{t.pwaUpdateReady}</span><button className="button secondary" disabled={busy} onClick={() => pwa.activateUpdate()}>{t.pwaApplyUpdate}</button></div>}
      {active.messages.length === 0 ? <Welcome language={settings.language} composer={composer} onSelectStarter={draft => {
        updateSession(active.id, s => ({ ...s, draft }));
        setFocusToken(value => value + 1);
      }}
        documentQuestions={active.suggestions?.key === activeSuggestionKey ? active.suggestions.questions : undefined}
        documentQuestionsLoading={suggesting === active.id}
        onSelectQuestion={question => void send(active, question)} /> : <>
        <ChatFeed key={active.id} messages={active.messages} language={settings.language} isGenerating={generatingId === active.id} activeMode={active.ragMode}
          queryStage={queryProgress?.sessionId === active.id ? queryProgress.stage : undefined}
          streamingDraft={streamDraft?.sessionId === active.id ? streamDraft : undefined}
          revealingMessageId={revealingMessageId} onRevealComplete={() => setRevealingMessageId(undefined)}
          imageUrl={(filename, image) => api.sourceImageUrl(active.id, filename, image)}
          isBusy={busy} onRetry={messageId => {
            const assistant = active.messages.find(message => message.id === messageId);
            const assistantIndex = active.messages.findIndex(message => message.id === messageId);
            const previous = assistant?.parentUserId ? active.messages.find(message => message.id === assistant.parentUserId) : active.messages.slice(0, assistantIndex).reverse().find(message => message.role === 'user');
            if (previous) void send(active, previous.content, { userId: previous.id, assistantId: messageId });
          }} onEditPrompt={(messageId, content) => {
            void send(active, content, { userId: messageId, assistantId: answerTo(active.messages, messageId)?.id, edit: true });
          }} onRetryQuestion={messageId => {
            const question = active.messages.find(message => message.id === messageId);
            if (question) void send(active, question.content, { userId: messageId });
          }} onSelectVariant={(messageId, variantIndex) => updateSession(active.id, session => ({
            ...session, messages: selectConversationBranch(session.messages, messageId, variantIndex), updatedAt: Date.now(),
          }))} />
        <div className="active-composer">
          {selectedDocuments.length > 0 && active.ragMode !== 'llm-only' && <button className="active-documents" onClick={() => setDocumentsOpen(true)}><FileText size={13} />{selectedDocuments.length.toLocaleString(settings.language)} {t.selectedDocs}</button>}
          {composer}
        </div>
      </>}
    </main>
    <DocumentCenter isOpen={documentsOpen} guided={guideOpen} onClose={() => setDocumentsOpen(false)} documents={active.documents}
      capabilities={ingestionCapabilities}
      reusableDocuments={sessions.filter(session => session.id !== active.id).flatMap(session => session.documents
        .filter(doc => doc.status === 'indexed' && !active.documents.some(current => current.name === doc.name))
        .map(doc => ({ sourceSessionId: session.id, sourceTitle: session.title, name: doc.name })))}
      onReuseDocument={(sourceSessionId, name) => void reuseDocument(sourceSessionId, name)}
      onUploadFiles={files => void upload(files)} language={settings.language} isUploading={busy} activeMode={active.ragMode}
      error={uploadError?.sessionId === active.id ? uploadError.text : null}
      onRemoveFailed={name => updateSession(active.id, s => ({ ...s, documents: s.documents.filter(d => d.name !== name || d.status !== 'error') }))}
      onDeleteDocument={name => void deleteDocument(name)} deletingDocuments={deletingDocuments}
      onToggleDocument={name => updateSession(active.id, s => {
        return { ...s, documents: s.documents.map(d => d.name === name ? { ...d, enabled: d.enabled === false } : d) };
      })} />
    <SettingsModal open={settingsOpen} guided={guideOpen} guidedTab={guideOpen ? tourStage.settingsTab : undefined} guidedProvider={guideOpen ? tourStage.provider : undefined} settings={settings} onClose={() => setSettingsOpen(false)}
      onStartGuide={() => setGuideOpen(true)}
      canInstall={pwa.canInstall} onInstall={() => void pwa.install()}
      onModelConfigured={configuration => { setModelRuntime(configuration); void checkHealth(); }}
      onRuntimeChanged={() => void checkHealth()}
      onUpdateSettings={updated => {
        if (updated.theme && updated.theme !== settings.theme) transitionTheme(updated.theme);
        else if (updated.language && updated.language !== settings.language) transitionLanguage(updated.language);
        else updateSettings(updated);
      }} busy={busy}
      onClearAllData={clearAllData}
      onExportBackup={exportBackup}
      updateStatus={updateStatus}
      onCheckUpdates={async () => {
        try { const status = await api.updates(true); setUpdateStatus(status); return status; } catch { return null; }
      }}
      onOpenUpdate={() => { setSettingsOpen(false); setUpdateOpen(true); }}
      onImportBackup={async file => {
        const backup = parseBackup(await file.text(), window.location.origin);
        const merged = mergeSessions(sessionsRef.current, backup.sessions);
        setSessions(merged.sessions);
        // Preferences come along; this page keeps its own service address.
        if (backup.settings) updateSettings({ ...backup.settings, backendUrl: settings.backendUrl });
        return { added: merged.added, updated: merged.updated };
      }} />
    {updateStatus?.update_available && <UpdateDialog open={updateOpen} status={updateStatus} language={settings.language}
      onClose={() => setUpdateOpen(false)} onBackup={exportBackup}
      onSkip={version => { writeStored(UPDATE_STORAGE.skippedUpdate, version); setSkippedUpdate(version); }} />}
    {whatsNew && <WhatsNewDialog notes={whatsNew.notes} currentVersion={whatsNew.version} language={settings.language} onClose={closeWhatsNew} />}
    <WorkspaceTour open={guideOpen} language={settings.language} onClose={closeGuide} onStageChange={changeTourStage} activeStage={tourStage} />
  </div>;
}

