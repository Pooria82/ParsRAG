import React, { useState, useEffect, useCallback } from 'react';
import { Sidebar } from './components/Sidebar';
import { Header } from './components/Header';
import { DocumentCenter } from './components/DocumentCenter';
import { ChatFeed } from './components/ChatFeed';
import { Composer } from './components/Composer';
import { SettingsModal } from './components/SettingsModal';
import { Session, Message, SessionDocument, AppSettings, RAGMode, Citation } from './types';
import { translations } from './i18n/translations';

const STORAGE_KEY_SESSIONS = 'parsrag_sessions_v1';
const STORAGE_KEY_ACTIVE_ID = 'parsrag_active_session_id_v1';
const STORAGE_KEY_SETTINGS = 'parsrag_settings_v1';

const DEFAULT_SETTINGS: AppSettings = {
  language: 'fa',
  theme: 'dark',
  defaultMode: 'hybrid',
  strictThreshold: 0.80,
  dynamicDepth: true,
  topK: 15,
  selectedModel: 'llama3.1:8b',
  backendUrl: 'http://localhost:8000',
};

const createNewSessionObject = (lang: string, defaultMode: RAGMode): Session => {
  const id = `session_${Date.now()}_${Math.random().toString(36).substring(2, 7)}`;
  const title = lang === 'fa' ? 'گفتگوی جدید' : 'New Chat';
  return {
    id,
    title,
    createdAt: Date.now(),
    updatedAt: Date.now(),
    documents: [],
    messages: [],
    ragMode: defaultMode,
  };
};

export const App: React.FC = () => {
  // 1. Settings State
  const [settings, setSettings] = useState<AppSettings>(() => {
    try {
      const stored = localStorage.getItem(STORAGE_KEY_SETTINGS);
      return stored ? { ...DEFAULT_SETTINGS, ...JSON.parse(stored) } : DEFAULT_SETTINGS;
    } catch {
      return DEFAULT_SETTINGS;
    }
  });

  // 2. Sessions State
  const [sessions, setSessions] = useState<Session[]>(() => {
    try {
      const stored = localStorage.getItem(STORAGE_KEY_SESSIONS);
      if (stored) {
        const parsed = JSON.parse(stored);
        if (Array.isArray(parsed) && parsed.length > 0) return parsed;
      }
    } catch {
      // ignore
    }
    return [createNewSessionObject(settings.language, settings.defaultMode)];
  });

  // 3. Active Session ID
  const [activeSessionId, setActiveSessionId] = useState<string>(() => {
    try {
      const stored = localStorage.getItem(STORAGE_KEY_ACTIVE_ID);
      if (stored && sessions.some(s => s.id === stored)) return stored;
    } catch {
      // ignore
    }
    return sessions[0]?.id || '';
  });

  // 4. Operational UI States
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const [isGenerating, setIsGenerating] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [isBackendOnline, setIsBackendOnline] = useState(true);

  const t = translations[settings.language];
  const activeSession = sessions.find(s => s.id === activeSessionId) || sessions[0];

  // Apply Direction and Theme to document root
  useEffect(() => {
    document.documentElement.dir = settings.language === 'fa' ? 'rtl' : 'ltr';
    document.documentElement.setAttribute('data-theme', settings.theme);
    localStorage.setItem(STORAGE_KEY_SETTINGS, JSON.stringify(settings));
  }, [settings]);

  // Persist sessions
  useEffect(() => {
    localStorage.setItem(STORAGE_KEY_SESSIONS, JSON.stringify(sessions));
  }, [sessions]);

  // Persist active session ID
  useEffect(() => {
    if (activeSessionId) {
      localStorage.setItem(STORAGE_KEY_ACTIVE_ID, activeSessionId);
    }
  }, [activeSessionId]);

  // Health check & session files sync
  const checkHealth = useCallback(async () => {
    try {
      const res = await fetch(`${settings.backendUrl}/health`);
      setIsBackendOnline(res.ok);
    } catch {
      setIsBackendOnline(false);
    }
  }, [settings.backendUrl]);

  useEffect(() => {
    checkHealth();
    const interval = setInterval(checkHealth, 30000);
    return () => clearInterval(interval);
  }, [checkHealth]);

  // Sync session files from backend when active session changes
  useEffect(() => {
    if (!activeSession?.id) return;
    const syncFiles = async () => {
      try {
        const res = await fetch(`${settings.backendUrl}/sessions/${activeSession.id}/files`);
        if (res.ok) {
          const remoteFiles: string[] = await res.json();
          if (Array.isArray(remoteFiles) && remoteFiles.length > 0) {
            setSessions(prev =>
              prev.map(s => {
                if (s.id !== activeSession.id) return s;
                // Merge remote files
                const existingNames = new Set(s.documents.map(d => d.name));
                const mergedDocs = [...s.documents];
                remoteFiles.forEach(rf => {
                  if (!existingNames.has(rf)) {
                    mergedDocs.push({ name: rf, status: 'indexed' });
                  }
                });
                return { ...s, documents: mergedDocs };
              })
            );
          }
        }
      } catch {
        // ignore offline error
      }
    };
    syncFiles();
  }, [activeSession?.id, settings.backendUrl]);

  // Global Keyboard Shortcuts (Ctrl+N for new chat)
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'n') {
        e.preventDefault();
        handleNewChat();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [settings.language, settings.defaultMode]);

  // Session Handlers
  const handleNewChat = () => {
    const newSession = createNewSessionObject(settings.language, settings.defaultMode);
    setSessions(prev => [newSession, ...prev]);
    setActiveSessionId(newSession.id);
    setIsSidebarOpen(false);
  };

  const handleSelectSession = (id: string) => {
    setActiveSessionId(id);
    setIsSidebarOpen(false);
  };

  const handleDeleteSession = async (id: string) => {
    // Delete vectors on backend
    try {
      await fetch(`${settings.backendUrl}/sessions/${id}`, { method: 'DELETE' });
    } catch {
      // ignore
    }

    const filtered = sessions.filter(s => s.id !== id);
    if (filtered.length === 0) {
      const fresh = createNewSessionObject(settings.language, settings.defaultMode);
      setSessions([fresh]);
      setActiveSessionId(fresh.id);
    } else {
      setSessions(filtered);
      if (activeSessionId === id) {
        setActiveSessionId(filtered[0].id);
      }
    }
  };

  const handleRenameSession = (id: string, newTitle: string) => {
    setSessions(prev =>
      prev.map(s => (s.id === id ? { ...s, title: newTitle, updatedAt: Date.now() } : s))
    );
  };

  const handleClearAllData = () => {
    const fresh = createNewSessionObject(settings.language, settings.defaultMode);
    setSessions([fresh]);
    setActiveSessionId(fresh.id);
    localStorage.removeItem(STORAGE_KEY_SESSIONS);
    localStorage.removeItem(STORAGE_KEY_ACTIVE_ID);
  };

  // Document Upload Handlers (Decoupled from Messages)
  const handleUploadFiles = async (files: File[]) => {
    if (!activeSession || files.length === 0) return;

    const remainingSlots = 5 - activeSession.documents.length;
    if (remainingSlots <= 0) return;

    const filesToUpload = files.slice(0, remainingSlots);
    setIsUploading(true);

    // Add optimistic uploading state
    const optimisticDocs: SessionDocument[] = filesToUpload.map(f => ({
      name: f.name,
      size: f.size,
      status: 'uploading',
    }));

    setSessions(prev =>
      prev.map(s => (s.id === activeSession.id ? { ...s, documents: [...s.documents, ...optimisticDocs] } : s))
    );

    const formData = new FormData();
    filesToUpload.forEach(f => {
      formData.append('files', f);
    });
    formData.append('session_id', activeSession.id);

    try {
      const res = await fetch(`${settings.backendUrl}/ingest`, {
        method: 'POST',
        body: formData,
      });

      if (!res.ok) {
        const errorData = await res.json().catch(() => ({ detail: 'Upload failed' }));
        throw new Error(errorData.detail || 'Failed to ingest documents');
      }

      // Mark uploaded docs as indexed
      setSessions(prev =>
        prev.map(s => {
          if (s.id !== activeSession.id) return s;
          const updatedDocs = s.documents.map(d => {
            const isJustUploaded = filesToUpload.some(f => f.name === d.name);
            return isJustUploaded ? { ...d, status: 'indexed' as const } : d;
          });
          return { ...s, documents: updatedDocs };
        })
      );
    } catch (err: any) {
      setSessions(prev =>
        prev.map(s => {
          if (s.id !== activeSession.id) return s;
          const updatedDocs = s.documents.map(d => {
            const isJustUploaded = filesToUpload.some(f => f.name === d.name);
            return isJustUploaded ? { ...d, status: 'error' as const, errorMessage: err.message } : d;
          });
          return { ...s, documents: updatedDocs };
        })
      );
    } finally {
      setIsUploading(false);
    }
  };

  const handleRemoveDocument = (docName: string) => {
    setSessions(prev =>
      prev.map(s => {
        if (s.id !== activeSession.id) return s;
        return {
          ...s,
          documents: s.documents.filter(d => d.name !== docName),
        };
      })
    );
  };

  // Mode Change Handler
  const handleChangeMode = (mode: RAGMode) => {
    setSessions(prev =>
      prev.map(s => (s.id === activeSession.id ? { ...s, ragMode: mode } : s))
    );
  };

  // Message Send Handler
  const handleSendMessage = async (text: string) => {
    if (!text.trim() || !activeSession || isGenerating) return;

    const userMessage: Message = {
      id: `msg_${Date.now()}_user`,
      role: 'user',
      content: text,
      timestamp: Date.now(),
    };

    // Auto-generate title from first message
    const isFirstMessage = activeSession.messages.length === 0;
    const newTitle = isFirstMessage
      ? text.length > 28 ? `${text.substring(0, 28)}...` : text
      : activeSession.title;

    const updatedMessages = [...activeSession.messages, userMessage];

    setSessions(prev =>
      prev.map(s =>
        s.id === activeSession.id
          ? { ...s, title: newTitle, messages: updatedMessages, updatedAt: Date.now() }
          : s
      )
    );

    setIsGenerating(true);

    try {
      const chatHistoryPayload = activeSession.messages.slice(-10).map(m => ({
        role: m.role,
        content: m.content,
      }));

      const payload = {
        prompt: text,
        mode: activeSession.ragMode || settings.defaultMode,
        session_id: activeSession.id,
        top_k: settings.dynamicDepth ? null : settings.topK,
        chat_history: chatHistoryPayload,
      };

      const res = await fetch(`${settings.backendUrl}/query`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      if (!res.ok) {
        const errData = await res.json().catch(() => ({ detail: 'Failed to generate answer' }));
        throw new Error(errData.detail || `Server error (${res.status})`);
      }

      const data = await res.json();

      // Parse source nodes into citations
      const citations: Citation[] = (data.source_nodes || []).map((node: any, idx: number) => ({
        title: `${t.citationsTitle} ${idx + 1}`,
        filename: node.metadata?.filename || 'Document',
        body: node.text || '',
        score: node.score || 0,
      }));

      const assistantMessage: Message = {
        id: `msg_${Date.now()}_bot`,
        role: 'assistant',
        content: data.answer || '',
        timestamp: Date.now(),
        citations,
      };

      setSessions(prev =>
        prev.map(s =>
          s.id === activeSession.id
            ? { ...s, messages: [...s.messages, assistantMessage], updatedAt: Date.now() }
            : s
        )
      );
    } catch (err: any) {
      const errorMessage: Message = {
        id: `msg_${Date.now()}_err`,
        role: 'assistant',
        content: `⚠️ ${err.message || 'Error occurred while contacting backend.'}`,
        timestamp: Date.now(),
        error: true,
      };

      setSessions(prev =>
        prev.map(s =>
          s.id === activeSession.id
            ? { ...s, messages: [...s.messages, errorMessage], updatedAt: Date.now() }
            : s
        )
      );
    } finally {
      setIsGenerating(false);
    }
  };

  return (
    <div
      style={{
        display: 'flex',
        width: '100vw',
        height: '100vh',
        overflow: 'hidden',
        backgroundColor: 'var(--bg-base)',
      }}
    >
      {/* Session Sidebar */}
      <Sidebar
        sessions={sessions}
        activeSessionId={activeSession?.id || ''}
        onSelectSession={handleSelectSession}
        onNewChat={handleNewChat}
        onDeleteSession={handleDeleteSession}
        onRenameSession={handleRenameSession}
        language={settings.language}
        onToggleLanguage={() =>
          setSettings(s => ({ ...s, language: s.language === 'fa' ? 'en' : 'fa' }))
        }
        theme={settings.theme}
        onToggleTheme={() =>
          setSettings(s => ({ ...s, theme: s.theme === 'dark' ? 'light' : 'dark' }))
        }
        onOpenSettings={() => setIsSettingsOpen(true)}
        isOpen={isSidebarOpen}
        onClose={() => setIsSidebarOpen(false)}
        isBackendOnline={isBackendOnline}
      />

      {/* Main Chat Workspace */}
      <main
        style={{
          flex: 1,
          display: 'flex',
          flexDirection: 'column',
          height: '100%',
          overflow: 'hidden',
          backgroundColor: 'var(--bg-base)',
          position: 'relative',
        }}
      >
        {/* Top Header */}
        <Header
          title={activeSession?.title || t.newChat}
          activeMode={activeSession?.ragMode || settings.defaultMode}
          language={settings.language}
          onToggleLanguage={() =>
            setSettings(s => ({ ...s, language: s.language === 'fa' ? 'en' : 'fa' }))
          }
          onOpenSettings={() => setIsSettingsOpen(true)}
          onToggleSidebar={() => setIsSidebarOpen(!isSidebarOpen)}
        />

        {/* Dedicated Document Center (Decoupled from Messages) */}
        <DocumentCenter
          documents={activeSession?.documents || []}
          onUploadFiles={handleUploadFiles}
          onRemoveDocument={handleRemoveDocument}
          language={settings.language}
          isUploading={isUploading}
        />

        {/* Chat Messages Feed */}
        <ChatFeed
          messages={activeSession?.messages || []}
          language={settings.language}
          onSelectStarterPrompt={handleSendMessage}
          isGenerating={isGenerating}
        />

        {/* Floating Message Composer */}
        <Composer
          onSendMessage={handleSendMessage}
          onStopGenerating={() => setIsGenerating(false)}
          isGenerating={isGenerating}
          activeMode={activeSession?.ragMode || settings.defaultMode}
          onChangeMode={handleChangeMode}
          language={settings.language}
        />
      </main>

      {/* Settings Modal */}
      <SettingsModal
        isOpen={isSettingsOpen}
        onClose={() => setIsSettingsOpen(false)}
        settings={settings}
        onUpdateSettings={(updated) => setSettings(s => ({ ...s, ...updated }))}
        onClearAllData={handleClearAllData}
      />
    </div>
  );
};
