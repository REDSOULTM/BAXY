import { useEffect, useState } from 'react';
import type { BaxyState, BootPieces } from '../types';

/* Under the face (design chat.jsx BxCap4, BxBoot; parts.jsx BxSub): BAXY's words as captions, the live transcription
   while it listens, the call it is running, what it waits for, and the start with each piece marked only once the host
   says it is ready — no percentages, no invented bar. */

function Sub({ text, animate, gone }: { text: string; animate: boolean; gone: boolean }) {
  const words = text.split(' ');
  const [shown, setShown] = useState(animate ? 0 : words.length);
  useEffect(() => {
    const n = text.split(' ').length;
    if (!animate) return;
    let i = 0;
    const id = window.setInterval(() => { i++; setShown(i); if (i >= n) window.clearInterval(id); }, 80);
    return () => window.clearInterval(id);
  }, [text, animate]);
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
  error: string;
}

export function Caption({ state, sub, subGone, live, step, waiting, error }: CapProps) {
  if (state === 'booting' || state === 'standby') return <div className="bx-cap"></div>;
  if (state === 'listening') return <div className="bx-cap"><div className="bx-live">{live || ' '}</div></div>;
  if (state === 'error') return <div className="bx-cap"><div className="bx-err bx-fade">{error}</div></div>;
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
    ['Reconocimiento de voz', boot.stt], ['Palabra de activación «BAXY»', boot.wake], ['Voz de BAXY', boot.tts], ['Modelo Qwen3.5-4B', boot.model ? true : boot.failed ? false : null],
  ];
  return (
    <div className="bx-boot">
      {parts.map(([l, d]) => (
        <div key={l} className={'r' + (d ? ' done' : '')}>
          <span className="ic">{d ? '✓' : d === false ? '–' : <i className="spin"></i>}</span>
          <span>{d === false ? l + ' · no disponible' : l}</span>
        </div>
      ))}
      {!boot.model && !boot.failed ? <div className="bar"><i></i></div> : null}
      <div className="el">
        {boot.model ? 'Listo · cargó en ' + secs + ' s'
          : boot.failed ? 'El modelo no arrancó'
            : secs + ' s' + (previous ? ' · la última vez tardó ' + previous + ' s' : '')}
      </div>
    </div>
  );
}
