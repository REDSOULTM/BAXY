import { memo, useEffect, useRef } from 'react';
import {
  BODYH, BXM, FK, FY, GLYPH_EX, GLYPH_Q, HUB_LABEL, HUB_NAME, IDLE, PLATE, SH, THINK, TALK, TILT,
  bxArc, bxBrow, bxEll, bxEye, bxMouth, bxRoute, bxSample, bxSuper, type Pt,
} from './geometry';
import type { Journey } from '../../store';
import { lipAt } from '../../lip';

/* The cartoon robot face made of firework particles, on top of the neural mesh (design face.jsx, ported almost as
   is): static parts painted into three offscreen bitmaps while still, 30 fps at rest and 60 while it thinks or speaks,
   DPR ≤ 1.25, the buffer capped at 4.5 MP. The one change: the walk through the mesh grows with the turn's real calls
   (the journey's path gets a family per call), so each new family adds a segment instead of replaying a whole flow.
   Design v5: with `overlay` the canvas sits over the video avatar (AvatarVid) and draws only the live network — mesh
   trail, hubs, sparks, tracer, labels — skipping helmet, body and features (NOC/NOR clip them away), stays still (no
   tilt or bounce) and publishes the face's geometry as --av-x / --av-y / --av-s on its parent so the video lines up. */

type FaceState = 'standby' | 'idle' | 'listening' | 'thinking' | 'speaking' | 'error' | 'confirm';
const PAL: Record<string, { f: string; l: string; p: string }> = {
  standby: { f: '#8B95A8', l: '#4A5470', p: '#C2C9D6' },
  idle: { f: '#FF5A6E', l: '#5B7FDB', p: '#FFB3BC' },
  listening: { f: '#FF7A88', l: '#E55366', p: '#FFE0E4' },
  thinking: { f: '#9DB4F5', l: '#4C6CC9', p: '#EEF2FF' },
  speaking: { f: '#F5D69C', l: '#C9A66B', p: '#FFF6E2' },
  error: { f: '#FF4D5E', l: '#8A3A48', p: '#FFC2C9' },
};
const PAL_L: Record<string, { f: string; l: string; p: string }> = {
  standby: { f: '#8B95A8', l: '#7A849A', p: '#5B6580' },
  idle: { f: '#FF5A6E', l: '#3A5BB8', p: '#C2334A' },
  listening: { f: '#FF7A88', l: '#C23A4E', p: '#B83A4A' },
  thinking: { f: '#9DB4F5', l: '#2E4BA0', p: '#2E4BA0' },
  speaking: { f: '#F5D69C', l: '#9A7A3A', p: '#8A6A2A' },
  error: { f: '#FF4D5E', l: '#B03A4A', p: '#B03A4A' },
};
type RGB = [number, number, number];
const hex = (c: string): RGB => [1, 3, 5].map((i) => parseInt(c.slice(i, i + 2), 16)) as RGB;
const rgba = (c: RGB, a: number) => `rgba(${c[0] | 0},${c[1] | 0},${c[2] | 0},${Math.max(0, Math.min(1, a)).toFixed(3)})`;
export const FACE_MAXPX = 4.5e6; /* canvas buffer cap: keeps 4K/8K smooth */
const RATE: Record<string, number> = { error: 0.3, standby: 0, idle: 0.8, listening: 3.5, thinking: 6, speaking: 4, confirm: 0.8 };

interface Particle { x: number; y: number; vx: number; vy: number; tx: number; ty: number; big: boolean }
interface Group { kind: 's' | 'e' | 'f'; closed: number; closedT: number; k: number; pts: Particle[] }
interface Tracer { nodes: number[]; L: number[]; total: number; t0: number; dur: number; u: number; done?: boolean }
interface Spark { a: number; b: number; u: number; hops: number; sp: number; tail: Pt[] }
interface Fx { k: 'conf' | 'note' | 'drop' | 'star'; x: number; y: number; vx: number; vy: number; t: number; life: number; c?: string; r?: number; vr?: number; ph?: number }
interface Act { name: string; t0: number; dur: number; s: number; fired: number }

export interface FaceProps {
  state: FaceState;
  expr: string;
  talking: boolean;
  journey: Journey | null;
  hold: boolean;
  light: boolean;
  net: boolean;
  overlay?: boolean;
}

function FaceView(props: FaceProps) {
  const ref = useRef<HTMLCanvasElement>(null);
  const P = useRef(props);
  useEffect(() => { P.current = props; });
  useEffect(() => {
    const cv = ref.current!, ctx = cv.getContext('2d')!;
    const DPR = Math.min(1.25, window.devicePixelRatio || 1);
    let dpr = DPR, refW = 0, dirty = true, w = 0, h = 0, raf = 0, last = performance.now();
    const mkG = (n: number, kind: Group['kind'], closed: number, k: number): Group => ({
      kind, closed, closedT: closed, k, pts: Array.from({ length: n }, () => ({ x: 0, y: -0.1, vx: 0, vy: 0, tx: 0, ty: 0, big: Math.random() < 0.22 })),
    });
    const G: Record<string, Group> = {
      shell: mkG(84, 's', 1, 70), visor: mkG(64, 's', 1, 70), earL: mkG(18, 's', 0, 70), earR: mkG(18, 's', 0, 70),
      inL: mkG(10, 'e', 1, 70), inR: mkG(10, 'e', 1, 70), stem: mkG(6, 's', 0, 90), bulb: mkG(12, 'e', 1, 90),
      bodyL: mkG(26, 's', 0, 55), bodyR: mkG(26, 's', 0, 55), plate: mkG(22, 's', 1, 60),
      eyeL: mkG(30, 'f', 1, 170), eyeR: mkG(30, 'f', 1, 170), mouth: mkG(34, 'f', 0, 170),
      browL: mkG(12, 'f', 0, 150), browR: mkG(12, 'f', 0, 150),
    };
    const STATIC: Record<string, Pt[]> = {
      shell: bxSample(bxSuper(0, 0, 1.0, 0.84, 3.1), 84, true), visor: bxSample(bxSuper(0, 0.05, 0.8, 0.6, 3.6), 64, true),
      earL: bxSample(bxArc(-1.0, 0.03, 0.17, 0.31, 1.5708, 4.7124, 30), 18, false), earR: bxSample(bxArc(1.0, 0.03, 0.17, 0.31, -1.5708, 1.5708, 30), 18, false),
      inL: bxEll(-1.07, 0.03, 0.055, 0.12, 10), inR: bxEll(1.07, 0.03, 0.055, 0.12, 10),
      bodyL: bxSample(BODYH(-1), 26, false), bodyR: bxSample(BODYH(1), 26, false),
      plate: bxSample(PLATE, 22, true),
    };
    const dust = Array.from({ length: 44 }, () => ({ a: Math.random() * 6.28, r: 1.35 + Math.random() * 0.75, sp: (0.03 + Math.random() * 0.06) * (Math.random() < 0.5 ? -1 : 1), yk: 0.7 + Math.random() * 0.2, odd: Math.random() < 0.5 }));
    const col: Record<'f' | 'l' | 'p', RGB> = { f: hex(PAL.idle.f), l: hex(PAL.idle.l), p: hex(PAL.idle.p) };
    let boot = performance.now() / 1000, lastKey = '', prevState = '', tilt = 0, gx = 0, gy = 0;
    let mouse: Pt | null = null;
    let blink = 1, nextBlink = 2, blinkT = -1, talk = 0, talkT = 0, talkTimer = 0, vis = 0, ant = 0, antV = 0, bounce = 0, bounceV = 0;
    const cache = { key: '', c: [0, 1, 2].map(() => document.createElement('canvas')) };
    let wasListen = false, act: Act | null = null, lastActs: string[] = [], nextAct = 3, thinkV: string | null = null, thinkT = 0;
    let gest: { name: string; t0: number; dur: number } | null = null, nextGest = 0.8, leanS = 1, hop = 0, hopV = 0, sq = 0, sqV = 0, browLift = 0;
    let fx: Fx[] = [], qA = 0, exA = 0, bubA = 0, scanA = 0, lastMouseT = -9, droopY = 0, prevExpr = '';
    let earL2 = 0, lvl = 0, sparks: Spark[] = [], flashes: { x: number; y: number; t: number }[] = [], earGlow = 0, trs: Tracer[] = [], trail = 0;
    let jTurn: string | null = null, jLen = 0;
    const heat = new Float32Array(BXM.N.length);
    const onMove = (e: PointerEvent) => { const r = cv.getBoundingClientRect(); mouse = [(e.clientX - r.left) / r.width, (e.clientY - r.top) / r.height]; lastMouseT = performance.now() / 1000; };
    const pick = <T,>(arr: T[]) => arr[Math.floor(Math.random() * arr.length)];
    const confetti = (n: number) => {
      const cs = ['#FFB3BC', '#F5D69C', '#9DB4F5', '#FF7A9A', '#EEF2FF'];
      for (let i = 0; i < n; i++) fx.push({ k: 'conf', x: (Math.random() - 0.5) * 0.5, y: -0.9, vx: (Math.random() - 0.5) * 2.4, vy: -1.4 - Math.random() * 1.6, t: 0, life: 1.3 + Math.random() * 0.8, c: cs[i % cs.length], r: Math.random() * 6.28, vr: (Math.random() - 0.5) * 14 });
    };
    window.addEventListener('pointermove', onMove, { passive: true });
    const size = () => {
      const lw = cv.clientWidth, lh = cv.clientHeight;
      if (!lw || !lh) return;
      const vz = cv.getBoundingClientRect().width / lw || 1;
      dpr = Math.max(0.5, Math.min(DPR * vz, Math.sqrt(FACE_MAXPX / (lw * lh)))); w = lw; h = lh;
      const host = cv.closest('.bx2');
      if (host) {
        const cs = getComputedStyle(host);
        refW = host.clientWidth - (parseFloat(cs.getPropertyValue('--rail')) || 0) - (host.classList.contains('narrow') ? 0 : parseFloat(cs.getPropertyValue('--chatfull')) || 0);
      }
      const bw = Math.round(w * dpr), bh = Math.round(h * dpr);
      if (cv.width !== bw || cv.height !== bh) { cv.width = bw; cv.height = bh; }
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0); dirty = true; cache.key = '';
    };
    let sizeQ = 0;
    const sizeSoon = () => { if (!sizeQ) sizeQ = requestAnimationFrame(() => { sizeQ = 0; size(); }); };
    const onVis = () => { if (!document.hidden) size(); };
    size();
    const ro = new ResizeObserver(sizeSoon); ro.observe(cv);
    window.addEventListener('resize', sizeSoon); window.addEventListener('bx-scale', size); document.addEventListener('visibilitychange', onVis);

    const explode = (groups: string[], power: number, from?: Pt) => groups.forEach((g) => G[g].pts.forEach((p) => {
      if (from) { p.x = from[0] + (Math.random() - 0.5) * 0.05; p.y = from[1] + (Math.random() - 0.5) * 0.05; }
      const a = Math.random() * 6.283, m = power * (0.4 + Math.random() * 0.8); p.vx += Math.cos(a) * m; p.vy += Math.sin(a) * m;
    }));
    const center = (g: string): Pt => { const pts = G[g].pts; let x = 0, y = 0; for (const p of pts) { x += p.x; y += p.y; } return [x / pts.length, y / pts.length]; };
    const burstFeature = (g: string, power: number) => {
      const c = center(g);
      G[g].pts.forEach((p) => { const dx = p.x - c[0], dy = p.y - c[1], d = Math.hypot(dx, dy) || 1, m = power * (0.6 + Math.random() * 0.8); p.vx += (dx / d) * m + (Math.random() - 0.5) * power * 0.5; p.vy += (dy / d) * m + (Math.random() - 0.5) * power * 0.5; });
      flashes.push({ x: c[0], y: c[1], t: 0 });
    };
    explode(Object.keys(G), 4.5, [0, -0.15]);

    const bulbPos = (): Pt => [Math.sin(ant * 0.14) * 0.36, -0.84 - Math.cos(ant * 0.14) * 0.36];
    const NP = (i: number): Pt => (i === BXM.hub.web ? bulbPos() : [BXM.N[i].x, BXM.N[i].y]);
    const mkTracer = (nodes: number[], dur: number, T: number): Tracer => {
      const L = [0];
      for (let i = 1; i < nodes.length; i++) { const a = BXM.N[nodes[i - 1]], b = BXM.N[nodes[i]]; L.push(L[i - 1] + Math.hypot(a.x - b.x, a.y - b.y)); }
      return { nodes, L, total: L[L.length - 1] || 1, t0: T, dur, u: 0 };
    };
    const trAt = (tr: Tracer, u: number) => {
      const e = u < 0.5 ? 2 * u * u : 1 - Math.pow(-2 * u + 2, 2) / 2, d = e * tr.total;
      let i = 1; while (i < tr.L.length - 1 && tr.L[i] < d) i++;
      const s = tr.L[i] - tr.L[i - 1] || 1, k = (d - tr.L[i - 1]) / s, A = NP(tr.nodes[i - 1]), B = NP(tr.nodes[i]);
      return { x: A[0] + (B[0] - A[0]) * k, y: A[1] + (B[1] - A[1]) * k, i, k };
    };
    const spark = (from: number, hops: number, sp: number) => {
      const nb = BXM.adj[from].filter((v) => !BXM.N[v].hub || v === BXM.hub.mente);
      if (!nb.length) return;
      sparks.push({ a: from, b: nb[Math.floor(Math.random() * nb.length)], u: 0, hops, sp, tail: [] });
    };

    let X = (x: number) => x, Y = (y: number) => y, rimG = 0;
    const fillDots = (arr: Particle[], r: number, style: string, g: CanvasRenderingContext2D = ctx) => {
      g.fillStyle = style; g.beginPath();
      for (const p of arr) { const x = X(p.x), y = Y(p.y), rr = p.big ? r * 1.5 : r; g.moveTo(x + rr, y); g.arc(x, y, rr, 0, 6.283); }
      g.fill();
    };
    const pathOf = (pts: Particle[], closed: boolean, g: CanvasRenderingContext2D = ctx) => {
      g.beginPath(); pts.forEach((p, i) => (i ? g.lineTo(X(p.x), Y(p.y)) : g.moveTo(X(p.x), Y(p.y)))); if (closed) g.closePath();
    };

    const tick = (now: number) => {
      raf = requestAnimationFrame(tick);
      const { state, expr, talking, journey, hold, light, net } = P.current;
      const ADD: GlobalCompositeOperation = light ? 'source-over' : 'lighter';
      const calm = state === 'standby' || ((state === 'idle' || state === 'confirm') && !trs.some((tr) => tr.u < 1) && !fx.length && !flashes.length);
      if (!dirty && (now - last) / 1000 < (state === 'standby' ? 0.048 : calm ? 0.031 : 0)) return;
      dirty = false;
      if (!w || !h || (cv.width === 300 && cv.height === 150)) { size(); if (!w || !h) return; }
      const dt = Math.min(0.1, (now - last) / 1000); last = now;
      const T = now / 1000;
      const pal = (light ? PAL_L : PAL)[state] ?? PAL.idle;
      (['f', 'l', 'p'] as const).forEach((k) => { const t = hex(pal[k]); col[k] = col[k].map((v, i) => v + (t[i] - v) * Math.min(1, dt * 3)) as RGB; });
      const TRC = light ? 'rgba(' + (col.p[0] | 0) + ',' + (col.p[1] | 0) + ',' + (col.p[2] | 0) + ',' : 'rgba(255,246,224,';
      vis += ((state === 'standby' ? 0.5 : 1) - vis) * Math.min(1, dt * 2);
      if (prevState === 'standby' && state !== 'standby') { explode(Object.keys(G), 3.2); boot = T - 0.3; }
      // journey through the mesh: a new turn starts a new walk; each new family of the same turn adds a segment after
      // the one walking now.
      if (journey && journey.turn !== jTurn) {
        jTurn = journey.turn; jLen = journey.path.length; heat.fill(0); trail = 1;
        trs = journey.path.length > 1 ? [mkTracer(bxRoute(journey.path), Math.max(1.2, 0.9 * (journey.path.length - 1)), T)] : [];
      } else if (journey && journey.path.length > jLen) {
        const seg = journey.path.slice(Math.max(0, jLen - 1));
        jLen = journey.path.length; trail = 1;
        const lastTr = trs[trs.length - 1];
        trs.push(mkTracer(bxRoute(seg), Math.max(0.9, 0.9 * (seg.length - 1)), lastTr ? Math.max(T, lastTr.t0 + lastTr.dur) : T));
      }
      if (state === 'speaking' && prevState !== 'speaking') { trs.forEach((tr) => { tr.t0 = T - tr.dur; }); trs.push(mkTracer([BXM.hub.verificar, BXM.hub.voz], 0.7, T + 0.05)); trail = 1; }
      prevState = state;
      if (talking) {
        // the mouth opens with the voice's loudness at this instant (lip.ts); a host without that timeline babbles
        const lip = lipAt();
        if (lip.known) talkT = lip.level;
        else { talkTimer -= dt; if (talkTimer <= 0) { talkT = Math.random() < 0.18 ? 0.05 : 0.25 + Math.random() * 0.75; talkTimer = 0.07 + Math.random() * 0.1; } }
        talk += (talkT - talk) * Math.min(1, dt * 22);
      }
      const key = expr + (talking ? '|t' : '');
      if (key !== lastKey) { if (lastKey && !talking) { ['eyeL', 'eyeR', 'mouth'].forEach((g) => burstFeature(g, 1.5)); bounceV += 3; antV += (Math.random() < 0.5 ? -1 : 1) * 6; } lastKey = key; }
      // mood entry reactions
      if (expr !== prevExpr) {
        if (expr === 'happy') { confetti(34); hopV -= 2.6; sqV += 2; }
        if (expr === 'sad') { fx.push({ k: 'drop', x: 0.8, y: -0.48, vx: 0, vy: 0.18, t: 0, life: 1.8 }); sqV -= 1.2; }
        if (expr === 'wink') for (let q = 0; q < 2; q++) fx.push({ k: 'star', x: 0.62 + q * 0.16, y: -0.42 + q * 0.12, vx: 0, vy: 0, t: -q * 0.15, life: 0.9 });
        if (expr === 'serious') { antV += 8; sqV -= 1.5; }
        if (expr === 'curious') { hopV -= 1.2; }
        prevExpr = expr;
      }
      // idle behaviours
      const mouseLive = T - lastMouseT < 2.5;
      if (state === 'idle' && expr === 'neutral' && !act) {
        nextAct -= dt;
        if (nextAct <= 0) {
          const pool = Object.keys(IDLE).filter((k) => !lastActs.includes(k) && !(mouseLive && (k === 'look' || k === 'chat' || k === 'peek')));
          const name = pick(pool);
          act = { name, t0: T, dur: IDLE[name], s: Math.random() < 0.5 ? -1 : 1, fired: 0 };
          lastActs = [name, ...lastActs].slice(0, 3); nextAct = 2.8 + Math.random() * 4.2;
          if (name === 'antenna') antV += 9 * act.s;
          if (name === 'dblink' || name === 'shake') blinkT = 0;
          if (name === 'hop') { hopV -= 2.2; sqV += 1.6; }
        }
      }
      if (act && (T - act.t0 > act.dur || state !== 'idle' || expr !== 'neutral')) act = null;
      const au = act ? (T - act.t0) / act.dur : 0, aenv = Math.sin(Math.PI * Math.min(1, au));
      if (act && act.name === 'dblink' && !act.fired && au > 0.45) { act.fired = 1; blinkT = 0; }
      if (act && act.name === 'hum' && Math.random() < dt * 2.4) fx.push({ k: 'note', x: 0.16, y: 0.36, vx: 0.22 + Math.random() * 0.1, vy: -0.42, t: 0, life: 1.6, ph: Math.random() * 6 });
      if (act && act.name === 'antenna' && !act.fired && au > 0.15) { act.fired = 1; spark(BXM.hub.mente, 6, 3); spark(BXM.hub.mente, 6, 3); }
      // thinking variants
      if (state === 'thinking') { thinkT -= dt; if (thinkT <= 0 || !thinkV) { thinkV = pick(THINK.filter((v) => v !== thinkV)); thinkT = 1.5 + Math.random() * 0.8; } } else thinkV = null;
      // speaking gestures
      if (talking) {
        nextGest -= dt;
        if (nextGest <= 0) {
          const g = pick(TALK.filter((x) => !gest || x !== gest.name));
          gest = { name: g, t0: T, dur: g === 'lean' ? 1.2 : 0.55 }; nextGest = 0.7 + Math.random() * 0.9;
          if (g === 'blink') blinkT = 0; if (g === 'nod') sqV += 1.2; if (g === 'tilt') leanS = -leanS;
        }
      } else gest = null;
      if (gest && T - gest.t0 > gest.dur) gest = null;
      const gu = gest ? (T - gest.t0) / gest.dur : 0, genv = Math.sin(Math.PI * Math.min(1, gu));
      if (state === 'listening' && !wasListen) leanS = Math.random() < 0.5 ? -1 : 1;
      wasListen = state === 'listening';
      // expression override from behaviours
      let ex = expr;
      if (act) { const nm = act.name; if (nm === 'yawn' && au > 0.12 && au < 0.82) ex = 'yawn'; if (nm === 'stretch' && au > 0.25 && au < 0.75) ex = 'yawn'; if (nm === 'hum') ex = 'hum'; if (nm === 'wink' && au < 0.75) ex = 'wink'; if (nm === 'tiltq') ex = 'curious'; if (nm === 'peek' && au > 0.2 && au < 0.8) ex = 'wide'; }
      if (thinkV === 'squint') ex = 'squint';
      if (gest && gest.name === 'smile' && expr === 'neutral') ex = 'hum';
      const round = ['neutral', 'listen', 'think', 'curious', 'wide'].includes(ex) && state !== 'standby';
      nextBlink -= dt;
      if (round && nextBlink <= 0 && blinkT < 0) { blinkT = 0; nextBlink = 2.4 + Math.random() * 3.5; if (Math.random() < 0.2) nextBlink = 0.32; }
      if (blinkT >= 0) { blinkT += dt; const u = blinkT / 0.16; blink = u < 0.5 ? 1 - u * 1.86 : 0.07 + (u - 0.5) * 1.86; if (u >= 1) { blinkT = -1; blink = 1; } }
      let tgx = 0, tgy = 0, xtilt = 0, xlift = 0, ycy = 0;
      if (state === 'thinking') {
        if (thinkV === 'up') { tgx = -0.05; tgy = -0.08; xlift = 0.02; }
        else if (thinkV === 'roll') { tgx = Math.cos(T * 5) * 0.055; tgy = Math.sin(T * 5) * 0.045 - 0.02; }
        else if (thinkV === 'scan') { tgx = Math.sin(T * 6.5) * 0.07; tgy = -0.01; }
        else if (thinkV === 'bubble') { tgx = 0.06; tgy = -0.07; xtilt = -0.04; }
        else { tgx = Math.sin(T * 0.7) * 0.02; tgy = 0.01; }
      } else if (act) {
        const nm = act.name;
        if (nm === 'look') { tgx = Math.sin(au * 6.283) * 0.08; tgy = -0.01; }
        if (nm === 'chat') { tgx = 0.085 * aenv; tgy = 0.015 * aenv; xtilt = 0.035 * aenv; xlift = 0.02 * aenv; }
        if (nm === 'peek') { tgx = act.s * 0.09 * aenv; tgy = 0.04 * aenv; xtilt = act.s * 0.05 * aenv; }
        if (nm === 'scan') { tgy = (au - 0.5) * 0.12; }
        if (nm === 'yawn') { xtilt = -0.05 * aenv; xlift = 0.03 * aenv; }
        if (nm === 'stretch') { xlift = 0.04 * aenv; }
        if (nm === 'tiltq') { xtilt = act.s * 0.1 * aenv; }
        if (nm === 'hum') { xtilt = Math.sin(au * 12.56) * 0.045; ycy = -Math.abs(Math.sin(au * 12.56)) * 0.012; }
        if (nm === 'shake') { xtilt = Math.sin(au * 25) * 0.06 * (1 - au); }
      } else if (mouse && mouseLive && state !== 'standby') {
        tgx = Math.max(-1, Math.min(1, (mouse[0] - 0.5) * 2)) * 0.06; tgy = Math.max(-1, Math.min(1, (mouse[1] - 0.4) * 2)) * 0.045;
      }
      if (state === 'listening') { tgy = -0.01; xtilt += leanS * 0.02; ycy += Math.sin(T * 3.4) * 0.01 * lvl; xlift += lvl * 0.025; }
      if (gest) { const nm = gest.name; if (nm === 'brow') xlift += 0.05 * genv; if (nm === 'nod') ycy += 0.02 * genv; if (nm === 'tilt') xtilt += leanS * 0.05 * genv; if (nm === 'lean') { xtilt += leanS * 0.04 * genv; tgx = leanS * 0.04 * genv; } }
      browLift += (xlift - browLift) * Math.min(1, dt * 10);
      droopY += ((expr === 'sad' ? 0.035 : state === 'standby' ? 0.02 : 0) - droopY) * Math.min(1, dt * 3);
      gx += (tgx - gx) * Math.min(1, dt * 5); gy += (tgy - gy) * Math.min(1, dt * 5);
      tilt += ((TILT[ex] || 0) + xtilt + (state === 'listening' ? leanS * (0.04 + Math.sin(T * 1.3) * 0.01) : 0) + (state === 'speaking' ? Math.sin(T * 2.1) * 0.014 : 0) - tilt) * Math.min(1, dt * 3);
      for (let s = 0, n = Math.max(1, Math.ceil(dt / 0.008)), q = dt / n; s < n; s++) {
        antV += (-ant * 90 - antV * 5 + (talking ? Math.sin(T * 9) * 7 : 0)) * q; ant += antV * q;
        bounceV += (-bounce * 160 - bounceV * 9) * q; bounce += bounceV * q;
        hopV += (-hop * 120 - hopV * 7) * q; hop += hopV * q;
        sqV += (-sq * 140 - sqV * 8) * q; sq += sqV * q;
      }
      earGlow += ((state === 'listening' ? 1 : state === 'speaking' ? 0.5 : 0.18) - earGlow) * Math.min(1, dt * 4);
      earL2 += ((state === 'listening' ? 1 : 0) - earL2) * Math.min(1, dt * 5);
      lvl += ((state === 'listening' ? 0.25 + Math.random() * 0.75 : 0) - lvl) * Math.min(1, dt * 16);
      // targets
      const droop = state === 'standby' ? 0.03 : 0;
      const setT = (g: string, s: Pt[]) => { const pts = G[g].pts; for (let i = 0; i < pts.length; i++) { pts[i].tx = s[i][0]; pts[i].ty = s[i][1] + (/^(body|plate)/.test(g) ? 0 : droop); } };
      for (const k in STATIC) setT(k, STATIC[k]);
      if (earL2 > 0.01) { const k = 1 + lvl * 0.7 * earL2; setT('inL', bxEll(-1.07, 0.03, 0.055 * k, 0.12 * k, 10)); setT('inR', bxEll(1.07, 0.03, 0.055 * k, 0.12 * k, 10)); }
      const bp = bulbPos();
      setT('stem', bxSample([[0, -0.84], [bp[0] * 0.85, bp[1] + 0.08]], 6, false)); setT('bulb', bxEll(bp[0], bp[1], 0.075, 0.075, 12));
      ['browL', 'browR'].forEach((g, i) => { const s = i ? 1 : -1, d = (1 - blink) * 0.025; setT(g, bxBrow(ex, s, browLift - d).map(([x, y]): Pt => [x * FK + gx * 0.8, y * FK + FY + gy * 0.7])); });
      ([['eyeL', bxEye(ex, -1)], ['eyeR', bxEye(ex, 1)], ['mouth', bxMouth(ex, talking ? talk : -1)]] as [string, [Pt[], number]][]).forEach(([g, [pts, cl]]) => {
        const m = g === 'mouth';
        let s = pts.map(([x, y]): Pt => [x * FK + (m ? gx * 0.5 : gx), y * FK + FY + (m ? gy * 0.4 : gy)]);
        if (!m && round) { const cy = s.reduce((a, p) => a + p[1], 0) / s.length; s = s.map(([x, y]): Pt => [x, cy + (y - cy) * blink]); }
        setT(g, bxSample(s, G[g].pts.length, !!cl)); G[g].closedT = cl;
      });
      // physics (sub-stepped)
      const ramp = Math.min(1, Math.max(0.08, (T - boot) / 1.3)), streaks: Particle[] = [];
      const subs = Math.max(1, Math.ceil(dt / 0.008)), h2 = dt / subs;
      for (const g of Object.values(G)) {
        const k = g.k * (g.kind === 'f' && talking ? 2.4 : 1) * ramp, d = Math.exp(-(g.kind === 'f' ? 11 : 7.5) * h2);
        for (const p of g.pts) {
          for (let s = 0; s < subs; s++) { p.vx = (p.vx + (p.tx - p.x) * k * h2) * d; p.vy = (p.vy + (p.ty - p.y) * k * h2) * d; p.x += p.vx * h2; p.y += p.vy * h2; }
          const v2 = p.vx * p.vx + p.vy * p.vy; if (v2 > 0.5 && v2 < 60) streaks.push(p);
        }
        g.closed += (g.closedT - g.closed) * Math.min(1, dt * 8);
      }
      // ambient sparks wander the mesh
      if (Math.random() < (RATE[state] || 0) * dt * ramp && sparks.length < 18) {
        const H = BXM.hub;
        const src = state === 'listening' ? [H.memoria, H.musica, H.verificar][Math.floor(Math.random() * 3)]
          : state === 'thinking' ? (Math.random() < 0.5 ? H.mente : BXM.ring[Math.floor(Math.random() * BXM.ring.length)])
            : BXM.ring[Math.floor(Math.random() * BXM.ring.length)];
        spark(src, 3 + Math.floor(Math.random() * 5), 2.2 + Math.random() * 1.8);
      }
      trail = state === 'thinking' || state === 'speaking' || hold ? Math.min(1, trail + dt * 3) : Math.max(0, trail - dt * 0.2);
      if (trail <= 0 && trs.length && trs.every((tr) => tr.done)) trs = [];
      for (let i = 0; i < heat.length; i++) heat[i] = Math.max(0, heat[i] - dt * 0.7);

      // ---- draw ----
      ctx.clearRect(0, 0, w, h);
      const OV = !!P.current.overlay;
      const NOC = () => { if (OV) { ctx.save(); ctx.beginPath(); ctx.rect(0, 0, 0, 0); ctx.clip(); } }, NOR = () => { if (OV) ctx.restore(); };
      const S =Math.max(1, Math.min((refW > 40 ? Math.min(w, refW) : w) / 3.0, (h - 10) / 2.7)), cx = w / 2, cy = 14 + 1.3 * S + Math.sin(T * 0.9) * S * 0.016 * (state === 'standby' ? 0.4 : 1);
      let stx = 0, sty = 0;
      if (act && act.name === 'stretch') { sty = 0.06 * aenv; stx = -0.03 * aenv; }
      if (act && act.name === 'yawn') sty = 0.03 * aenv;
      if (OV) {
        const cy0 = 14 + 1.3 * S, hostEl = cv.parentElement, gk = Math.round(cx) + ',' + Math.round(cy0) + ',' + Math.round(S);
        if (hostEl && hostEl.dataset.avg !== gk) { hostEl.dataset.avg = gk; hostEl.style.setProperty('--av-x', cx + 'px'); hostEl.style.setProperty('--av-y', cy0 + 'px'); hostEl.style.setProperty('--av-s', S + 'px'); }
        ctx.save(); ctx.translate(cx, cy0);
      } else {
        ctx.save(); ctx.translate(cx, cy + (hop * 0.12 + ycy + droopY) * S); ctx.rotate(tilt); ctx.scale(1 + bounce * 0.05 - sq * 0.04 + stx, 1 - bounce * 0.05 + sq * 0.05 + sty);
      }
      X = (x) => x * S; Y = (y) => y * S;
      const sh = 0.5 + 0.5 * Math.sin(T * 2);
      for (const d of dust) d.a += d.sp * dt * (state === 'thinking' ? 3 : 1);
      [true, false].forEach((odd) => {
        ctx.fillStyle = rgba(col.l, (odd ? 0.15 + 0.25 * sh : 0.4 - 0.25 * sh) * vis); ctx.beginPath();
        for (const d of dust) { if (d.odd !== odd) continue; const x = X(Math.cos(d.a) * d.r), y = Y(Math.sin(d.a) * d.r * d.yk - 0.05); ctx.moveTo(x + 1, y); ctx.arc(x, y, 1, 0, 6.283); }
        ctx.fill();
      });
      const mA = ramp * vis;
      const settle = (g: string) => { let e = 0; for (const p of G[g].pts) e += Math.abs(p.tx - p.x) + Math.abs(p.ty - p.y); return Math.max(0, 1 - (e / G[g].pts.length) * 6); };
      const SG = ['shell', 'visor', 'earL', 'earR', 'bodyL', 'bodyR', 'plate'];
      let still = ramp >= 1;
      if (still) outer: for (const g of SG) for (const p of G[g].pts) if (Math.abs(p.tx - p.x) + Math.abs(p.ty - p.y) > 0.0015 || Math.abs(p.vx) + Math.abs(p.vy) > 0.012) { still = false; break outer; }
      const structOf = () => { const a: Particle[] = []; for (const g of SG) for (const p of G[g].pts) a.push(p); return a; };
      // static layer: helmet, visor, mesh, contours, particles — painted once into offscreen bitmaps while still
      const paintBase = (g: CanvasRenderingContext2D) => {
        const hg = g.createRadialGradient(0, -S * 0.25, S * 0.1, 0, 0, S * 1.15);
        hg.addColorStop(0, rgba(col.l, 0.12 * vis)); hg.addColorStop(1, rgba(col.l, 0));
        g.fillStyle = hg; pathOf(G.shell.pts, true, g); g.fill();
        g.fillStyle = 'rgba(6,9,14,' + ((light ? 0.92 : 0.62) * vis).toFixed(3) + ')'; pathOf(G.visor.pts, true, g); g.fill();
        { // dotted visor texture and dotted ears
          const st = Math.max(3, S * 0.026), d = Math.max(0.9, S * 0.0055);
          g.save(); pathOf(G.visor.pts, true, g); g.clip(); g.fillStyle = rgba(col.l, 0.2 * vis); g.beginPath();
          for (let y = Y(-0.6); y < Y(0.7); y += st) for (let x = X(-0.85); x < X(0.85); x += st) g.rect(x - d / 2, y - d / 2, d, d);
          g.fill(); g.restore();
          g.fillStyle = rgba(col.l, 0.55 * vis); g.beginPath();
          for (const s of [-1, 1]) for (let yy = -0.28; yy <= 0.34; yy += 0.045) for (let xx = 0.02; xx <= 0.17; xx += 0.04) {
            if ((xx * xx) / 0.0289 + ((yy - 0.03) * (yy - 0.03)) / 0.0961 > 1) continue;
            const x = X(s * (1.0 + xx)), y = Y(yy); g.rect(x - d * 0.7, y - d * 0.7, d * 1.4, d * 1.4);
          }
          g.fill();
        }
        g.lineWidth = 0.8; g.strokeStyle = rgba(col.l, 0.26 * mA); g.beginPath();
        for (const [i, j] of BXM.E) { const a = NP(i), b = NP(j); g.moveTo(X(a[0]), Y(a[1])); g.lineTo(X(b[0]), Y(b[1])); }
        g.stroke();
        g.globalCompositeOperation = ADD;
        SG.forEach((k) => { const s = settle(k); if (s < 0.02) return; g.lineWidth = 1; g.strokeStyle = rgba(col.l, (k === 'visor' ? 0.2 : 0.28) * vis * s); pathOf(G[k].pts, G[k].closed > 0.5, g); g.stroke(); });
        fillDots(structOf().filter((_, i) => i % 3 === 0), 3.4, rgba(col.l, 0.12 * vis), g);
        g.globalCompositeOperation = 'source-over';
      };
      const paintDots = (g: CanvasRenderingContext2D, b: number, aS: number, aN: number) => {
        g.globalCompositeOperation = ADD;
        fillDots(structOf().filter((_, i) => i % 2 === b), 1.4, rgba(col.l, aS * vis), g);
        g.fillStyle = rgba(col.l, aN * mA); g.beginPath();
        for (const i of BXM.ring) { if (i % 2 !== b) continue; const n = BXM.N[i], x = X(n.x), y = Y(n.y); g.moveTo(x + 1.5, y); g.arc(x, y, 1.5, 0, 6.283); }
        g.fill();
        g.globalCompositeOperation = 'source-over';
      };
      const OX = 1.45 * S, OY = 1.0 * S, CW = 2.9 * S, CH = 2.7 * S;
      NOC();
      if (still) {
        const ck = [Math.round(S), Math.round(dpr * 100), light ? 1 : 0, col.l.map((v) => v | 0).join(','), Math.round(vis * 40), Math.round(mA * 40), Math.round(G.shell.pts[0].y * 1000), Math.round(G.visor.pts[0].y * 1000)].join('|');
        if (cache.key !== ck) {
          const pw = Math.ceil(CW * dpr), ph = Math.ceil(CH * dpr);
          cache.c.forEach((cv2, k) => {
            if (cv2.width !== pw || cv2.height !== ph) { cv2.width = pw; cv2.height = ph; }
            const g = cv2.getContext('2d')!;
            g.setTransform(1, 0, 0, 1, 0, 0); g.clearRect(0, 0, pw, ph); g.setTransform(dpr, 0, 0, dpr, OX * dpr, OY * dpr);
            if (k === 0) paintBase(g); else paintDots(g, k - 1, 1, 0.78);
          });
          cache.key = ck;
        }
        ctx.drawImage(cache.c[0], -OX, -OY, CW, CH);
        const op = ctx.globalCompositeOperation; ctx.globalCompositeOperation = ADD;
        ctx.globalAlpha = 0.95 - 0.3 * sh; ctx.drawImage(cache.c[1], -OX, -OY, CW, CH);
        ctx.globalAlpha = 0.65 + 0.3 * sh; ctx.drawImage(cache.c[2], -OX, -OY, CW, CH);
        ctx.globalAlpha = 1; ctx.globalCompositeOperation = op;
      } else {
        cache.key = '';
        paintBase(ctx); paintDots(ctx, 0, 0.95 - 0.3 * sh, 0.8 - 0.35 * sh); paintDots(ctx, 1, 0.65 + 0.3 * sh, 0.45 + 0.35 * sh);
      }
      NOR();
      // journey trail — the exact path BAXY walked this turn
      if (trail > 0.01 && trs.length) {
        const jp = () => {
          ctx.beginPath();
          for (const tr of trs) {
            const u = Math.min(1, Math.max(0, tr.u)); if (u <= 0) continue;
            const hd = trAt(tr, u), A = NP(tr.nodes[0]);
            ctx.moveTo(X(A[0]), Y(A[1]));
            for (let i = 1; i < hd.i; i++) { const p = NP(tr.nodes[i]); ctx.lineTo(X(p[0]), Y(p[1])); }
            ctx.lineTo(X(hd.x), Y(hd.y));
          }
        };
        ctx.lineCap = 'round'; ctx.lineJoin = 'round'; jp();
        ctx.strokeStyle = rgba(col.p, 0.16 * trail * vis); ctx.lineWidth = 7; ctx.stroke();
        ctx.setLineDash([5, 6]); ctx.lineDashOffset = -T * 34; ctx.strokeStyle = rgba(col.p, 0.95 * trail * vis); ctx.lineWidth = 2; ctx.stroke(); ctx.setLineDash([]); ctx.lineDashOffset = 0;
      }
      ctx.globalCompositeOperation = ADD;
      NOC();
      // antenna stem (moves, always live)
      { const s = settle('stem'); if (s > 0.02) { ctx.lineWidth = 1; ctx.strokeStyle = rgba(col.l, 0.28 * vis * s); pathOf(G.stem.pts, false); ctx.stroke(); } fillDots(G.stem.pts, 1.4, rgba(col.l, 0.85 * vis)); }
      if (streaks.length) { ctx.strokeStyle = rgba(col.p, 0.35 * vis); ctx.lineWidth = 1.1; ctx.beginPath(); for (const p of streaks) { ctx.moveTo(X(p.x - p.vx * 0.045), Y(p.y - p.vy * 0.045)); ctx.lineTo(X(p.x), Y(p.y)); } ctx.stroke(); }
      ctx.beginPath();
      let hot = false;
      for (const i of BXM.ring) { if (heat[i] < 0.05) continue; hot = true; const n = BXM.N[i], x = X(n.x), y = Y(n.y), r = 1.6 + heat[i] * 2.4; ctx.moveTo(x + r, y); ctx.arc(x, y, r, 0, 6.283); }
      if (hot) { ctx.fillStyle = rgba(col.p, 0.85 * vis); ctx.fill(); }
      const ears = [...G.inL.pts, ...G.inR.pts];
      fillDots(ears, 4, rgba(col.f, 0.12 * earGlow * vis)); fillDots(ears, 1.4, rgba(col.f, (0.35 + earGlow * 0.6) * vis));
      if (earL2 > 0.02) {
        ctx.fillStyle = rgba(col.f, vis);
        for (const s of [-1, 1]) for (let k = 0; k < 4; k++) {
          const ph = (T * 1.1 + k / 4) % 1, r = 0.5 - ph * 0.34, a0 = s > 0 ? 0 : Math.PI, al = Math.sin(ph * Math.PI) * 0.8 * earL2 * (0.6 + lvl * 0.4);
          ctx.globalAlpha = al; ctx.beginPath();
          for (let q = 0; q <= 8; q++) { const a = a0 - 0.75 + (q / 8) * 1.5, x = X(1.07 * s + Math.cos(a) * r), y = Y(0.03 + Math.sin(a) * r * 1.25), rr = q === 4 ? 2 : 1.4; ctx.moveTo(x + rr, y); ctx.arc(x, y, rr, 0, 6.283); }
          ctx.fill();
        }
        ctx.globalAlpha = 1;
      }
      // antenna bulb = the «web» node
      {
        const hc = heat[BXM.hub.web], g = ctx.createRadialGradient(X(bp[0]), Y(bp[1]), 0, X(bp[0]), Y(bp[1]), S * 0.2);
        g.addColorStop(0, rgba(col.f, (0.4 + 0.25 * Math.sin(T * (state === 'thinking' ? 7 : 2)) + hc * 0.35) * vis)); g.addColorStop(1, rgba(col.f, 0));
        ctx.fillStyle = g; ctx.beginPath(); ctx.arc(X(bp[0]), Y(bp[1]), S * 0.2, 0, 6.283); ctx.fill();
      }
      fillDots(G.bulb.pts, 1.7, rgba(col.p, 0.95 * vis));
      if (net) { ctx.strokeStyle = rgba(col.f, vis); ctx.lineWidth = 1.4; for (let q = 0; q < 3; q++) { const u = (T * 0.8 + q / 3) % 1; ctx.globalAlpha = (1 - u) * 0.8; ctx.beginPath(); ctx.arc(X(bp[0]), Y(bp[1]), S * (0.1 + u * 0.32), Math.PI * 1.05, Math.PI * 1.95); ctx.stroke(); } ctx.globalAlpha = 1; }
      NOR();
      // hubs: hidden until the signal goes through them
      ['mente', 'apps', 'ventanas', 'memoria', 'musica', 'archivos', 'alarmas', 'verificar'].forEach((k) => {
        const i = BXM.hub[k], n = BXM.N[i], v = heat[i];
        if (v < 0.05) return;
        const ha = Math.min(1, v * 2);
        if (v > 0.02) { const r = S * 0.17, g = ctx.createRadialGradient(X(n.x), Y(n.y), 0, X(n.x), Y(n.y), r); g.addColorStop(0, rgba(col.p, 0.45 * v * vis)); g.addColorStop(1, rgba(col.l, 0)); ctx.fillStyle = g; ctx.beginPath(); ctx.arc(X(n.x), Y(n.y), r, 0, 6.283); ctx.fill(); }
        ctx.fillStyle = rgba(v > 0.2 ? col.p : col.l, (0.7 + v * 0.3) * vis * ha); ctx.beginPath(); ctx.arc(X(n.x), Y(n.y), 3.2, 0, 6.283); ctx.fill();
        ctx.fillStyle = rgba(col.p, 0.9 * vis * ha); ctx.beginPath(); ctx.arc(X(n.x), Y(n.y), 1.3, 0, 6.283); ctx.fill();
      });
      // a family whose call failed is marked with a red ✕
      if (journey && journey.fail && trail > 0.02 && BXM.hub[journey.fail] != null) {
        const n = BXM.N[BXM.hub[journey.fail]], x = X(n.x), y = Y(n.y), pu = 0.5 + 0.5 * Math.sin(T * 6), r = 9 + pu * 3;
        ctx.globalCompositeOperation = 'source-over'; ctx.strokeStyle = 'rgba(255,77,94,' + (0.9 * trail * vis).toFixed(3) + ')'; ctx.lineWidth = 2;
        ctx.beginPath(); ctx.arc(x, y, r, 0, 6.283); ctx.stroke();
        ctx.beginPath(); ctx.moveTo(x - 4, y - 4); ctx.lineTo(x + 4, y + 4); ctx.moveTo(x + 4, y - 4); ctx.lineTo(x - 4, y + 4); ctx.stroke();
        ctx.globalCompositeOperation = ADD;
      }
      // chest core (the «voz» node) beats with the state
      NOC();
      {
        const bpm = state === 'speaking' ? 2.4 : state === 'thinking' ? 1.8 : state === 'listening' ? 1.4 : state === 'standby' ? 0.5 : 1.0;
        const ph = (T * bpm) % 1, beat = Math.exp(-ph * 9) + 0.55 * Math.exp(-Math.max(0, ph - 0.18) * 11) * (ph > 0.18 ? 1 : 0);
        const v = (state === 'standby' ? 0.35 : 0.7) + beat * 0.45, ccx = 0, ccy = Y(1.25), R = S * 0.13;
        const g = ctx.createRadialGradient(ccx, ccy, 0, ccx, ccy, R * 2.6);
        g.addColorStop(0, rgba(col.f, 0.5 * v * vis)); g.addColorStop(0.45, rgba(col.f, 0.14 * v * vis)); g.addColorStop(1, rgba(col.f, 0));
        ctx.fillStyle = g; ctx.beginPath(); ctx.arc(ccx, ccy, R * 2.6, 0, 6.283); ctx.fill();
        const spin = T * (state === 'thinking' ? 1.6 : 0.5);
        ctx.lineCap = 'round'; ctx.lineWidth = 1.6; ctx.strokeStyle = rgba(col.f, 0.8 * vis);
        ctx.beginPath(); for (let q = 0; q < 6; q++) { const a = spin + q * 1.0472; ctx.moveTo(ccx + Math.cos(a + 0.12) * R * 0.92, ccy + Math.sin(a + 0.12) * R * 0.92); ctx.arc(ccx, ccy, R * 0.92, a + 0.12, a + 0.86); } ctx.stroke();
        ctx.fillStyle = rgba(col.p, (0.55 + beat * 0.45) * vis); ctx.beginPath();
        for (let q = 0; q < 8; q++) { const a = -spin * 1.4 + q * 0.7854, x = ccx + Math.cos(a) * R * 0.6, y = ccy + Math.sin(a) * R * 0.6; ctx.moveTo(x + 1.5, y); ctx.arc(x, y, 1.5, 0, 6.283); } ctx.fill();
        ctx.lineWidth = 1; ctx.strokeStyle = rgba(col.p, 0.55 * vis); ctx.beginPath();
        for (let q = 0; q < 6; q++) { const a = q * 1.0472 + 0.5236, x = ccx + Math.cos(a) * R * 0.3, y = ccy + Math.sin(a) * R * 0.3; if (q) ctx.lineTo(x, y); else ctx.moveTo(x, y); }
        ctx.closePath();
        for (let q = 0; q < 6; q++) { const a = q * 1.0472 + 0.5236; ctx.moveTo(ccx + Math.cos(a) * R * 0.3, ccy + Math.sin(a) * R * 0.3); ctx.lineTo(ccx + Math.cos(a) * R * 0.5, ccy + Math.sin(a) * R * 0.5); }
        ctx.stroke();
        const cg = ctx.createRadialGradient(ccx, ccy, 0, ccx, ccy, R * 0.36);
        cg.addColorStop(0, 'rgba(255,250,240,' + (0.95 * vis).toFixed(3) + ')'); cg.addColorStop(0.5, rgba(col.p, 0.8 * v * vis)); cg.addColorStop(1, rgba(col.f, 0));
        ctx.fillStyle = cg; ctx.beginPath(); ctx.arc(ccx, ccy, R * (0.3 + beat * 0.08), 0, 6.283); ctx.fill();
        if (state !== 'standby') { ctx.strokeStyle = rgba(col.f, 0.4 * (1 - ph) * vis); ctx.lineWidth = 1; ctx.beginPath(); ctx.arc(ccx, ccy, R * (1 + ph * 0.9), 0, 6.283); ctx.stroke(); }
      }
      // features
      ctx.globalCompositeOperation = 'source-over';
      { // LED fill: a radial gradient with a dot grid; the open mouth shows a tongue
        const pr = Math.max(1.4, S * 0.0105), stp = pr * 2.25;
        ['eyeL', 'eyeR', 'mouth'].forEach((g) => {
          if (G[g].closed < 0.05) return;
          const k = G[g].closed * vis, pts = G[g].pts, isM = g === 'mouth';
          let x0 = 1e9, y0 = 1e9, x1 = -1e9, y1 = -1e9;
          for (const p of pts) { const x = X(p.x), y = Y(p.y); if (x < x0) x0 = x; if (x > x1) x1 = x; if (y < y0) y0 = y; if (y > y1) y1 = y; }
          const mx = (x0 + x1) / 2, my = (y0 + y1) / 2, rw = (x1 - x0) / 2, rh = (y1 - y0) / 2;
          if (rw < 2 || rh < 2) return;
          ctx.save(); pathOf(pts, true); ctx.clip();
          const gr = ctx.createRadialGradient(mx - rw * 0.2, my - rh * 0.25, 0, mx, my, Math.max(rw, rh) * 1.15);
          if (isM) { gr.addColorStop(0, 'rgba(46,8,16,' + (0.92 * k).toFixed(3) + ')'); gr.addColorStop(1, rgba(col.f, 0.42 * k)); }
          else { gr.addColorStop(0, rgba(col.p, 0.62 * k)); gr.addColorStop(0.5, rgba(col.f, 0.5 * k)); gr.addColorStop(1, 'rgba(34,6,14,' + (0.85 * k).toFixed(3) + ')'); }
          ctx.fillStyle = gr; ctx.fillRect(x0 - 2, y0 - 2, rw * 2 + 4, rh * 2 + 4);
          ctx.globalCompositeOperation = ADD; ctx.fillStyle = rgba(col.p, (isM ? 0.16 : 0.3) * k); ctx.beginPath();
          for (let y = y0 + stp / 2; y < y1; y += stp) for (let x = x0 + stp / 2; x < x1; x += stp) ctx.rect(x - pr / 2, y - pr / 2, pr, pr);
          ctx.fill();
          if (isM && rh > S * 0.028) { ctx.fillStyle = rgba(col.f, 0.6 * k); ctx.beginPath(); ctx.ellipse(mx, y1 + rh * 0.08, rw * 0.5, rh * 0.62, 0, Math.PI, 2 * Math.PI); ctx.fill(); }
          ctx.restore(); ctx.globalCompositeOperation = 'source-over';
        });
      }
      ctx.globalCompositeOperation = ADD; ctx.lineJoin = 'round'; ctx.lineCap = 'round';
      const lw = Math.max(2, S * 0.02);
      ['eyeL', 'eyeR', 'mouth'].forEach((g) => {
        const cl = G[g].closed > 0.5; if (settle(g) < 0.15) return;
        ctx.strokeStyle = rgba(col.f, 0.16 * vis); ctx.lineWidth = lw * 3.6; pathOf(G[g].pts, cl); ctx.stroke();
        ctx.strokeStyle = rgba(col.f, 0.9 * vis); ctx.lineWidth = lw; ctx.stroke();
      });
      if (settle('browL') > 0.15) {
        ctx.strokeStyle = 'rgba(110,145,245,' + (0.22 * vis).toFixed(3) + ')'; ctx.lineWidth = lw * 2.8; pathOf(G.browL.pts, false); ctx.stroke(); pathOf(G.browR.pts, false); ctx.stroke();
        ctx.strokeStyle = rgba(col.f, 0.85 * vis); ctx.lineWidth = lw * 0.85; pathOf(G.browL.pts, false); ctx.stroke(); pathOf(G.browR.pts, false); ctx.stroke();
      }
      fillDots([...G.eyeL.pts, ...G.eyeR.pts, ...G.mouth.pts, ...G.browL.pts, ...G.browR.pts].filter((_, i) => !(i % 2)), Math.max(1.2, S * 0.011), rgba(col.p, vis));
      // carmine rim glow: strongest while speaking, then listening, then happy
      rimG += ((state === 'speaking' ? 1 : state === 'listening' ? 0.75 : ex === 'happy' ? 0.5 : 0.14) - rimG) * Math.min(1, dt * 3);
      if (rimG > 0.03) {
        ctx.globalCompositeOperation = ADD; ctx.lineJoin = 'round'; ctx.beginPath();
        for (let q = 0; q <= 64; q++) { const [x, y] = SH((q / 64) * 6.2832); if (q) ctx.lineTo(X(x * 1.01), Y(y * 1.01)); else ctx.moveTo(X(x * 1.01), Y(y * 1.01)); }
        ctx.closePath();
        const pu = 0.85 + 0.15 * Math.sin(T * 3.2);
        ctx.strokeStyle = 'rgba(229,83,102,' + (0.12 * rimG * pu * vis).toFixed(3) + ')'; ctx.lineWidth = Math.max(6, S * 0.05); ctx.stroke();
        ctx.strokeStyle = 'rgba(255,122,136,' + (0.55 * rimG * pu * vis).toFixed(3) + ')'; ctx.lineWidth = Math.max(1.2, S * 0.008); ctx.stroke();
      }
      { // glass sheen on the helmet, upper-left, with a slow glint travelling along it
        ctx.globalCompositeOperation = ADD; ctx.lineCap = 'round';
        const arcP = (k: number, a0: number, a1: number, n: number): Pt[] => { const o: Pt[] = []; for (let q = 0; q <= n; q++) { const [x, y] = SH(a0 + ((a1 - a0) * q) / n); o.push([X(x * k), Y(y * k)]); } return o; };
        const line = (pts: Pt[]) => { ctx.beginPath(); pts.forEach(([x, y], q) => (q ? ctx.lineTo(x, y) : ctx.moveTo(x, y))); ctx.stroke(); };
        const sheen = arcP(0.9, Math.PI + 0.42, Math.PI + 1.02, 14);
        ctx.strokeStyle = 'rgba(255,255,255,' + ((light ? 0.22 : 0.13) * vis).toFixed(3) + ')'; ctx.lineWidth = Math.max(2, S * 0.022); line(sheen);
        ctx.lineWidth = Math.max(1.5, S * 0.012); line(arcP(0.84, Math.PI + 0.5, Math.PI + 0.66, 5));
        const gp = (T * 0.16) % 1;
        if (gp < 0.35) {
          const u = gp / 0.35, [x, y] = sheen[Math.min(sheen.length - 1, Math.floor(u * sheen.length))], a = Math.sin(u * Math.PI) * 0.7 * vis;
          const gg = ctx.createRadialGradient(x, y, 0, x, y, S * 0.05); gg.addColorStop(0, 'rgba(255,255,255,' + a.toFixed(3) + ')'); gg.addColorStop(1, 'rgba(255,255,255,0)');
          ctx.fillStyle = gg; ctx.beginPath(); ctx.arc(x, y, S * 0.05, 0, 6.283); ctx.fill();
        }
      }
      if (earL2 > 0.03) { // rings out of the ears while listening
        ctx.globalCompositeOperation = ADD; ctx.lineCap = 'round';
        for (const s of [-1, 1]) for (let k = 0; k < 4; k++) {
          const ph = (T * 0.7 + k / 4) % 1, r = 0.22 + ph * 0.42, al = Math.sin(ph * Math.PI) * earL2 * (0.55 + lvl * 0.45);
          ctx.strokeStyle = k % 2 ? 'rgba(255,170,90,' + (0.5 * al * vis).toFixed(3) + ')' : 'rgba(110,160,255,' + (0.8 * al * vis).toFixed(3) + ')'; ctx.lineWidth = Math.max(1.2, S * 0.012 * (1 - ph * 0.5));
          ctx.beginPath(); ctx.ellipse(X(s * 1.04), Y(0.03), r * S * 0.6, r * S * 1.15, 0, s > 0 ? -1.15 : Math.PI - 1.15, s > 0 ? 1.15 : Math.PI + 1.15); ctx.stroke();
        }
        ctx.globalCompositeOperation = 'source-over';
      }
      if (state === 'thinking') { // sparks running along the rim
        ctx.globalCompositeOperation = ADD;
        for (let k = 0; k < 6; k++) {
          const u = ((T * 0.22 + k / 6) % 1) * 6.2832, [x, y] = SH(u), sx = X(x * 1.01), sy = Y(y * 1.01), [x2, y2] = SH(u - 0.18);
          ctx.strokeStyle = k % 2 ? 'rgba(255,90,110,' + (0.85 * vis).toFixed(3) + ')' : 'rgba(130,175,255,' + (0.85 * vis).toFixed(3) + ')'; ctx.lineWidth = Math.max(1.5, S * 0.013);
          ctx.beginPath(); ctx.moveTo(X(x2 * 1.01), Y(y2 * 1.01)); ctx.lineTo(sx, sy); ctx.stroke();
          ctx.fillStyle = 'rgba(255,240,240,' + (0.9 * vis).toFixed(3) + ')'; ctx.beginPath(); ctx.arc(sx, sy, Math.max(1.4, S * 0.009), 0, 6.283); ctx.fill();
        }
        ctx.globalCompositeOperation = 'source-over';
      }
      // scanline sweeping the visor
      scanA += (((act && act.name === 'scan') || thinkV === 'scan' ? 1 : 0) - scanA) * Math.min(1, dt * 6);
      if (scanA > 0.02) {
        const yy = act && act.name === 'scan' ? -0.5 + au * 1.1 : 0.05 + Math.sin(T * 3) * 0.5, wd = 0.78 * Math.sqrt(Math.max(0, 1 - Math.pow(Math.abs((yy - 0.05) / 0.6), 3.6)));
        ctx.strokeStyle = rgba(col.p, 0.22 * scanA * vis); ctx.lineWidth = 6; ctx.beginPath(); ctx.moveTo(X(-wd), Y(yy)); ctx.lineTo(X(wd), Y(yy)); ctx.stroke();
        ctx.fillStyle = rgba(col.p, 0.9 * scanA * vis); ctx.beginPath();
        for (let q = 0; q <= 16; q++) { const x = X(-wd + (q / 16) * wd * 2), y = Y(yy); ctx.moveTo(x + 1.3, y); ctx.arc(x, y, 1.3, 0, 6.283); }
        ctx.fill();
      }
      flashes = flashes.filter((f) => f.t < 1);
      for (const f of flashes) { f.t += dt * 2.2; const r = S * 0.35 * (0.4 + f.t), g = ctx.createRadialGradient(X(f.x), Y(f.y), 0, X(f.x), Y(f.y), r); g.addColorStop(0, rgba(col.p, 0.3 * (1 - f.t))); g.addColorStop(1, rgba(col.f, 0)); ctx.fillStyle = g; ctx.beginPath(); ctx.arc(X(f.x), Y(f.y), r, 0, 6.283); ctx.fill(); }
      NOR();
      // ambient sparks
      sparks = sparks.filter((s) => s.hops > 0);
      ctx.fillStyle = rgba(col.p, 0.9 * vis);
      for (const s of sparks) {
        const A = NP(s.a), B = NP(s.b), len = Math.hypot(A[0] - B[0], A[1] - B[1]) || 0.1;
        s.u += (dt * s.sp * 0.25) / len;
        if (s.u >= 1) {
          heat[s.b] = Math.max(heat[s.b], 0.6); s.hops--;
          const nb = BXM.adj[s.b].filter((v) => v !== s.a && !BXM.N[v].hub);
          if (!nb.length) { s.hops = 0; continue; }
          s.a = s.b; s.b = nb[Math.floor(Math.random() * nb.length)]; s.u = 0;
        }
        const A2 = NP(s.a), B2 = NP(s.b), x = A2[0] + (B2[0] - A2[0]) * s.u, y = A2[1] + (B2[1] - A2[1]) * s.u;
        s.tail.unshift([x, y]); if (s.tail.length > 6) s.tail.pop();
        ctx.beginPath(); s.tail.forEach(([tx, ty], k) => { const r = 2.1 - k * 0.3; ctx.moveTo(X(tx) + r, Y(ty)); ctx.arc(X(tx), Y(ty), r, 0, 6.283); }); ctx.fill();
      }
      // the big tracer: walks the journey node by node
      for (const tr of trs) {
        tr.u = (T - tr.t0) / tr.dur; if (tr.u <= 0) continue;
        const u = Math.min(1, tr.u), hd = trAt(tr, u);
        for (let i = 0; i < hd.i; i++) heat[tr.nodes[i]] = Math.max(heat[tr.nodes[i]], 0.55 * trail + (i === hd.i - 1 ? 0.45 : 0));
        if (tr.u >= 1) { if (!tr.done) { tr.done = true; heat[tr.nodes[tr.nodes.length - 1]] = 1; } continue; }
        const g = ctx.createRadialGradient(X(hd.x), Y(hd.y), 0, X(hd.x), Y(hd.y), 16); g.addColorStop(0, TRC + (0.55 * vis).toFixed(3) + ')'); g.addColorStop(1, TRC + '0)');
        ctx.fillStyle = g; ctx.beginPath(); ctx.arc(X(hd.x), Y(hd.y), 16, 0, 6.283); ctx.fill();
        ctx.fillStyle = TRC + (0.9 * vis).toFixed(3) + ')'; ctx.beginPath();
        for (let k = 0; k < 18; k++) { const p = trAt(tr, Math.max(0, u - k * 0.006)), r = Math.max(0.6, 4.6 - k * 0.24); ctx.moveTo(X(p.x) + r, Y(p.y)); ctx.arc(X(p.x), Y(p.y), r, 0, 6.283); }
        ctx.fill();
      }
      ctx.globalCompositeOperation = 'source-over';
      if (round && blink > 0.6) {
        ctx.fillStyle = 'rgba(255,255,255,' + (0.8 * vis).toFixed(3) + ')'; ctx.beginPath();
        ['eyeL', 'eyeR'].forEach((g) => { const c = center(g), x1 = X(c[0]) - S * 0.05, y1 = Y(c[1]) - S * 0.07, x2 = X(c[0]) + S * 0.035, y2 = Y(c[1]) + S * 0.05; ctx.moveTo(x1 + S * 0.034, y1); ctx.ellipse(x1, y1, S * 0.034, S * 0.026, -0.55, 0, 6.283); ctx.moveTo(x2 + S * 0.013, y2); ctx.arc(x2, y2, S * 0.013, 0, 6.283); });
        ctx.fill();
      }
      NOC();
      { // blush by expression, a soft glow with a dot grid
        const bl = (({ happy: 1, wink: 0.9, hum: 0.85, curious: 0.55, neutral: 0.42, think: 0.3, sad: 0.25, serious: 0.08 } as Record<string, number>)[ex] ?? 0.4) * (state === 'standby' ? 0.35 : 1) * vis;
        if (bl > 0.02) {
          ctx.globalCompositeOperation = ADD;
          [-1, 1].forEach((s) => {
            const x = X(s * 0.55), y = Y(0.21), r = S * 0.1;
            const g = ctx.createRadialGradient(x, y, 0, x, y, r); g.addColorStop(0, 'rgba(255,110,140,' + (0.2 * bl).toFixed(3) + ')'); g.addColorStop(1, 'rgba(255,110,140,0)');
            ctx.fillStyle = g; ctx.beginPath(); ctx.ellipse(x, y, r, r * 0.55, 0, 0, 6.283); ctx.fill();
            const d = Math.max(1.3, S * 0.008), st = d * 2.3; ctx.fillStyle = 'rgba(255,120,145,' + (0.75 * bl).toFixed(3) + ')'; ctx.beginPath();
            for (let yy = -r * 0.42; yy <= r * 0.42; yy += st) for (let xx = -r * 0.8; xx <= r * 0.8; xx += st) if ((xx * xx) / (r * r * 0.64) + (yy * yy) / (r * r * 0.18) <= 1) ctx.rect(x + xx - d / 2, y + yy - d / 2, d, d);
            ctx.fill();
          });
          ctx.globalCompositeOperation = 'source-over';
        }
      }
      if (ex === 'happy' || ex === 'wink' || ex === 'hum') {
        ctx.fillStyle = 'rgba(255,122,154,0.4)'; ctx.beginPath();
        [-1, 1].forEach((s) => { for (let q = 0; q < 8; q++) { const a = q * 0.785, x = X(s * 0.56 + Math.cos(a) * 0.06), y = Y(0.22 + Math.sin(a) * 0.025); ctx.moveTo(x + 1.6, y); ctx.arc(x, y, 1.6, 0, 6.283); } });
        ctx.fill();
      }
      // ? and ! glyphs made of dots, thought bubble, fx particles
      qA += ((ex === 'curious' ? 1 : 0) - qA) * Math.min(1, dt * 6); exA += ((expr === 'serious' ? 1 : 0) - exA) * Math.min(1, dt * 6);
      bubA += ((thinkV === 'bubble' ? 1 : 0) - bubA) * Math.min(1, dt * 5);
      const glyph = (pts: Pt[], a: number, gx0: number, gy0: number, sc: number) => {
        if (a < 0.02) return;
        const pop = sc * (0.6 + 0.4 * a + Math.sin(T * 6) * 0.03);
        ctx.fillStyle = rgba(col.p, a * vis); ctx.beginPath();
        for (const [x, y] of bxSample(pts, 14, false)) { const px = X(gx0 + x * pop), py = Y(gy0 + y * pop); ctx.moveTo(px + 1.9, py); ctx.arc(px, py, 1.9, 0, 6.283); }
        const ly = pts[pts.length - 1][1];
        ctx.moveTo(X(gx0) + 2.6, Y(gy0 + (ly + 0.06) * pop)); ctx.arc(X(gx0), Y(gy0 + (ly + 0.06) * pop), 2.6, 0, 6.283); ctx.fill();
      };
      glyph(GLYPH_Q, qA, 0.62, -1.02 + Math.sin(T * 2.2) * 0.02, 1.15);
      glyph(GLYPH_EX, exA, -0.6, -1.02 + Math.sin(T * 3) * 0.015, 1.15);
      if (bubA > 0.02) {
        ctx.strokeStyle = rgba(col.p, 0.8 * bubA * vis); ctx.lineWidth = 1.4;
        ([[0.72, -0.72, 0.035], [0.86, -0.88, 0.055], [1.06, -1.08, 0.11]] as const).forEach(([x, y, r], i) => { const a = Math.max(0, Math.min(1, bubA * 3 - i)); if (a <= 0) return; ctx.globalAlpha = a; ctx.beginPath(); ctx.arc(X(x), Y(y + Math.sin(T * 2 + i) * 0.015), r * S, 0, 6.283); ctx.stroke(); });
        ctx.globalAlpha = 1;
        ctx.fillStyle = rgba(col.p, bubA * vis); ctx.beginPath();
        for (let q = 0; q < 3; q++) { const x = X(1.0 + q * 0.06), y = Y(-1.08 + Math.sin(T * 6 + q) * 0.012); ctx.moveTo(x + 1.6, y); ctx.arc(x, y, 1.6, 0, 6.283); }
        ctx.fill();
      }
      fx = fx.filter((p) => p.t < p.life);
      for (const p of fx) {
        p.t += dt; if (p.t < 0) continue;
        const a = Math.min(1, (1 - p.t / p.life) * 2.5) * vis;
        if (p.k === 'conf') { p.vy += 4.2 * dt; p.vx *= 1 - dt * 0.8; p.x += p.vx * dt; p.y += p.vy * dt; p.r = (p.r ?? 0) + (p.vr ?? 0) * dt; ctx.strokeStyle = p.c ?? '#fff'; ctx.globalAlpha = a; ctx.lineWidth = 2.2; ctx.beginPath(); ctx.moveTo(X(p.x) - Math.cos(p.r) * 3, Y(p.y) - Math.sin(p.r) * 3); ctx.lineTo(X(p.x) + Math.cos(p.r) * 3, Y(p.y) + Math.sin(p.r) * 3); ctx.stroke(); }
        if (p.k === 'note') { p.x += (p.vx + Math.sin(p.t * 5 + (p.ph ?? 0)) * 0.15) * dt; p.y += p.vy * dt; const x = X(p.x), y = Y(p.y); ctx.globalAlpha = a; ctx.fillStyle = rgba(col.p, 1); ctx.strokeStyle = rgba(col.p, 1); ctx.lineWidth = 1.3; ctx.beginPath(); ctx.ellipse(x, y, 3, 2.2, -0.4, 0, 6.283); ctx.fill(); ctx.beginPath(); ctx.moveTo(x + 2.6, y - 1); ctx.lineTo(x + 2.6, y - 10); ctx.quadraticCurveTo(x + 6, y - 8, x + 6.5, y - 5); ctx.stroke(); }
        if (p.k === 'drop') { p.vy += 0.25 * dt; p.y += p.vy * dt; const x = X(p.x), y = Y(p.y), r = 3.2 + Math.min(1, p.t * 3) * 1.6; ctx.globalAlpha = a * 0.9; ctx.fillStyle = '#9DD7F5'; ctx.beginPath(); ctx.moveTo(x, y - r * 2.1); ctx.quadraticCurveTo(x + r * 1.1, y - r * 0.4, x, y + r); ctx.quadraticCurveTo(x - r * 1.1, y - r * 0.4, x, y - r * 2.1); ctx.fill(); ctx.fillStyle = 'rgba(255,255,255,0.8)'; ctx.beginPath(); ctx.arc(x - r * 0.3, y - r * 0.1, r * 0.25, 0, 6.283); ctx.fill(); }
        if (p.k === 'star') { const s2 = Math.sin(Math.min(1, p.t / p.life) * Math.PI) * 7, x = X(p.x), y = Y(p.y); ctx.globalAlpha = a; ctx.strokeStyle = '#FFF6E0'; ctx.lineWidth = 1.5; ctx.beginPath(); ctx.moveTo(x - s2, y); ctx.lineTo(x + s2, y); ctx.moveTo(x, y - s2); ctx.lineTo(x, y + s2); ctx.moveTo(x - s2 * 0.4, y - s2 * 0.4); ctx.lineTo(x + s2 * 0.4, y + s2 * 0.4); ctx.moveTo(x + s2 * 0.4, y - s2 * 0.4); ctx.lineTo(x - s2 * 0.4, y + s2 * 0.4); ctx.stroke(); }
      }
      ctx.globalAlpha = 1;
      NOR();
      // labels appear with their hubs
      ctx.font = '500 ' + Math.max(9, Math.round(S * 0.058)) + 'px Inter, sans-serif'; ctx.textBaseline = 'middle'; ctx.lineJoin = 'round';
      for (const k in HUB_LABEL) {
        const i = BXM.hub[k], v = heat[i];
        if (v < 0.06) continue;
        ctx.globalAlpha = Math.min(1, v * 1.8);
        const [hx, hy] = NP(i), [ox, oy, al] = HUB_LABEL[k];
        ctx.textAlign = al; ctx.strokeStyle = light ? 'rgba(244,245,248,0.92)' : 'rgba(8,11,16,0.85)'; ctx.lineWidth = 3; ctx.strokeText(HUB_NAME[k] || k, X(hx + ox), Y(hy + oy));
        ctx.fillStyle = v > 0.25 ? rgba(col.p, (0.6 + v * 0.4) * vis) : (light ? 'rgba(60,70,92,' : 'rgba(163,173,194,') + (0.6 * vis).toFixed(3) + ')';
        ctx.fillText(HUB_NAME[k] || k, X(hx + ox), Y(hy + oy));
      }
      ctx.globalAlpha = 1;
      NOC();
      ctx.strokeStyle = 'rgba(216,220,230,' + (0.07 * vis).toFixed(3) + ')'; ctx.lineWidth = S * 0.04; ctx.lineCap = 'round';
      ctx.beginPath(); ctx.arc(-S * 0.24, -S * 0.12, S * 0.48, Math.PI * 1.1, Math.PI * 1.38); ctx.stroke();
      if (state === 'standby') {
        ctx.textAlign = 'left';
        for (let k = 0; k < 3; k++) { const u = (T * 0.35 + k / 3) % 1; ctx.fillStyle = rgba(col.f, Math.sin(u * Math.PI) * 0.85); ctx.font = '600 ' + Math.round(S * (0.11 + u * 0.09)) + 'px Inter, sans-serif'; ctx.fillText('z', X(0.7 + u * 0.4), Y(-0.6 - u * 0.5)); }
      }
      NOR();
      ctx.restore();
    };
    raf = requestAnimationFrame(tick);
    return () => {
      cancelAnimationFrame(raf); cancelAnimationFrame(sizeQ); ro.disconnect();
      window.removeEventListener('pointermove', onMove); window.removeEventListener('resize', sizeSoon); window.removeEventListener('bx-scale', size); document.removeEventListener('visibilitychange', onVis);
    };
  }, []);
  return <canvas className="bx-face" ref={ref} data-overlay={props.overlay ? '1' : '0'}></canvas>;
}

export const Face = memo(FaceView);
