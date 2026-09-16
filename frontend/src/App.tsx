import { useCallback, useEffect, useRef, useState } from 'react';
import { AlertCircle, FileText, X } from 'lucide-react';
import { Sidebar } from './components/Sidebar';
import { Header } from './components/Header';
import { DocumentCenter } from './components/DocumentCenter';
import { ChatFeed } from './components/ChatFeed';
import { Composer } from './components/Composer';
import { SettingsModal } from './components/SettingsModal';
import { Welcome } from './components/Welcome';
import { useMediaQuery } from './hooks/useMediaQuery';
import type { AppSettings, Message, Session, SessionDocument } from './types';
import { translations } from './i18n/translations';
import { buildQuery, createSession, isRecord, mergeRemoteDocuments, parseAnswer, parseSessions, parseSettings, STORAGE, validateUploads } from './core/state';

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
      const response = await fetch(endpoint + '/health', { signal: controller.signal });
      if (healthRef.current === controller) setConnection(response.ok ? 'online' : 'offline');
    } catch {
      if (healthRef.current === controller) setConnection('offline');
    } finally { clearTimeout(timeout); }
  }, [endpoint]);

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
        const response = await fetch(endpoint + '/sessions/' + active.id + '/files', { signal: controller.signal });
        if (!response.ok) return;
        const remote: unknown = await response.json();
        if (!controller.signal.aborted) updateSession(active.id, s => ({ ...s, documents: mergeRemoteDocuments(s.documents, remote) }));
      } catch { /* Keep the last known documents when the service is unavailable. */ }
      finally { clearTimeout(timeout); }
    })();
    return () => { controller.abort(); clearTimeout(timeout); };
  }, [active.id, endpoint, connection, uploadingId, updateSession]);
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

  const send = async (session: Session, prompt: string, retryId?: string) => {
    if (!prompt.trim() || queryRef.current || uploadRef.current) return;
    if (session.ragMode === 'strict' && !session.documents.some(d => d.status === 'indexed')) {
      setNotice(t.uploadFirst); setDocumentsOpen(true); return;
    }
    const requestSession = retryId ? { ...session, messages: session.messages.filter(m => m.id !== retryId) } : session;
    // A retried prompt is already present in history; do not duplicate it.
    const historySession = retryId ? { ...requestSession, messages: requestSession.messages.slice(0, -1) } : requestSession;
    const payload = buildQuery(historySession, settings, prompt);
    const controller = new AbortController();
    queryRef.current = { controller, sessionId: session.id };
    setGeneratingId(session.id); setNotice(null);
    const userMessage: Message = { id: crypto.randomUUID(), role: 'user', content: prompt.trim(), timestamp: Date.now() };
    updateSession(session.id, s => ({
      ...s, messages: retryId ? s.messages.filter(m => m.id !== retryId) : [...s.messages, userMessage],
      draft: retryId ? s.draft : '',
      title: s.messages.length ? s.title : prompt.trim().slice(0, 48) + (prompt.trim().length > 48 ? '…' : ''),
      updatedAt: Date.now(),
    }));
    const timeout = setTimeout(() => controller.abort('timeout'), 180000);
    try {
      const response = await fetch(endpoint + '/query', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload), signal: controller.signal,
      });
      if (!response.ok) throw new Error('query_failed');
      const data = parseAnswer(await response.json());
      if (controller.signal.aborted) return;
      updateSession(session.id, s => ({ ...s, messages: [...s.messages, {
        id: crypto.randomUUID(), role: 'assistant', content: data.answer, citations: data.citations, timestamp: Date.now(),
      }], updatedAt: Date.now() }));
      setConnection('online');
    } catch (error: unknown) {
      if (controller.signal.aborted && controller.signal.reason !== 'timeout') return;
      const content = controller.signal.reason === 'timeout' ? t.timeout
        : error instanceof Error && error.message === 'invalid_response' ? t.invalidResponse : t.queryFailed;
      updateSession(session.id, s => ({ ...s, messages: [...s.messages, {
        id: crypto.randomUUID(), role: 'assistant', content, error: true, timestamp: Date.now(),
      }], updatedAt: Date.now() }));
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
    const optimistic: SessionDocument[] = acceptedFiles.map(file => ({ name: file.name, size: file.size, status: 'uploading', enabled: true }));
    updateSession(sessionId, s => ({ ...s, documents: [...s.documents, ...optimistic], updatedAt: Date.now() }));
    try {
      for (const file of acceptedFiles) {
        const form = new FormData(); form.append('files', file); form.append('session_id', sessionId);
        const controller = new AbortController();
        const timeout = setTimeout(() => controller.abort(), 180000);
        try {
          const response = await fetch(endpoint + '/ingest', { method: 'POST', body: form, signal: controller.signal });
          if (!response.ok) {
            const detail: unknown = await response.json().catch(() => null);
            const text = isRecord(detail) && typeof detail.detail === 'string' ? detail.detail : '';
            if (text.includes('Scanned PDFs')) throw new Error(settings.language === 'fa' ? 'این PDF اسکن‌شده است و متن قابل انتخاب ندارد.' : 'This PDF is scanned and has no selectable text.');
            throw new Error(t.uploadFailed);
          }
          updateSession(sessionId, s => ({ ...s, documents: s.documents.map(d => d.name === file.name ? { ...d, status: 'indexed', errorMessage: undefined } : d) }));
        } catch (error: unknown) {
          updateSession(sessionId, s => ({ ...s, documents: s.documents.map(d => d.name === file.name ? {
            ...d, status: 'error', errorMessage: error instanceof Error && error.message !== 'Failed to fetch' && error.name !== 'AbortError' ? error.message : t.uploadFailed,
          } : d) }));
        } finally { clearTimeout(timeout); }
      }
    } finally { uploadRef.current = false; setUploadingId(undefined); }
  };

  const deleteSession = async (id: string): Promise<boolean> => {
    if (uploadingId === id) return false;
    const session = sessionsRef.current.find(s => s.id === id);
    if (!session) return true;
    try {
      if (session.documents.length || session.messages.length) {
        const response = await fetch(endpoint + '/sessions/' + id, { method: 'DELETE', signal: AbortSignal.timeout(15000) });
        if (!response.ok) return false;
      }
      if (queryRef.current?.sessionId === id) { queryRef.current.controller.abort('deleted'); queryRef.current = null; setGeneratingId(undefined); }
      const remaining = sessionsRef.current.filter(s => s.id !== id);
      if (!remaining.length) remaining.push(createSession(settings.language, settings.defaultMode));
      setSessions(remaining);
      if (activeId === id) setActiveId(remaining[0].id);
      return true;
    } catch { return false; }
  };

  const updateSettings = (updated: Partial<AppSettings>) => setSettings(current => ({ ...current, ...updated }));
  const selectedDocuments = active.documents.filter(d => d.status === 'indexed' && d.enabled !== false);
  const composer = <Composer key={active.id} value={active.draft ?? ''} onChange={draft => updateSession(active.id, s => ({ ...s, draft }))}
    onSendMessage={() => void send(active, active.draft ?? '')} onStopGenerating={stop}
    isGenerating={generatingId === active.id} isBusy={busy} activeMode={active.ragMode}
    onChangeMode={ragMode => updateSession(active.id, s => ({ ...s, ragMode }))}
    language={settings.language} onOpenDocuments={() => setDocumentsOpen(true)} documentCount={selectedDocuments.length} focusToken={focusToken} />;

  return <div className="app-shell">
    <a href="#message-input" className="skip-link">{t.messageLabel}</a>
    <Sidebar sessions={sessions} activeSessionId={active.id} generatingSessionId={generatingId}
      onSelectSession={id => { setActiveId(id); setNotice(null); setDocumentsOpen(false); if (isMobile) setSidebarOpen(false); }}
      onNewChat={newChat} onDeleteSession={deleteSession}
      onRenameSession={(id, title) => updateSession(id, s => ({ ...s, title, updatedAt: Date.now() }))}
      language={settings.language} theme={settings.theme}
      onToggleTheme={() => updateSettings({ theme: settings.theme === 'dark' ? 'light' : 'dark' })}
      onOpenSettings={() => setSettingsOpen(true)} isOpen={sidebarOpen} isMobile={isMobile} onClose={() => setSidebarOpen(false)}
      connection={connection} onRetryConnection={() => void checkHealth()} uploadingSessionId={uploadingId} />
    <main className="workspace">
      <Header title={active.title} language={settings.language} isSidebarOpen={sidebarOpen} isEmpty={!active.messages.length}
        documentCount={active.documents.length} onToggleSidebar={() => setSidebarOpen(value => !value)} onOpenDocuments={() => setDocumentsOpen(true)} />
      {(notice || storageError) && <div className="notice" role="status"><AlertCircle size={17} /><span>{storageError ? t.storageFailed : notice}</span>{!storageError && <button className="icon-button" onClick={() => setNotice(null)} aria-label={t.dismiss}><X size={16} /></button>}</div>}
      {active.messages.length === 0 ? <Welcome language={settings.language} composer={composer} onSelectStarter={(draft, index) => {
        updateSession(active.id, s => ({ ...s, draft, ragMode: index === 2 ? 'llm-only' : 'hybrid' }));
        setFocusToken(value => value + 1);
      }} /> : <>
        <ChatFeed key={active.id} messages={active.messages} language={settings.language} isGenerating={generatingId === active.id} activeMode={active.ragMode}
          isBusy={busy} onRetry={messageId => {
            const errorIndex = active.messages.findIndex(m => m.id === messageId);
            const previous = active.messages.slice(0, errorIndex).reverse().find(m => m.role === 'user');
            if (previous) void send(active, previous.content, messageId);
          }} />
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
      onToggleDocument={name => updateSession(active.id, s => {
        const selected = s.documents.filter(d => d.status === 'indexed' && d.enabled !== false);
        if (selected.length === 1 && selected[0].name === name) return s;
        return { ...s, documents: s.documents.map(d => d.name === name ? { ...d, enabled: d.enabled === false } : d) };
      })} />
    {settingsOpen && <SettingsModal settings={settings} onClose={() => setSettingsOpen(false)} onUpdateSettings={updateSettings} busy={busy}
      onClearAllData={() => { const fresh = createSession(settings.language, settings.defaultMode); setSessions([fresh]); setActiveId(fresh.id); setNotice(null); }} />}
  </div>;
}

