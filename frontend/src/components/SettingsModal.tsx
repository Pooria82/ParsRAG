import { useState } from 'react';
import { Check, CircleHelp, Database, Moon, SlidersHorizontal, Sun, Trash2 } from 'lucide-react';
import type { AppSettings, RAGMode } from '../types';
import { translations } from '../i18n/translations';
import { isLocalEndpoint, MODES } from '../core/state';
import { Dialog } from './Dialog';
import { ChoiceMenu } from './ui/ChoiceMenu';

interface SettingsModalProps {
  open?: boolean;
  onClose: () => void; settings: AppSettings;
  onUpdateSettings: (settings: Partial<AppSettings>) => void; onClearAllData: () => void; busy: boolean;
}

export function SettingsModal({ open = true, onClose, settings, onUpdateSettings, onClearAllData, busy }: SettingsModalProps) {
  const t = translations[settings.language];
  const [tab, setTab] = useState<'general' | 'rag' | 'connection'>('general');
  const [clearConfirm, setClearConfirm] = useState(false);
  const [endpoint, setEndpoint] = useState(settings.backendUrl);
  const [invalid, setInvalid] = useState(false);
  const [saved, setSaved] = useState(false);
  const tabs = [{ id: 'general', label: t.tabGeneral, Icon: Sun }, { id: 'rag', label: t.tabRAG, Icon: SlidersHorizontal }, { id: 'connection', label: t.tabModel, Icon: Database }] as const;
  return <Dialog open={open} onClose={onClose} title={t.settingsTitle} subtitle={t.settingsSubtitle} closeLabel={t.close} className="settings-dialog">
    <div className="settings-tabs" role="tablist" aria-label={t.settingsTitle}>
      {tabs.map(({ id, label, Icon }, index) => <button key={id} id={'tab-' + id} role="tab" aria-controls={'panel-' + id}
        aria-selected={tab === id} tabIndex={tab === id ? 0 : -1} onClick={() => setTab(id)}
        onKeyDown={event => {
          if (!['ArrowRight', 'ArrowLeft', 'Home', 'End'].includes(event.key)) return;
          event.preventDefault();
          const delta = (event.key === 'ArrowRight' ? 1 : -1) * (settings.language === 'fa' ? -1 : 1);
          const next = event.key === 'Home' ? 0 : event.key === 'End' ? tabs.length - 1 : (index + delta + tabs.length) % tabs.length;
          setTab(tabs[next].id); document.getElementById('tab-' + tabs[next].id)?.focus();
        }}><Icon size={16} />{label}</button>)}
    </div>
    <div key={tab} className="settings-body" role="tabpanel" id={'panel-' + tab} aria-labelledby={'tab-' + tab} tabIndex={0}>
      {tab === 'general' && <>
        <fieldset className="setting-field"><legend>{t.themeLabel}</legend><div className="theme-choices">
          {(['light', 'dark'] as const).map(theme => <label className={'theme-choice preview-' + theme + (settings.theme === theme ? ' is-selected' : '')} key={theme}>
            <input type="radio" name="theme" value={theme} checked={settings.theme === theme} onChange={() => onUpdateSettings({ theme })} />
            <span className="theme-preview" aria-hidden="true"><i /><span><b /><b /><em /></span></span>
            <span className="theme-choice-label">{theme === 'light' ? <Sun size={16} /> : <Moon size={16} />}{theme === 'light' ? t.themeLight : t.themeDark}{settings.theme === theme && <Check size={15} />}</span>
          </label>)}
        </div></fieldset>
        <fieldset className="setting-field"><legend>{t.languageLabel}</legend><div className="segmented-control">
          <label><input type="radio" name="language" checked={settings.language === 'fa'} onChange={() => onUpdateSettings({ language: 'fa' })} /><span lang="fa">فارسی</span></label>
          <label><input type="radio" name="language" checked={settings.language === 'en'} onChange={() => onUpdateSettings({ language: 'en' })} /><span lang="en">English</span></label>
        </div></fieldset>
      </>}
      {tab === 'rag' && <>
        <div className="setting-field"><label>{t.defaultModeLabel}</label>
          <ChoiceMenu<RAGMode> label={t.defaultModeLabel} value={settings.defaultMode}
            options={MODES.map(mode => ({ value: mode, label: t.ragModes[mode].label, description: t.ragModes[mode].desc }))}
            onChange={defaultMode => onUpdateSettings({ defaultMode })} disabled={busy} />
        </div>
        <label className="switch-setting"><span><strong>{t.dynamicDepthLabel}</strong><small>{t.dynamicDepthDesc}</small></span>
          <input type="checkbox" role="switch" checked={settings.dynamicDepth} onChange={e => onUpdateSettings({ dynamicDepth: e.target.checked })} />
        </label>
        {!settings.dynamicDepth && <div className="setting-field"><label htmlFor="top-k">{t.manualTopKLabel}<output>{settings.topK.toLocaleString(settings.language)}</output></label>
          <input type="range" id="top-k" min="1" max="50" value={settings.topK} onChange={e => onUpdateSettings({ topK: Number(e.target.value) })} />
        </div>}
        <p className="info-note"><CircleHelp size={18} />{t.serverManaged}</p>
      </>}
      {tab === 'connection' && <>
        <form className="setting-field" onSubmit={event => {
          event.preventDefault();
          if (!isLocalEndpoint(endpoint, window.location.origin)) { setInvalid(true); return; }
          onUpdateSettings({ backendUrl: endpoint.trim().replace(/\/+$/, '') }); setInvalid(false); setSaved(true);
        }}>
          <label htmlFor="backend-url">{t.backendUrlLabel}</label>
          <input className="text-input" id="backend-url" type="text" dir="ltr" placeholder="http://localhost:8000" value={endpoint} aria-invalid={invalid} aria-describedby="endpoint-hint" disabled={busy}
            onChange={e => { setEndpoint(e.target.value); setInvalid(false); setSaved(false); }} />
          <small id="endpoint-hint">{t.backendUrlHint}</small>
          {invalid && <p className="inline-error" role="alert">{t.invalidEndpoint}</p>}
          <div className="endpoint-save"><button className="button secondary" disabled={busy}>{t.save}</button>{saved && <span role="status"><Check size={14} />{t.saved}</span>}</div>
        </form>
        <div className="data-setting"><h3>{t.clearAllData}</h3><p>{t.clearAllDesc}</p>
          {!clearConfirm ? <button className="button danger-outline" disabled={busy} onClick={() => setClearConfirm(true)}><Trash2 size={16} />{t.clearAllData}</button>
            : <div className="clear-confirm"><strong>{t.clearAllConfirm}</strong><div className="dialog-actions"><button className="button secondary" onClick={() => setClearConfirm(false)}>{t.cancel}</button><button className="button danger" disabled={busy} onClick={() => { onClearAllData(); onClose(); }}>{t.clear}</button></div></div>}
        </div>
      </>}
    </div>
  </Dialog>;
}

