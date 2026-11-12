import { memo, useEffect, useRef, useState } from 'react';
import { Globe, Icon } from './Icon';
import type { ChatItem, Confirmation, Ring, Step, StepStatus } from '../types';
import { outcomeOf } from '../outcome';
import { sourcesOf, withoutSource } from '../sources';
import { useT, type Words } from '../i18n';
import { useApproval } from '../approval';
import { Marked } from '../markdown';

/* The conversation (design chat.jsx, BxChat4; interfaz v5, V5.md §5): the person's words, and each reply of BAXY's as a
   card that says how the request ended, what BAXY said (the last one largest) and «Cómo lo comprobé»; the Sí / No card
   of a call waiting for the person, always inside the conversation and never as a modal. */

const ST: Record<StepStatus, { ic: string | null; label: Words }> = {
  run: { ic: null, label: { es: 'en curso', en: 'running' } },
  ok: { ic: '✓', label: { es: 'comprobado', en: 'checked' } },
  same: { ic: '=', label: { es: 'ya estaba así', en: 'already set' } },
  sent: { ic: '↗', label: { es: 'enviado, sin comprobar', en: 'sent, not checked' } },
  read: { ic: '✓', label: { es: 'leído', en: 'read' } },
  fail: { ic: '✕', label: { es: 'falló', en: 'failed' } },
  skip: { ic: '–', label: { es: 'no se ejecutó', en: 'did not run' } },
  maybe: { ic: '?', label: { es: 'puede haber corrido', en: 'may have run' } },
};

/* «Cómo lo comprobé» (V5 §5): one row per step with what the provider observed, or why it failed or did not run. An
   observation that only repeats the status («Leído») is left out instead of said twice. It is open while a step runs,
   when one failed and when one changed a setting of BAXY's own (COR1: a change of the person's settings is never
   only behind the fold); otherwise a click away. Its title says a check only when every step was checked or read (INT13):
   a step sent without a check, failed, skipped or still running is told as what was done. What went online is said
   once: a step's line leaves out what the card's foot already says (DEP5: the same search showed twice). */
function HowChecked({ steps, net, open: always }: { steps: Step[]; net: string | null; open: boolean }) {
  const t = useT();
  const live = steps.some((s) => s.status === 'run' || s.status === 'fail' || s.pin);
  const checked = steps.every((s) => s.status === 'ok' || s.status === 'same' || s.status === 'read');
  const [mine, setOpen] = useState<boolean | null>(null);
  if (!steps.length) return null;
  const open = mine ?? (live || always);
  const n = steps.length;
  return (
    <div className="bx-how">
      <button className="bx-how-t" aria-expanded={open} onClick={() => setOpen(!open)}>
        {checked ? t('Cómo lo comprobé', 'How I checked it') : t('Qué hice', 'What I did')} · {n} {n === 1 ? t('paso', 'step') : t('pasos', 'steps')}<span className="ar" aria-hidden="true">{open ? '▴' : '▾'}</span>
      </button>
      {open ? (
        <ol className="bx-how-l">
          {steps.map((s) => {
            const st = ST[s.status] ?? ST.run;
            const said = s.status === 'fail' || s.status === 'skip' || s.status === 'maybe' ? s.reason : s.obs && withoutSource(s.obs);
            const note = said && said.trim().toLowerCase() !== t.w(st.label).toLowerCase() ? said : null;
            return (
              <li key={s.id} className={'bx-how-s st-' + s.status}>
                <span className="ic" aria-label={t.w(st.label)}>{s.status === 'run' ? <i className="spin"></i> : st.ic}</span>
                <span className="b">
                  <span className="k">{s.label}</span>
                  {note ? <span className="o">{note}</span> : null}
                  {s.net && s.net !== net ? <span className="o netb"><Globe s={10} /> {t('salió a internet', 'went online')} · {s.net}</span> : null}
                </span>
              </li>
            );
          })}
        </ol>
      ) : null}
    </div>
  );
}

function mmss(ms: number): string {
  const s = Math.max(0, Math.ceil(ms / 1000));
  return Math.floor(s / 60) + ':' + String(s % 60).padStart(2, '0');
}

function Card({ c, onYes, onNo }: { c: Confirmation; onYes: () => void; onNo: () => void }) {
  const t = useT();
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
  // OVL1: the Sí authorizes an effect: it is off, and looks it, until it has been drawn in its place for its wait
  const yesButton = useRef<HTMLButtonElement>(null);
  const yes = useApproval(c.id, [c.kind, c.title, c.target, c.risk, c.context, c.effectStarted].join('\n'), pend, yesButton);
  // nothing was done by this card unless an earlier attempt of the same call may already have run (then it only did
  // not run again)
  const none = c.effectStarted ? t('no se repitió', 'not run again') : t('no se hizo nada', 'nothing was done');
  return (
    <div className={'bx-card k-' + c.kind + ' s-' + status}>
      <div className="hd">
        <span className="tag">{c.kind === 'proposal' ? t('Propuesta', 'Proposal') : t('Confirmación', 'Confirmation')}</span>
        {c.risk ? <span className="risk">{c.risk}</span> : null}
        {c.effectStarted ? <span className="risk">{t('un intento anterior pudo haber corrido', 'an earlier attempt may have run')}</span> : null}
        {c.context ? <span className="ctx">{c.context}</span> : null}
      </div>
      <div className="ti">{c.title}</div>
      {c.target ? <div className="tg">{c.target}</div> : null}
      {pend ? (
        <div className="ft">
          <span className="exp">{t('vence en', 'expires in')} {mmss(left)}</span>
          <div className="btns">
            <button className="bx-btn" onClick={onNo}>No <kbd>esc</kbd></button>
            <button ref={yesButton} className={'bx-btn yes' + (yes.lit ? '' : ' off')} aria-disabled={!yes.armed} onPointerDown={yes.down} onKeyDown={yes.key}
              onClick={(e) => { if (yes.click(e)) onYes(); }}>{t('Sí', 'Yes')} <kbd className={yes.keys ? undefined : 'off'}>↵</kbd></button>
          </div>
        </div>
      ) : (
        <div className="res">
          {status === 'yes' ? t('✓ Aceptado', '✓ Accepted') + (c.via ? ' ' + c.via : '')
            : status === 'no' ? t('✕ Rechazado', '✕ Declined') + (c.via ? ' ' + c.via : '') + (c.effectStarted ? ' · ' + none : '')
              : status === 'dropped' ? t('Ya no está pendiente · ', 'No longer pending · ') + none
                : t('Venció sin respuesta · ', 'Expired with no answer · ') + none}
        </div>
      )}
    </div>
  );
}

/* An alarm or a reminder ringing now (ALR1): its words, and Stop and Snooze as a phone's alarm has them (Android's
   clock snoozes 10 minutes); a reminder's are Done and Remind in 10 min. Both go through schedule.alarms, as the
   model's call when the person says it. */
function RingCard({ r, onRing }: { r: Ring; onRing: (id: string, action: 'stop' | 'snooze') => void }) {
  const t = useT();
  const alarm = r.kind === 'alarm';
  const live = r.status === 'ringing';
  const ended: Record<Ring['status'], Words> = {
    ringing: { es: 'sonando', en: 'ringing' },
    stopped: alarm ? { es: '✓ Parada', en: '✓ Stopped' } : { es: '✓ Listo', en: '✓ Done' },
    snoozed: alarm ? { es: 'Pospuesta', en: 'Snoozed' } : { es: 'Pospuesto', en: 'Snoozed' },
    timeout: { es: 'Sonó 10 min sin respuesta', en: 'Rang 10 min with no answer' },
    unanswered: { es: 'Dicho dos veces sin respuesta', en: 'Said twice with no answer' },
    closed: { es: 'BAXY se cerró mientras sonaba', en: 'BAXY closed while it rang' },
    ended: { es: 'Ya no suena', en: 'No longer ringing' },
    windows: alarm ? { es: 'BAXY no pudo hacerla sonar: te avisa Windows', en: 'BAXY couldn’t ring it: Windows notifies you' }
      : { es: 'BAXY no pudo hacerlo sonar: te avisa Windows', en: 'BAXY couldn’t ring it: Windows notifies you' },
    failed: alarm ? { es: 'BAXY no pudo hacerla sonar', en: 'BAXY couldn’t ring it' } : { es: 'BAXY no pudo hacerlo sonar', en: 'BAXY couldn’t ring it' },
  };
  return (
    <div className={'bx-card k-ring' + (live ? ' s-pending' : ' s-' + r.status)} role={live ? 'alert' : undefined}>
      <div className="hd">
        <span className="tag">{alarm ? t('Alarma', 'Alarm') : t('Recordatorio', 'Reminder')}</span>
        <span className="ctx">{r.clock}</span>
      </div>
      <div className="ti">{r.title ?? r.words}</div>
      {live ? (
        <div className="ft">
          <span className="exp">{t('sonando · di «BAXY, para» o «cinco minutos más»', 'ringing · say “BAXY, stop” or “five more minutes”')}</span>
          <div className="btns">
            <button className="bx-btn" onClick={() => onRing(r.id, 'snooze')}>{alarm ? t('Posponer 10 min', 'Snooze 10 min') : t('Recordar en 10 min', 'Remind in 10 min')}</button>
            <button className="bx-btn yes" onClick={() => onRing(r.id, 'stop')}>{alarm ? t('Parar', 'Stop') : t('Listo', 'Done')}</button>
          </div>
        </div>
      ) : (
        <div className="res">{t.w(ended[r.status])}</div>
      )}
    </div>
  );
}

interface ChatProps {
  items: ChatItem[];
  title: string;
  meta: string;
  busy: boolean;
  /** the person's Sí or No on the card it names */
  onAnswer: (approve: boolean, card: string) => void;
  /** Stop or Snooze on the alarm or reminder ringing now */
  onRing: (id: string, action: 'stop' | 'snooze') => void;
  onCollapse: () => void;
  onNew: () => void;
  /** the conversations kept before (SessionsPanel) */
  onHistory: () => void;
  /** Personalización: «Cómo lo comprobé» open on every reply */
  stepsOpen?: boolean;
}

function ChatView({ items, title, meta, busy, onAnswer, onRing, onCollapse, onNew, onHistory, stepsOpen = false }: ChatProps) {
  const t = useT();
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
  let last = -1;
  for (let i = items.length - 1; i >= 0; i--) if (items[i].who === 'baxy') { last = i; break; }
  return (
    <div className="bx-chat4">
      <div className="bx-chat-head pywebview-drag-region">
        <div className="bx-c4-tt"><span className="ttl">{title}</span>{meta ? <span className="mt">{meta}</span> : null}</div>
        <div className="acts">
          <button className="bx-ib plain" title={t('Conversaciones anteriores', 'Earlier conversations')} aria-label={t('Conversaciones anteriores', 'Earlier conversations')} onClick={onHistory}><Icon name="history" size={13} /></button>
          <button className="bx-ib plain" title={t('Nueva conversación', 'New conversation')} onClick={onNew}><Icon name="plus" size={13} /></button>
          <button className="bx-ib plain" title={t('Ocultar conversación', 'Hide conversation')} onClick={onCollapse}>
            <svg width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="1.25"><path d="M4.5 2.5L8 6L4.5 9.5"></path></svg>
          </button>
        </div>
      </div>
      <div className="bx-c4-list" ref={ref}>
        {items.length === 0 ? <div className="bx-c4-empty">{t('Conversación nueva. Escribe o di «BAXY».', 'New conversation. Type, or say “BAXY”.')}</div> : null}
        {items.map((h, i) => {
          if (h.who === 'you') return <div key={h.id} className="bx-c4-you">{h.text}</div>;
          if (h.who === 'sys') return <div key={h.id} className="bx-c4-sys">{h.text}</div>;
          if (h.who === 'card') return <Card key={h.id} c={h} onYes={() => onAnswer(true, h.id)} onNo={() => onAnswer(false, h.id)} />;
          if (h.who === 'ring') return <RingCard key={h.id} r={h.ring} onRing={onRing} />;
          const out = outcomeOf(h.steps);
          const credited = sourcesOf(h.steps);
          return (
            <article key={h.id} className={'bx-c4-baxy' + (i === last ? ' last' : '') + (out ? ' o-' + out.kind : '')}
              aria-label={out ? t('Respuesta de BAXY: ', 'BAXY’s reply: ') + t.w(out.label) : t('Respuesta de BAXY', 'BAXY’s reply')}>
              {out ? <span className={'bx-out o-' + out.kind}><span aria-hidden="true">{out.ic}</span> {t.w(out.label)}</span> : null}
              {/* its own line breaks are drawn (white-space: pre-line, VIVO2 F16); none before or after it; its marks as what
                  they mean (markdown.tsx: CommonMark, never as HTML) */}
              {h.text ? <div className="tx"><Marked text={h.text.trim()} /></div> : null}
              {/* the source that answered, on the card's face and never behind a click (OSMF attribution, src/sources.ts) */}
              {credited.length ? <p className="bx-src">{(credited.length === 1 ? t('Fuente', 'Source') : t('Fuentes', 'Sources')) + ': ' + credited.join(' · ')}</p> : null}
              <HowChecked steps={h.steps} net={h.net ?? null} open={stepsOpen} />
              {h.net || h.silent ? (
                <div className="mt">
                  {h.net ? <span className="netb"><Globe s={10} /> {t('salió a internet', 'went online')} · {h.net}</span> : null}
                  {h.silent ? <span>{t('sin voz', 'no voice')} · {h.silent}</span> : null}
                </div>
              ) : null}
            </article>
          );
        })}
        {busy ? <div className="bx-c-think"><i></i><i></i><i></i></div> : null}
      </div>
    </div>
  );
}

export const Chat = memo(ChatView);
