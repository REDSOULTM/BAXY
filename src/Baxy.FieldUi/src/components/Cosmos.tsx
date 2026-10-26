import { memo, useEffect, useRef } from 'react';
import { seededRng } from '../utils/seededRng';
import type { BaxyState } from '../types';

/* Full-window starfield + travelling comets (design cosmos.jsx, ported as is): batched draws at 30 fps, the nebula
   painted at a third of the size and cached, the same sky on every rebuild (seed 707), the buffer capped at 4 MP and
   DPR ≤ 1.25. With prefers-reduced-motion the sky stays still: no turning, no twinkle, no comets (its colours still
   follow the state). */

type SkyState = 'standby' | 'idle' | 'listening' | 'thinking' | 'speaking';
const NEB: Record<SkyState, [string, string]> = {
  standby: ['#3F4860', '#5B6580'], idle: ['#1B2A5E', '#7A1E2B'], listening: ['#6B5A2F', '#1B2A5E'],
  thinking: ['#7A1E2B', '#6B5A2F'], speaking: ['#1B2A5E', '#2E4BA0'],
};
const COMET: Record<SkyState, { rate: number; cols: string[] }> = {
  standby: { rate: 0, cols: ['#5B6580'] },
  idle: { rate: 0.3, cols: ['#E55366', '#5B7FDB', '#5B7FDB'] },
  listening: { rate: 0.8, cols: ['#FF6677', '#E55366', '#F5C6CC'] },
  thinking: { rate: 1.8, cols: ['#7B95D9', '#5B7FDB', '#C8D6F5'] },
  speaking: { rate: 1, cols: ['#E8C98E', '#C9A66B', '#F8EED2'] },
};
const COSMOS_MAXPX = 4e6;
const STAR_COLS = ['#D8DCE6', '#7B95D9', '#E55366'];
const STAR_COLS_L = ['#7A849A', '#3A5BB8', '#C2334A'];

interface Star { a: number; d: number; s: number; b: number; c: number }
interface Comet { sx: number; sy: number; tx: number; ty: number; mx: number; my: number; t: number; dur: number; col: string; inward: boolean }

function sky(state: BaxyState): SkyState {
  return state === 'error' ? 'idle' : state === 'confirm' ? 'idle' : state === 'booting' ? 'standby' : state;
}

function CosmosView({ state, focusX, light }: { state: BaxyState; focusX: number; light: boolean }) {
  const ref = useRef<HTMLCanvasElement>(null);
  const S = useRef({ state: sky(state), focusX, light });
  useEffect(() => { S.current = { state: sky(state), focusX, light }; }, [state, focusX, light]);
  useEffect(() => {
    const cv = ref.current!, ctx = cv.getContext('2d')!;
    let dpr = 1, rnd: () => number;
    let w = 0, h = 0, raf = 0, last = performance.now(), acc = 0;
    let stars: Star[] = [], comets: Comet[] = [], spawn = 0, rot = 0, vis = 1, nebKey = '';
    const neb = document.createElement('canvas');
    const calmQ = window.matchMedia('(prefers-reduced-motion: reduce)');
    const build = () => {
      const lw = cv.clientWidth, lh = cv.clientHeight;
      if (!lw || !lh) return;
      // the screen's density now: a window moved to a screen of another scale keeps its CSS size (no resize)
      const DPR = Math.min(1.25, window.devicePixelRatio || 1), vz = cv.getBoundingClientRect().width / lw || 1;
      dpr = Math.max(0.5, Math.min(DPR * vz, Math.sqrt(COSMOS_MAXPX / (lw * lh))));
      const resize = Math.abs(lw - w) > 0.5 || Math.abs(lh - h) > 0.5 || !stars.length;
      w = lw; h = lh;
      const bw = Math.round(w * dpr), bh = Math.round(h * dpr);
      if (cv.width !== bw || cv.height !== bh) { cv.width = bw; cv.height = bh; }
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      nebKey = '';
      if (!resize) return;
      rnd = seededRng(707); /* same sky every rebuild */
      const reach = Math.hypot(w, h) * 0.62, n = Math.round((w * h) / 1500);
      stars = Array.from({ length: n }, () => {
        const a = rnd() * Math.PI * 2, d = Math.sqrt(rnd()) * reach, rc = rnd();
        return { a, d, s: rnd() < 0.08 ? 1.4 : 0.4 + rnd() * 0.7, b: Math.floor(rnd() * 3), c: rc < 0.18 ? 1 : rc < 0.26 ? 2 : 0 };
      });
    };
    const paintNebula = (st: SkyState) => {
      neb.width = Math.max(1, Math.round(w / 3)); neb.height = Math.max(1, Math.round(h / 3));
      const n = neb.getContext('2d')!, c = NEB[st] ?? NEB.idle, W = neb.width, H = neb.height;
      n.clearRect(0, 0, W, H);
      ([[0.12, 0.3, c[0], 0.9], [0.88, 0.7, c[1], 0.8], [0.02, 0.85, c[1], 0.6], [0.98, 0.18, c[0], 0.6]] as const).forEach(([fx, fy, col, k]) => {
        const r = Math.max(W, H) * 0.34, g = n.createRadialGradient(fx * W, fy * H, 0, fx * W, fy * H, r);
        g.addColorStop(0, col); g.addColorStop(1, 'rgba(0,0,0,0)');
        n.globalAlpha = (S.current.light ? 0.07 : 0.16) * k; n.fillStyle = g; n.fillRect(0, 0, W, H);
      });
    };
    const newComet = (st: SkyState) => {
      const conf = COMET[st], cx = S.current.focusX * w, cy = h * 0.46, edge = Math.floor(Math.random() * 4);
      const sx = edge === 0 ? -10 : edge === 1 ? w + 10 : Math.random() * w, sy = edge === 2 ? -10 : edge === 3 ? h + 10 : Math.random() * h;
      const inward = Math.random() < 0.55;
      const tx = inward ? cx + (Math.random() - 0.5) * 60 : Math.random() * w;
      const ty = inward ? cy + (Math.random() - 0.5) * 60 : (edge === 2 ? h + 10 : edge === 3 ? -10 : Math.random() * h);
      const bend = (Math.random() - 0.5) * 0.6;
      comets.push({ sx, sy, tx, ty, mx: (sx + tx) / 2 + (ty - sy) * bend, my: (sy + ty) / 2 - (tx - sx) * bend, t: 0, dur: 2.4 + Math.random() * 2.6, col: conf.cols[Math.floor(Math.random() * conf.cols.length)], inward });
    };
    const at = (c: Comet, t: number): [number, number] => { const u = 1 - t; return [u * u * c.sx + 2 * u * t * c.mx + t * t * c.tx, u * u * c.sy + 2 * u * t * c.my + t * t * c.ty]; };
    const tick = (now: number) => {
      raf = requestAnimationFrame(tick);
      acc += now - last; last = now;
      if (acc < 32) return;
      const dt = Math.min(0.08, acc / 1000); acc = 0;
      if (!w || !h) { build(); if (!w || !h) return; }
      const st = S.current.state, T = now / 1000, rm = calmQ.matches;
      vis += ((st === 'standby' ? 0.35 : 1) - vis) * Math.min(1, dt * 1.5);
      if (!rm) rot += dt * (st === 'standby' ? 0.002 : st === 'thinking' ? 0.012 : 0.005);
      if (nebKey !== st + S.current.light) { paintNebula(st); nebKey = st + S.current.light; }
      ctx.clearRect(0, 0, w, h);
      ctx.globalAlpha = vis; ctx.drawImage(neb, 0, 0, w, h);
      const cx = S.current.focusX * w, cy = h * 0.46, ca = Math.cos(rot), sa = Math.sin(rot);
      for (let c = 0; c < 3; c++) for (let b = 0; b < 3; b++) {
        ctx.globalAlpha = vis * (0.35 + 0.55 * (rm ? 0.5 : 0.5 + 0.5 * Math.sin(T * (0.8 + b * 0.5) + b * 2.1)));
        ctx.fillStyle = (S.current.light ? STAR_COLS_L : STAR_COLS)[c]; ctx.beginPath();
        for (const s of stars) {
          if (s.c !== c || s.b !== b) continue;
          const ox = Math.cos(s.a) * s.d, oy = Math.sin(s.a) * s.d, x = cx + ox * ca - oy * sa, y = cy + (ox * sa + oy * ca) * 0.8;
          if (x < -2 || x > w + 2 || y < -2 || y > h + 2) continue;
          ctx.moveTo(x + s.s, y); ctx.arc(x, y, s.s, 0, 6.283);
        }
        ctx.fill();
      }
      if (rm) { comets = []; spawn = 0; }
      else spawn += dt * COMET[st].rate;
      while (spawn >= 1) { spawn -= 1; if (comets.length < 14) newComet(st); }
      comets = comets.filter((c) => c.t < 1.08);
      for (const c of comets) {
        c.t += dt / c.dur;
        const head = Math.min(1, c.t), fade = c.inward ? Math.min(1, (1 - head) * 6 + 0.15) : 1;
        ctx.fillStyle = c.col;
        for (let k = 0; k < 10; k++) {
          const tt = head - k * 0.02; if (tt <= 0) break;
          const [x, y] = at(c, tt);
          ctx.globalAlpha = vis * fade * (1 - k / 10) * 0.85; ctx.beginPath(); ctx.arc(x, y, Math.max(0.4, 1.7 - k * 0.13), 0, 6.283); ctx.fill();
        }
      }
      ctx.globalAlpha = 1;
    };
    build();
    let bq = 0;
    const buildSoon = () => { if (!bq) bq = requestAnimationFrame(() => { bq = 0; build(); }); };
    const onVis = () => { if (!document.hidden) build(); };
    let dense: MediaQueryList | null = null;
    const onDense = () => { watchDense(); build(); };
    const watchDense = () => { dense?.removeEventListener('change', onDense); dense = window.matchMedia('(resolution: ' + (window.devicePixelRatio || 1) + 'dppx)'); dense.addEventListener('change', onDense); };
    watchDense();
    const ro = new ResizeObserver(buildSoon); ro.observe(cv);
    window.addEventListener('resize', buildSoon); window.addEventListener('bx-scale', build); document.addEventListener('visibilitychange', onVis);
    raf = requestAnimationFrame(tick);
    return () => {
      cancelAnimationFrame(raf); cancelAnimationFrame(bq); ro.disconnect(); dense?.removeEventListener('change', onDense);
      window.removeEventListener('resize', buildSoon); window.removeEventListener('bx-scale', build); document.removeEventListener('visibilitychange', onVis);
    };
  }, []);
  return <canvas className="bx-cosmos" ref={ref}></canvas>;
}

export const Cosmos = memo(CosmosView);
