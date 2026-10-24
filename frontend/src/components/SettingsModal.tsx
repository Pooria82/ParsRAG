import { useEffect, useMemo, useRef, useState } from 'react';
import { Check, CircleHelp, Database, Download, FileUp, KeyRound, Keyboard, Moon, RefreshCw, ShieldCheck, SlidersHorizontal, Sun, Trash2 } from 'lucide-react';
import type { AppSettings, ModelConfiguration, ModelProvider, OllamaModel, RAGMode, RuntimeSettingGroup, RuntimeSettings, UpdateStatus } from '../types';
import { APP_VERSION } from '../core/appVersion';
import { ServerSettings } from './ServerSettings';
import { GROUP_TEXT, RUNTIME_TEXT } from '../i18n/runtimeSettings';
import { translations } from '../i18n/translations';
import { DEFAULT_SETTINGS, isLocalEndpoint, MODES } from '../core/state';
import { Dialog } from './Dialog';
import { ChoiceMenu } from './ui/ChoiceMenu';
import { ApiError, ParsRagApiClient } from '../services/api';
import { modelSettingsErrorMessage } from '../i18n/errors';
import { isApplePlatform, SHORTCUTS, shortcutLabel } from '../core/shortcuts';

interface SettingsModalProps {
  open?: boolean;
  onClose: () => void; settings: AppSettings;
  onUpdateSettings: (settings: Partial<AppSettings>) => void; onClearAllData: () => Promise<void>; busy: boolean;
  /** Download every conversation as a backup file. */
  onExportBackup?: () => void;
  /** Restore conversations from a backup file; resolves with the counts merged. */
  onImportBackup?: (file: File) => Promise<{ added: number; updated: number }>;
  onModelConfigured?: (configuration: ModelConfiguration) => void;
  /** Server settings changed (upload limits among them). */
  onRuntimeChanged?: () => void;
  /** The running version and the last update check. */
  updateStatus?: UpdateStatus | null;
  /** Ask GitHub again now; resolves with the new status, or null when it failed. */
  onCheckUpdates?: () => Promise<UpdateStatus | null>;
  onOpenUpdate?: () => void;
  onStartGuide: () => void;
  canInstall?: boolean; onInstall?: () => void;
  guided?: boolean;
  guidedTab?: 'general' | 'rag' | 'connection';
  guidedProvider?: ModelProvider;
}

export function SettingsModal({ open = true, onClose, settings, onUpdateSettings, onClearAllData, onExportBackup, onImportBackup, busy, onModelConfigured, onRuntimeChanged, updateStatus, onCheckUpdates, onOpenUpdate, onStartGuide, canInstall, onInstall, guided = false, guidedTab, guidedProvider }: SettingsModalProps) {
  const backupInput = useRef<HTMLInputElement>(null);
  const [backupStatus, setBackupStatus] = useState<{ kind: 'done' | 'error'; text: string } | null>(null);
  const t = translations[settings.language];
  const applePlatform = isApplePlatform(navigator.platform || navigator.userAgent);
  const [tab, setTab] = useState<'general' | 'rag' | 'connection' | 'documents'>('general');
  const activeTab = guidedTab ?? tab;
  const [clearConfirm, setClearConfirm] = useState(false);
  const [clearStatus, setClearStatus] = useState<'idle' | 'loading' | 'error'>('idle');
  const [endpoint, setEndpoint] = useState(settings.backendUrl);
  const [invalid, setInvalid] = useState(false);
  const [saved, setSaved] = useState(false);
  const [provider, setProvider] = useState<ModelProvider>('api');
  const activeProvider = guidedProvider ?? provider;
  const [apiModelName, setApiModelName] = useState(settings.apiModelName);
  const [ollamaModelName, setOllamaModelName] = useState(settings.ollamaModelName);
  const [apiModelUrl, setApiModelUrl] = useState(settings.apiBaseUrl);
  const [ollamaModelUrl, setOllamaModelUrl] = useState(settings.ollamaBaseUrl);
  const [apiKey, setApiKey] = useState('');
  const [apiDisclosureAccepted, setApiDisclosureAccepted] = useState(false);
  const [keyConfigured, setKeyConfigured] = useState(false);
  const [keyHosts, setKeyHosts] = useState<string[] | null>(null);
  const [models, setModels] = useState<OllamaModel[]>([]);
  const [modelStatus, setModelStatus] = useState<'idle' | 'loading' | 'saved' | 'error'>('idle');
  const [modelError, setModelError] = useState<string | null>(null);
  const modelApi = useMemo(() => new ParsRagApiClient(settings.backendUrl), [settings.backendUrl]);
  const [runtime, setRuntime] = useState<RuntimeSettings | null>(null);
  const [runtimeError, setRuntimeError] = useState(false);
  const [updateCheck, setUpdateCheck] = useState<'idle' | 'checking' | 'latest' | 'failed'>('idle');
  const checkUpdates = async () => {
    if (!onCheckUpdates) return;
    setUpdateCheck('checking');
    const status = await onCheckUpdates();
    if (!status) setUpdateCheck('failed');
    else if (status.update_available) { setUpdateCheck('idle'); onOpenUpdate?.(); }
    else setUpdateCheck(status.enabled ? 'latest' : 'idle');
  };
  useEffect(() => {
    if (!open || guided) return;
    const controller = new AbortController(); setRuntimeError(false);
    void modelApi.runtimeSettings(controller.signal).then(setRuntime).catch(error => {
      if (!(error instanceof DOMException && error.name === 'AbortError')) setRuntimeError(true);
    });
    return () => controller.abort();
  }, [open, guided, modelApi]);
  const serverSettings = (groups: RuntimeSettingGroup[]) => runtime
    ? <ServerSettings api={modelApi} language={settings.language} runtime={runtime} groups={groups} onChange={updated => { setRuntime(updated); onRuntimeChanged?.(); }} />
    : runtimeError ? <p className="info-note"><CircleHelp size={18} />{RUNTIME_TEXT[settings.language].loadError}</p> : null;
  const modelName = activeProvider === 'api' ? apiModelName : ollamaModelName;
  const setModelName = (value: string) => provider === 'api' ? setApiModelName(value) : setOllamaModelName(value);
  const modelUrl = activeProvider === 'api' ? apiModelUrl : ollamaModelUrl;
  const setModelUrl = (value: string) => provider === 'api' ? setApiModelUrl(value) : setOllamaModelUrl(value);
  useEffect(() => {
    if (!open || activeTab !== 'connection') return;
    const controller = new AbortController(); setModelStatus('idle'); setModelError(null);
    void modelApi.modelConfiguration(controller.signal).then(config => {
      setProvider(config.provider);
      if (config.provider === 'api') {
        setApiModelName(config.model_name); setApiModelUrl(config.base_url);
        // Offer the server's own Ollama (for example the host's, from Docker) instead of the built-in default.
        if (config.ollama_base_url && settings.ollamaBaseUrl === DEFAULT_SETTINGS.ollamaBaseUrl) setOllamaModelUrl(config.ollama_base_url);
      }
      else { setOllamaModelName(config.model_name); setOllamaModelUrl(config.base_url); }
      setKeyConfigured(config.api_key_configured); setKeyHosts(config.api_key_hosts ?? null);
      setApiDisclosureAccepted(config.disclosure_acknowledged);
      if (!guided) onUpdateSettings({ selectedModel: config.model_name, ...(config.provider === 'api'
        ? { apiModelName: config.model_name, apiBaseUrl: config.base_url }
        : { ollamaModelName: config.model_name, ollamaBaseUrl: config.base_url }) });
    }).catch(() => { /* Keep editable defaults when an older or offline service cannot expose configuration. */ });
    return () => controller.abort();
  }, [open, activeTab, modelApi, guided]);
  // A key is only sent to the host it belongs to: say whether the typed address has one.
  const apiHost = (() => { try { return new URL(apiModelUrl).hostname.toLowerCase(); } catch { return ''; } })();
  const keyAvailable = keyHosts ? keyHosts.includes(apiHost) : keyConfigured;
  const otherKeyHosts = keyHosts && !keyAvailable && keyHosts.length ? keyHosts.join(settings.language === 'fa' ? '، ' : ', ') : '';
  const settingsError = (error: unknown) => modelSettingsErrorMessage(error instanceof ApiError ? error.code : undefined, settings.language);
  const loadOllamaModels = async (quiet = false) => {
    if (!quiet) { setModelStatus('loading'); setModelError(null); }
    try {
      const installed = await modelApi.ollamaModels(ollamaModelUrl);
      setModels(installed); if (installed.length && !installed.some(model => model.name === ollamaModelName)) setOllamaModelName(installed[0].name);
      if (!quiet) setModelStatus('idle');
    } catch (error) {
      setModels([]);
      if (!quiet) { setModelStatus('error'); setModelError(settingsError(error) ?? t.ollamaConnectionError); }
    }
  };
  // Offer the installed models as soon as the Ollama connection is shown.
  useEffect(() => {
    if (!open || guided || activeTab !== 'connection' || activeProvider !== 'ollama' || !ollamaModelUrl.trim()) return;
    void loadOllamaModels(true);
  }, [open, guided, activeTab, activeProvider, ollamaModelUrl]);
  const gigabytes = (bytes: number) => `${(bytes / 1e9).toLocaleString(settings.language, { maximumFractionDigits: 1 })} ${settings.language === 'fa' ? 'گیگابایت' : 'GB'}`;
  const ollamaOptions = [
    ...(models.some(model => model.name === ollamaModelName) || !ollamaModelName ? [] : [{ value: ollamaModelName, label: ollamaModelName, description: t.modelNotInstalled }]),
    ...models.map(model => ({ value: model.name, label: model.name, description: model.size ? gigabytes(model.size) : undefined })),
  ];
  const tabs = [{ id: 'general', label: t.tabGeneral, Icon: Sun }, { id: 'rag', label: t.tabRAG, Icon: SlidersHorizontal }, { id: 'connection', label: t.tabModel, Icon: Database }, { id: 'documents', label: t.tabDocuments, Icon: FileUp }] as const;
  return <Dialog open={open} guided={guided} onClose={onClose} title={t.settingsTitle} subtitle={t.settingsSubtitle} closeLabel={t.close} className="settings-dialog">
    <div className="settings-tabs" data-tour="settings-tabs" role="tablist" aria-label={t.settingsTitle}>
      {tabs.map(({ id, label, Icon }, index) => <button key={id} id={'tab-' + id} role="tab" aria-controls={'panel-' + id}
        aria-selected={activeTab === id} tabIndex={activeTab === id ? 0 : -1} onClick={() => setTab(id)}
        onKeyDown={event => {
          if (!['ArrowRight', 'ArrowLeft', 'Home', 'End'].includes(event.key)) return;
          event.preventDefault();
          const delta = (event.key === 'ArrowRight' ? 1 : -1) * (settings.language === 'fa' ? -1 : 1);
          const next = event.key === 'Home' ? 0 : event.key === 'End' ? tabs.length - 1 : (index + delta + tabs.length) % tabs.length;
          setTab(tabs[next].id); document.getElementById('tab-' + tabs[next].id)?.focus();
        }}><Icon size={16} />{label}</button>)}
    </div>
    <div key={activeTab} className="settings-body" role="tabpanel" id={'panel-' + activeTab} aria-labelledby={'tab-' + activeTab} tabIndex={0}>
      {activeTab === 'general' && <>
        <fieldset className="setting-field" data-tour="settings-theme"><legend>{t.themeLabel}</legend><div className="theme-choices">
          {(['light', 'dark'] as const).map(theme => <label className={'theme-choice preview-' + theme + (settings.theme === theme ? ' is-selected' : '')} key={theme}>
            <input type="radio" name="theme" value={theme} checked={settings.theme === theme} onChange={() => onUpdateSettings({ theme })} />
            <span className="theme-preview" aria-hidden="true"><i /><span><b /><b /><em /></span></span>
            <span className="theme-choice-label">{theme === 'light' ? <Sun size={16} /> : <Moon size={16} />}{theme === 'light' ? t.themeLight : t.themeDark}{settings.theme === theme && <Check size={15} />}</span>
          </label>)}
        </div></fieldset>
        <fieldset className="setting-field" data-tour="settings-palette"><legend>{t.paletteLabel}</legend><div className="palette-choices">
          {(['evergreen', 'ocean', 'indigo', 'sienna'] as const).map(palette => <label className={'palette-choice palette-' + palette} key={palette}>
            <input type="radio" name="palette" checked={settings.palette === palette} onChange={() => onUpdateSettings({ palette })} />
            <span className="palette-swatch" aria-hidden="true" /><span>{t.palettes[palette]}</span>{settings.palette === palette && <Check size={14} />}
          </label>)}
        </div></fieldset>
        <fieldset className="setting-field" data-tour="settings-language"><legend>{t.languageLabel}</legend><div className="segmented-control">
          <label><input type="radio" name="language" checked={settings.language === 'fa'} onChange={() => onUpdateSettings({ language: 'fa' })} /><span lang="fa">فارسی</span></label>
          <label><input type="radio" name="language" checked={settings.language === 'en'} onChange={() => onUpdateSettings({ language: 'en' })} /><span lang="en">English</span></label>
        </div></fieldset>
        <div className="setting-field guide-setting" data-tour="settings-guide"><span><strong>{t.guideReplay}</strong><small>{t.guideReplayHint}</small></span>
          <button className="button secondary" onClick={() => { onClose(); onStartGuide(); }}><CircleHelp size={16} />{t.guideStart}</button>
        </div>
        <section className="update-setting" aria-label={t.aboutTitle}>
          <h3>{t.aboutTitle}</h3>
          <p dir="auto">{t.versionLabel.replace('{version}', updateStatus?.current_version ?? APP_VERSION)}</p>
          {serverSettings(['updates'])}
          {onCheckUpdates && <div className="update-check">
            <button type="button" className="button secondary" disabled={updateCheck === 'checking' || updateStatus?.enabled === false} onClick={() => void checkUpdates()}>
              <RefreshCw size={15} className={updateCheck === 'checking' ? 'spin' : undefined} />{t.checkUpdates}</button>
            {updateStatus?.enabled === false ? <small>{t.updatesOff}</small>
              : updateCheck === 'latest' ? <small role="status"><Check size={13} />{t.upToDate}</small>
                : updateCheck === 'failed' ? <small className="inline-error" role="alert">{t.updateCheckFailed}</small> : null}
          </div>}
        </section>
        <section className="shortcut-guide" data-tour="settings-shortcuts" aria-label={t.shortcutTitle}>
          <h3><Keyboard size={17} />{t.shortcutTitle}</h3><p>{t.shortcutHint}</p>
          <dl>{SHORTCUTS.map(shortcut => <div key={shortcut.action}><dt>{t.shortcutActions[shortcut.action]}</dt><dd><kbd dir="ltr">{shortcutLabel(shortcut.action, applePlatform)}</kbd></dd></div>)}</dl>
        </section>
        {(canInstall || guided) && <div className="setting-field guide-setting" data-tour="settings-pwa"><span><strong>{t.pwaInstallTitle}</strong><small>{t.pwaInstallHint}</small></span>
          {canInstall ? <button className="button secondary" onClick={onInstall}><Download size={16} />{t.pwaInstall}</button>
            : <small>{settings.language === 'fa' ? 'نصب در مرورگر و سیستم‌عامل پشتیبانی‌شده نمایش داده می‌شود.' : 'Install appears when your browser and operating system support it.'}</small>}
        </div>}
      </>}
      {activeTab === 'rag' && <>
        <div className="setting-field" data-tour="settings-default-mode"><label>{t.defaultModeLabel}</label>
          <ChoiceMenu<RAGMode> label={t.defaultModeLabel} value={settings.defaultMode}
            options={MODES.map(mode => ({ value: mode, label: t.ragModes[mode].label, description: t.ragModes[mode].desc }))}
            onChange={defaultMode => onUpdateSettings({ defaultMode })} disabled={busy} />
        </div>
        <label className="switch-setting" data-tour="settings-depth"><span><strong>{t.dynamicDepthLabel}</strong><small>{t.dynamicDepthDesc}</small></span>
          <input type="checkbox" role="switch" checked={settings.dynamicDepth} onChange={e => onUpdateSettings({ dynamicDepth: e.target.checked })} />
        </label>
        {!settings.dynamicDepth && <div className="setting-field"><label htmlFor="top-k">{t.manualTopKLabel}<output>{settings.topK.toLocaleString(settings.language)}</output></label>
          <input type="range" id="top-k" min="1" max="50" value={settings.topK} onChange={e => onUpdateSettings({ topK: Number(e.target.value) })} />
        </div>}
        {serverSettings(['retrieval'])}
      </>}
      {activeTab === 'documents' && <>
        {serverSettings(['documents', 'performance'])}
        <p className="info-note"><CircleHelp size={18} />{RUNTIME_TEXT[settings.language].envOnly}</p>
      </>}
      {activeTab === 'connection' && <>
        <form className="model-settings" onSubmit={event => {
          event.preventDefault();
          if (activeProvider === 'api' && !apiDisclosureAccepted) { setModelStatus('error'); setModelError(t.apiConsentRequired); return; }
          setModelStatus('loading'); setModelError(null);
          void modelApi.configureModel({ provider: activeProvider, model_name: modelName.trim(), base_url: modelUrl.trim(), disclosure_acknowledged: activeProvider === 'api' && apiDisclosureAccepted, ...(apiKey ? { api_key: apiKey } : {}) }).then(config => {
            setKeyConfigured(config.api_key_configured); setKeyHosts(config.api_key_hosts ?? null); setApiKey(''); setModelStatus('saved');
            onModelConfigured?.(config);
            onUpdateSettings({ selectedModel: config.model_name, ...(config.provider === 'api'
              ? { apiModelName: config.model_name, apiBaseUrl: config.base_url }
              : { ollamaModelName: config.model_name, ollamaBaseUrl: config.base_url }) });
          }).catch((error: unknown) => { setModelStatus('error'); setModelError(settingsError(error) ?? t.modelSaveError); });
        }}>
          <div className="setting-field" data-tour="settings-provider"><label>{t.modelProviderLabel}</label><div className="segmented-control">
            <label><input type="radio" name="provider" checked={activeProvider === 'api'} onChange={() => { setProvider('api'); setModelStatus('idle'); setModelError(null); }} /><span>{t.modelProviderApi}</span></label>
            <label><input type="radio" name="provider" checked={activeProvider === 'ollama'} onChange={() => { setProvider('ollama'); setModelStatus('idle'); setModelError(null); }} /><span>{t.modelProviderOllama}</span></label>
          </div></div>
          <div className="setting-field" data-tour="settings-model-url"><label htmlFor="model-url">{t.modelBaseUrl}</label><input key={'url-' + activeProvider} className="text-input model-field-swap localized-placeholder" id="model-url" dir="ltr" value={modelUrl} placeholder={t.modelUrlPlaceholder} required onChange={event => setModelUrl(event.target.value)} /></div>
          <div className="setting-field" data-tour="settings-model-name"><label htmlFor="model-name">{t.modelName}</label>{activeProvider === 'ollama' && models.length > 0
            ? <ChoiceMenu<string> label={t.modelName} value={ollamaModelName} options={ollamaOptions} onChange={setOllamaModelName} disabled={modelStatus === 'loading'} />
            : <input key={'name-' + activeProvider} className="text-input model-field-swap localized-placeholder" id="model-name" dir="ltr" value={modelName} placeholder={t.modelNamePlaceholder} required onChange={event => setModelName(event.target.value)} />}</div>
          {activeProvider === 'api' && <><div className="setting-field" data-tour="settings-api-key"><label htmlFor="api-key">{t.apiKey}</label><p className="credential-state" data-state={keyAvailable ? 'configured' : 'missing'} role="status">{keyAvailable ? <ShieldCheck size={15} /> : <KeyRound size={15} />}<span><strong>{keyAvailable ? t.apiKeyAvailable : t.apiKeyMissing}</strong><small>{keyAvailable ? t.apiKeyAvailableHint : t.apiKeyMissingHint}{otherKeyHosts && <> {t.apiKeyOtherHost.replace('{hosts}', otherKeyHosts)}</>}</small></span></p><input className="text-input localized-placeholder" id="api-key" type="password" dir="ltr" value={apiKey} placeholder={keyAvailable ? '••••••••' : t.apiKeyOptional} onChange={event => setApiKey(event.target.value)} /><small>{t.apiKeyRuntimeOnly}</small></div>
            <label className="api-disclosure" data-tour="settings-api-disclosure"><input type="checkbox" checked={apiDisclosureAccepted} onChange={event => setApiDisclosureAccepted(event.target.checked)} /><span><strong>{t.remoteApiDisclosureTitle}</strong><small>{t.remoteApiDisclosure}</small></span></label></>}
          <div className="model-actions" data-tour="settings-model-actions">{activeProvider === 'ollama' && <button type="button" className="button secondary" onClick={() => void loadOllamaModels()} disabled={modelStatus === 'loading'}><RefreshCw size={15} />{t.findOllamaModels}</button>}<button className="button primary model-save" disabled={busy || modelStatus === 'loading' || !modelName.trim()}>{modelStatus === 'loading' ? t.saving : t.saveModel}</button></div>
          {modelStatus === 'saved' && <p className="success-note" role="status"><Check size={14} />{t.modelSaved}</p>}{modelStatus === 'error' && modelError && <p className="inline-error" role="alert">{modelError}</p>}
        </form>
        {(runtime || runtimeError) && <details className="advanced-settings"><summary>{GROUP_TEXT.model[settings.language]}</summary>{serverSettings(['model'])}</details>}
        <form className="setting-field" data-tour="settings-backend" onSubmit={event => {
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
        {(onExportBackup || onImportBackup) && <div className="data-setting backup-setting"><h3>{t.backupTitle}</h3><p>{t.backupDesc}</p>
          <input ref={backupInput} type="file" accept="application/json,.json" className="visually-hidden" tabIndex={-1} aria-label={t.importBackup} onChange={event => {
            const file = event.target.files?.[0]; event.target.value = '';
            if (!file || !onImportBackup) return;
            void onImportBackup(file).then(({ added, updated }) => setBackupStatus({ kind: 'done', text: t.importDone.replace('{added}', added.toLocaleString(settings.language)).replace('{updated}', updated.toLocaleString(settings.language)) }))
              .catch((error: unknown) => setBackupStatus({ kind: 'error', text: error instanceof Error && error.message === 'unsupported_version' ? t.importNewerVersion : t.importInvalid }));
          }} />
          <div className="model-actions">
            {onExportBackup && <button type="button" className="button secondary" onClick={() => { onExportBackup(); setBackupStatus(null); }}><Download size={16} />{t.exportBackup}</button>}
            {onImportBackup && <button type="button" className="button secondary" disabled={busy} onClick={() => backupInput.current?.click()}><FileUp size={16} />{t.importBackup}</button>}
          </div>
          {backupStatus && <p className={backupStatus.kind === 'done' ? 'success-note' : 'inline-error'} role="status">{backupStatus.kind === 'done' && <Check size={14} />}{backupStatus.text}</p>}
        </div>}
        <div className="data-setting" data-tour="settings-data"><h3>{t.clearAllData}</h3><p>{t.clearAllDesc}</p>
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

