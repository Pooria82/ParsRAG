import React, { useState, useRef, useEffect } from 'react';
import { ArrowUp, Square, ChevronUp, Zap, Shield, Brain, Check } from 'lucide-react';
import { RAGMode, Language } from '../types';
import { translations } from '../i18n/translations';

interface ComposerProps {
  onSendMessage: (text: string) => void;
  onStopGenerating?: () => void;
  isGenerating: boolean;
  activeMode: RAGMode;
  onChangeMode: (mode: RAGMode) => void;
  language: Language;
}

export const Composer: React.FC<ComposerProps> = ({
  onSendMessage,
  onStopGenerating,
  isGenerating,
  activeMode,
  onChangeMode,
  language,
}) => {
  const t = translations[language];
  const [input, setInput] = useState('');
  const [isModeOpen, setIsModeOpen] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const modePopupRef = useRef<HTMLDivElement>(null);

  // Auto-resize textarea
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 180)}px`;
    }
  }, [input]);

  // Click outside to close mode popup
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (modePopupRef.current && !modePopupRef.current.contains(e.target as Node)) {
        setIsModeOpen(false);
      }
    };
    if (isModeOpen) {
      document.addEventListener('mousedown', handleClickOutside);
    }
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, [isModeOpen]);

  const handleSend = () => {
    if (!input.trim() || isGenerating) return;
    onSendMessage(input.trim());
    setInput('');
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const modeIcons: Record<RAGMode, React.ReactNode> = {
    hybrid: <Zap size={14} style={{ color: 'var(--accent-emerald)' }} />,
    strict: <Shield size={14} style={{ color: 'var(--accent-amber)' }} />,
    'llm-only': <Brain size={14} style={{ color: 'var(--accent-purple)' }} />,
  };

  return (
    <div style={{ padding: '0.75rem 1rem 1.25rem 1rem', position: 'relative', width: '100%', maxWidth: '840px', margin: '0 auto' }}>
      {/* Upward Mode Popup */}
      {isModeOpen && (
        <div
          ref={modePopupRef}
          className="animate-slide-up"
          style={{
            position: 'absolute',
            bottom: 'calc(100% - 0.25rem)',
            insetInlineStart: '1rem',
            width: '320px',
            backgroundColor: 'var(--bg-surface)',
            border: '1px solid var(--border-medium)',
            borderRadius: 'var(--radius-lg)',
            boxShadow: 'var(--shadow-lg)',
            padding: '0.5rem',
            zIndex: 60,
            display: 'flex',
            flexDirection: 'column',
            gap: '0.35rem',
          }}
        >
          <div style={{ padding: '0.35rem 0.5rem', fontSize: '0.75rem', fontWeight: 600, color: 'var(--text-muted)' }}>
            {t.defaultModeLabel}
          </div>

          {(['hybrid', 'strict', 'llm-only'] as RAGMode[]).map((m) => {
            const isSelected = activeMode === m;
            const modeInfo = t.ragModes[m];

            return (
              <button
                key={m}
                onClick={() => {
                  onChangeMode(m);
                  setIsModeOpen(false);
                }}
                style={{
                  display: 'flex',
                  alignItems: 'flex-start',
                  gap: '0.6rem',
                  padding: '0.6rem 0.75rem',
                  borderRadius: 'var(--radius-md)',
                  backgroundColor: isSelected ? 'var(--bg-card)' : 'transparent',
                  border: isSelected ? '1px solid var(--border-medium)' : '1px solid transparent',
                  textAlign: 'start',
                  transition: 'background var(--transition-fast)',
                }}
                onMouseEnter={(e) => {
                  if (!isSelected) e.currentTarget.style.backgroundColor = 'var(--bg-card-hover)';
                }}
                onMouseLeave={(e) => {
                  if (!isSelected) e.currentTarget.style.backgroundColor = 'transparent';
                }}
              >
                <div style={{ marginTop: '0.15rem' }}>{modeIcons[m]}</div>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-primary)', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                    <span>{modeInfo.label}</span>
                    {isSelected && <Check size={14} style={{ color: 'var(--accent-emerald)' }} />}
                  </div>
                  <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)', marginTop: '0.2rem', lineHeight: 1.35 }}>
                    {modeInfo.desc}
                  </div>
                </div>
              </button>
            );
          })}
        </div>
      )}

      {/* Main Composer Box */}
      <div
        style={{
          borderRadius: 'var(--radius-lg)',
          backgroundColor: 'var(--bg-surface)',
          border: '1px solid var(--border-highlight)',
          boxShadow: 'var(--shadow-md)',
          padding: '0.5rem 0.75rem',
          display: 'flex',
          flexDirection: 'column',
          transition: 'border-color var(--transition-fast)',
        }}
        onFocus={() => {
          // highlight border
        }}
      >
        {/* Input Textarea */}
        <textarea
          ref={textareaRef}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={t.composerPlaceholder}
          rows={1}
          disabled={isGenerating}
          style={{
            width: '100%',
            background: 'transparent',
            border: 'none',
            resize: 'none',
            fontSize: '0.92rem',
            lineHeight: 1.5,
            padding: '0.35rem 0.25rem',
            color: 'var(--text-primary)',
            outline: 'none',
            maxHeight: '180px',
            minHeight: '24px',
          }}
        />

        {/* Toolbar Bottom Row */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginTop: '0.35rem' }}>
          {/* Mode Selector Pill Button */}
          <button
            onClick={() => setIsModeOpen(!isModeOpen)}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '0.4rem',
              padding: '0.35rem 0.65rem',
              borderRadius: 'var(--radius-full)',
              backgroundColor: 'var(--bg-card)',
              border: '1px solid var(--border-subtle)',
              fontSize: '0.78rem',
              color: 'var(--text-secondary)',
              fontWeight: 500,
              transition: 'all var(--transition-fast)',
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.backgroundColor = 'var(--bg-card-hover)';
              e.currentTarget.style.color = 'var(--text-primary)';
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.backgroundColor = 'var(--bg-card)';
              e.currentTarget.style.color = 'var(--text-secondary)';
            }}
          >
            {modeIcons[activeMode]}
            <span>{t.ragModes[activeMode].short}</span>
            <ChevronUp size={13} style={{ opacity: 0.7 }} />
          </button>

          {/* Send / Stop Button */}
          {isGenerating ? (
            <button
              onClick={onStopGenerating}
              style={{
                width: '32px',
                height: '32px',
                borderRadius: 'var(--radius-md)',
                backgroundColor: 'var(--accent-rose)',
                color: '#fff',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                boxShadow: 'var(--shadow-sm)',
              }}
              title={t.stop}
            >
              <Square size={14} fill="#fff" />
            </button>
          ) : (
            <button
              onClick={handleSend}
              disabled={!input.trim()}
              style={{
                width: '32px',
                height: '32px',
                borderRadius: 'var(--radius-md)',
                backgroundColor: input.trim() ? 'var(--accent-blue)' : 'var(--bg-card)',
                color: input.trim() ? '#fff' : 'var(--text-muted)',
                cursor: input.trim() ? 'pointer' : 'not-allowed',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                transition: 'all var(--transition-fast)',
                boxShadow: input.trim() ? 'var(--shadow-sm)' : 'none',
              }}
              title={t.send}
            >
              <ArrowUp size={16} />
            </button>
          )}
        </div>
      </div>
    </div>
  );
};
