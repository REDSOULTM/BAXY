import { useEffect, useState } from 'react';

/* The mouth follows what is heard (owner, 2026-10-21: «si se corta antes la animación de habla, no está funcionando»).
   The mind sends each take of BAXY's voice as it starts writing it: its loudness every `step` ms (0 closed … 1 open)
   from the wall-clock time `t0` its first sample sounds, and `stop` when the voice is cut. The avatar reads this
   timeline every frame with the same clock; nothing here goes through React. */

export interface Take { t0: number; step: number; env: number[]; voicedEnd: number }

const VOICED = 0.12;      // a level above this is voice; below it, a pause
const BRIDGE_MS = 450;    // a pause shorter than this keeps the mouth in «speaking» (between words and sentences)
const LEAD_MS = 80;       // the mouth opens this much before the first sound (a mouth moves before its sound)
const AHEAD_MS = 50;      // the shape shown is the one 50 ms ahead: measured against the sound the device plays
                          // (WASAPI loopback, 2026-10-21) the mouth trailed the voice by 40-50 ms without it
const KEEP_MS = 30_000;

let takes: Take[] = [];
let known = false;

const voicedEnd = (t0: number, step: number, env: number[]) => {
  let last = -1;
  for (let i = env.length - 1; i >= 0; i--) if (env[i] >= VOICED) { last = i; break; }
  return last < 0 ? t0 : t0 + (last + 1) * step;
};

/** A «lip» event of the host: a take, or the moment the voice was cut. */
export function lipPush(ev: { t0?: number | null; step?: number | null; env?: number[] | null; stop?: number | null }, now = Date.now()): void {
  known = true;
  takes = takes.filter((t) => t.t0 + t.env.length * t.step > now - KEEP_MS);
  if (typeof ev.stop === 'number') {
    const stop = ev.stop;
    takes = takes.flatMap((t) => {
      if (t.t0 >= stop) return [];
      const env = t.env.slice(0, Math.max(0, Math.floor((stop - t.t0) / t.step)));
      return [{ ...t, env, voicedEnd: voicedEnd(t.t0, t.step, env) }];
    });
    return;
  }
  if (typeof ev.t0 !== 'number' || typeof ev.step !== 'number' || ev.step <= 0 || !Array.isArray(ev.env)) return;
  const env = ev.env.map((v) => (Number.isFinite(v) ? Math.max(0, Math.min(1, v)) : 0));
  takes.push({ t0: ev.t0, step: ev.step, env, voicedEnd: voicedEnd(ev.t0, ev.step, env) });
  takes.sort((a, b) => a.t0 - b.t0);
}

export interface LipNow {
  /** how open the mouth is now, 0..1 (0 in a pause) */
  level: number;
  /** BAXY's voice is sounding now or within a short pause of it */
  active: boolean;
  /** the host sends the voice's timeline (a mind without it leaves the clip's own mouth) */
  known: boolean;
}

export function lipAt(now = Date.now()): LipNow {
  let level = 0, active = false;
  for (const t of takes) {
    // from just before its first sound to a short pause after its last voiced step: a pause between takes no longer
    // than BRIDGE_MS (words, sentences, a synthesis a little late) keeps it speaking
    if (now >= t.t0 - LEAD_MS && now <= t.voicedEnd + BRIDGE_MS && t.voicedEnd > t.t0) active = true;
    const x = (now + AHEAD_MS - t.t0) / t.step;
    if (x >= 0 && x < t.env.length) {
      const i = Math.floor(x), f = x - i, a = t.env[i], b = t.env[Math.min(t.env.length - 1, i + 1)];
      level = Math.max(level, a + (b - a) * f);
    }
  }
  return { level: active ? level : 0, active, known };
}

/** For tests: forgets every take. */
export function lipReset(): void { takes = []; known = false; }

/** Whether BAXY's voice sounds now (null while the host sends no timeline): re-renders only when it changes. */
export function useLipActive(): boolean | null {
  const [v, setV] = useState<boolean | null>(() => { const l = lipAt(); return l.known ? l.active : null; });
  useEffect(() => {
    const id = window.setInterval(() => { const l = lipAt(); setV(l.known ? l.active : null); }, 40);
    return () => window.clearInterval(id);
  }, []);
  return v;
}
