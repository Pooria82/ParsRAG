import { ChevronLeft, FolderOpen, PanelRightClose, PanelRightOpen } from 'lucide-react';
import type { Language } from '../types';
import { translations } from '../i18n/translations';

interface HeaderProps {
  title: string; language: Language; isSidebarOpen: boolean; isEmpty: boolean;
  documentCount: number; onToggleSidebar: () => void; onOpenDocuments: () => void;
}

export function Header({ title, language, isSidebarOpen, isEmpty, documentCount, onToggleSidebar, onOpenDocuments }: HeaderProps) {
  const t = translations[language];
  return <header className="workspace-header">
    <div className="header-leading">
      <button className="icon-button sidebar-toggle" onClick={onToggleSidebar} aria-label={t.sidebarToggle}
        aria-expanded={isSidebarOpen} aria-controls="conversation-sidebar">
        {isSidebarOpen ? <PanelRightClose size={20} /> : <PanelRightOpen size={20} />}
      </button>
      <span className="header-brand">{t.appName}</span>
      <ChevronLeft size={13} className="breadcrumb-separator" />
      <span className="header-title" title={title}>{isEmpty ? t.newChat : title}</span>
    </div>
    <button className="documents-button" onClick={onOpenDocuments}>
      <FolderOpen size={17} /><span>{t.documents}</span>
      {documentCount > 0 && <span className="count-badge">{documentCount.toLocaleString(language)}</span>}
    </button>
  </header>;
}

