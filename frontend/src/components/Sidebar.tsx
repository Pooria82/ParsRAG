import React, { useState } from 'react';
import { Plus, MessageSquare, Trash2, Edit2, Check, X, Settings, ShieldCheck, Globe, Sun, Moon } from 'lucide-react';
import { Session, Language, Theme } from '../types';
import { translations } from '../i18n/translations';

interface SidebarProps {
  sessions: Session[];
  activeSessionId: string;
  onSelectSession: (id: string) => void;
  onNewChat: () => void;
  onDeleteSession: (id: string) => void;
  onRenameSession: (id: string, newTitle: string) => void;
  language: Language;
  onToggleLanguage: () => void;
  theme: Theme;
  onToggleTheme: () => void;
  onOpenSettings: () => void;
  isOpen: boolean;
  onClose: () => void;
  isBackendOnline: boolean;
}

export const Sidebar: React.FC<SidebarProps> = ({
  sessions,
  activeSessionId,
  onSelectSession,
  onNewChat,
  onDeleteSession,
  onRenameSession,
  language,
  onToggleLanguage,
  theme,
  onToggleTheme,
  onOpenSettings,
  isOpen,
  onClose,
  isBackendOnline,
}) => {
  const t = translations[language];
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editTitle, setEditTitle] = useState('');

  const startRename = (s: Session, e: React.MouseEvent) => {
    e.stopPropagation();
    setEditingId(s.id);
    setEditTitle(s.title);
  };

  const saveRename = (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    if (editTitle.trim()) {
      onRenameSession(id, editTitle.trim());
    }
    setEditingId(null);
  };

  const cancelRename = (e: React.MouseEvent) => {
    e.stopPropagation();
    setEditingId(null);
  };

  // Group sessions by date
  const now = Date.now();
  const dayMs = 24 * 60 * 60 * 1000;
  const todaySessions = sessions.filter(s => now - s.createdAt < dayMs);
  const yesterdaySessions = sessions.filter(s => now - s.createdAt >= dayMs && now - s.createdAt < 2 * dayMs);
  const olderSessions = sessions.filter(s => now - s.createdAt >= 2 * dayMs);

  const renderSessionItem = (session: Session) => {
    const isActive = session.id === activeSessionId;
    const isEditing = session.id === editingId;

    return (
      <div
        key={session.id}
        onClick={() => !isEditing && onSelectSession(session.id)}
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '0.6rem 0.75rem',
          borderRadius: 'var(--radius-md)',
          cursor: isEditing ? 'default' : 'pointer',
          backgroundColor: isActive ? 'var(--bg-active)' : 'transparent',
          color: isActive ? 'var(--text-primary)' : 'var(--text-secondary)',
          border: isActive ? '1px solid var(--border-medium)' : '1px solid transparent',
          transition: 'all var(--transition-fast)',
          marginBottom: '0.25rem',
          userSelect: 'none',
        }}
        onMouseEnter={(e) => {
          if (!isActive && !isEditing) {
            e.currentTarget.style.backgroundColor = 'var(--bg-card-hover)';
            e.currentTarget.style.color = 'var(--text-primary)';
          }
        }}
        onMouseLeave={(e) => {
          if (!isActive && !isEditing) {
            e.currentTarget.style.backgroundColor = 'transparent';
            e.currentTarget.style.color = 'var(--text-secondary)';
          }
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', flex: 1, minWidth: 0 }}>
          <MessageSquare size={16} style={{ flexShrink: 0, opacity: isActive ? 1 : 0.7 }} />
          {isEditing ? (
            <input
              type="text"
              value={editTitle}
              onChange={(e) => setEditTitle(e.target.value)}
              onClick={(e) => e.stopPropagation()}
              onKeyDown={(e) => {
                if (e.key === 'Enter') saveRename(session.id, e as any);
                if (e.key === 'Escape') setEditingId(null);
              }}
              autoFocus
              style={{
                background: 'var(--bg-base)',
                border: '1px solid var(--accent-blue)',
                color: 'var(--text-primary)',
                borderRadius: 'var(--radius-sm)',
                padding: '0.2rem 0.4rem',
                fontSize: '0.85rem',
                width: '100%',
              }}
            />
          ) : (
            <span
              style={{
                fontSize: '0.875rem',
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                whiteSpace: 'nowrap',
                fontWeight: isActive ? 500 : 400,
              }}
              title={session.title}
            >
              {session.title}
            </span>
          )}
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '0.25rem', flexShrink: 0 }}>
          {isEditing ? (
            <>
              <button
                onClick={(e) => saveRename(session.id, e)}
                style={{ padding: '0.25rem', color: 'var(--accent-emerald)' }}
                title={t.save}
              >
                <Check size={14} />
              </button>
              <button
                onClick={cancelRename}
                style={{ padding: '0.25rem', color: 'var(--text-muted)' }}
                title={t.cancel}
              >
                <X size={14} />
              </button>
            </>
          ) : (
            <>
              {session.documents.length > 0 && (
                <span
                  style={{
                    fontSize: '0.7rem',
                    padding: '0.1rem 0.35rem',
                    borderRadius: 'var(--radius-full)',
                    background: 'var(--bg-card)',
                    color: 'var(--accent-emerald)',
                    border: '1px solid var(--border-subtle)',
                    marginInlineEnd: '0.25rem',
                  }}
                  title={t.docCenterCounter(session.documents.length, 5)}
                >
                  {session.documents.length}
                </span>
              )}
              <button
                onClick={(e) => startRename(session, e)}
                style={{
                  padding: '0.25rem',
                  color: 'var(--text-muted)',
                  opacity: isActive ? 0.8 : 0,
                  transition: 'opacity var(--transition-fast)',
                }}
                className="session-action-btn"
                title={t.rename}
              >
                <Edit2 size={13} />
              </button>
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  onDeleteSession(session.id);
                }}
                style={{
                  padding: '0.25rem',
                  color: 'var(--accent-rose)',
                  opacity: isActive ? 0.8 : 0,
                  transition: 'opacity var(--transition-fast)',
                }}
                className="session-action-btn"
                title={t.delete}
              >
                <Trash2 size={13} />
              </button>
            </>
          )}
        </div>
      </div>
    );
  };

  return (
    <>
      {/* Mobile Backdrop */}
      {isOpen && (
        <div
          onClick={onClose}
          style={{
            position: 'fixed',
            inset: 0,
            background: 'rgba(0, 0, 0, 0.6)',
            zIndex: 40,
            backdropFilter: 'blur(4px)',
          }}
        />
      )}

      <aside
        style={{
          width: '280px',
          height: '100%',
          backgroundColor: 'var(--bg-surface)',
          borderInlineEnd: '1px solid var(--border-subtle)',
          display: 'flex',
          flexDirection: 'column',
          zIndex: 50,
          transition: 'transform var(--transition-normal)',
          flexShrink: 0,
        }}
      >
        {/* Header Branding & New Chat Button */}
        <div style={{ padding: '1rem', borderBottom: '1px solid var(--border-subtle)' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1rem' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
              <div
                style={{
                  width: '32px',
                  height: '32px',
                  borderRadius: 'var(--radius-md)',
                  background: 'linear-gradient(135deg, var(--accent-emerald), var(--accent-blue))',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  color: '#fff',
                  boxShadow: 'var(--shadow-sm)',
                }}
              >
                <ShieldCheck size={18} />
              </div>
              <div>
                <h1 style={{ fontSize: '1rem', fontWeight: 700, lineHeight: 1.2 }}>{t.appName}</h1>
                <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>Air-Gapped RAG</span>
              </div>
            </div>
            
            {/* Close button on mobile */}
            <button
              onClick={onClose}
              style={{ display: 'none', padding: '0.4rem', color: 'var(--text-secondary)' }}
              className="sidebar-close-btn"
            >
              <X size={18} />
            </button>
          </div>

          <button
            onClick={onNewChat}
            style={{
              width: '100%',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              padding: '0.65rem 0.85rem',
              borderRadius: 'var(--radius-md)',
              backgroundColor: 'var(--bg-card)',
              color: 'var(--text-primary)',
              border: '1px solid var(--border-medium)',
              boxShadow: 'var(--shadow-sm)',
              fontWeight: 500,
              fontSize: '0.875rem',
              transition: 'all var(--transition-fast)',
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.backgroundColor = 'var(--bg-card-hover)';
              e.currentTarget.style.borderColor = 'var(--accent-blue)';
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.backgroundColor = 'var(--bg-card)';
              e.currentTarget.style.borderColor = 'var(--border-medium)';
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <Plus size={16} style={{ color: 'var(--accent-emerald)' }} />
              <span>{t.newChat}</span>
            </div>
            <kbd
              style={{
                fontSize: '0.7rem',
                padding: '0.1rem 0.4rem',
                borderRadius: 'var(--radius-sm)',
                background: 'var(--bg-base)',
                color: 'var(--text-muted)',
                border: '1px solid var(--border-subtle)',
              }}
            >
              {t.newChatShortcut}
            </kbd>
          </button>
        </div>

        {/* Sessions Scrollable List */}
        <div style={{ flex: 1, overflowY: 'auto', padding: '0.75rem' }}>
          {sessions.length === 0 ? (
            <div style={{ padding: '2rem 1rem', textAlign: 'center', color: 'var(--text-muted)', fontSize: '0.85rem' }}>
              {t.noChats}
            </div>
          ) : (
            <>
              {todaySessions.length > 0 && (
                <div style={{ marginBottom: '1rem' }}>
                  <span style={{ fontSize: '0.72rem', fontWeight: 600, color: 'var(--text-muted)', padding: '0 0.5rem' }}>
                    {t.today}
                  </span>
                  <div style={{ marginTop: '0.35rem' }}>
                    {todaySessions.map(renderSessionItem)}
                  </div>
                </div>
              )}

              {yesterdaySessions.length > 0 && (
                <div style={{ marginBottom: '1rem' }}>
                  <span style={{ fontSize: '0.72rem', fontWeight: 600, color: 'var(--text-muted)', padding: '0 0.5rem' }}>
                    {t.yesterday}
                  </span>
                  <div style={{ marginTop: '0.35rem' }}>
                    {yesterdaySessions.map(renderSessionItem)}
                  </div>
                </div>
              )}

              {olderSessions.length > 0 && (
                <div style={{ marginBottom: '1rem' }}>
                  <span style={{ fontSize: '0.72rem', fontWeight: 600, color: 'var(--text-muted)', padding: '0 0.5rem' }}>
                    {t.previous}
                  </span>
                  <div style={{ marginTop: '0.35rem' }}>
                    {olderSessions.map(renderSessionItem)}
                  </div>
                </div>
              )}
            </>
          )}
        </div>

        {/* Footer Actions */}
        <div
          style={{
            padding: '0.75rem 1rem',
            borderTop: '1px solid var(--border-subtle)',
            backgroundColor: 'var(--bg-surface)',
            display: 'flex',
            flexDirection: 'column',
            gap: '0.5rem',
          }}
        >
          {/* Quick status badge */}
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              fontSize: '0.75rem',
              color: isBackendOnline ? 'var(--accent-emerald)' : 'var(--accent-rose)',
              padding: '0.3rem 0.5rem',
              borderRadius: 'var(--radius-sm)',
              background: 'var(--bg-base)',
              border: '1px solid var(--border-subtle)',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
              <span
                style={{
                  width: '7px',
                  height: '7px',
                  borderRadius: '50%',
                  background: isBackendOnline ? 'var(--accent-emerald)' : 'var(--accent-rose)',
                  display: 'inline-block',
                }}
                className={isBackendOnline ? 'animate-pulse-subtle' : ''}
              />
              <span>{isBackendOnline ? t.backendOnline : t.backendOffline}</span>
            </div>
            <span style={{ color: 'var(--text-muted)', fontSize: '0.7rem' }}>:8000</span>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginTop: '0.25rem' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.3rem' }}>
              {/* Language Switch */}
              <button
                onClick={onToggleLanguage}
                style={{
                  padding: '0.45rem',
                  borderRadius: 'var(--radius-md)',
                  color: 'var(--text-secondary)',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.3rem',
                  fontSize: '0.8rem',
                  border: '1px solid var(--border-subtle)',
                }}
                title={language === 'fa' ? 'Switch to English' : 'تغییر به زبان فارسی'}
              >
                <Globe size={15} />
                <span style={{ fontWeight: 600 }}>{language === 'fa' ? 'EN' : 'فا'}</span>
              </button>

              {/* Theme Switch */}
              <button
                onClick={onToggleTheme}
                style={{
                  padding: '0.45rem',
                  borderRadius: 'var(--radius-md)',
                  color: 'var(--text-secondary)',
                  border: '1px solid var(--border-subtle)',
                }}
                title={theme === 'dark' ? t.themeLight : t.themeDark}
              >
                {theme === 'dark' ? <Sun size={15} /> : <Moon size={15} />}
              </button>
            </div>

            {/* Settings Button */}
            <button
              onClick={onOpenSettings}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '0.4rem',
                padding: '0.45rem 0.65rem',
                borderRadius: 'var(--radius-md)',
                color: 'var(--text-secondary)',
                border: '1px solid var(--border-subtle)',
                fontSize: '0.8rem',
              }}
              title={t.settingsTitle}
            >
              <Settings size={15} />
              <span>{t.settingsTitle}</span>
            </button>
          </div>
        </div>
      </aside>
    </>
  );
};
