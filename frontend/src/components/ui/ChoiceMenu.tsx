import { Check, ChevronDown } from 'lucide-react';
import { useEffect, useId, useRef, useState, type KeyboardEvent } from 'react';

export interface ChoiceOption<T extends string> {
  value: T;
  label: string;
  description?: string;
}

interface ChoiceMenuProps<T extends string> {
  label: string;
  value: T;
  options: readonly ChoiceOption<T>[];
  onChange: (value: T) => void;
  disabled?: boolean;
}

export function ChoiceMenu<T extends string>({ label, value, options, onChange, disabled = false }: ChoiceMenuProps<T>) {
  const [open, setOpen] = useState(false);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const menuRef = useRef<HTMLDivElement>(null);
  const menuId = useId();
  const selected = options.find(option => option.value === value) ?? options[0];

  useEffect(() => {
    if (!open) return;
    menuRef.current?.querySelector<HTMLButtonElement>('[aria-checked="true"]')?.focus();
    const dismiss = (event: PointerEvent) => {
      if (!menuRef.current?.contains(event.target as Node) && !triggerRef.current?.contains(event.target as Node)) setOpen(false);
    };
    document.addEventListener('pointerdown', dismiss);
    return () => document.removeEventListener('pointerdown', dismiss);
  }, [open]);

  const handleKeyboard = (event: KeyboardEvent<HTMLDivElement>) => {
    const items = [...(menuRef.current?.querySelectorAll<HTMLButtonElement>('[role="menuitemradio"]') ?? [])];
    const current = items.indexOf(document.activeElement as HTMLButtonElement);
    if (event.key === 'Escape') {
      event.preventDefault();
      setOpen(false);
      triggerRef.current?.focus();
    } else if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
      event.preventDefault();
      items[(current + (event.key === 'ArrowDown' ? 1 : -1) + items.length) % items.length]?.focus();
    } else if (event.key === 'Home' || event.key === 'End') {
      event.preventDefault();
      items[event.key === 'Home' ? 0 : items.length - 1]?.focus();
    } else if (event.key === 'Tab') {
      setOpen(false);
    }
  };

  return <div className="choice-menu">
    <button ref={triggerRef} type="button" className="choice-menu-trigger" aria-label={label} aria-haspopup="menu"
      aria-controls={menuId} aria-expanded={open} disabled={disabled} onClick={() => setOpen(current => !current)}>
      <span><strong>{selected?.label}</strong>{selected?.description && <small>{selected.description}</small>}</span>
      <ChevronDown size={16} className={open ? 'rotate' : ''} />
    </button>
    {open && <div ref={menuRef} id={menuId} className="choice-menu-popover" role="menu" aria-label={label} onKeyDown={handleKeyboard}>
      {options.map(option => <button type="button" key={option.value} role="menuitemradio" aria-checked={option.value === value}
        onClick={() => { onChange(option.value); setOpen(false); triggerRef.current?.focus(); }}>
        <span><strong>{option.label}</strong>{option.description && <small>{option.description}</small>}</span>
        {option.value === value && <Check size={16} />}
      </button>)}
    </div>}
  </div>;
}
