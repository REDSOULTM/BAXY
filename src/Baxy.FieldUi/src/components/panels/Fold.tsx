import { useId, useState, type ReactNode } from 'react';

/* A section of Settings that folds with its arrow and, folded, says its summary (owner, 2026-11-08: «es mucha información …
   ni siquiera hay una flechita para desplegar o contraer»; design boards 13 to 24). Whether it is open is kept per section
   in this browser profile, so it stays as the person left it; anything that fails to read or write it opens as designed. */

const KEY = 'baxy.fold.';

function kept(id: string): boolean | null {
  try {
    const v = localStorage.getItem(KEY + id);
    return v === '1' ? true : v === '0' ? false : null;
  } catch { return null; }
}

function keep(id: string, open: boolean) {
  try { localStorage.setItem(KEY + id, open ? '1' : '0'); } catch { /* the section still opens and closes */ }
}

export function Fold({ id, title, summary, open: byDefault = false, children }: { id: string; title: string; summary?: ReactNode; open?: boolean; children: ReactNode }) {
  const [open, setOpen] = useState(() => kept(id) ?? byDefault);
  const body = useId();
  return (
    <section className={'bx-fold' + (open ? ' open' : '')}>
      <button className="bx-fold-h" aria-expanded={open} aria-controls={body} onClick={() => { keep(id, !open); setOpen(!open); }}>
        <svg className="chev" width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden="true">
          <path d={open ? 'M2.5 4.5L6 8l3.5-3.5' : 'M4.5 2.5L8 6l-3.5 3.5'} />
        </svg>
        <span className="tt">{title}</span>
        {summary ? <span className="sum">{summary}</span> : null}
      </button>
      {open ? <div className="bx-fold-b" id={body}>{children}</div> : null}
    </section>
  );
}
