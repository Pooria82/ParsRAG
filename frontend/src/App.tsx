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
import type { AppSettings, IngestionCapabilities, Message, ModelConfiguration, QueryStage, ResponseVariant, Session, SessionDocument } from './types';
import { translations } from './i18n/translations';
import { appendResponseVariant, buildQuery, createSession, DEFAULT_INGESTION_CAPABILITIES, fallbackConversationTitle, mergeRemoteDocuments, parseAnswer, prepareTurnRegeneration, selectConversationBranch, validateUploads } from './core/state';
import { isApplePlatform, resolveShortcut } from './core/shortcuts';

export function App() {
  const { settings, setSettings, sessions, setSessions, activeId, setActiveId, storageError } = usePersistentWorkspace();
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
  const [revealingMessageId, setRevealingMessageId] = useState<string>();
  const [modelRuntime, setModelRuntime] = useState<ModelConfiguration>();
  const [ingestionCapabilities, setIngestionCapabilities] = useState<IngestionCapabilities>(DEFAULT_INGESTION_CAPABILITIES);
  const [focusToken, setFocusToken] = useState(0);
  const [searchFocusToken, setSearchFocusToken] = useState(0);
  const [guideOpen, setGuideOpen] = useState(false);
  const [tourStage, setTourStage] = useState<TourStage>({});
  const [guideEligible] = useState(() => { try { return localStorage.getItem('parsrag_tour_v1') !== 'done'; } catch { return true; } });
  const queryRef = useRef<{ controller: AbortController; sessionId: string } | null>(null);
  const progressRef = useRef<AbortController>();
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
          } catch { setModelRuntime(undefined); }
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
    current.controller.abort('user');
    progressRef.current?.abort(); progressRef.current = undefined;
    queryRef.current = null; setGeneratingId(undefined);
    setQueryProgress(undefined);
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
    const firstTurn = !target && session.messages.length === 0;
    const fallbackTitle = fallbackConversationTitle(prompt);
    const historySession = prepared ? { ...session, messages: prepared.history } : session;
    const payload = buildQuery(historySession, settings, prompt);
    const controller = new AbortController();
    const progressController = new AbortController();
    const requestId = crypto.randomUUID();
    queryRef.current = { controller, sessionId: session.id };
    progressRef.current?.abort(); progressRef.current = progressController;
    setGeneratingId(session.id); setQueryProgress({ sessionId: session.id, stage: 'understanding' }); setNotice(null);
    const userMessage: Message = { id: target?.userId ?? crypto.randomUUID(), role: 'user', content: prompt.trim(), timestamp: Date.now() };
    updateSession(session.id, s => ({
      ...s, messages: target ? prepareTurnRegeneration(s.messages, target.userId, target.assistantId, prompt, Boolean(target.edit)).visible : [...s.messages, userMessage],
      draft: target ? s.draft : '',
      title: s.messages.length ? s.title : fallbackTitle,
      updatedAt: Date.now(),
    }));
    const timeout = setTimeout(() => controller.abort('timeout'), 180000);
    const pollProgress = async () => {
      if (progressController.signal.aborted) return;
      try {
        const stage = await api.queryProgress(requestId, progressController.signal);
        if (stage && stage !== 'complete' && stage !== 'failed' && !progressController.signal.aborted) {
          setQueryProgress({ sessionId: session.id, stage });
        }
      } catch { /* The answer request remains authoritative if progress polling is interrupted. */ }
      if (!progressController.signal.aborted) setTimeout(() => void pollProgress(), 350);
    };
    void pollProgress();
    try {
      const data = parseAnswer(await api.query({ ...payload, request_id: requestId }, controller.signal));
      if (controller.signal.aborted) return;
      const variant: ResponseVariant = { id: crypto.randomUUID(), content: data.answer, citations: data.citations, timestamp: Date.now(), prompt: prompt.trim(), continuation: [] };
      const responseMessageId = target?.assistantId ?? crypto.randomUUID();
      updateSession(session.id, s => {
        if (target?.assistantId && s.messages.some(message => message.id === target.assistantId)) {
          return { ...s, messages: s.messages.map(message => {
            if (message.id !== target.assistantId) return message;
            return appendResponseVariant(message, variant);
          }), updatedAt: Date.now() };
        }
        const assistant: Message = { id: responseMessageId, role: 'assistant', parentUserId: userMessage.id, content: variant.content, citations: variant.citations, timestamp: variant.timestamp, variants: [variant], activeVariant: 0 };
        return { ...s, messages: [...s.messages, assistant], updatedAt: Date.now() };
      });
      setRevealingMessageId(responseMessageId);
      setConnection('online');
      if (firstTurn) {
        void api.conversationTitle(prompt.trim(), settings.language, AbortSignal.timeout(120000)).then(title => {
          updateSession(session.id, current => current.title === fallbackTitle
            ? { ...current, title, updatedAt: Date.now() } : current);
        }).catch(() => { /* The local fallback remains valid when title generation is unavailable. */ });
      }
    } catch (error: unknown) {
      if (controller.signal.aborted && controller.signal.reason !== 'timeout') return;
      const content = controller.signal.reason === 'timeout' ? t.timeout
        : error instanceof Error && error.message === 'invalid_response' ? t.invalidResponse : t.queryFailed;
      const variant: ResponseVariant = { id: crypto.randomUUID(), content, error: true, timestamp: Date.now(), prompt: prompt.trim(), continuation: [] };
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
      progressController.abort();
      if (progressRef.current === progressController) progressRef.current = undefined;
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
          await api.ingest(file, sessionId, controller.signal, uploadProgress => updateSession(sessionId, s => ({ ...s, documents: s.documents.map(d => d.name === file.name ? uploadProgress >= 100
            ? { ...d, status: 'processing', uploadProgress: undefined }
            : { ...d, status: 'uploading', uploadProgress } : d) })));
          updateSession(sessionId, s => ({ ...s, documents: s.documents.map(d => d.name === file.name ? { ...d, status: 'indexed', uploadProgress: undefined, errorMessage: undefined } : d) }));
        } catch (error: unknown) {
          updateSession(sessionId, s => ({ ...s, documents: s.documents.map(d => d.name === file.name ? {
            ...d, status: 'error', errorMessage: error instanceof ApiError && error.code === 'ocr_unavailable'
              ? settings.language === 'fa' ? 'OCR این فایل تصویری در دسترس نیست یا غیرفعال شده است.' : 'OCR for this image-based file is unavailable or disabled.'
              : t.uploadFailed,
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
    } catch {
      updateSession(sessionId, session => ({ ...session, documents: session.documents.filter(doc => doc.name !== name) }));
      setUploadError({ sessionId, text: t.reuseDocumentFailed });
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
    isGenerating={generatingId === active.id} isBusy={busy} activeMode={active.ragMode}
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
      connection={connection} modelRuntime={modelRuntime} onRetryConnection={() => void checkHealth()} uploadingSessionId={uploadingId} />
    <main className="workspace">
      <Header title={active.title} language={settings.language} isSidebarOpen={sidebarOpen} isEmpty={!active.messages.length} onNewChat={newChat}
        documentCount={active.documents.length} onToggleSidebar={() => setSidebarOpen(value => !value)} onOpenDocuments={() => setDocumentsOpen(true)} />
      {(notice || storageError) && <div className="notice" role="status"><AlertCircle size={17} /><span>{storageError ? t.storageFailed : notice}</span>{!storageError && <button className="icon-button" onClick={() => setNotice(null)} aria-label={t.dismiss}><X size={16} /></button>}</div>}
      {pwa.updateReady && <div className="notice pwa-update" role="status"><span>{t.pwaUpdateReady}</span><button className="button secondary" disabled={busy} onClick={pwa.activateUpdate}>{t.pwaApplyUpdate}</button></div>}
      {active.messages.length === 0 ? <Welcome language={settings.language} composer={composer} onSelectStarter={(draft, index) => {
        updateSession(active.id, s => ({ ...s, draft, ragMode: index === 2 ? 'llm-only' : 'hybrid' }));
        setFocusToken(value => value + 1);
      }} /> : <>
        <ChatFeed key={active.id} messages={active.messages} language={settings.language} isGenerating={generatingId === active.id} activeMode={active.ragMode}
          queryStage={queryProgress?.sessionId === active.id ? queryProgress.stage : undefined}
          revealingMessageId={revealingMessageId} onRevealComplete={() => setRevealingMessageId(undefined)}
          isBusy={busy} onRetry={messageId => {
            const assistant = active.messages.find(message => message.id === messageId);
            const assistantIndex = active.messages.findIndex(message => message.id === messageId);
            const previous = assistant?.parentUserId ? active.messages.find(message => message.id === assistant.parentUserId) : active.messages.slice(0, assistantIndex).reverse().find(message => message.role === 'user');
            if (previous) void send(active, previous.content, { userId: previous.id, assistantId: messageId });
          }} onEditPrompt={(messageId, content) => {
            const userIndex = active.messages.findIndex(message => message.id === messageId);
            const assistant = active.messages.slice(userIndex + 1).find(message => message.role === 'assistant');
            void send(active, content, { userId: messageId, assistantId: assistant?.id, edit: true });
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
      onDeleteDocument={name => void deleteDocument(name)}
      onToggleDocument={name => updateSession(active.id, s => {
        return { ...s, documents: s.documents.map(d => d.name === name ? { ...d, enabled: d.enabled === false } : d) };
      })} />
    <SettingsModal open={settingsOpen} guided={guideOpen} guidedTab={guideOpen ? tourStage.settingsTab : undefined} guidedProvider={guideOpen ? tourStage.provider : undefined} settings={settings} onClose={() => setSettingsOpen(false)}
      onStartGuide={() => setGuideOpen(true)}
      canInstall={pwa.canInstall} onInstall={() => void pwa.install()}
      onModelConfigured={setModelRuntime}
      onUpdateSettings={updated => {
        if (updated.theme && updated.theme !== settings.theme) transitionTheme(updated.theme);
        else if (updated.language && updated.language !== settings.language) transitionLanguage(updated.language);
        else updateSettings(updated);
      }} busy={busy}
      onClearAllData={clearAllData} />
    <WorkspaceTour open={guideOpen} language={settings.language} onClose={closeGuide} onStageChange={changeTourStage} activeStage={tourStage} />
  </div>;
}

