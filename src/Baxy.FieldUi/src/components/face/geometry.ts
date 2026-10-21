import { seededRng } from '../../utils/seededRng';

/* The face's shapes and its neural mesh (design face.jsx, ported as is). Coordinates are in units of the face's size S. */

export type Pt = [number, number];

export function bxSample(pts: Pt[], N: number, closed: boolean): Pt[] {
  const P = closed ? [...pts, pts[0]] : pts, seg: number[] = [], L = [0];
  for (let i = 1; i < P.length; i++) { const d = Math.hypot(P[i][0] - P[i - 1][0], P[i][1] - P[i - 1][1]); seg.push(d); L.push(L[i - 1] + d); }
  const total = L[L.length - 1] || 1, out: Pt[] = [];
  for (let k = 0; k < N; k++) {
    const t = closed ? (k / N) * total : (k / (N - 1)) * total;
    let i = 1; while (i < L.length - 1 && L[i] < t) i++;
    const u = seg[i - 1] ? (t - L[i - 1]) / seg[i - 1] : 0;
    out.push([P[i - 1][0] + (P[i][0] - P[i - 1][0]) * u, P[i - 1][1] + (P[i][1] - P[i - 1][1]) * u]);
  }
  return out;
}
export const bxEll = (cx: number, cy: number, rx: number, ry: number, n = 48): Pt[] =>
  Array.from({ length: n }, (_, i) => { const a = (i / n) * 6.2832 - 1.5708; return [cx + Math.cos(a) * rx, cy + Math.sin(a) * ry]; });
export const bxArc = (cx: number, cy: number, rx: number, ry: number, a0: number, a1: number, n = 40): Pt[] =>
  Array.from({ length: n }, (_, i) => { const a = a0 + (a1 - a0) * (i / (n - 1)); return [cx + Math.cos(a) * rx, cy + Math.sin(a) * ry]; });
export const bxSuper = (cx: number, cy: number, a: number, b: number, e: number, n = 120): Pt[] =>
  Array.from({ length: n }, (_, i) => { const t = (i / n) * 6.2832 - 1.5708, c = Math.cos(t), s = Math.sin(t); return [cx + a * Math.sign(c) * Math.pow(Math.abs(c), 2 / e), cy + b * Math.sign(s) * Math.pow(Math.abs(s), 2 / e)]; });

export const FK = 0.78, FY = 0.05;

export function bxEye(expr: string, s: number): [Pt[], number] {
  const ex = 0.42 * s, ey = -0.1, inX = ex - s * 0.16, outX = ex + s * 0.16;
  switch (expr) {
    case 'listen': return [bxEll(ex, ey - 0.03, 0.17, 0.27, 32), 1];
    case 'happy': return [[...bxArc(ex, ey + 0.1, 0.17, 0.2, Math.PI + 0.15, 2 * Math.PI - 0.15, 20), ...bxArc(ex, ey + 0.1, 0.1, 0.1, 2 * Math.PI - 0.3, Math.PI + 0.3, 12)], 1];
    case 'sleep': return [bxArc(ex, ey, 0.16, 0.1, 0.25, Math.PI - 0.25, 20), 0];
    case 'sad': return [[[outX, ey + 0.06], [inX, ey - 0.04]], 0];
    case 'serious': return [[[outX, ey - 0.16], [inX, ey + 0.03], [inX + s * 0.02, ey + 0.13], [outX - s * 0.02, ey + 0.13]], 1];
    case 'think': return s > 0 ? [bxEll(ex, ey - 0.02, 0.15, 0.1, 32), 1] : [bxEll(ex, ey - 0.05, 0.14, 0.21, 32), 1];
    case 'curious': return s > 0 ? [bxEll(ex, ey - 0.07, 0.19, 0.29, 32), 1] : [bxEll(ex, ey, 0.13, 0.17, 32), 1];
    case 'wink': return s > 0 ? [[...bxArc(ex, ey + 0.08, 0.16, 0.17, Math.PI + 0.2, 2 * Math.PI - 0.2, 20), ...bxArc(ex, ey + 0.08, 0.09, 0.08, 2 * Math.PI - 0.35, Math.PI + 0.35, 12)], 1] : [bxEll(ex, ey, 0.16, 0.24, 32), 1];
    case 'yawn': return [bxArc(ex, ey - 0.04, 0.15, 0.07, 0.3, Math.PI - 0.3, 20), 0];
    case 'squint': return [bxEll(ex, ey + 0.01, 0.15, 0.065, 32), 1];
    case 'hum': return [bxArc(ex, ey + 0.1, 0.15, 0.15, Math.PI + 0.25, 2 * Math.PI - 0.25, 20), 0];
    case 'wide': return [bxEll(ex, ey - 0.03, 0.19, 0.29, 32), 1];
    default: return [bxEll(ex, ey, 0.16, 0.24, 32), 1];
  }
}

/* cartoon brows: [inner y, outer y, bulge] per expression */
const BROW: Record<string, [number, number, number]> = {
  neutral: [-0.44, -0.43, 0.04], happy: [-0.52, -0.49, 0.07], listen: [-0.53, -0.5, 0.05], wide: [-0.56, -0.53, 0.06],
  sad: [-0.52, -0.39, 0.01], serious: [-0.34, -0.49, -0.01], sleep: [-0.37, -0.36, 0.02], yawn: [-0.5, -0.45, 0.04],
  squint: [-0.36, -0.39, 0.02], hum: [-0.5, -0.47, 0.05], wink: [-0.47, -0.45, 0.05],
};
export function bxBrow(expr: string, s: number, lift: number): Pt[] {
  let b = BROW[expr] ?? BROW.neutral;
  if (expr === 'curious') b = s > 0 ? [-0.6, -0.57, 0.06] : [-0.42, -0.42, 0.03];
  if (expr === 'think') b = s < 0 ? [-0.56, -0.51, 0.06] : [-0.38, -0.42, 0.02];
  if (expr === 'wink' && s > 0) b = [-0.38, -0.4, 0.03];
  const ex = 0.42 * s, xi = ex - s * 0.13, xo = ex + s * 0.14, yi = b[0] - lift, yo = b[1] - lift, my = (yi + yo) / 2 - b[2];
  return Array.from({ length: 12 }, (_, i) => { const t = i / 11, u = 1 - t; return [u * u * xi + 2 * u * t * ex + t * t * xo, u * u * yi + 2 * u * t * my + t * t * yo]; });
}
export const GLYPH_Q: Pt[] = [...bxArc(0, -0.05, 0.065, 0.065, Math.PI * 1.05, Math.PI * 2.5, 11), [0, 0.04], [0, 0.065]];
export const GLYPH_EX: Pt[] = [[0, -0.12], [0, -0.08], [0, -0.04], [0, 0], [0, 0.04]];

export function bxMouth(expr: string, talk: number): [Pt[], number] {
  if (talk >= 0 && (expr === 'sad' || expr === 'serious')) { const w = 0.13 + talk * 0.04, d = 0.035 + talk * 0.13; return [bxEll(0, 0.45, w, d, 22), 1]; }
  // design v5: the open mouth is for speaking happy; otherwise speech is a voice wave (the concepts' mouth)
  if (talk >= 0 && expr === 'happy') { const d = 0.05 + talk * 0.22, w = 0.2 + talk * 0.06; return [[[-w, 0.36], [w, 0.36], ...bxArc(0, 0.36, w, d, 0, Math.PI, 20)], 1]; }
  if (talk >= 0) {
    const t = performance.now() / 1000, n = 15, o: Pt[] = [];
    for (let i = 0; i < n; i++) {
      const u = i / (n - 1), x = -0.26 + u * 0.52, env = Math.sin(u * Math.PI), amp = (0.015 + talk * 0.13) * env * (0.55 + 0.45 * Math.sin(t * 13 + i * 1.7));
      o.push([x, 0.42 + (i % 2 ? -amp : amp)]);
    }
    return [o, 0];
  }
  switch (expr) {
    case 'happy': return [[[-0.32, 0.3], [0.32, 0.3], ...bxArc(0, 0.3, 0.32, 0.27, 0, Math.PI, 24)], 1];
    case 'listen': return [bxEll(0, 0.44, 0.08, 0.09, 24), 1];
    case 'sad': return [bxArc(0, 0.62, 0.22, 0.17, Math.PI + 0.45, 2 * Math.PI - 0.45, 24), 0];
    case 'sleep': return [bxEll(0, 0.46, 0.05, 0.035, 16), 1];
    case 'think': return [[[-0.15, 0.46], [-0.05, 0.42], [0.05, 0.46], [0.15, 0.42]], 0];
    case 'serious': return [Array.from({ length: 9 }, (_, i): Pt => [-0.24 + i * 0.06, 0.46 + (i % 2 ? -0.035 : 0.035)]), 0];
    case 'curious': return [bxArc(0.08, 0.3, 0.17, 0.13, 0.35, Math.PI - 0.6, 24), 0];
    case 'wink': return [[[-0.26, 0.32], [0.26, 0.32], ...bxArc(0, 0.32, 0.26, 0.18, 0, Math.PI, 20)], 1];
    case 'yawn': return [bxEll(0, 0.44, 0.13, 0.17, 24), 1];
    case 'hum': return [bxEll(0, 0.42, 0.055, 0.065, 16), 1];
    case 'squint': return [[[-0.15, 0.46], [-0.05, 0.42], [0.05, 0.46], [0.15, 0.42]], 0];
    case 'wide': return [bxEll(0, 0.42, 0.09, 0.11, 20), 1];
    default: return [[[-0.23, 0.33], [0.23, 0.33], ...bxArc(0, 0.33, 0.23, 0.16, 0, Math.PI, 22)], 1]; // open smile
  }
}

export const TILT: Record<string, number> = { curious: 0.08, think: -0.05, sad: 0.04, sleep: 0.07, happy: -0.025, wink: 0.06, yawn: -0.04, hum: 0.02 };
/* behaviour library — picked at random, never the same twice in a row */
export const IDLE: Record<string, number> = { look: 2.4, dblink: 0.7, yawn: 2.3, antenna: 1.3, hum: 2.8, wink: 0.9, hop: 1.2, chat: 1.8, scan: 1.5, stretch: 1.4, tiltq: 1.8, shake: 0.9, peek: 1.6 };
export const THINK = ['up', 'roll', 'scan', 'squint', 'bubble'];
export const TALK = ['nod', 'brow', 'tilt', 'blink', 'smile', 'lean'];

/* ---------- neural mesh living inside the helmet rim ---------- */
const SUP = (cx: number, cy: number, a: number, b: number, e: number) => (t: number): Pt => {
  const c = Math.cos(t), s = Math.sin(t);
  return [cx + a * Math.sign(c) * Math.pow(Math.abs(c), 2 / e), cy + b * Math.sign(s) * Math.pow(Math.abs(s), 2 / e)];
};
export const SH = SUP(0, 0, 1.0, 0.84, 3.1);
const VI = SUP(0, 0.05, 0.8, 0.6, 3.6);
export const HUBS: Record<string, Pt> = {
  web: [0, -1.2], mente: [0, -0.715], apps: [-0.66, -0.6], ventanas: [0.66, -0.6], memoria: [-1.13, 0.03], musica: [1.13, 0.03],
  archivos: [-0.64, 0.63], alarmas: [0.64, 0.63], verificar: [0, 0.75], voz: [0, 1.25],
};
export const HUB_NAME: Record<string, string> = { musica: 'música' };
export const HUB_LABEL: Record<string, [number, number, CanvasTextAlign]> = {
  web: [0.14, 0, 'left'], mente: [0.09, -0.005, 'left'], apps: [-0.05, -0.27, 'center'], ventanas: [0.05, -0.27, 'center'],
  memoria: [0, 0.43, 'center'], musica: [0, 0.43, 'center'], archivos: [-0.08, 0.25, 'center'], alarmas: [0.08, 0.25, 'center'],
  verificar: [0.1, 0.005, 'left'], voz: [0.26, 0, 'left'],
};

export interface MeshNode { x: number; y: number; hub?: string; ph: number }
export interface Mesh { N: MeshNode[]; E: [number, number][]; adj: number[][]; hub: Record<string, number>; ring: number[] }

export function bxBuildMesh(): Mesh {
  const rnd = seededRng(9091), N: MeshNode[] = [], E: [number, number][] = [], hub: Record<string, number> = {};
  Object.entries(HUBS).forEach(([k, p]) => { hub[k] = N.length; N.push({ x: p[0], y: p[1], hub: k, ph: 0 }); });
  const cols = 30;
  [0.22, 0.5, 0.78].forEach((f, r) => {
    for (let i = 0; i < cols; i++) {
      const t = ((i + (r % 2 ? 0.5 : 0)) / cols) * 6.2832 - 1.5708 + (rnd() - 0.5) * 0.05;
      const a = VI(t), b = SH(t), ff = f + (rnd() - 0.5) * 0.07, x = a[0] + (b[0] - a[0]) * ff, y = a[1] + (b[1] - a[1]) * ff;
      if (Object.values(HUBS).some((hp) => Math.hypot(hp[0] - x, hp[1] - y) < 0.075)) continue;
      N.push({ x, y, ph: rnd() * 6.28 });
    }
  });
  const ring = N.map((n, i) => (n.hub ? -1 : i)).filter((i) => i >= 0), seen = new Set<string>();
  const add = (i: number, j: number) => { const k = i < j ? i + '-' + j : j + '-' + i; if (i === j || seen.has(k)) return; seen.add(k); E.push([i, j]); };
  const near = (i: number, pool: number[], k: number) => pool.filter((j) => j !== i).map((j): [number, number] => [j, Math.hypot(N[i].x - N[j].x, N[i].y - N[j].y)]).sort((a, b) => a[1] - b[1]).slice(0, k);
  ring.forEach((i) => near(i, ring, 4).forEach(([j, d]) => { if (d < 0.27) add(i, j); }));
  ([['mente', 4], ['apps', 3], ['ventanas', 3], ['memoria', 3], ['musica', 3], ['archivos', 3], ['alarmas', 3], ['verificar', 4]] as const)
    .forEach(([k, n]) => near(hub[k], ring, n).forEach(([j]) => add(hub[k], j)));
  add(hub.web, hub.mente); add(hub.verificar, hub.voz);
  const adj: number[][] = N.map(() => []);
  E.forEach(([i, j]) => { adj[i].push(j); adj[j].push(i); });
  return { N, E, adj, hub, ring };
}
export const BXM = bxBuildMesh();

/* a wandering shortest path through the mesh, hub to hub */
export function bxRoute(hubs: string[]): number[] {
  const out = [BXM.hub[hubs[0]]];
  for (let s = 0; s < hubs.length - 1; s++) {
    const A = BXM.hub[hubs[s]], B = BXM.hub[hubs[s + 1]], dist = new Map<number, number>([[A, 0]]), prev = new Map<number, number>(), done = new Set<number>(), W: Record<string, number> = {};
    for (;;) {
      let u = -1, du = Infinity;
      dist.forEach((d, k) => { if (!done.has(k) && d < du) { du = d; u = k; } });
      if (u < 0 || u === B) break;
      done.add(u);
      for (const v of BXM.adj[u]) {
        if (BXM.N[v].hub && v !== B) continue;
        const key = u < v ? u + '-' + v : v + '-' + u;
        if (!(key in W)) W[key] = 0.35 + Math.random() * 2.4;
        const nd = du + Math.hypot(BXM.N[u].x - BXM.N[v].x, BXM.N[u].y - BXM.N[v].y) * W[key];
        if (nd < (dist.has(v) ? dist.get(v)! : Infinity)) { dist.set(v, nd); prev.set(v, u); }
      }
    }
    const seg: number[] = [];
    let c: number | undefined = B;
    while (c !== undefined && c !== A) { seg.push(c); c = prev.get(c); }
    out.push(...seg.reverse());
  }
  return out;
}

/* body follows the owner's sketch: straight neck, then soft sloping shoulders */
export const BODYH = (s: number): Pt[] => [[0.2 * s, 0.86], [0.21 * s, 1.03], [0.32 * s, 1.07], [0.5 * s, 1.1], [0.68 * s, 1.16], [0.84 * s, 1.27], [0.95 * s, 1.4], [1.0 * s, 1.5]];
export const PLATE = bxEll(0, 1.25, 0.15, 0.15, 40);
