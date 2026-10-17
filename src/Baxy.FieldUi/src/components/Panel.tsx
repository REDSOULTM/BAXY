import type { ReactNode } from 'react';
import { Icon } from './Icon';

/* A floating panel over a veil, inside the app: it never opens a window and never takes Windows' focus
   (design components/panels.jsx). */
export function Panel({ title, onClose, width, children }: { title: string; onClose: () => void; width?: number; children: ReactNode }) {
  return (
    <div className="panel-shroud" onClick={onClose}>
      <div className="panel" style={width ? { width } : undefined} onClick={(e) => e.stopPropagation()} role="dialog" aria-label={title}>
        <div className="panel-head">
          <span className="panel-title">{title}</span>
          <button className="ibtn" onClick={onClose} data-tip="Cerrar" title="Cerrar"><Icon name="x" /></button>
        </div>
        <div className="panel-body">{children}</div>
      </div>
    </div>
  );
}

/** the two-step confirmation inside a row (design panels4.jsx BxConfirmRow). */
export function ConfirmRow({ label, yes, onYes, onNo }: { label: string; yes: string; onYes: () => void; onNo: () => void }) {
  return (
    <span className="bx-irow">
      <span>{label}</span>
      <button className="bx-sbtn" onClick={onNo}>No</button>
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
      {options.map(([v, l]) => <button key={v} className={value === v ? 'on' : ''} onClick={() => onChange(v)}>{l}</button>)}
    </div>
  );
}
