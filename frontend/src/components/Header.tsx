import { ChevronLeft, FolderOpen, PanelRightClose, PanelRightOpen } from 'lucide-react';
import type { Language } from '../types';
import { translations } from '../i18n/translations';

interface HeaderProps {
  title: string; language: Language; isSidebarOpen: boolean; isEmpty: boolean;
  documentCount: number; onToggleSidebar: () => void; onOpenDocuments: () => void; onNewChat: () => void;
}

export function Header({ title, language, isSidebarOpen, isEmpty, documentCount, onToggleSidebar, onOpenDocuments, onNewChat }: HeaderProps) {
  const t = translations[language];
  return <header className="workspace-header">
    <div className="header-leading">
      <button className="icon-button sidebar-toggle" onClick={onToggleSidebar} aria-label={t.sidebarToggle}
        aria-expanded={isSidebarOpen} aria-controls="conversation-sidebar">
        {isSidebarOpen ? <PanelRightClose size={20} /> : <PanelRightOpen size={20} />}
      </button>
      <button className="header-brand" onClick={onNewChat} title={t.newChat}>{t.appName}</button>
      <ChevronLeft size={13} className="breadcrumb-separator" />
      <span className="header-title" title={title}>{isEmpty ? t.newChat : title}</span>
    </div>
    <button className="documents-button" onClick={onOpenDocuments}>
      <FolderOpen size={17} /><span>{t.documents}</span>
      {documentCount > 0 && <span className="count-badge">{documentCount.toLocaleString(language)}</span>}
    </button>
  </header>;
}

