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
import { useMediaQuery } from './hooks/useMediaQuery';
import { useThemeTransition } from './hooks/useThemeTransition';
import { useLanguageTransition } from './hooks/useLanguageTransition';
import { ApiError, ParsRagApiClient } from './services/api';
import type { AppSettings, Message, ResponseVariant, Session, SessionDocument } from './types';
import { translations } from './i18n/translations';
import { appendResponseVariant, buildQuery, createSession, mergeRemoteDocuments, parseAnswer, parseSessions, parseSettings, prepareTurnRegeneration, selectResponseVariant, STORAGE, validateUploads } from './core/state';

function readStorage(key: string): string | null {
  try { return localStorage.getItem(key); } catch { return null; }
}

export function App() {
  const [settings, setSettings] = useState(() => parseSettings(readStorage(STORAGE.settings), window.location.origin));
  const [sessions, setSessions] = useState<Session[]>(() => {
    const stored = parseSessions(readStorage(STORAGE.sessions));
    return stored.length ? stored : [createSession(settings.language, settings.defaultMode)];
  });
  const [activeId, setActiveId] = useState(() => {
    const stored = readStorage(STORAGE.active);
    return sessions.some(s => s.id === stored) ? stored! : sessions[0].id;
  });
  const isMobile = useMediaQuery('(max-width: 760px)');
  const [sidebarOpen, setSidebarOpen] = useState(!isMobile);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [documentsOpen, setDocumentsOpen] = useState(false);
  const [generatingId, setGeneratingId] = useState<string>();
  const [uploadingId, setUploadingId] = useState<string>();
  const [connection, setConnection] = useState<'checking' | 'online' | 'offline'>('checking');
  const [notice, setNotice] = useState<string | null>(null);
  const [uploadError, setUploadError] = useState<{ sessionId: string; text: string } | null>(null);
  const [storageError, setStorageError] = useState(false);
  const [focusToken, setFocusToken] = useState(0);
  const queryRef = useRef<{ controller: AbortController; sessionId: string } | null>(null);
  const uploadRef = useRef(false);
  const healthRef = useRef<AbortController>();
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
    document.documentElement.dir = settings.language === 'fa' ? 'rtl' : 'ltr';
    document.documentElement.lang = settings.language;
    document.documentElement.dataset.theme = settings.theme;
    document.title = settings.language === 'fa' ? 'پارس‌رگ — از پرسش، به بینش' : 'ParsRAG — A clearer perspective';
  }, [settings.language, settings.theme]);
  useEffect(() => {
    try {
      localStorage.setItem(STORAGE.settings, JSON.stringify(settings));
      localStorage.setItem(STORAGE.sessions, JSON.stringify(sessions));
      localStorage.setItem(STORAGE.active, activeId);
      setStorageError(false);
    } catch { setStorageError(true); }
  }, [settings, sessions, activeId]);

  const checkHealth = useCallback(async () => {
    healthRef.current?.abort();
    const controller = new AbortController();
    healthRef.current = controller;
    const timeout = setTimeout(() => controller.abort(), 5000);
    try {
      const online = await api.isHealthy(controller.signal);
      if (healthRef.current === controller) setConnection(online ? 'online' : 'offline');
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
  useEffect(() => () => queryRef.current?.controller.abort(), []);

  const newChat = useCallback(() => {
    const blank = sessionsRef.current.find(s => !s.messages.length && !s.documents.length && !s.draft?.trim());
    const session = blank ?? createSession(settings.language, settings.defaultMode);
    if (!blank) setSessions(previous => [session, ...previous]);
    setActiveId(session.id); setNotice(null); setDocumentsOpen(false);
    if (isMobile) setSidebarOpen(false);
    setFocusToken(value => value + 1);
  }, [settings.language, settings.defaultMode, isMobile]);

  useEffect(() => {
    const shortcut = (event: KeyboardEvent) => {
      if ((event.ctrlKey || event.metaKey) && event.shiftKey && event.key.toLowerCase() === 'o' && !document.querySelector('dialog[open]')) {
        event.preventDefault(); newChat();
      }
    };
    window.addEventListener('keydown', shortcut);
    return () => window.removeEventListener('keydown', shortcut);
  }, [newChat]);

  const stop = () => {
    const current = queryRef.current;
    if (!current) return;
    current.controller.abort('user');
    queryRef.current = null; setGeneratingId(undefined);
    updateSession(current.sessionId, s => ({ ...s, messages: [...s.messages, {
      id: crypto.randomUUID(), role: 'system', content: t.stopped, timestamp: Date.now(),
    }] }));
  };

  const send = async (session: Session, prompt: string, target?: { userId: string; assistantId?: string; edit?: boolean }) => {
    if (!prompt.trim() || queryRef.current || uploadRef.current) return;
    if (session.ragMode === 'strict' && !session.documents.some(d => d.status === 'indexed')) {
      setNotice(t.uploadFirst); setDocumentsOpen(true); return;
    }
    const prepared = target ? prepareTurnRegeneration(session.messages, target.userId, target.assistantId, prompt, Boolean(target.edit)) : null;
    const historySession = prepared ? { ...session, messages: prepared.history } : session;
    const payload = buildQuery(historySession, settings, prompt);
    const controller = new AbortController();
    queryRef.current = { controller, sessionId: session.id };
    setGeneratingId(session.id); setNotice(null);
    const userMessage: Message = { id: target?.userId ?? crypto.randomUUID(), role: 'user', content: prompt.trim(), timestamp: Date.now() };
    updateSession(session.id, s => ({
      ...s, messages: target ? prepareTurnRegeneration(s.messages, target.userId, target.assistantId, prompt, Boolean(target.edit)).visible : [...s.messages, userMessage],
      draft: target ? s.draft : '',
      title: s.messages.length ? s.title : prompt.trim().slice(0, 48) + (prompt.trim().length > 48 ? '…' : ''),
      updatedAt: Date.now(),
    }));
    const timeout = setTimeout(() => controller.abort('timeout'), 180000);
    try {
      const data = parseAnswer(await api.query(payload, controller.signal));
      if (controller.signal.aborted) return;
      const variant: ResponseVariant = { id: crypto.randomUUID(), content: data.answer, citations: data.citations, timestamp: Date.now() };
      updateSession(session.id, s => {
        if (target?.assistantId && s.messages.some(message => message.id === target.assistantId)) {
          return { ...s, messages: s.messages.map(message => {
            if (message.id !== target.assistantId) return message;
            return appendResponseVariant(message, variant);
          }), updatedAt: Date.now() };
        }
        const assistant: Message = { id: crypto.randomUUID(), role: 'assistant', parentUserId: userMessage.id, content: variant.content, citations: variant.citations, timestamp: variant.timestamp, variants: [variant], activeVariant: 0 };
        return { ...s, messages: [...s.messages, assistant], updatedAt: Date.now() };
      });
      setConnection('online');
    } catch (error: unknown) {
      if (controller.signal.aborted && controller.signal.reason !== 'timeout') return;
      const content = controller.signal.reason === 'timeout' ? t.timeout
        : error instanceof Error && error.message === 'invalid_response' ? t.invalidResponse : t.queryFailed;
      const variant: ResponseVariant = { id: crypto.randomUUID(), content, error: true, timestamp: Date.now() };
      updateSession(session.id, s => {
        if (target?.assistantId && s.messages.some(message => message.id === target.assistantId)) {
          return { ...s, messages: s.messages.map(message => {
            if (message.id !== target.assistantId) return message;
            return appendResponseVariant(message, variant);
          }), updatedAt: Date.now() };
        }
        const assistant: Message = { id: crypto.randomUUID(), role: 'assistant', parentUserId: userMessage.id, content, error: true, timestamp: variant.timestamp, variants: [variant], activeVariant: 0 };
        return { ...s, messages: [...s.messages, assistant], updatedAt: Date.now() };
      });
      void checkHealth();
    } finally {
      clearTimeout(timeout);
      if (queryRef.current?.controller === controller) { queryRef.current = null; setGeneratingId(undefined); }
    }
  };

  const upload = async (files: File[]) => {
    if (uploadRef.current || queryRef.current) return;
    const sessionId = active.id;
    const validation = validateUploads(files, active.documents);
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
        const timeout = setTimeout(() => controller.abort(), 180000);
        try {
          await api.ingest(file, sessionId, controller.signal, uploadProgress => updateSession(sessionId, s => ({ ...s, documents: s.documents.map(d => d.name === file.name ? uploadProgress >= 100
            ? { ...d, status: 'processing', uploadProgress: undefined }
            : { ...d, status: 'uploading', uploadProgress } : d) })));
          updateSession(sessionId, s => ({ ...s, documents: s.documents.map(d => d.name === file.name ? { ...d, status: 'indexed', uploadProgress: undefined, errorMessage: undefined } : d) }));
        } catch (error: unknown) {
          updateSession(sessionId, s => ({ ...s, documents: s.documents.map(d => d.name === file.name ? {
            ...d, status: 'error', errorMessage: error instanceof ApiError && error.code === 'scanned_pdf'
              ? settings.language === 'fa' ? 'پردازش OCR این PDF اسکن‌شده در دسترس نیست یا غیرفعال شده است.' : 'OCR for this scanned PDF is unavailable or disabled.'
              : t.uploadFailed,
          } : d) }));
        } finally { clearTimeout(timeout); }
      }
    } finally { uploadRef.current = false; setUploadingId(undefined); }
  };

  const deleteDocument = async (name: string) => {
    if (busy) return;
    try {
      await api.deleteDocument(active.id, name, AbortSignal.timeout(15000));
      updateSession(active.id, s => ({ ...s, documents: s.documents.filter(d => d.name !== name), updatedAt: Date.now() }));
    } catch { setUploadError({ sessionId: active.id, text: t.documentDeleteFailed }); }
  };

  const deleteSession = async (id: string): Promise<boolean> => {
    if (uploadingId === id) return false;
    const session = sessionsRef.current.find(s => s.id === id);
    if (!session) return true;
    try {
      if (session.documents.length || session.messages.length) {
        await api.deleteSession(id, AbortSignal.timeout(15000));
      }
      if (queryRef.current?.sessionId === id) { queryRef.current.controller.abort('deleted'); queryRef.current = null; setGeneratingId(undefined); }
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
        await api.deleteSession(session.id, AbortSignal.timeout(15000));
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
  const selectedDocuments = active.documents.filter(d => d.status === 'indexed' && d.enabled !== false);
  const composer = <Composer key={active.id} value={active.draft ?? ''} onChange={draft => updateSession(active.id, s => ({ ...s, draft }))}
    onSendMessage={() => void send(active, active.draft ?? '')} onStopGenerating={stop}
    isGenerating={generatingId === active.id} isBusy={busy} activeMode={active.ragMode}
    onChangeMode={ragMode => updateSession(active.id, s => ({ ...s, ragMode }))}
    language={settings.language} onOpenDocuments={() => setDocumentsOpen(true)} documentCount={selectedDocuments.length} focusToken={focusToken} />;

  return <div className="app-shell">
    <BootSequence language={settings.language} />
    <a href="#message-input" className="skip-link">{t.messageLabel}</a>
    <Sidebar sessions={sessions} activeSessionId={active.id} generatingSessionId={generatingId}
      onSelectSession={id => { setActiveId(id); setNotice(null); setDocumentsOpen(false); if (isMobile) setSidebarOpen(false); }}
      onNewChat={newChat} onDeleteSession={deleteSession}
      onRenameSession={(id, title) => updateSession(id, s => ({ ...s, title, updatedAt: Date.now() }))}
      language={settings.language} theme={settings.theme}
      onToggleTheme={origin => transitionTheme(settings.theme === 'dark' ? 'light' : 'dark', origin)}
      onOpenSettings={() => setSettingsOpen(true)} isOpen={sidebarOpen} isMobile={isMobile} onClose={() => setSidebarOpen(false)}
      connection={connection} onRetryConnection={() => void checkHealth()} uploadingSessionId={uploadingId} />
    <main className="workspace">
      <Header title={active.title} language={settings.language} isSidebarOpen={sidebarOpen} isEmpty={!active.messages.length} onNewChat={newChat}
        documentCount={active.documents.length} onToggleSidebar={() => setSidebarOpen(value => !value)} onOpenDocuments={() => setDocumentsOpen(true)} />
      {(notice || storageError) && <div className="notice" role="status"><AlertCircle size={17} /><span>{storageError ? t.storageFailed : notice}</span>{!storageError && <button className="icon-button" onClick={() => setNotice(null)} aria-label={t.dismiss}><X size={16} /></button>}</div>}
      {active.messages.length === 0 ? <Welcome language={settings.language} composer={composer} onSelectStarter={(draft, index) => {
        updateSession(active.id, s => ({ ...s, draft, ragMode: index === 2 ? 'llm-only' : 'hybrid' }));
        setFocusToken(value => value + 1);
      }} /> : <>
        <ChatFeed key={active.id} messages={active.messages} language={settings.language} isGenerating={generatingId === active.id} activeMode={active.ragMode}
          isBusy={busy} onRetry={messageId => {
            const assistant = active.messages.find(message => message.id === messageId);
            const assistantIndex = active.messages.findIndex(message => message.id === messageId);
            const previous = assistant?.parentUserId ? active.messages.find(message => message.id === assistant.parentUserId) : active.messages.slice(0, assistantIndex).reverse().find(message => message.role === 'user');
            if (previous) void send(active, previous.content, { userId: previous.id, assistantId: messageId });
          }} onEditPrompt={(messageId, content) => {
            const userIndex = active.messages.findIndex(message => message.id === messageId);
            const assistant = active.messages.slice(userIndex + 1).find(message => message.role === 'assistant');
            void send(active, content, { userId: messageId, assistantId: assistant?.id, edit: true });
          }} onSelectVariant={(messageId, variantIndex) => updateSession(active.id, session => ({ ...session, messages: session.messages.map(message => {
            if (message.id !== messageId || !message.variants?.[variantIndex]) return message;
            return selectResponseVariant(message, variantIndex);
          }) }))} />
        <div className="active-composer">
          {selectedDocuments.length > 0 && active.ragMode !== 'llm-only' && <button className="active-documents" onClick={() => setDocumentsOpen(true)}><FileText size={13} />{selectedDocuments.length.toLocaleString(settings.language)} {t.selectedDocs}</button>}
          {composer}
        </div>
      </>}
    </main>
    <DocumentCenter isOpen={documentsOpen} onClose={() => setDocumentsOpen(false)} documents={active.documents}
      onUploadFiles={files => void upload(files)} language={settings.language} isUploading={busy} activeMode={active.ragMode}
      error={uploadError?.sessionId === active.id ? uploadError.text : null}
      onRemoveFailed={name => updateSession(active.id, s => ({ ...s, documents: s.documents.filter(d => d.name !== name || d.status !== 'error') }))}
      onDeleteDocument={name => void deleteDocument(name)}
      onToggleDocument={name => updateSession(active.id, s => {
        return { ...s, documents: s.documents.map(d => d.name === name ? { ...d, enabled: d.enabled === false } : d) };
      })} />
    <SettingsModal open={settingsOpen} settings={settings} onClose={() => setSettingsOpen(false)}
      onUpdateSettings={updated => {
        if (updated.theme && updated.theme !== settings.theme) transitionTheme(updated.theme);
        else if (updated.language && updated.language !== settings.language) transitionLanguage(updated.language);
        else updateSettings(updated);
      }} busy={busy}
      onClearAllData={clearAllData} />
  </div>;
}

