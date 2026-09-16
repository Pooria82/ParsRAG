import React from 'react';
import { Menu, Globe, Settings, Zap, Shield, Brain } from 'lucide-react';
import { RAGMode, Language } from '../types';
import { translations } from '../i18n/translations';

interface HeaderProps {
  title: string;
  activeMode: RAGMode;
  language: Language;
  onToggleLanguage: () => void;
  onOpenSettings: () => void;
  onToggleSidebar: () => void;
}

export const Header: React.FC<HeaderProps> = ({
  title,
  activeMode,
  language,
  onToggleLanguage,
  onOpenSettings,
  onToggleSidebar,
}) => {
  const t = translations[language];

  const modeIcons: Record<RAGMode, React.ReactNode> = {
    hybrid: <Zap size={14} style={{ color: 'var(--accent-emerald)' }} />,
    strict: <Shield size={14} style={{ color: 'var(--accent-amber)' }} />,
    'llm-only': <Brain size={14} style={{ color: 'var(--accent-purple)' }} />,
  };

  return (
    <header
      style={{
        height: '56px',
        padding: '0 1rem',
        borderBottom: '1px solid var(--border-subtle)',
        backgroundColor: 'var(--bg-surface)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        flexShrink: 0,
        zIndex: 10,
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', minWidth: 0, flex: 1 }}>
        <button
          onClick={onToggleSidebar}
          style={{
            padding: '0.4rem',
            borderRadius: 'var(--radius-md)',
            color: 'var(--text-secondary)',
            display: 'flex',
            alignItems: 'center',
          }}
          title="Toggle Sidebar"
        >
          <Menu size={18} />
        </button>

        <h2
          style={{
            fontSize: '0.95rem',
            fontWeight: 600,
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
            color: 'var(--text-primary)',
          }}
          title={title}
        >
          {title}
        </h2>
      </div>

      <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', flexShrink: 0 }}>
        {/* Mode Pill Badge */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '0.35rem',
            padding: '0.3rem 0.6rem',
            borderRadius: 'var(--radius-full)',
            background: 'var(--bg-base)',
            border: '1px solid var(--border-subtle)',
            fontSize: '0.75rem',
            fontWeight: 500,
            color: 'var(--text-secondary)',
          }}
        >
          {modeIcons[activeMode]}
          <span>{t.ragModes[activeMode].short}</span>
        </div>

        {/* Fast Language Switcher */}
        <button
          onClick={onToggleLanguage}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '0.3rem',
            padding: '0.35rem 0.6rem',
            borderRadius: 'var(--radius-md)',
            background: 'var(--bg-base)',
            border: '1px solid var(--border-subtle)',
            fontSize: '0.75rem',
            fontWeight: 600,
            color: 'var(--text-secondary)',
          }}
          title={language === 'fa' ? 'Switch to English' : 'تغییر به زبان فارسی'}
        >
          <Globe size={14} />
          <span>{language === 'fa' ? 'EN' : 'فا'}</span>
        </button>

        {/* Settings button */}
        <button
          onClick={onOpenSettings}
          style={{
            padding: '0.4rem',
            borderRadius: 'var(--radius-md)',
            color: 'var(--text-secondary)',
            display: 'flex',
            alignItems: 'center',
          }}
          title={t.settingsTitle}
        >
          <Settings size={18} />
        </button>
      </div>
    </header>
  );
};
