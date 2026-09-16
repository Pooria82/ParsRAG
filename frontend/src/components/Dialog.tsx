import { useEffect, useId, useRef, useState, type ReactNode } from 'react';
import { X } from 'lucide-react';

interface DialogProps {
  open: boolean;
  onClose: () => void;
  title: string;
  closeLabel: string;
  subtitle?: string;
  className?: string;
  children: ReactNode;
}

/** Native modal semantics keep keyboard focus and background interaction scoped. */
export function Dialog({ open, onClose, title, closeLabel, subtitle, className = '', children }: DialogProps) {
  const ref = useRef<HTMLDialogElement>(null);
  const [closing, setClosing] = useState(false);
  const titleId = useId();
  useEffect(() => {
    const dialog = ref.current;
    if (open && !dialog?.open) {
      setClosing(false);
      dialog?.showModal();
    }
    if (!open && dialog?.open) {
      setClosing(true);
      const timeout = window.setTimeout(() => {
        dialog.close();
        setClosing(false);
      }, window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 0 : 150);
      return () => window.clearTimeout(timeout);
    }
    return () => { if (dialog?.open) dialog.close(); };
  }, [open]);

  return <dialog ref={ref} className={`dialog ${className}`} data-closing={closing || undefined} aria-labelledby={titleId}
    onCancel={event => { event.preventDefault(); onClose(); }}
    onClick={event => { if (event.target === event.currentTarget) onClose(); }}>
    <div className="dialog-surface">
      <header className="dialog-header">
        <div><h2 id={titleId}>{title}</h2>{subtitle && <p>{subtitle}</p>}</div>
        <button className="icon-button" onClick={onClose} aria-label={closeLabel}><X size={19} /></button>
      </header>
      {children}
    </div>
  </dialog>;
}
