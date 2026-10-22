import { useEffect, useId, useRef, useState, type ReactNode } from 'react';
import { X } from 'lucide-react';

interface DialogProps {
  open: boolean;
  onClose: () => void;
  title: string;
  closeLabel: string;
  subtitle?: string;
  className?: string;
  guided?: boolean;
  children: ReactNode;
}

/** Native modal semantics keep keyboard focus and background interaction scoped. */
export function Dialog({ open, onClose, title, closeLabel, subtitle, className = '', guided = false, children }: DialogProps) {
  const ref = useRef<HTMLDialogElement>(null);
  const closeTimer = useRef<number | undefined>(undefined);
  /** Whether the press began on the backdrop: a drag out of the dialog is not a click outside it. */
  const pressedBackdrop = useRef(false);
  const [closing, setClosing] = useState(false);
  const titleId = useId();
  useEffect(() => {
    const dialog = ref.current;
    if (!dialog) return;
    if (open) {
      window.clearTimeout(closeTimer.current);
      setClosing(false);
      if (dialog.open && dialog.matches(':modal') === guided) dialog.close();
      if (!dialog.open) {
        if (guided) dialog.show();
        else dialog.showModal();
        // The browser focuses the first button (Close); prefer the field meant for typing.
        dialog.querySelector<HTMLElement>('[data-autofocus]')?.focus();
      }
      return;
    }
    if (dialog.open) {
      if (guided) { dialog.close(); setClosing(false); return; }
      setClosing(true);
      closeTimer.current = window.setTimeout(() => {
        dialog.close();
        setClosing(false);
      }, window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 0 : className.includes('documents-dialog') ? 340 : 180);
    }
  }, [open, className, guided]);
  useEffect(() => () => {
    window.clearTimeout(closeTimer.current);
    if (ref.current?.open) ref.current.close();
  }, []);

  return <dialog ref={ref} className={`dialog ${className}`} data-closing={closing || undefined} aria-labelledby={titleId}
    onCancel={event => { event.preventDefault(); onClose(); }}
    onPointerDown={event => { pressedBackdrop.current = event.target === event.currentTarget; }}
    onClick={event => { if (event.target === event.currentTarget && pressedBackdrop.current) onClose(); pressedBackdrop.current = false; }}>
    <div className="dialog-surface">
      <header className="dialog-header">
        <div><h2 id={titleId}>{title}</h2>{subtitle && <p>{subtitle}</p>}</div>
        <button className="icon-button" onClick={onClose} aria-label={closeLabel}><X size={19} /></button>
      </header>
      {children}
    </div>
  </dialog>;
}
