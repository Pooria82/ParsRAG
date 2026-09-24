import { useEffect, useMemo, useRef, useState } from 'react';
import { Check, Loader2, MessageSquare, Moon, MoreHorizontal, Pencil, Plus, Search, Settings2, Sun, Trash2 } from 'lucide-react';
import type { Language, ModelConfiguration, Session, Theme } from '../types';
import { translations } from '../i18n/translations';
import { BrandMark } from './BrandMark';
import { Dialog } from './Dialog';
import { isApplePlatform, shortcutLabel } from '../core/shortcuts';

interface SidebarProps {
  sessions: Session[]; activeSessionId: string; generatingSessionId?: string;
  onSelectSession: (id: string) => void; onNewChat: () => void;
  onDeleteSession: (id: string) => Promise<boolean>; onRenameSession: (id: string, title: string) => void;
  language: Language; theme: Theme; onToggleTheme: (origin: { x: number; y: number }) => void;
  onOpenSettings: () => void; isOpen: boolean; isMobile: boolean; onClose: () => void;
  connection: 'checking' | 'preparing' | 'online' | 'offline'; onRetryConnection: () => void;
  modelRuntime?: ModelConfiguration;
  uploadingSessionId?: string;
  searchFocusToken?: number;
}

export function Sidebar(props: SidebarProps) {
  const { sessions, activeSessionId, onSelectSession, onNewChat, language, theme, isOpen, isMobile } = props;
  const t = translations[language];
  const newChatShortcut = shortcutLabel('newChat', isApplePlatform(navigator.platform || navigator.userAgent));
  const [search, setSearch] = useState('');
  const [edit, setEdit] = useState<{ session: Session; action: 'rename' | 'delete' } | null>(null);
  const [title, setTitle] = useState('');
  const [deleting, setDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState(false);
  const searchRef = useRef<HTMLInputElement>(null);
  useEffect(() => {
    if (!props.searchFocusToken) return;
    const frame = requestAnimationFrame(() => searchRef.current?.focus());
    return () => cancelAnimationFrame(frame);
  }, [props.searchFocusToken]);
  const groups = useMemo(() => {
    const midnight = new Date().setHours(0, 0, 0, 0);
    const yesterday = new Date(); yesterday.setDate(yesterday.getDate() - 1); yesterday.setHours(0, 0, 0, 0);
    const filtered = sessions.filter(s => s.messages.length > 0 || s.documents.length > 0)
      .filter(s => (s.title + ' ' + s.messages.map(m => m.content).join(' ')).toLocaleLowerCase().includes(search.toLocaleLowerCase()))
      .sort((a, b) => b.updatedAt - a.updatedAt);
    return [
      { label: t.today, items: filtered.filter(s => s.updatedAt >= midnight) },
      { label: t.yesterday, items: filtered.filter(s => s.updatedAt >= yesterday.getTime() && s.updatedAt < midnight) },
      { label: t.previous, items: filtered.filter(s => s.updatedAt < yesterday.getTime()) },
    ];
  }, [sessions, search, t]);
  const empty = groups.every(g => !g.items.length);
  const closeEdit = () => { if (!deleting) setEdit(null); };

  const content = <>
    <button className="sidebar-brand" onClick={() => { setSearch(''); onNewChat(); }} title={t.newChat}><BrandMark /><span><strong>{t.appName}</strong><small>{t.workspace}</small></span></button>
    <button className="new-chat-button" onClick={() => { setSearch(''); onNewChat(); }} title={`${t.newChat} · ${newChatShortcut}`}>
      <Plus size={19} /><span>{t.newChat}</span><span className="shortcut-symbol" aria-hidden="true">{newChatShortcut}</span>
    </button>
    <label className="history-search"><Search size={16} aria-hidden="true" />
      <input ref={searchRef} value={search} onChange={e => setSearch(e.target.value)} placeholder={t.searchChats} aria-label={t.searchChats} />
    </label>
    <nav className="history-list" aria-label={t.conversations}>
      {empty ? <div className="history-empty"><MessageSquare size={23} />
        <p>{search ? t.noChats : t.historyEmpty}</p>{!search && <span>{t.historyEmptyDesc}</span>}
      </div> : groups.map(group => group.items.length > 0 && <section className="history-group" key={group.label}>
        <h2>{group.label}</h2>
        {group.items.map(session => <div className={'history-row ' + (session.id === activeSessionId ? 'is-active' : '')} key={session.id}>
          <button className="history-select" onClick={() => onSelectSession(session.id)} aria-current={session.id === activeSessionId ? 'page' : undefined}>
            {props.generatingSessionId === session.id ? <Loader2 size={15} className="spin" /> : <MessageSquare size={15} />}
            <span>{session.title || t.untitled}</span>
          </button>
          <details className="history-menu" onKeyDown={e => { if (e.key === 'Escape') { e.currentTarget.removeAttribute('open'); e.currentTarget.querySelector('summary')?.focus(); } }}>
            <summary aria-label={t.chatOptions + ': ' + session.title}><MoreHorizontal size={17} /></summary>
            <div className="history-menu-popover">
              <button onClick={e => { e.currentTarget.closest('details')?.removeAttribute('open'); setTitle(session.title); setEdit({ session, action: 'rename' }); }}><Pencil size={14} />{t.rename}</button>
              <button className="danger-text" disabled={props.uploadingSessionId === session.id} onClick={e => { e.currentTarget.closest('details')?.removeAttribute('open'); setDeleteError(false); setEdit({ session, action: 'delete' }); }}><Trash2 size={14} />{t.delete}</button>
            </div>
          </details>
        </div>)}
      </section>)}
    </nav>
    <div className="sidebar-bottom">
      <div className="connection-status" data-status={props.connection}>
        <span className="status-dot" /><span><strong>{props.connection === 'checking' ? t.backendChecking : props.connection === 'preparing' ? t.backendPreparing : props.connection === 'online' ? t.backendOnline : t.backendOffline}</strong>
          {props.connection === 'online' && props.modelRuntime ? <small><bdi>{props.modelRuntime.provider === 'ollama' ? t.modelProviderOllama : t.modelProviderApi}</bdi><i aria-hidden="true">·</i><bdi dir="ltr">{props.modelRuntime.model_name}</bdi></small> : null}
        </span>
        {props.connection === 'offline' && <button onClick={props.onRetryConnection} title={t.retryConnection} aria-label={t.retryConnection}>↻</button>}
      </div>
      <div className="sidebar-footer">
        <button className="settings-button" onClick={props.onOpenSettings}><Settings2 size={18} /><span>{t.settingsTitle}</span></button>
        <button className="icon-button theme-toggle" onClick={event => {
          const bounds = event.currentTarget.getBoundingClientRect();
          props.onToggleTheme({ x: bounds.left + bounds.width / 2, y: bounds.top + bounds.height / 2 });
        }} aria-label={theme === 'dark' ? t.themeLight : t.themeDark} title={theme === 'dark' ? t.themeLight : t.themeDark}>
          {theme === 'dark' ? <Sun size={18} /> : <Moon size={18} />}
        </button>
      </div>
    </div>
  </>;

  return <>
    {isMobile ? <Dialog open={isOpen} onClose={props.onClose} title={t.conversations} closeLabel={t.close} className="sidebar-dialog">
      <div id="conversation-sidebar" className="sidebar-content">{content}</div>
    </Dialog> : <aside id="conversation-sidebar" className={'sidebar ' + (isOpen ? 'is-open' : '')} aria-hidden={!isOpen}>
      {isOpen && <div className="sidebar-content">{content}</div>}
    </aside>}
    <Dialog open={Boolean(edit)} onClose={closeEdit} title={edit?.action === 'rename' ? t.rename : t.deleteConfirmTitle} closeLabel={t.close} className="confirm-dialog">
      {edit?.action === 'rename' ? <form className="dialog-body" onSubmit={e => { e.preventDefault(); if (title.trim()) { props.onRenameSession(edit.session.id, title.trim()); setEdit(null); } }}>
        <label className="field-label" htmlFor="chat-title">{t.chatTitle}</label>
        <input id="chat-title" className="text-input" autoFocus value={title} onChange={e => setTitle(e.target.value)} maxLength={100} />
        <div className="dialog-actions"><button type="button" className="button secondary" onClick={closeEdit}>{t.cancel}</button><button className="button primary" disabled={!title.trim()}><Check size={16} />{t.save}</button></div>
      </form> : <div className="dialog-body"><p>{t.deleteConfirmDesc}</p><p className="confirm-chat-title">{edit?.session.title}</p>
        {deleteError && <p className="inline-error" role="alert">{t.deleteFailed}</p>}
        <div className="dialog-actions"><button className="button secondary" disabled={deleting} onClick={closeEdit}>{t.cancel}</button>
          <button className="button danger" disabled={deleting} onClick={async () => { if (!edit) return; setDeleting(true); const deleted = await props.onDeleteSession(edit.session.id); setDeleting(false); if (deleted) setEdit(null); else setDeleteError(true); }}>{deleting ? <Loader2 size={16} className="spin" /> : <Trash2 size={16} />}{deleting ? t.saving : t.delete}</button>
        </div>
      </div>}
    </Dialog>
  </>;
}

