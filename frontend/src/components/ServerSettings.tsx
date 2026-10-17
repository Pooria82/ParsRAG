import { useEffect, useMemo, useState } from 'react';
import { Check, RotateCcw } from 'lucide-react';
import type { Language, RuntimeSetting, RuntimeSettingGroup, RuntimeSettings } from '../types';
import { ApiError, type ParsRagApiClient } from '../services/api';
import { GROUP_TEXT, RUNTIME_TEXT, SETTING_TEXT } from '../i18n/runtimeSettings';

const MEBIBYTE = 1024 * 1024;
// Where a number starts when "Automatic" is switched off.
const MANUAL_START: Record<string, string> = { STRICT_RAG_TOP_K: '15', HYBRID_RERANK_TOP_K: '15', OCR_WORKERS: '4', EMBED_BATCH_SIZE: '16', PARSRAG_CPU_THREADS: '4' };

/** A setting's value as shown in a field (sizes in MB). */
export function displayValue(setting: Pick<RuntimeSetting, 'kind'>, value: string): string {
  if (setting.kind === 'bytes' && value) return String(Math.round(Number(value) / MEBIBYTE));
  return value;
}

/** The automatic value as shown in its disabled field. */
export function automaticText(setting: Pick<RuntimeSetting, 'automatic_value'>, language: Language): string {
  const t = RUNTIME_TEXT[language];
  const value = setting.automatic_value ?? '';
  const range = /^(\d+)-(\d+)$/.exec(value);
  if (range) return `${range[1]}–${range[2]} (${t.perQuestion})`;
  return value || t.automatic;
}

/** Where a number starts when "Automatic" is switched off: the value it had. */
export function manualStart(setting: Pick<RuntimeSetting, 'key' | 'automatic_value' | 'env_value' | 'minimum'>): string {
  if (setting.automatic_value && /^\d+$/.test(setting.automatic_value)) return setting.automatic_value;
  return setting.env_value || MANUAL_START[setting.key] || String(setting.minimum ?? 1);
}

/** A field's text as the environment string the server expects. */
export function storedValue(setting: Pick<RuntimeSetting, 'kind'>, shown: string): string {
  if (setting.kind === 'bytes' && shown.trim()) return String(Math.round(Number(shown) * MEBIBYTE));
  return shown.trim();
}

/** Settings whose field differs from the value in effect. */
export function changedValues(settings: RuntimeSetting[], draft: Record<string, string>): Record<string, string> {
  const changes: Record<string, string> = {};
  for (const setting of settings) {
    const next = draft[setting.key];
    if (next !== undefined && next !== setting.value) changes[setting.key] = next;
  }
  return changes;
}

interface ServerSettingsProps {
  api: ParsRagApiClient;
  language: Language;
  runtime: RuntimeSettings;
  groups: RuntimeSettingGroup[];
  onChange: (runtime: RuntimeSettings) => void;
}

/** Server settings that apply without a restart, grouped like `.env.example`. */
export function ServerSettings({ api, language, runtime, groups, onChange }: ServerSettingsProps) {
  const t = RUNTIME_TEXT[language];
  const shown = useMemo(() => runtime.settings.filter(setting => groups.includes(setting.group)), [runtime, groups]);
  const [draft, setDraft] = useState<Record<string, string>>({});
  const [status, setStatus] = useState<'idle' | 'saving' | 'saved' | 'error'>('idle');
  const [error, setError] = useState<string | null>(null);
  useEffect(() => { setDraft(Object.fromEntries(shown.map(setting => [setting.key, setting.value]))); }, [shown]);
  const changes = changedValues(shown, draft);
  const overridden = shown.filter(setting => setting.overridden);

  const send = async (values: Record<string, string | null>) => {
    setStatus('saving'); setError(null);
    try {
      onChange(await api.updateRuntimeSettings(values));
      setStatus('saved');
    } catch (failure) {
      const code = failure instanceof ApiError ? failure.code : '';
      setStatus('error');
      setError(code === 'upload_ceiling' ? t.ceiling : code === 'invalid_setting' ? t.invalid : t.saveError);
    }
  };

  return <div className="server-settings">
    {groups.map(group => {
      const items = shown.filter(setting => setting.group === group);
      if (!items.length) return null;
      return <section key={group} className="server-settings-group" aria-label={GROUP_TEXT[group][language]}>
        <h3>{GROUP_TEXT[group][language]}</h3>
        {items.map(setting => <SettingField key={setting.key} setting={setting} language={language}
          value={draft[setting.key] ?? setting.value} disabled={status === 'saving'}
          onChange={value => { setDraft(current => ({ ...current, [setting.key]: value })); setStatus('idle'); }}
          onReset={() => void send({ [setting.key]: null })} />)}
      </section>;
    })}
    <div className="model-actions">
      {overridden.length > 0 && <button type="button" className="button secondary" disabled={status === 'saving'}
        onClick={() => void send(Object.fromEntries(overridden.map(setting => [setting.key, null])))}><RotateCcw size={15} />{t.resetAll}</button>}
      <button type="button" className="button primary" disabled={status === 'saving' || !Object.keys(changes).length}
        onClick={() => void send(changes)}>{status === 'saving' ? t.saving : t.save}</button>
    </div>
    {status === 'saved' && <p className="success-note" role="status"><Check size={14} />{t.saved}</p>}
    {status === 'error' && error && <p className="inline-error" role="alert">{error}</p>}
  </div>;
}

function SettingField({ setting, language, value, disabled, onChange, onReset }: {
  setting: RuntimeSetting; language: Language; value: string; disabled: boolean;
  onChange: (value: string) => void; onReset: () => void;
}) {
  const t = RUNTIME_TEXT[language];
  const text = SETTING_TEXT[setting.key];
  const label = text?.label[language] ?? setting.key;
  const id = `runtime-${setting.key}`;
  const envShown = setting.kind === 'bool' ? (setting.env_value === '1' ? t.on : t.off)
    : setting.env_value === '' ? t.automatic : displayValue(setting, setting.env_value);
  const footer = <small>
    {text?.hint[language]}
    {setting.overridden && <span className="setting-origin"> {t.fromEnv} <bdi dir="ltr">{envShown}</bdi>
      <button type="button" className="setting-reset" onClick={onReset} disabled={disabled} aria-label={`${t.resetOne}: ${label}`} title={t.resetOne}><RotateCcw size={12} /></button></span>}
  </small>;

  if (setting.kind === 'bool') {
    return <div className="server-setting">
      <label className="switch-setting" htmlFor={id}><span><strong>{label}</strong>{footer}</span>
        <input id={id} type="checkbox" role="switch" checked={value === '1'} disabled={disabled} onChange={event => onChange(event.target.checked ? '1' : '0')} />
      </label>
    </div>;
  }
  const automatic = setting.automatic && value === '';
  const numeric = setting.kind !== 'text';
  const minimum = setting.minimum ?? undefined;
  const maximum = setting.maximum ?? undefined;
  const scale = setting.kind === 'bytes' ? MEBIBYTE : 1;
  return <div className="setting-field server-setting">
    <label htmlFor={id}>{label}{setting.overridden && <span className="setting-badge">{t.overridden}</span>}</label>
    <div className="server-setting-input">
      <input id={id} className="text-input" dir="ltr" disabled={disabled || automatic}
        type={numeric && !automatic ? 'number' : 'text'} inputMode={numeric ? (setting.kind === 'float' ? 'decimal' : 'numeric') : undefined}
        min={minimum !== undefined ? minimum / scale : undefined} max={maximum !== undefined ? maximum / scale : undefined}
        step={setting.kind === 'float' ? 0.05 : 1}
        value={automatic ? automaticText(setting, language) : displayValue(setting, value)} readOnly={automatic}
        onChange={event => onChange(storedValue(setting, event.target.value))} />
      {setting.automatic && <label className="automatic-choice"><input type="checkbox" checked={automatic} disabled={disabled}
        onChange={event => onChange(event.target.checked ? '' : manualStart(setting))} />{t.automatic}</label>}
    </div>
    {footer}
  </div>;
}
