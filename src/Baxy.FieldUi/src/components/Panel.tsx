import type { ReactNode } from 'react';
import { Icon } from './Icon';
import { useDialogFocus } from '../utils/dialogFocus';
import { radioKeys, rovingIndex } from '../utils/radioKeys';
import { useT } from '../i18n';

/* A floating panel over a veil, inside the app: it never opens a window and never takes Windows' focus
   (design components/panels.jsx). */
export function Panel({ title, onClose, width, children }: { title: string; onClose: () => void; width?: number; children: ReactNode }) {
  const t = useT();
  const ref = useDialogFocus<HTMLDivElement>();
  return (
    <div className="panel-shroud" onClick={onClose}>
      <div ref={ref} tabIndex={-1} className="panel" style={{ outline: 'none', ...(width ? { width } : null) }} onClick={(e) => e.stopPropagation()} role="dialog" aria-modal="true" aria-label={title}>
        <div className="panel-head">
          <span className="panel-title">{title}</span>
          <button className="ibtn" onClick={onClose} data-tip={t('Cerrar', 'Close')} title={t('Cerrar', 'Close')} aria-label={t('Cerrar', 'Close')}><Icon name="x" /></button>
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

/** One choice among a few. Locked when it does not apply under another choice (the border's speed with the border off). */
export function Seg<T extends string>({ value, options, onChange, label, locked }: { value: T; options: [T, string][]; onChange: (v: T) => void; label?: string; locked?: boolean }) {
  return (
    <div className={'bxs-seg' + (locked ? ' locked' : '')} role={label ? 'group' : undefined} aria-label={label}>
      {options.map(([v, l]) => <button key={v} className={value === v ? 'on' : ''} aria-pressed={value === v} disabled={locked} onClick={() => onChange(v)}>{l}</button>)}
    </div>
  );
}

/** One choice among a few, as cards (owner, 2026-11-09: «hazlo como en los tableros»; design boards 17 to 24): the chosen one
 *  glows like the window's ring. For choices that say more than a word; two short options stay a Seg. */
export function Pick<T extends string>({ label, value, options, onChange, locked }: {
  label: string; value: T; onChange: (v: T) => void; locked?: boolean;
  options: { v: T; title: string; sub?: string; tag?: string; tone?: 'on' | 'busy' }[];
}) {
  return (
    <div className="bx-pick" role="radiogroup" aria-label={label} onKeyDown={radioKeys(true)}>
      {options.map((o, i) => (
        <button key={o.v} className={'bx-pick-o' + (value === o.v ? ' on' : '')} role="radio" aria-checked={value === o.v} aria-label={o.title}
          tabIndex={rovingIndex(i, options.findIndex((x) => x.v === value))}
          disabled={locked} onClick={() => onChange(o.v)}>
          <span className="t"><span className="dot" />{o.title}</span>
          {o.sub ? <span className="s">{o.sub}</span> : null}
          {o.tag ? <span className={'bx-tag' + (o.tone ? ' ' + o.tone : '')}>{o.tag}</span> : null}
        </button>
      ))}
    </div>
  );
}
