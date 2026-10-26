import type { ReactNode } from 'react';
import { Icon } from './Icon';
import { useDialogFocus } from '../utils/dialogFocus';

/* A floating panel over a veil, inside the app: it never opens a window and never takes Windows' focus
   (design components/panels.jsx). */
export function Panel({ title, onClose, width, children }: { title: string; onClose: () => void; width?: number; children: ReactNode }) {
  const ref = useDialogFocus<HTMLDivElement>();
  return (
    <div className="panel-shroud" onClick={onClose}>
      <div ref={ref} tabIndex={-1} className="panel" style={{ outline: 'none', ...(width ? { width } : null) }} onClick={(e) => e.stopPropagation()} role="dialog" aria-modal="true" aria-label={title}>
        <div className="panel-head">
          <span className="panel-title">{title}</span>
          <button className="ibtn" onClick={onClose} data-tip="Cerrar" title="Cerrar" aria-label="Cerrar"><Icon name="x" /></button>
        </div>
        <div className="panel-body">{children}</div>
      </div>
    </div>
  );
}

/** the two-step confirmation inside a row (design panels4.jsx BxConfirmRow). The button that asked it is gone, so the
 *  keyboard's focus goes to its «No» (Enter never confirms by itself), and a screen reader hears the question first. */
export function ConfirmRow({ label, yes, onYes, onNo }: { label: string; yes: string; onYes: () => void; onNo: () => void }) {
  return (
    <span className="bx-irow" role="group" aria-label={label}>
      <span>{label}</span>
      <button className="bx-sbtn" onClick={onNo} autoFocus>No</button>
      <button className="bx-sbtn go" onClick={onYes}>{yes}</button>
    </span>
  );
}

export function Toggle({ on, onChange, locked, label }: { on: boolean; onChange?: (v: boolean) => void; locked?: boolean; label?: string }) {
  return (
    <button className={'toggle' + (on ? ' on' : '') + (locked ? ' locked' : '')} role="switch" aria-checked={on} aria-label={label}
      disabled={locked} onClick={() => !locked && onChange?.(!on)}>
      <span className="knob"></span>
    </button>
  );
}

export function Seg<T extends string>({ value, options, onChange }: { value: T; options: [T, string][]; onChange: (v: T) => void }) {
  return (
    <div className="bxs-seg">
      {options.map(([v, l]) => <button key={v} className={value === v ? 'on' : ''} aria-pressed={value === v} onClick={() => onChange(v)}>{l}</button>)}
    </div>
  );
}
