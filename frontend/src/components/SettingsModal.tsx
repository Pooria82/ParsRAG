import React, { useState } from 'react';
import { X, Moon, Sun, Trash2, CheckCircle2 } from 'lucide-react';
import { AppSettings, RAGMode } from '../types';
import { translations } from '../i18n/translations';

interface SettingsModalProps {
  isOpen: boolean;
  onClose: () => void;
  settings: AppSettings;
  onUpdateSettings: (newSettings: Partial<AppSettings>) => void;
  onClearAllData: () => void;
}

const AVAILABLE_MODELS = [
  'llama3.1:8b',
  'deepseek-r1:14b',
  'gemma3:12b',
  'gemma3:27b',
  'qwen2.5-coder:7b',
  'qwen3:14b',
  'gpt-oss:20b',
];

export const SettingsModal: React.FC<SettingsModalProps> = ({
  isOpen,
  onClose,
  settings,
  onUpdateSettings,
  onClearAllData,
}) => {
  if (!isOpen) return null;

  const t = translations[settings.language];
  const [activeTab, setActiveTab] = useState<'general' | 'rag' | 'model'>('general');
  const [showClearConfirm, setShowClearConfirm] = useState(false);

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        backgroundColor: 'rgba(0, 0, 0, 0.65)',
        backdropFilter: 'blur(6px)',
        zIndex: 100,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '1rem',
      }}
      onClick={onClose}
    >
      <div
        className="animate-slide-up"
        style={{
          width: '100%',
          maxWidth: '560px',
          backgroundColor: 'var(--bg-surface)',
          border: '1px solid var(--border-medium)',
          borderRadius: 'var(--radius-lg)',
          boxShadow: 'var(--shadow-lg)',
          overflow: 'hidden',
          display: 'flex',
          flexDirection: 'column',
          maxHeight: '85vh',
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Modal Header */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            padding: '1rem 1.25rem',
            borderBottom: '1px solid var(--border-subtle)',
            backgroundColor: 'var(--bg-card)',
          }}
        >
          <h3 style={{ fontSize: '1.05rem', fontWeight: 600, color: 'var(--text-primary)' }}>
            {t.settingsTitle}
          </h3>
          <button
            onClick={onClose}
            style={{ padding: '0.25rem', color: 'var(--text-muted)' }}
            onMouseEnter={(e) => (e.currentTarget.style.color = 'var(--text-primary)')}
            onMouseLeave={(e) => (e.currentTarget.style.color = 'var(--text-muted)')}
          >
            <X size={18} />
          </button>
        </div>

        {/* Tabs Bar */}
        <div
          style={{
            display: 'flex',
            borderBottom: '1px solid var(--border-subtle)',
            backgroundColor: 'var(--bg-base)',
          }}
        >
          <button
            onClick={() => setActiveTab('general')}
            style={{
              flex: 1,
              padding: '0.75rem 0.5rem',
              fontSize: '0.85rem',
              fontWeight: 500,
              color: activeTab === 'general' ? 'var(--accent-blue)' : 'var(--text-secondary)',
              borderBottom: activeTab === 'general' ? '2px solid var(--accent-blue)' : '2px solid transparent',
              transition: 'all var(--transition-fast)',
            }}
          >
            {t.tabGeneral}
          </button>

          <button
            onClick={() => setActiveTab('rag')}
            style={{
              flex: 1,
              padding: '0.75rem 0.5rem',
              fontSize: '0.85rem',
              fontWeight: 500,
              color: activeTab === 'rag' ? 'var(--accent-blue)' : 'var(--text-secondary)',
              borderBottom: activeTab === 'rag' ? '2px solid var(--accent-blue)' : '2px solid transparent',
              transition: 'all var(--transition-fast)',
            }}
          >
            {t.tabRAG}
          </button>

          <button
            onClick={() => setActiveTab('model')}
            style={{
              flex: 1,
              padding: '0.75rem 0.5rem',
              fontSize: '0.85rem',
              fontWeight: 500,
              color: activeTab === 'model' ? 'var(--accent-blue)' : 'var(--text-secondary)',
              borderBottom: activeTab === 'model' ? '2px solid var(--accent-blue)' : '2px solid transparent',
              transition: 'all var(--transition-fast)',
            }}
          >
            {t.tabModel}
          </button>
        </div>

        {/* Tab Content Body */}
        <div style={{ padding: '1.25rem', overflowY: 'auto', flex: 1, display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
          {/* TAB 1: GENERAL */}
          {activeTab === 'general' && (
            <>
              {/* Language Selection */}
              <div>
                <label style={{ display: 'block', fontSize: '0.85rem', fontWeight: 600, marginBottom: '0.4rem' }}>
                  {t.languageLabel}
                </label>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.5rem' }}>
                  <button
                    onClick={() => onUpdateSettings({ language: 'fa' })}
                    style={{
                      padding: '0.65rem',
                      borderRadius: 'var(--radius-md)',
                      backgroundColor: settings.language === 'fa' ? 'var(--bg-active)' : 'var(--bg-card)',
                      border: settings.language === 'fa' ? '1px solid var(--accent-blue)' : '1px solid var(--border-subtle)',
                      color: settings.language === 'fa' ? 'var(--text-primary)' : 'var(--text-secondary)',
                      fontWeight: 600,
                      fontSize: '0.85rem',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      gap: '0.4rem',
                    }}
                  >
                    <span>فارسی (Persian - RTL)</span>
                    {settings.language === 'fa' && <CheckCircle2 size={15} style={{ color: 'var(--accent-emerald)' }} />}
                  </button>

                  <button
                    onClick={() => onUpdateSettings({ language: 'en' })}
                    style={{
                      padding: '0.65rem',
                      borderRadius: 'var(--radius-md)',
                      backgroundColor: settings.language === 'en' ? 'var(--bg-active)' : 'var(--bg-card)',
                      border: settings.language === 'en' ? '1px solid var(--accent-blue)' : '1px solid var(--border-subtle)',
                      color: settings.language === 'en' ? 'var(--text-primary)' : 'var(--text-secondary)',
                      fontWeight: 600,
                      fontSize: '0.85rem',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      gap: '0.4rem',
                    }}
                  >
                    <span>English (LTR)</span>
                    {settings.language === 'en' && <CheckCircle2 size={15} style={{ color: 'var(--accent-emerald)' }} />}
                  </button>
                </div>
              </div>

              {/* Theme Selection */}
              <div>
                <label style={{ display: 'block', fontSize: '0.85rem', fontWeight: 600, marginBottom: '0.4rem' }}>
                  {t.themeLabel}
                </label>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.5rem' }}>
                  <button
                    onClick={() => onUpdateSettings({ theme: 'dark' })}
                    style={{
                      padding: '0.65rem',
                      borderRadius: 'var(--radius-md)',
                      backgroundColor: settings.theme === 'dark' ? 'var(--bg-active)' : 'var(--bg-card)',
                      border: settings.theme === 'dark' ? '1px solid var(--accent-blue)' : '1px solid var(--border-subtle)',
                      color: 'var(--text-primary)',
                      fontSize: '0.85rem',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      gap: '0.4rem',
                    }}
                  >
                    <Moon size={15} />
                    <span>{t.themeDark}</span>
                  </button>

                  <button
                    onClick={() => onUpdateSettings({ theme: 'light' })}
                    style={{
                      padding: '0.65rem',
                      borderRadius: 'var(--radius-md)',
                      backgroundColor: settings.theme === 'light' ? 'var(--bg-active)' : 'var(--bg-card)',
                      border: settings.theme === 'light' ? '1px solid var(--accent-blue)' : '1px solid var(--border-subtle)',
                      color: 'var(--text-primary)',
                      fontSize: '0.85rem',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      gap: '0.4rem',
                    }}
                  >
                    <Sun size={15} />
                    <span>{t.themeLight}</span>
                  </button>
                </div>
              </div>
            </>
          )}

          {/* TAB 2: RAG CONFIGURATION */}
          {activeTab === 'rag' && (
            <>
              {/* Default Mode */}
              <div>
                <label style={{ display: 'block', fontSize: '0.85rem', fontWeight: 600, marginBottom: '0.4rem' }}>
                  {t.defaultModeLabel}
                </label>
                <select
                  value={settings.defaultMode}
                  onChange={(e) => onUpdateSettings({ defaultMode: e.target.value as RAGMode })}
                  style={{
                    width: '100%',
                    padding: '0.6rem 0.75rem',
                    borderRadius: 'var(--radius-md)',
                    backgroundColor: 'var(--bg-card)',
                    border: '1px solid var(--border-subtle)',
                    color: 'var(--text-primary)',
                    fontSize: '0.85rem',
                    outline: 'none',
                  }}
                >
                  <option value="hybrid">{t.ragModes.hybrid.label}</option>
                  <option value="strict">{t.ragModes.strict.label}</option>
                  <option value="llm-only">{t.ragModes['llm-only'].label}</option>
                </select>
              </div>

              {/* Strict Acceptance Threshold Slider */}
              <div>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.35rem' }}>
                  <label style={{ fontSize: '0.85rem', fontWeight: 600 }}>{t.strictThresholdLabel}</label>
                  <span style={{ fontSize: '0.82rem', color: 'var(--accent-emerald)', fontWeight: 600 }}>
                    {Math.round(settings.strictThreshold * 100)}% ({settings.strictThreshold.toFixed(2)})
                  </span>
                </div>
                <input
                  type="range"
                  min="0.50"
                  max="0.95"
                  step="0.05"
                  value={settings.strictThreshold}
                  onChange={(e) => onUpdateSettings({ strictThreshold: parseFloat(e.target.value) })}
                  style={{ width: '100%', accentColor: 'var(--accent-blue)' }}
                />
                <p style={{ fontSize: '0.72rem', color: 'var(--text-muted)', marginTop: '0.25rem' }}>
                  {t.strictThresholdDesc}
                </p>
              </div>

              {/* Dynamic Depth Switch */}
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  padding: '0.75rem',
                  borderRadius: 'var(--radius-md)',
                  backgroundColor: 'var(--bg-card)',
                  border: '1px solid var(--border-subtle)',
                }}
              >
                <div>
                  <div style={{ fontSize: '0.85rem', fontWeight: 600 }}>{t.dynamicDepthLabel}</div>
                  <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)', marginTop: '0.2rem' }}>
                    {t.dynamicDepthDesc}
                  </div>
                </div>
                <input
                  type="checkbox"
                  checked={settings.dynamicDepth}
                  onChange={(e) => onUpdateSettings({ dynamicDepth: e.target.checked })}
                  style={{
                    width: '18px',
                    height: '18px',
                    accentColor: 'var(--accent-emerald)',
                    cursor: 'pointer',
                  }}
                />
              </div>

              {/* Manual Top-K Slider */}
              <div style={{ opacity: settings.dynamicDepth ? 0.45 : 1, pointerEvents: settings.dynamicDepth ? 'none' : 'auto' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.35rem' }}>
                  <label style={{ fontSize: '0.85rem', fontWeight: 600 }}>{t.manualTopKLabel}</label>
                  <span style={{ fontSize: '0.82rem', color: 'var(--accent-blue)', fontWeight: 600 }}>
                    {settings.topK}
                  </span>
                </div>
                <input
                  type="range"
                  min="5"
                  max="30"
                  step="1"
                  disabled={settings.dynamicDepth}
                  value={settings.topK}
                  onChange={(e) => onUpdateSettings({ topK: parseInt(e.target.value) })}
                  style={{ width: '100%', accentColor: 'var(--accent-blue)' }}
                />
                <p style={{ fontSize: '0.72rem', color: 'var(--text-muted)', marginTop: '0.25rem' }}>
                  {t.manualTopKDesc}
                </p>
              </div>
            </>
          )}

          {/* TAB 3: MODEL & SERVER */}
          {activeTab === 'model' && (
            <>
              {/* Ollama Model Selection */}
              <div>
                <label style={{ display: 'block', fontSize: '0.85rem', fontWeight: 600, marginBottom: '0.4rem' }}>
                  {t.selectedModelLabel}
                </label>
                <select
                  value={settings.selectedModel}
                  onChange={(e) => onUpdateSettings({ selectedModel: e.target.value })}
                  style={{
                    width: '100%',
                    padding: '0.6rem 0.75rem',
                    borderRadius: 'var(--radius-md)',
                    backgroundColor: 'var(--bg-card)',
                    border: '1px solid var(--border-subtle)',
                    color: 'var(--text-primary)',
                    fontSize: '0.85rem',
                    outline: 'none',
                  }}
                >
                  {AVAILABLE_MODELS.map((m) => (
                    <option key={m} value={m}>
                      {m}
                    </option>
                  ))}
                </select>
              </div>

              {/* Backend URL */}
              <div>
                <label style={{ display: 'block', fontSize: '0.85rem', fontWeight: 600, marginBottom: '0.4rem' }}>
                  {t.backendUrlLabel}
                </label>
                <input
                  type="text"
                  value={settings.backendUrl}
                  onChange={(e) => onUpdateSettings({ backendUrl: e.target.value })}
                  style={{
                    width: '100%',
                    padding: '0.6rem 0.75rem',
                    borderRadius: 'var(--radius-md)',
                    backgroundColor: 'var(--bg-card)',
                    border: '1px solid var(--border-subtle)',
                    color: 'var(--text-primary)',
                    fontSize: '0.85rem',
                    fontFamily: 'monospace',
                  }}
                />
              </div>

              {/* Air Gapped Assurance Callout */}
              <div
                style={{
                  padding: '0.75rem 1rem',
                  borderRadius: 'var(--radius-md)',
                  backgroundColor: 'rgba(16, 185, 129, 0.1)',
                  border: '1px solid rgba(16, 185, 129, 0.25)',
                  color: 'var(--accent-emerald)',
                  fontSize: '0.78rem',
                  lineHeight: 1.45,
                }}
              >
                {t.airGappedNotice}
              </div>

              {/* Clear History Danger Zone */}
              <div style={{ marginTop: '0.5rem', paddingTop: '1rem', borderTop: '1px solid var(--border-subtle)' }}>
                {showClearConfirm ? (
                  <div
                    style={{
                      padding: '0.75rem',
                      borderRadius: 'var(--radius-md)',
                      backgroundColor: 'rgba(239, 68, 68, 0.1)',
                      border: '1px solid rgba(239, 68, 68, 0.3)',
                    }}
                  >
                    <p style={{ fontSize: '0.8rem', color: 'var(--accent-rose)', marginBottom: '0.6rem' }}>
                      {t.clearAllConfirm}
                    </p>
                    <div style={{ display: 'flex', gap: '0.5rem' }}>
                      <button
                        onClick={() => {
                          onClearAllData();
                          setShowClearConfirm(false);
                          onClose();
                        }}
                        style={{
                          padding: '0.4rem 0.8rem',
                          borderRadius: 'var(--radius-sm)',
                          backgroundColor: 'var(--accent-rose)',
                          color: '#fff',
                          fontSize: '0.8rem',
                          fontWeight: 600,
                        }}
                      >
                        {t.confirm}
                      </button>
                      <button
                        onClick={() => setShowClearConfirm(false)}
                        style={{
                          padding: '0.4rem 0.8rem',
                          borderRadius: 'var(--radius-sm)',
                          backgroundColor: 'var(--bg-card)',
                          color: 'var(--text-secondary)',
                          fontSize: '0.8rem',
                        }}
                      >
                        {t.cancel}
                      </button>
                    </div>
                  </div>
                ) : (
                  <button
                    onClick={() => setShowClearConfirm(true)}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '0.4rem',
                      color: 'var(--accent-rose)',
                      fontSize: '0.82rem',
                      padding: '0.4rem 0',
                    }}
                  >
                    <Trash2 size={15} />
                    <span>{t.clearAllData}</span>
                  </button>
                )}
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
};
