import { useEffect, useMemo, useState } from 'react';
import { Check, CircleHelp, Database, Download, KeyRound, Keyboard, Moon, RefreshCw, ShieldCheck, SlidersHorizontal, Sun, Trash2 } from 'lucide-react';
import type { AppSettings, ModelConfiguration, ModelProvider, OllamaModel, RAGMode } from '../types';
import { translations } from '../i18n/translations';
import { isLocalEndpoint, MODES } from '../core/state';
import { Dialog } from './Dialog';
import { ChoiceMenu } from './ui/ChoiceMenu';
import { ParsRagApiClient } from '../services/api';
import { isApplePlatform, SHORTCUTS, shortcutLabel } from '../core/shortcuts';

interface SettingsModalProps {
  open?: boolean;
  onClose: () => void; settings: AppSettings;
  onUpdateSettings: (settings: Partial<AppSettings>) => void; onClearAllData: () => Promise<void>; busy: boolean;
  onModelConfigured?: (configuration: ModelConfiguration) => void;
  onStartGuide: () => void;
  canInstall?: boolean; onInstall?: () => void;
}

export function SettingsModal({ open = true, onClose, settings, onUpdateSettings, onClearAllData, busy, onModelConfigured, onStartGuide, canInstall, onInstall }: SettingsModalProps) {
  const t = translations[settings.language];
  const applePlatform = isApplePlatform(navigator.platform || navigator.userAgent);
  const [tab, setTab] = useState<'general' | 'rag' | 'connection'>('general');
  const [clearConfirm, setClearConfirm] = useState(false);
  const [clearStatus, setClearStatus] = useState<'idle' | 'loading' | 'error'>('idle');
  const [endpoint, setEndpoint] = useState(settings.backendUrl);
  const [invalid, setInvalid] = useState(false);
  const [saved, setSaved] = useState(false);
  const [provider, setProvider] = useState<ModelProvider>('api');
  const [apiModelName, setApiModelName] = useState(settings.apiModelName);
  const [ollamaModelName, setOllamaModelName] = useState(settings.ollamaModelName);
  const [apiModelUrl, setApiModelUrl] = useState(settings.apiBaseUrl);
  const [ollamaModelUrl, setOllamaModelUrl] = useState(settings.ollamaBaseUrl);
  const [apiKey, setApiKey] = useState('');
  const [apiDisclosureAccepted, setApiDisclosureAccepted] = useState(false);
  const [keyConfigured, setKeyConfigured] = useState(false);
  const [models, setModels] = useState<OllamaModel[]>([]);
  const [modelStatus, setModelStatus] = useState<'idle' | 'loading' | 'saved' | 'error'>('idle');
  const [modelError, setModelError] = useState<string | null>(null);
  const modelApi = useMemo(() => new ParsRagApiClient(settings.backendUrl), [settings.backendUrl]);
  const modelName = provider === 'api' ? apiModelName : ollamaModelName;
  const setModelName = (value: string) => provider === 'api' ? setApiModelName(value) : setOllamaModelName(value);
  const modelUrl = provider === 'api' ? apiModelUrl : ollamaModelUrl;
  const setModelUrl = (value: string) => provider === 'api' ? setApiModelUrl(value) : setOllamaModelUrl(value);
  useEffect(() => {
    if (!open || tab !== 'connection') return;
    const controller = new AbortController(); setModelStatus('idle'); setModelError(null);
    void modelApi.modelConfiguration(controller.signal).then(config => {
      setProvider(config.provider);
      if (config.provider === 'api') { setApiModelName(config.model_name); setApiModelUrl(config.base_url); }
      else { setOllamaModelName(config.model_name); setOllamaModelUrl(config.base_url); }
      setKeyConfigured(config.api_key_configured);
      setApiDisclosureAccepted(config.disclosure_acknowledged);
      onUpdateSettings({ selectedModel: config.model_name, ...(config.provider === 'api'
        ? { apiModelName: config.model_name, apiBaseUrl: config.base_url }
        : { ollamaModelName: config.model_name, ollamaBaseUrl: config.base_url }) });
    }).catch(() => { /* Keep editable defaults when an older or offline service cannot expose configuration. */ });
    return () => controller.abort();
  }, [open, tab, modelApi]);
  const loadOllamaModels = async () => {
    setModelStatus('loading'); setModelError(null);
    try {
      const installed = await modelApi.ollamaModels(modelUrl);
      setModels(installed); if (installed.length && !installed.some(model => model.name === ollamaModelName)) setOllamaModelName(installed[0].name);
      setModelStatus('idle');
    } catch { setModelStatus('error'); setModelError(t.ollamaConnectionError); }
  };
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
        <fieldset className="setting-field"><legend>{t.paletteLabel}</legend><div className="palette-choices">
          {(['evergreen', 'ocean', 'indigo', 'sienna'] as const).map(palette => <label className={'palette-choice palette-' + palette} key={palette}>
            <input type="radio" name="palette" checked={settings.palette === palette} onChange={() => onUpdateSettings({ palette })} />
            <span className="palette-swatch" aria-hidden="true" /><span>{t.palettes[palette]}</span>{settings.palette === palette && <Check size={14} />}
          </label>)}
        </div></fieldset>
        <fieldset className="setting-field"><legend>{t.languageLabel}</legend><div className="segmented-control">
          <label><input type="radio" name="language" checked={settings.language === 'fa'} onChange={() => onUpdateSettings({ language: 'fa' })} /><span lang="fa">فارسی</span></label>
          <label><input type="radio" name="language" checked={settings.language === 'en'} onChange={() => onUpdateSettings({ language: 'en' })} /><span lang="en">English</span></label>
        </div></fieldset>
        <div className="setting-field guide-setting"><span><strong>{t.guideReplay}</strong><small>{t.guideReplayHint}</small></span>
          <button className="button secondary" onClick={() => { onClose(); onStartGuide(); }}><CircleHelp size={16} />{t.guideStart}</button>
        </div>
        <section className="shortcut-guide" aria-label={t.shortcutTitle}>
          <h3><Keyboard size={17} />{t.shortcutTitle}</h3><p>{t.shortcutHint}</p>
          <dl>{SHORTCUTS.map(shortcut => <div key={shortcut.action}><dt>{t.shortcutActions[shortcut.action]}</dt><dd><kbd dir="ltr">{shortcutLabel(shortcut.action, applePlatform)}</kbd></dd></div>)}</dl>
        </section>
        {canInstall && <div className="setting-field guide-setting"><span><strong>{t.pwaInstallTitle}</strong><small>{t.pwaInstallHint}</small></span>
          <button className="button secondary" onClick={onInstall}><Download size={16} />{t.pwaInstall}</button>
        </div>}
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
        <form className="model-settings" onSubmit={event => {
          event.preventDefault();
          if (provider === 'api' && !apiDisclosureAccepted) { setModelStatus('error'); setModelError(t.apiConsentRequired); return; }
          setModelStatus('loading'); setModelError(null);
          void modelApi.configureModel({ provider, model_name: modelName.trim(), base_url: modelUrl.trim(), disclosure_acknowledged: provider === 'api' && apiDisclosureAccepted, ...(apiKey ? { api_key: apiKey } : {}) }).then(config => {
            setKeyConfigured(config.api_key_configured); setApiKey(''); setModelStatus('saved');
            onModelConfigured?.(config);
            onUpdateSettings({ selectedModel: config.model_name, ...(config.provider === 'api'
              ? { apiModelName: config.model_name, apiBaseUrl: config.base_url }
              : { ollamaModelName: config.model_name, ollamaBaseUrl: config.base_url }) });
          }).catch(() => { setModelStatus('error'); setModelError(t.modelSaveError); });
        }}>
          <div className="setting-field"><label>{t.modelProviderLabel}</label><div className="segmented-control">
            <label><input type="radio" name="provider" checked={provider === 'api'} onChange={() => { setProvider('api'); setModelStatus('idle'); setModelError(null); }} /><span>{t.modelProviderApi}</span></label>
            <label><input type="radio" name="provider" checked={provider === 'ollama'} onChange={() => { setProvider('ollama'); setModelStatus('idle'); setModelError(null); }} /><span>{t.modelProviderOllama}</span></label>
          </div></div>
          <div className="setting-field"><label htmlFor="model-url">{t.modelBaseUrl}</label><input key={'url-' + provider} className="text-input model-field-swap localized-placeholder" id="model-url" dir="ltr" value={modelUrl} placeholder={t.modelUrlPlaceholder} required onChange={event => setModelUrl(event.target.value)} /></div>
          <div className="setting-field"><label htmlFor="model-name">{t.modelName}</label><input key={'name-' + provider} className="text-input model-field-swap localized-placeholder" id="model-name" dir="ltr" list="ollama-models" value={modelName} placeholder={t.modelNamePlaceholder} required onChange={event => setModelName(event.target.value)} /><datalist id="ollama-models">{models.map(model => <option value={model.name} key={model.name} />)}</datalist></div>
          {provider === 'api' && <><div className="setting-field"><label htmlFor="api-key">{t.apiKey}</label><p className="credential-state" data-state={keyConfigured ? 'configured' : 'missing'} role="status">{keyConfigured ? <ShieldCheck size={15} /> : <KeyRound size={15} />}<span><strong>{keyConfigured ? t.apiKeyAvailable : t.apiKeyMissing}</strong><small>{keyConfigured ? t.apiKeyAvailableHint : t.apiKeyMissingHint}</small></span></p><input className="text-input localized-placeholder" id="api-key" type="password" dir="ltr" value={apiKey} placeholder={keyConfigured ? '••••••••' : t.apiKeyOptional} onChange={event => setApiKey(event.target.value)} /><small>{t.apiKeyRuntimeOnly}</small></div>
            <label className="api-disclosure"><input type="checkbox" checked={apiDisclosureAccepted} onChange={event => setApiDisclosureAccepted(event.target.checked)} /><span><strong>{t.remoteApiDisclosureTitle}</strong><small>{t.remoteApiDisclosure}</small></span></label></>}
          <div className="model-actions">{provider === 'ollama' && <button type="button" className="button secondary" onClick={() => void loadOllamaModels()} disabled={modelStatus === 'loading'}><RefreshCw size={15} />{t.findOllamaModels}</button>}<button className="button primary model-save" disabled={busy || modelStatus === 'loading' || !modelName.trim()}>{modelStatus === 'loading' ? t.saving : t.saveModel}</button></div>
          {modelStatus === 'saved' && <p className="success-note" role="status"><Check size={14} />{t.modelSaved}</p>}{modelStatus === 'error' && modelError && <p className="inline-error" role="alert">{modelError}</p>}
        </form>
        <form className="setting-field" onSubmit={event => {
          event.preventDefault();
          if (!isLocalEndpoint(endpoint, window.location.origin)) { setInvalid(true); return; }
          onUpdateSettings({ backendUrl: endpoint.trim().replace(/\/+$/, '') }); setInvalid(false); setSaved(true);
        }}>
          <label htmlFor="backend-url">{t.backendUrlLabel}</label>
          <input className="text-input localized-placeholder" id="backend-url" type="text" dir="ltr" placeholder={t.backendUrlPlaceholder} value={endpoint} aria-invalid={invalid} aria-describedby="endpoint-hint" disabled={busy}
            onChange={e => { setEndpoint(e.target.value); setInvalid(false); setSaved(false); }} />
          <small id="endpoint-hint">{t.backendUrlHint}</small>
          {invalid && <p className="inline-error" role="alert">{t.invalidEndpoint}</p>}
          <div className="endpoint-save"><button className="button secondary" disabled={busy}>{t.save}</button>{saved && <span role="status"><Check size={14} />{t.saved}</span>}</div>
        </form>
        <div className="data-setting"><h3>{t.clearAllData}</h3><p>{t.clearAllDesc}</p>
          {!clearConfirm ? <button className="button danger-outline" disabled={busy} onClick={() => setClearConfirm(true)}><Trash2 size={16} />{t.clearAllData}</button>
            : <div className="clear-confirm"><strong>{t.clearAllConfirm}</strong><div className="dialog-actions"><button className="button secondary" disabled={clearStatus === 'loading'} onClick={() => { setClearConfirm(false); setClearStatus('idle'); }}>{t.cancel}</button><button className="button danger" disabled={busy || clearStatus === 'loading'} onClick={() => {
              setClearStatus('loading');
              void onClearAllData().then(onClose).catch(() => setClearStatus('error'));
            }}>{clearStatus === 'loading' ? t.saving : t.clear}</button></div>{clearStatus === 'error' && <p className="inline-error" role="alert">{t.clearAllFailed}</p>}</div>}
        </div>
      </>}
    </div>
  </Dialog>;
}

