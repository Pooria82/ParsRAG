import { useEffect, useRef, useState, type KeyboardEvent } from 'react';
import { ArrowUp, BookOpen, Check, ChevronDown, Layers2, MessageCircle, Paperclip, Square } from 'lucide-react';
import type { RAGMode, Language } from '../types';
import { translations } from '../i18n/translations';
import { MODES } from '../core/state';

interface ComposerProps {
  value: string; onChange: (value: string) => void; onSendMessage: () => void;
  onStopGenerating: () => void; isGenerating: boolean; isBusy: boolean;
  activeMode: RAGMode; onChangeMode: (mode: RAGMode) => void;
  language: Language; onOpenDocuments: () => void; documentCount: number; focusToken: number;
}

const modeIcons = { hybrid: Layers2, strict: BookOpen, 'llm-only': MessageCircle };

export function Composer(props: ComposerProps) {
  const { value, onChange, isGenerating, activeMode, language } = props;
  const t = translations[language];
  const [modeOpen, setModeOpen] = useState(false);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const menuRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const ModeIcon = modeIcons[activeMode];

  useEffect(() => {
    if (!inputRef.current) return;
    inputRef.current.style.height = '0px';
    inputRef.current.style.height = Math.min(Math.max(inputRef.current.scrollHeight, 58), 180) + 'px';
  }, [value]);
  useEffect(() => { if (props.focusToken) inputRef.current?.focus(); }, [props.focusToken]);
  useEffect(() => {
    if (!modeOpen) return;
    menuRef.current?.querySelector<HTMLButtonElement>('[aria-checked="true"]')?.focus();
    const closeOutside = (event: PointerEvent) => {
      if (!menuRef.current?.contains(event.target as Node) && !triggerRef.current?.contains(event.target as Node)) setModeOpen(false);
    };
    document.addEventListener('pointerdown', closeOutside);
    return () => document.removeEventListener('pointerdown', closeOutside);
  }, [modeOpen]);
  const send = () => { if (value.trim() && !props.isBusy) props.onSendMessage(); };
  const onKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing && event.keyCode !== 229) {
      event.preventDefault(); send();
    }
  };
  const menuKeyboard = (event: KeyboardEvent<HTMLDivElement>) => {
    const buttons = [...(menuRef.current?.querySelectorAll<HTMLButtonElement>('[role="menuitemradio"]') ?? [])];
    const index = buttons.indexOf(document.activeElement as HTMLButtonElement);
    if (event.key === 'Escape') { event.preventDefault(); setModeOpen(false); triggerRef.current?.focus(); }
    else if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
      event.preventDefault(); buttons[(index + (event.key === 'ArrowDown' ? 1 : -1) + buttons.length) % buttons.length]?.focus();
    } else if (event.key === 'Home' || event.key === 'End') {
      event.preventDefault(); buttons[event.key === 'Home' ? 0 : buttons.length - 1]?.focus();
    } else if (event.key === 'Tab') setModeOpen(false);
  };

  return <div className="composer-wrap">
    <div className="composer">
      <textarea id="message-input" ref={inputRef} value={value} onChange={e => onChange(e.target.value)}
        onKeyDown={onKeyDown} placeholder={t.composerPlaceholder} aria-label={t.messageLabel}
        rows={2} dir={value ? 'auto' : language === 'fa' ? 'rtl' : 'ltr'} maxLength={30000} />
      <div className="composer-toolbar">
        <div className="composer-tools">
          <button className="icon-button attach-button" onClick={props.onOpenDocuments} aria-label={t.attach} title={t.attach}><Paperclip size={20} />
            {props.documentCount > 0 && <span className="attachment-dot" />}
          </button>
          <span className="toolbar-divider" />
          <div className="mode-control">
            <button ref={triggerRef} className="mode-trigger" aria-haspopup="menu" aria-expanded={modeOpen} aria-controls="answer-mode-menu"
              onClick={() => setModeOpen(!modeOpen)} title={t.modeLabel}>
              <ModeIcon size={16} /><span>{t.ragModes[activeMode].short}</span><ChevronDown size={14} className={modeOpen ? 'rotate' : ''} />
            </button>
            {modeOpen && <div ref={menuRef} id="answer-mode-menu" className="mode-menu" role="menu" aria-label={t.modeLabel} onKeyDown={menuKeyboard}>
              <p className="menu-caption">{t.modeLabel}</p>
              {MODES.map(mode => {
                const Icon = modeIcons[mode];
                return <button key={mode} role="menuitemradio" aria-checked={mode === activeMode} className="mode-option"
                  onClick={() => { props.onChangeMode(mode); setModeOpen(false); triggerRef.current?.focus(); }}>
                  <span className="mode-icon"><Icon size={18} /></span>
                  <span><strong>{t.ragModes[mode].label}</strong><small>{t.ragModes[mode].desc}</small></span>
                  {mode === activeMode && <Check size={16} className="mode-check" />}
                </button>;
              })}
            </div>}
          </div>
        </div>
        <div className="composer-send"><span className="input-hint">{t.inputHint}</span>
          {isGenerating ? <button className="send-button stop-button" onClick={props.onStopGenerating} aria-label={t.stop} title={t.stop}><Square size={16} fill="currentColor" /></button>
            : <button className="send-button" disabled={!value.trim() || props.isBusy} onClick={send} aria-label={t.send} title={t.send}><ArrowUp size={20} /></button>}
        </div>
      </div>
    </div>
    <p className="composer-disclaimer">{props.isBusy && !isGenerating ? t.otherGenerating : t.disclaimer}</p>
  </div>;
}

