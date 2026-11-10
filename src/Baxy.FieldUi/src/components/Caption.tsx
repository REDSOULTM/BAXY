import { useEffect, useState } from 'react';
import type { BaxyState, BootPieces } from '../types';
import { useT } from '../i18n';
import { causeText, ON_PROCESSOR_TEXT, readingText } from '../causes';
import { plainOf } from '../marks';

/* Under the face (design chat.jsx BxCap4, BxBoot; parts.jsx BxSub): BAXY's words as captions, the live transcription
   while it listens, the call it is running, what it waits for, and the start with each piece marked only once the host
   says it is ready — no percentages, no invented bar. */

function Sub({ text: written, animate, gone }: { text: string; animate: boolean; gone: boolean }) {
  // the reply as the voice says it: its words without the marks the chat draws (F16; speech_text.unmarked)
  const text = plainOf(written);
  const words = text.split(' ');
  // the words appear once, when the reply first shows while BAXY speaks; BAXY speaking again later (its notice, the next
  // answer) never runs them again over what it says then (owner, 2026-10-20)
  const [typed] = useState(animate);
  const [shown, setShown] = useState(typed ? 0 : words.length);
  useEffect(() => {
    if (!typed) return;
    const n = text.split(' ').length;
    let i = 0;
    const id = window.setInterval(() => { i++; setShown(i); if (i >= n) window.clearInterval(id); }, 80);
    return () => window.clearInterval(id);
  }, [text, typed]);
  return (
    <div className={'bx-sub' + (gone ? ' gone' : '')}>
      {words.map((w, k) => <span key={k} style={{ opacity: k < shown ? 1 : 0 }}>{w + ' '}</span>)}
    </div>
  );
}

interface CapProps {
  state: BaxyState;
  sub: { text: string; key: string } | null;
  subGone: boolean;
  live: string;
  step: string | null;
  waiting: string | null;
}

export function Caption({ state, sub, subGone, live, step, waiting }: CapProps) {
  if (state === 'booting' || state === 'standby') return <div className="bx-cap"></div>;
  if (state === 'listening') return <div className="bx-cap"><div className="bx-live">{live || ' '}</div></div>;
  // a failure is the state's label above (the ear's, the model's): the captions are BAXY's own words only
  if (state === 'error') return <div className="bx-cap"></div>;
  if (state === 'thinking' && step) return <div className="bx-cap"><div className="bx-step bx-fade" key={step}><span className="txt">{step}</span></div></div>;
  if (waiting) return <div className="bx-cap"><div className="bx-wait bx-fade">{waiting} <span className="ar">→</span></div></div>;
  return <div className="bx-cap">{sub ? <Sub key={sub.key} text={sub.text} animate={state === 'speaking'} gone={subGone} /> : null}</div>;
}

// How long the model took to load the last time on this PC (this view's own note), never a promise of how long it takes.
function lastLoad(): number | null {
  try {
    const v = Number(localStorage.getItem('baxy.lastLoad'));
    return Number.isFinite(v) && v > 0 ? v : null;
  } catch {
    return null;
  }
}

export function Boot({ boot }: { boot: BootPieces }) {
  const t = useT();
  const [now, setNow] = useState(() => Date.now());
  const [previous] = useState(lastLoad);
  useEffect(() => {
    if (boot.model || boot.failed) return;
    const id = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(id);
  }, [boot.model, boot.failed]);
  const secs = Math.max(0, Math.round(((boot.readyAt ?? now) - boot.startedAt) / 1000));
  // a piece the host found missing is said so; one it has not read yet keeps its spinner.
  const parts: [string, boolean | null][] = [
    [t('Reconocimiento de voz', 'Speech recognition'), boot.stt], [t('Palabra de activación «BAXY»', 'Wake word “BAXY”'), boot.wake],
    [t('Voz de BAXY', 'BAXY’s voice'), boot.tts], [t('Modelo Qwen3.5-4B', 'Qwen3.5-4B model'), boot.model ? true : boot.failed ? false : null],
  ];
  return (
    <div className="bx-boot">
      {parts.map(([l, d]) => (
        <div key={l} className={'r' + (d ? ' done' : '')}>
          <span className="ic">{d ? '✓' : d === false ? '–' : <i className="spin"></i>}</span>
          <span>{d === false ? l + t(' · no disponible', ' · not available') : l}</span>
        </div>
      ))}
      {!boot.model && !boot.failed ? <div className="bar"><i></i></div> : null}
      {!boot.model && !boot.failed && boot.reading ? <div className="el">{readingText(boot.reading, t)}</div> : null}
      {!boot.model && boot.onProcessor ? <div className="el">{t.w(ON_PROCESSOR_TEXT)}</div> : null}
      {!boot.model && !boot.failed && boot.lastFailure ? (
        <div className="el">
          {t('El intento anterior no arrancó', 'The last attempt did not start') + (causeText(boot.lastFailure, t, boot.failureMemory, boot.failureRead) ? ': ' + causeText(boot.lastFailure, t, boot.failureMemory, boot.failureRead) : '') + t(' · reintentando', ' · retrying')}
        </div>
      ) : null}
      <div className="el">
        {boot.model ? t('Listo · cargó en ', 'Ready · loaded in ') + secs + ' s'
          : boot.failed ? t('El modelo no arrancó', 'The model did not start') + (causeText(boot.lastFailure, t, boot.failureMemory, boot.failureRead) ? ': ' + causeText(boot.lastFailure, t, boot.failureMemory, boot.failureRead) : '')
            : secs + ' s' + (previous ? t(' · la última vez tardó ', ' · last time it took ') + previous + ' s' : '')}
      </div>
    </div>
  );
}
