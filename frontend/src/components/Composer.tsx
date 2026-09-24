import { useEffect, useRef, useState, type KeyboardEvent } from 'react';
import { ArrowUp, BookOpen, Check, ChevronDown, Layers2, MessageCircle, Paperclip, Square } from 'lucide-react';
import type { RAGMode, Language } from '../types';
import { translations } from '../i18n/translations';
import { MODES } from '../core/state';
import { activeComposerTrigger, applyComposerCommand, COMMANDS, insertDocumentMention } from '../core/composerActions';

interface ComposerProps {
  value: string; onChange: (value: string) => void; onSendMessage: () => void;
  onStopGenerating: () => void; isGenerating: boolean; isBusy: boolean;
  activeMode: RAGMode; onChangeMode: (mode: RAGMode) => void;
  language: Language; onOpenDocuments: () => void; documentCount: number; focusToken: number;
  documentNames: string[]; onSelectMention: (name: string) => void; onOpenGuide: () => void;
  guidedMenu?: 'mode' | 'document' | 'command' | null;
}

const modeIcons = { hybrid: Layers2, strict: BookOpen, 'llm-only': MessageCircle };

export function Composer(props: ComposerProps) {
  const { value, onChange, isGenerating, activeMode, language } = props;
  const t = translations[language];
  const [modeOpen, setModeOpen] = useState(false);
  const [cursor, setCursor] = useState(0);
  const [menuIndex, setMenuIndex] = useState(0);
  const [menuDismissed, setMenuDismissed] = useState(false);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const suggestionsRef = useRef<HTMLDivElement>(null);
  const menuRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const ModeIcon = modeIcons[activeMode];
  const trigger = props.guidedMenu === 'document' || props.guidedMenu === 'command'
    ? { kind: props.guidedMenu, query: '', start: 0, end: 0 }
    : menuDismissed ? null : activeComposerTrigger(value, cursor);
  const showModeMenu = modeOpen || props.guidedMenu === 'mode';
  const suggestions = trigger?.kind === 'document'
    ? props.documentNames.filter(name => name.toLocaleLowerCase().includes(trigger.query.trim().toLocaleLowerCase())).slice(0, 8)
    : trigger?.kind === 'command' ? COMMANDS.filter(command => command.id.startsWith(trigger.query.toLowerCase())).slice(0, 9) : [];

  const chooseSuggestion = (index: number) => {
    if (!trigger || index < 0 || index >= suggestions.length) return;
    if (trigger.kind === 'document') {
      const name = suggestions[index] as string;
      const inserted = insertDocumentMention(value, trigger, name);
      onChange(inserted.text); props.onSelectMention(name);
      requestAnimationFrame(() => { inputRef.current?.focus(); inputRef.current?.setSelectionRange(inserted.cursor, inserted.cursor); });
    } else {
      const command = suggestions[index] as typeof COMMANDS[number];
      const applied = applyComposerCommand(command.id, language, value, trigger);
      onChange(applied.text);
      if (applied.mode) props.onChangeMode(applied.mode);
      if (applied.action === 'documents') props.onOpenDocuments();
      if (applied.action === 'help') props.onOpenGuide();
      requestAnimationFrame(() => inputRef.current?.focus());
    }
    setMenuDismissed(true);
  };

  useEffect(() => {
    if (!inputRef.current) return;
    inputRef.current.style.height = '0px';
    inputRef.current.style.height = Math.min(Math.max(inputRef.current.scrollHeight, 58), 180) + 'px';
  }, [value]);
  useEffect(() => { if (props.focusToken) inputRef.current?.focus(); }, [props.focusToken]);
  useEffect(() => { if (props.guidedMenu) setModeOpen(false); }, [props.guidedMenu]);
  useEffect(() => {
    const list = suggestionsRef.current;
    const selected = list?.querySelector<HTMLElement>('[aria-selected="true"]');
    if (!list || !selected) return;
    const listBounds = list.getBoundingClientRect();
    const optionBounds = selected.getBoundingClientRect();
    if (optionBounds.top < listBounds.top + 6) list.scrollTop += optionBounds.top - listBounds.top - 6;
    else if (optionBounds.bottom > listBounds.bottom - 6) list.scrollTop += optionBounds.bottom - listBounds.bottom + 6;
  }, [menuIndex, trigger?.kind, trigger?.query, suggestions.length]);
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
    if (trigger && suggestions.length && !event.nativeEvent.isComposing) {
      if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
        event.preventDefault(); setMenuIndex(current => (current + (event.key === 'ArrowDown' ? 1 : -1) + suggestions.length) % suggestions.length); return;
      }
      if (event.key === 'Enter') { event.preventDefault(); chooseSuggestion(menuIndex % suggestions.length); return; }
      if (event.key === 'Escape') { event.preventDefault(); setMenuDismissed(true); return; }
    }
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

  return <div className="composer-wrap" data-tour="composer">
    <div className="composer">
      <textarea id="message-input" ref={inputRef} value={value} onChange={e => { onChange(e.target.value); setCursor(e.target.selectionStart); setMenuIndex(0); setMenuDismissed(false); }}
        onClick={e => setCursor(e.currentTarget.selectionStart)} onKeyUp={e => setCursor(e.currentTarget.selectionStart)}
        onKeyDown={onKeyDown} placeholder={t.composerPlaceholder} aria-label={t.messageLabel}
        aria-controls={trigger && (suggestions.length || props.guidedMenu === 'document') ? 'composer-suggestions' : undefined} aria-expanded={Boolean(trigger && (suggestions.length || props.guidedMenu === 'document'))}
        aria-activedescendant={trigger && suggestions.length ? `composer-option-${menuIndex % suggestions.length}` : undefined}
        aria-autocomplete="list"
        rows={2} dir={value ? 'auto' : language === 'fa' ? 'rtl' : 'ltr'} maxLength={30000} />
      {trigger && (suggestions.length > 0 || props.guidedMenu === 'document') && <div ref={suggestionsRef} data-tour={trigger.kind === 'document' ? 'mention-menu' : 'command-menu'} className="composer-suggestions" id="composer-suggestions" role="listbox" aria-label={trigger.kind === 'document' ? t.mentionDocuments : t.slashCommands}>
        <p>{trigger.kind === 'document' ? t.mentionDocuments : t.slashCommands}</p>
        {suggestions.length === 0 && <p className="tour-empty-hint">{language === 'fa' ? 'پس از بارگذاری سند، نام فایل‌ها اینجا پیشنهاد می‌شود.' : 'After uploading documents, their filenames are suggested here.'}</p>}
        {suggestions.map((option, index) => <button type="button" role="option" id={`composer-option-${index}`} aria-selected={index === menuIndex} key={typeof option === 'string' ? option : option.id}
          className={index === menuIndex ? 'is-active' : ''} onMouseDown={event => event.preventDefault()} onClick={() => chooseSuggestion(index)}>
          {typeof option === 'string' ? <><Paperclip size={15} /><bdi>{option}</bdi></>
            : <><span dir="ltr">{option.label}</span><small>{language === 'fa' ? option.fa : option.en}</small></>}
        </button>)}
      </div>}
      <div className="composer-toolbar">
        <div className="composer-tools">
          <button className="icon-button attach-button" data-tour="attach" onClick={props.onOpenDocuments} aria-label={t.attach} title={t.attach}><Paperclip size={20} />
            {props.documentCount > 0 && <span className="attachment-dot" />}
          </button>
          <span className="toolbar-divider" />
          <div className="mode-control">
            <button ref={triggerRef} className="mode-trigger" data-tour="mode" aria-haspopup="menu" aria-expanded={showModeMenu} aria-controls="answer-mode-menu"
              onClick={() => setModeOpen(!modeOpen)} title={t.modeLabel}>
              <ModeIcon size={16} /><span>{t.ragModes[activeMode].short}</span><ChevronDown size={14} className={showModeMenu ? 'rotate' : ''} />
            </button>
            {showModeMenu && <div ref={menuRef} data-tour="mode-menu" id="answer-mode-menu" className="mode-menu" role="menu" aria-label={t.modeLabel} onKeyDown={menuKeyboard}>
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
          {isGenerating ? <button className="send-button stop-button" data-tour="send" onClick={props.onStopGenerating} aria-label={t.stop} title={t.stop}><Square size={16} fill="currentColor" /></button>
            : <button className="send-button" data-tour="send" disabled={!value.trim() || props.isBusy} onClick={send} aria-label={t.send} title={t.send}><ArrowUp size={20} /></button>}
        </div>
      </div>
    </div>
    <p className="composer-disclaimer">{props.isBusy && !isGenerating ? t.otherGenerating : t.disclaimer}</p>
  </div>;
}

