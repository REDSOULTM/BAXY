import { memo, useEffect, useRef, useState } from 'react';
import { Globe, Icon } from './Icon';
import type { ChatItem, Confirmation, Fam, Step, StepStatus } from '../types';

/* The conversation (design chat.jsx, BxChat4): the person's words, BAXY's, a chip per call under each reply and the
   Sí / No card of a call waiting for the person, always inside the conversation and never as a modal. */

const ST: Record<StepStatus, { ic: string | null; label: string }> = {
  run: { ic: null, label: 'en curso' },
  ok: { ic: '✓', label: 'verificado' },
  same: { ic: '=', label: 'ya estaba así' },
  sent: { ic: '↗', label: 'enviado, sin comprobar' },
  read: { ic: '✓', label: 'leído' },
  fail: { ic: '✕', label: 'falló' },
  skip: { ic: '–', label: 'no se ejecutó' },
  maybe: { ic: '?', label: 'puede haber corrido' },
};

const FAM_LABEL: Record<Fam, string> = {
  apps: 'apps', ventanas: 'ventanas', archivos: 'archivos', web: 'web', musica: 'música', memoria: 'memoria', alarmas: 'alarmas',
};

function StepChip({ s, open, onClick }: { s: Step; open: boolean; onClick: () => void }) {
  const st = ST[s.status] ?? ST.run;
  return (
    <button className={'bx-chip st-' + s.status + (open ? ' open' : '')} onClick={onClick} title={st.label}>
      <span className="ic">{s.status === 'run' ? <i className="spin"></i> : st.ic}</span>
      <span className="lb">{s.label}</span>
      {s.net ? <span className="nt"><Globe s={10} /></span> : null}
    </button>
  );
}

function Steps({ steps }: { steps: Step[] }) {
  const [open, setOpen] = useState(-1);
  if (!steps.length) return null;
  const o = open >= 0 ? steps[open] : undefined;
  return (
    <div className="bx-steps">
      <div className="row">
        {steps.map((s, i) => <StepChip key={s.id} s={s} open={open === i} onClick={() => setOpen(open === i ? -1 : i)} />)}
      </div>
      {steps.map((s, i) => (s.status === 'fail' && open !== i ? <div key={s.id} className="bx-why"><b>✕ {s.label}:</b> {s.reason}</div> : null))}
      {o ? (
        <div className={'bx-obs st-' + o.status}>
          <div className="h"><span>{ST[o.status].label}</span><span className="fam">{FAM_LABEL[o.fam]}</span></div>
          <div className="t">{o.obs || o.reason || 'En curso…'}</div>
          {o.net ? <div className="net"><Globe s={10} /> salió a internet · {o.net}</div> : null}
        </div>
      ) : null}
    </div>
  );
}

function mmss(ms: number): string {
  const s = Math.max(0, Math.ceil(ms / 1000));
  return Math.floor(s / 60) + ':' + String(s % 60).padStart(2, '0');
}

export function Card({ c, onYes, onNo }: { c: Confirmation; onYes: () => void; onNo: () => void }) {
  const [now, setNow] = useState(() => Date.now());
  const live = c.status === 'pending';
  useEffect(() => {
    if (!live) return;
    const id = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(id);
  }, [live]);
  const left = c.expires - now;
  // the kernel's token is dead past its time even before the host says so: the card never offers a Sí that cannot run.
  const status = live && left <= 0 ? 'expired' : c.status;
  const pend = status === 'pending';
  // nothing was done by this card unless an earlier attempt of the same call may already have run (then it only did
  // not run again)
  const none = c.effectStarted ? 'no se repitió' : 'no se hizo nada';
  return (
    <div className={'bx-card k-' + c.kind + ' s-' + status}>
      <div className="hd">
        <span className="tag">{c.kind === 'proposal' ? 'Propuesta' : 'Necesito tu ok'}</span>
        {c.risk ? <span className="risk">{c.risk}</span> : null}
        {c.effectStarted ? <span className="risk">un intento anterior pudo haber corrido</span> : null}
        {c.context ? <span className="ctx">{c.context}</span> : null}
      </div>
      <div className="ti">{c.title}</div>
      {c.target ? <div className="tg">{c.target}</div> : null}
      {pend ? (
        <div className="ft">
          <span className="exp">vence en {mmss(left)}</span>
          <div className="btns">
            <button className="bx-btn" onClick={onNo}>No <kbd>esc</kbd></button>
            <button className="bx-btn yes" onClick={onYes}>Sí <kbd>↵</kbd></button>
          </div>
        </div>
      ) : (
        <div className="res">
          {status === 'yes' ? '✓ Aceptado' + (c.via ? ' ' + c.via : '')
            : status === 'no' ? '✕ Rechazado' + (c.via ? ' ' + c.via : '') + (c.effectStarted ? ' · ' + none : '')
              : status === 'dropped' ? 'Ya no está pendiente · ' + none
                : 'Venció sin respuesta · ' + none}
        </div>
      )}
    </div>
  );
}

interface ChatProps {
  items: ChatItem[];
  title: string;
  meta: string;
  busy: boolean;
  onAnswer: (approve: boolean) => void;
  onCollapse: () => void;
  onNew: () => void;
}

function ChatView({ items, title, meta, busy, onAnswer, onCollapse, onNew }: ChatProps) {
  const ref = useRef<HTMLDivElement>(null);
  const stick = useRef(true);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const toEnd = () => { if (stick.current) el.scrollTop = el.scrollHeight; };
    // design v5: only a scroll the person makes by hand (wheel, touch, pointer, keys) unsticks the chat from the end;
    // a scroll the layout causes (a card growing, the panel resizing) never does
    let user = 0;
    const intent = () => { user = performance.now(); };
    const INTENT = ['wheel', 'touchstart', 'pointerdown', 'keydown'] as const;
    const onScroll = () => { if (performance.now() - user < 1200) stick.current = el.scrollHeight - el.scrollTop - el.clientHeight < 48; };
    const mo = new MutationObserver(() => requestAnimationFrame(toEnd));
    mo.observe(el, { childList: true, subtree: true, characterData: true });
    el.addEventListener('scroll', onScroll, { passive: true });
    INTENT.forEach((e) => el.addEventListener(e, intent, { passive: true }));
    toEnd();
    return () => { mo.disconnect(); el.removeEventListener('scroll', onScroll); INTENT.forEach((e) => el.removeEventListener(e, intent)); };
  }, []);
  useEffect(() => {
    const l = items[items.length - 1];
    if (l && (l.who === 'you' || l.who === 'card')) stick.current = true;
    const el = ref.current;
    if (el && stick.current) requestAnimationFrame(() => { el.scrollTop = el.scrollHeight; });
  }, [items]);
  return (
    <div className="bx-chat4">
      <div className="bx-chat-head">
        <div className="bx-c4-tt"><span className="ttl">{title}</span>{meta ? <span className="mt">{meta}</span> : null}</div>
        <div className="acts">
          <button className="bx-ib plain" title="Nueva conversación" onClick={onNew}><Icon name="plus" size={13} /></button>
          <button className="bx-ib plain" title="Ocultar conversación" onClick={onCollapse}>
            <svg width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="1.25"><path d="M4.5 2.5L8 6L4.5 9.5"></path></svg>
          </button>
        </div>
      </div>
      <div className="bx-c4-list" ref={ref}>
        {items.length === 0 ? <div className="bx-c4-empty">Conversación nueva. Escribe o di «BAXY».</div> : null}
        {items.map((h) => {
          if (h.who === 'you') return <div key={h.id} className="bx-c4-you">{h.text}</div>;
          if (h.who === 'sys') return <div key={h.id} className="bx-c4-sys">{h.text}</div>;
          if (h.who === 'card') return <Card key={h.id} c={h} onYes={() => onAnswer(true)} onNo={() => onAnswer(false)} />;
          return (
            <div key={h.id} className="bx-c4-baxy">
              {h.text ? <div className="tx">{h.text}</div> : null}
              <Steps steps={h.steps} />
              {h.net || h.silent ? (
                <div className="mt">
                  {h.net ? <span className="netb"><Globe s={10} /> salió a internet · {h.net}</span> : null}
                  {h.silent ? <span>sin voz · {h.silent}</span> : null}
                </div>
              ) : null}
            </div>
          );
        })}
        {busy ? <div className="bx-c-think"><i></i><i></i><i></i></div> : null}
      </div>
    </div>
  );
}

export const Chat = memo(ChatView);
