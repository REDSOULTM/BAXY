/* eslint-disable react-hooks/refs, react-hooks/purity --
 * the RAF-driven animation loop here intentionally writes animation state to
 * useRef and reads `.current` during render. that's the pattern the design
 * handoff explicitly mandates ("use refs, not state, for animation values —
 * a single forceUpdate() per RAF tick"). it's both faster than setState
 * (hundreds of updates per second avoided) and behaviourally correct because
 * force() schedules a re-render after each tick, so the values read during
 * render are always one frame fresh. the eslint rule (preview, agresive)
 * is right for typical components but wrong for this one. */
import { useEffect, useMemo, useReducer, useRef, useState } from 'react';
import type { ConvState } from '../types';
import { seededRng } from '../utils/seededRng';

/* node + edge tables — copied 1:1 from prototype/components/graph.jsx so the
   visual matches. positions are normalized 0..1; rendered into a padded box.
   re-ordering these tables changes which subgraphs light up for each state,
   which is part of the design — don't reshuffle. */

type Tag = 'context' | 'agent' | 'tools' | 'voice' | 'memory' | 'core';

interface NodeT {
  id: string;
  x: number;
  y: number;
  label?: string;
  r: number;
}

const HUBS: NodeT[] = [
  { id: 'context', x: 0.50, y: 0.13, label: 'context', r: 9 },
  { id: 'router',  x: 0.16, y: 0.32, label: 'router',  r: 9 },
  { id: 'agent',   x: 0.84, y: 0.28, label: 'agent',   r: 9 },
  { id: 'tools',   x: 0.88, y: 0.58, label: 'tools',   r: 9 },
  { id: 'memory',  x: 0.04, y: 0.56, label: 'memory',  r: 9 },
  { id: 'voice',   x: 0.58, y: 0.88, label: 'voice',   r: 10 },
];

const SMALL_DEFS: Omit<NodeT, 'r'>[] = [
  { id: 'n1',  x: 0.30, y: 0.20 },
  { id: 'n2',  x: 0.40, y: 0.08 },
  { id: 'n3',  x: 0.62, y: 0.10 },
  { id: 'n4',  x: 0.72, y: 0.18 },
  { id: 'n5',  x: 0.94, y: 0.42 },
  { id: 'n6',  x: 0.82, y: 0.74 },
  { id: 'n7',  x: 0.72, y: 0.84 },
  { id: 'n8',  x: 0.40, y: 0.94 },
  { id: 'n9',  x: 0.28, y: 0.84 },
  { id: 'n10', x: 0.06, y: 0.52 },
  { id: 'n11', x: 0.10, y: 0.42 },
  { id: 'n12', x: 0.04, y: 0.20 },
  { id: 'n13', x: 0.96, y: 0.18 },
  { id: 'n14', x: 0.96, y: 0.78 },
  { id: 'n15', x: 0.20, y: 0.70 },
  { id: 'n16', x: 0.50, y: 0.04 },
  { id: 'n17', x: 0.30, y: 0.46 },
  { id: 'n18', x: 0.66, y: 0.40 },
  { id: 'n19', x: 0.34, y: 0.66 },
  { id: 'n20', x: 0.68, y: 0.62 },
];

const ALL_NODES: NodeT[] = [
  ...HUBS,
  ...SMALL_DEFS.map((n, i) => ({ ...n, r: 4 + ((i * 13) % 5 === 0 ? 1.5 : 0) })),
];
const NODE_BY_ID: Record<string, NodeT> = Object.fromEntries(ALL_NODES.map((n) => [n.id, n]));

interface EdgeT { a: string; b: string; tag: Tag; }
const EDGES: EdgeT[] = ([
  ['context', 'n1',     'context'],
  ['context', 'n2',     'context'],
  ['context', 'n3',     'context'],
  ['context', 'n4',     'context'],
  ['context', 'n16',    'context'],
  ['n2',      'n1',     'context'],
  ['n2',      'n3',     'context'],
  ['n2',      'n16',    'context'],
  ['n3',      'n4',     'context'],
  ['n1',      'router', 'context'],
  ['n4',      'agent',  'context'],
  ['agent',   'n5',     'agent'],
  ['agent',   'n13',    'agent'],
  ['n5',      'tools',  'tools'],
  ['agent',   'tools',  'core'],
  ['tools',   'n14',    'tools'],
  ['tools',   'n6',     'tools'],
  ['n6',      'voice',  'voice'],
  ['n6',      'n7',     'voice'],
  ['n7',      'voice',  'voice'],
  ['tools',   'n7',     'tools'],
  ['voice',   'n8',     'voice'],
  ['voice',   'n9',     'voice'],
  ['n9',      'memory', 'memory'],
  ['n8',      'n9',     'voice'],
  ['memory',  'n15',    'memory'],
  ['memory',  'n10',    'memory'],
  ['memory',  'n11',    'memory'],
  ['n10',     'n11',    'memory'],
  ['n10',     'router', 'memory'],
  ['n11',     'router', 'core'],
  ['router',  'n12',    'core'],
  ['n12',     'n11',    'core'],
  ['n17',     'n18',    'core'],
  ['n18',     'n20',    'core'],
  ['n20',     'n19',    'core'],
  ['n19',     'n17',    'core'],
  ['n17',     'router', 'core'],
  ['n17',     'context','core'],
  ['n18',     'context','core'],
  ['n18',     'agent',  'core'],
  ['n20',     'tools',  'core'],
  ['n20',     'voice',  'voice'],
  ['n19',     'voice',  'voice'],
  ['n19',     'memory', 'memory'],
] as Array<[string, string, Tag]>).map(([a, b, tag]) => ({ a, b, tag }));

const CORE_FEEDS = ['n17', 'n18', 'n19', 'n20'];

const STATE_EDGES: Record<ConvState, EdgeT[]> = {
  standby: [],
  idle: EDGES,
  listening: EDGES.filter((e) => e.tag === 'voice' || e.tag === 'core'),
  thinking: EDGES.filter((e) => e.tag === 'core' || e.tag === 'memory' || e.tag === 'context' || e.tag === 'agent'),
  speaking: EDGES.filter((e) => e.tag === 'voice' || e.tag === 'tools' || e.tag === 'core'),
};

const STATE_SPAWN_RATE: Record<ConvState, number> = {
  standby: 0,
  idle: 0.8,
  listening: 5,
  thinking: 12,
  speaking: 7,
};

interface CorePalette {
  halo: string; mid: string; inner: string; hot: string;
  labelColor: string; pulseSpeed: number;
}
const CORE_COLORS: Record<ConvState, CorePalette> = {
  standby:   { halo: '#3F4860', mid: '#5B6580', inner: '#8B95A8', hot: '#D8DCE6', labelColor: '#5B6580', pulseSpeed: 0.8 },
  idle:      { halo: '#7A1E2B', mid: '#B83A4A', inner: '#E55366', hot: '#F5C6CC', labelColor: '#7A1E2B', pulseSpeed: 1.1 },
  listening: { halo: '#B83A4A', mid: '#E55366', inner: '#F5C6CC', hot: '#FFE9EC', labelColor: '#B83A4A', pulseSpeed: 2.4 },
  thinking:  { halo: '#1B2A5E', mid: '#2E4BA0', inner: '#5B7FDB', hot: '#B8C6E8', labelColor: '#2E4BA0', pulseSpeed: 3.4 },
  speaking:  { halo: '#6B5A2F', mid: '#C9A66B', inner: '#E8C98E', hot: '#F5E6C0', labelColor: '#8A7A4A', pulseSpeed: 2.2 },
};

function orbitTint(state: ConvState, isRed: boolean): string {
  if (state === 'standby')   return isRed ? '#5B6580' : '#3F4860';
  if (state === 'thinking')  return isRed ? '#5B7FDB' : '#2E4BA0';
  if (state === 'speaking')  return isRed ? '#C9A66B' : '#8A7A4A';
  if (state === 'listening') return isRed ? '#E55366' : '#B83A4A';
  return isRed ? '#B83A4A' : '#5B7FDB';
}

function pulseTint(state: ConvState): { glow: string; dot: string } {
  if (state === 'thinking') return { glow: 'url(#pulseGlowBlue)', dot: '#7B95D9' };
  if (state === 'speaking') return { glow: 'url(#pulseGlowGold)', dot: '#E8C98E' };
  return { glow: 'url(#pulseGlow)', dot: '#E55366' };
}

interface NodeTint { outerFill: string; innerFill: string; glow: string; labelFill: string; }

/** colour table for the 26 mesh nodes per state. extracted out of the render
 *  body so each branch produces a fresh object instead of mutating defaults
 *  (which eslint flags as no-useless-assignment). */
function nodeTint(state: ConvState, id: string, isHub: boolean, isInner: boolean): NodeTint {
  if (state === 'thinking') {
    return {
      outerFill: isInner ? '#1B2A5E' : '#2E4BA0',
      innerFill: '#7B95D9',
      glow: 'url(#nodeGlow)',
      labelFill: isHub ? '#7B95D9' : '#5B6580',
    };
  }
  if (state === 'speaking') {
    return {
      outerFill: isInner ? '#6B5A2F' : '#8A7A4A',
      innerFill: '#E8C98E',
      glow: 'url(#hubGoldGlow)',
      labelFill: isHub ? '#C9A66B' : '#5B6580',
    };
  }
  if (state === 'listening') {
    return {
      outerFill: isInner ? '#7A1E2B' : '#B83A4A',
      innerFill: '#E55366',
      glow: 'url(#hubRedGlow)',
      labelFill: isHub ? '#E55366' : '#5B6580',
    };
  }
  if (state === 'standby') {
    return {
      outerFill: isInner ? '#3F4860' : '#5B6580',
      innerFill: '#8B95A8',
      glow: 'url(#nodeStandbyGlow)',
      labelFill: '#3F4860',
    };
  }
  // idle — voice/memory hubs glow red, the rest stay blue
  const hubRed = isHub && (id === 'voice' || id === 'memory');
  return {
    outerFill: isInner ? '#7A1E2B' : hubRed ? '#B83A4A' : '#2E4BA0',
    innerFill: hubRed ? '#E55366' : '#5B7FDB',
    glow: hubRed ? 'url(#hubRedGlow)' : 'url(#nodeGlow)',
    labelFill: hubRed ? '#B83A4A' : '#5B6580',
  };
}

const NEBULA_TINT: Record<ConvState, { a: string; b: string }> = {
  standby:   { a: '#3F4860', b: '#5B6580' },
  idle:      { a: '#1B2A5E', b: '#7A1E2B' },
  listening: { a: '#6B5A2F', b: '#1B2A5E' },
  thinking:  { a: '#7A1E2B', b: '#6B5A2F' },
  speaking:  { a: '#1B2A5E', b: '#7A1E2B' },
};

interface Star {
  x: number; y: number; r: number; op: number; color: string; twink: number;
}
function useStars(w: number, h: number): Star[] {
  return useMemo(() => {
    const rng = seededRng(91);
    const stars: Star[] = [];
    const reach = Math.max(w, h) * 1.5;
    const cx = w / 2;
    const cy = h / 2;
    const n = Math.round((reach * reach) / 2400);
    for (let i = 0; i < n; i++) {
      const t = rng();
      const dx = (rng() - 0.5) * 2 * reach;
      const dy = (rng() - 0.5) * 2 * reach;
      stars.push({
        x: cx + dx,
        y: cy + dy,
        r: 0.25 + rng() * 0.85,
        op: 0.12 + rng() * 0.55,
        color: t < 0.10 ? '#B83A4A' : t < 0.18 ? '#5B7FDB' : '#D8DCE6',
        twink: rng() * 6.28,
      });
    }
    return stars;
  }, [w, h]);
}

interface OrbitParticle { theta: number; r: number; size: number; op: number; red: boolean; }
function useOrbitRing(minR: number, maxR: number): OrbitParticle[] {
  return useMemo(() => {
    const rng = seededRng(311);
    const arr: OrbitParticle[] = [];
    for (let i = 0; i < 64; i++) {
      arr.push({
        theta: rng() * Math.PI * 2,
        r: minR + rng() * (maxR - minR),
        size: 0.8 + rng() * 1.3,
        op: 0.45 + rng() * 0.45,
        red: rng() < 0.7,
      });
    }
    return arr;
  }, [minR, maxR]);
}

interface Pulse { edgeIdx: number; t: number; speed: number; reverse: boolean; }
interface Tracer { active: boolean; t: number; startedAt: number; path: string[]; }
interface LastTurn { endedAt: number; tags: Set<string>; }

interface Props {
  state: ConvState;
}

const NODE_COUNT = ALL_NODES.length;
const EDGE_COUNT = EDGES.length;

export function NeuralGraph({ state }: Props) {
  const wrapRef = useRef<HTMLDivElement | null>(null);
  const [size, setSize] = useState({ w: 720, h: 480 });
  const pulsesRef = useRef<Pulse[]>([]);
  const rotationRef = useRef(0);
  const galaxyRotRef = useRef(0);
  const nebulaRotRef = useRef(0);
  const corePulseRef = useRef(0);
  const prevStateRef = useRef<ConvState>('idle');
  const lastTurnRef = useRef<LastTurn>({ endedAt: 0, tags: new Set() });
  const tracerRef = useRef<Tracer>({ active: false, t: 0, startedAt: 0, path: [] });
  const lastSpawnRef = useRef(0);
  // stateRef mirrors `state` so the RAF tick reads the latest value without
  // forcing the effect to re-subscribe on every transition (which would
  // restart the loop, lose `prev` time, and stutter for one frame).
  // assigned in an effect rather than at render time so we don't violate
  // react's "no ref writes during render" rule.
  const stateRef = useRef<ConvState>(state);
  useEffect(() => { stateRef.current = state; }, [state]);

  // single forced re-render per frame — much cheaper than setState'ing positions.
  const [, force] = useReducer((x: number) => x + 1, 0);

  useEffect(() => {
    if (!wrapRef.current) return;
    const ro = new ResizeObserver((ents) => {
      for (const e of ents) {
        const cr = e.contentRect;
        setSize({ w: Math.max(200, cr.width), h: Math.max(160, cr.height) });
      }
    });
    ro.observe(wrapRef.current);
    return () => ro.disconnect();
  }, []);

  // state transition side effects: trigger afterglow on edges, fire the tracer
  useEffect(() => {
    const prev = prevStateRef.current;
    if ((state === 'idle' || state === 'standby') && (prev === 'speaking' || prev === 'thinking')) {
      lastTurnRef.current = {
        endedAt: performance.now(),
        tags: new Set(['core', 'memory', 'context', 'agent', 'voice', 'tools']),
      };
    }
    if (state === 'thinking' && prev !== 'thinking') {
      tracerRef.current = {
        active: true,
        t: 0,
        startedAt: performance.now(),
        path: ['voice', 'router', 'context', 'n4', 'memory', 'n11', 'router', 'agent', 'n7', 'tools', 'n6', 'voice'],
      };
    }
    prevStateRef.current = state;
  }, [state]);

  // A sleeping scheduler replaces the permanent RAF loop: idle breathes at
  // 4 Hz, active states remain fluid at 30 Hz, and hidden work drops to 1 Hz. State
  // transitions are read through stateRef so changing chips never restarts it.
  useEffect(() => {
    let timer = 0;
    let prev = performance.now();
    const schedule = () => {
      const s = stateRef.current;
      const active = s === 'listening' || s === 'thinking' || s === 'speaking';
      const interval = document.hidden ? 1000 : 1000 / (active ? 30 : 4);
      timer = window.setTimeout(() => tick(performance.now()), interval);
    };
    const tick = (now: number) => {
      const s = stateRef.current;
      const active = s === 'listening' || s === 'thinking' || s === 'speaking';
      if (document.hidden) {
        prev = now;
        schedule();
        return;
      }
      const dt = Math.min(active ? 0.05 : 0.25, (now - prev) / 1000);
      prev = now;

      // pulses
      const next: Pulse[] = [];
      const arr = pulsesRef.current;
      for (let i = 0; i < arr.length; i++) {
        const p = arr[i];
        p.t += p.speed * dt;
        if (p.t < 1) next.push(p);
      }
      pulsesRef.current = next;

      // tracer
      if (tracerRef.current.active) {
        tracerRef.current.t += dt / 5.0;
        if (tracerRef.current.t >= 1) tracerRef.current.active = false;
      }

      const rate = STATE_SPAWN_RATE[s];
      lastSpawnRef.current += dt * rate;
      while (lastSpawnRef.current >= 1) {
        lastSpawnRef.current -= 1;
        const pool = STATE_EDGES[s];
        if (pool.length > 0) {
          const edge = pool[Math.floor(Math.random() * pool.length)];
          const idx = EDGES.indexOf(edge);
          if (idx >= 0) {
            pulsesRef.current.push({
              edgeIdx: idx,
              t: 0,
              speed: 0.45 + Math.random() * 0.55,
              reverse: Math.random() < 0.35,
            });
          }
        }
      }

      const rotSpeed = s === 'standby' ? 1.5
        : s === 'idle' ? 4
        : s === 'listening' ? 9
        : s === 'thinking' ? 22
        : s === 'speaking' ? 14 : 4;
      rotationRef.current = (rotationRef.current + rotSpeed * dt) % 360;

      const galSpeed = s === 'standby' ? 0.15
        : s === 'idle' ? 0.30
        : s === 'listening' ? 0.55
        : s === 'thinking' ? 1.20
        : s === 'speaking' ? 0.70 : 0.30;
      galaxyRotRef.current = (galaxyRotRef.current + galSpeed * dt) % 360;
      nebulaRotRef.current = (nebulaRotRef.current - galSpeed * 0.4 * dt) % 360;

      corePulseRef.current = now / 1000;

      force();
      schedule();
    };
    const onVisibilityChange = () => {
      window.clearTimeout(timer);
      prev = performance.now();
      schedule();
    };
    document.addEventListener('visibilitychange', onVisibilityChange);
    schedule();
    return () => {
      document.removeEventListener('visibilitychange', onVisibilityChange);
      window.clearTimeout(timer);
    };
  }, []);

  const { w, h } = size;
  const pad = 14;
  const inW = w - pad * 2;
  const inH = h - pad * 2;
  const px = (n: NodeT) => pad + n.x * inW;
  const py = (n: NodeT) => pad + n.y * inH;
  const cx = pad + 0.5 * inW;
  const cy = pad + 0.5 * inH;
  const coreR = Math.max(48, Math.min(112, Math.min(inW, inH) * 0.18));
  const ringInner = coreR * 2.4;
  const ringOuter = coreR * 3.6;

  const stars = useStars(w, h);
  const orbit = useOrbitRing(ringInner, ringOuter);

  const litTags: Set<string> = {
    standby: new Set<string>(),
    idle: new Set<string>(),
    listening: new Set<string>(['voice']),
    thinking: new Set<string>(['core', 'memory', 'context', 'agent']),
    speaking: new Set<string>(['voice', 'tools', 'core']),
  }[state];

  const coreC = CORE_COLORS[state];
  const nebC = NEBULA_TINT[state];

  // snapshot the animation refs ONCE per render. reading `.current` inside
  // the JSX trips react's "no refs during render" rule (and is also slower
  // because each access can't be optimized). the RAF loop calls force() so
  // these snapshots are always fresh on the next frame.
  const tNow = corePulseRef.current;
  const nebulaRot = nebulaRotRef.current;
  const galaxyRot = galaxyRotRef.current;
  const rotation = rotationRef.current;
  const pulses = pulsesRef.current;
  const tracer = tracerRef.current;
  const lastTurn = lastTurnRef.current;
  // performance.now() during render is impure; sample it once and reuse below.
  const renderNow = typeof performance !== 'undefined' ? performance.now() : 0;

  const corePulse = state === 'standby'
    ? 0.35 + Math.sin(tNow * coreC.pulseSpeed) * 0.05
    : 0.55 + Math.sin(tNow * coreC.pulseSpeed) * 0.18;
  const coreHotPulse = state === 'standby'
    ? 0.4 + Math.sin(tNow * 1.5) * 0.1
    : 0.7 + Math.sin(tNow * coreC.pulseSpeed * 1.8) * 0.25;
  const pulseStyle = pulseTint(state);

  return (
    <div className="field-stage" ref={wrapRef}>
      <svg
        width={w}
        height={h}
        style={{ display: 'block' }}
        role="img"
        aria-label="agent state visualization"
      >
        <defs>
          <linearGradient id="nebA" x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%"  stopColor={nebC.a} stopOpacity="0" />
            <stop offset="50%" stopColor={nebC.a} stopOpacity="0.22" />
            <stop offset="100%" stopColor={nebC.a} stopOpacity="0" />
          </linearGradient>
          <linearGradient id="nebB" x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%"  stopColor={nebC.b} stopOpacity="0" />
            <stop offset="50%" stopColor={nebC.b} stopOpacity="0.18" />
            <stop offset="100%" stopColor={nebC.b} stopOpacity="0" />
          </linearGradient>
          <radialGradient id="coreHalo" cx="50%" cy="50%" r="50%">
            <stop offset="0%"  stopColor={coreC.inner} stopOpacity="0.7" />
            <stop offset="30%" stopColor={coreC.mid}   stopOpacity="0.45" />
            <stop offset="65%" stopColor={coreC.halo}  stopOpacity="0.2" />
            <stop offset="100%" stopColor={coreC.halo} stopOpacity="0" />
          </radialGradient>
          <radialGradient id="coreInner" cx="50%" cy="50%" r="50%">
            <stop offset="0%"  stopColor={coreC.hot}   stopOpacity="0.95" />
            <stop offset="40%" stopColor={coreC.inner} stopOpacity="0.6" />
            <stop offset="100%" stopColor={coreC.mid}  stopOpacity="0" />
          </radialGradient>
          <radialGradient id="nodeGlow" cx="50%" cy="50%" r="50%">
            <stop offset="0%" stopColor="#5B7FDB" stopOpacity="0.45" />
            <stop offset="60%" stopColor="#2E4BA0" stopOpacity="0.15" />
            <stop offset="100%" stopColor="#2E4BA0" stopOpacity="0" />
          </radialGradient>
          <radialGradient id="hubRedGlow" cx="50%" cy="50%" r="50%">
            <stop offset="0%" stopColor="#E55366" stopOpacity="0.55" />
            <stop offset="60%" stopColor="#B83A4A" stopOpacity="0.18" />
            <stop offset="100%" stopColor="#B83A4A" stopOpacity="0" />
          </radialGradient>
          <radialGradient id="hubGoldGlow" cx="50%" cy="50%" r="50%">
            <stop offset="0%" stopColor="#E8C98E" stopOpacity="0.55" />
            <stop offset="60%" stopColor="#8A7A4A" stopOpacity="0.18" />
            <stop offset="100%" stopColor="#8A7A4A" stopOpacity="0" />
          </radialGradient>
          <radialGradient id="nodeStandbyGlow" cx="50%" cy="50%" r="50%">
            <stop offset="0%" stopColor="#8B95A8" stopOpacity="0.35" />
            <stop offset="60%" stopColor="#5B6580" stopOpacity="0.10" />
            <stop offset="100%" stopColor="#5B6580" stopOpacity="0" />
          </radialGradient>
          <radialGradient id="pulseGlow" cx="50%" cy="50%" r="50%">
            <stop offset="0%"  stopColor="#E55366" stopOpacity="0.85" />
            <stop offset="100%" stopColor="#B83A4A" stopOpacity="0" />
          </radialGradient>
          <radialGradient id="pulseGlowBlue" cx="50%" cy="50%" r="50%">
            <stop offset="0%"  stopColor="#7B95D9" stopOpacity="0.85" />
            <stop offset="100%" stopColor="#2E4BA0" stopOpacity="0" />
          </radialGradient>
          <radialGradient id="pulseGlowGold" cx="50%" cy="50%" r="50%">
            <stop offset="0%"  stopColor="#E8C98E" stopOpacity="0.85" />
            <stop offset="100%" stopColor="#8A7A4A" stopOpacity="0" />
          </radialGradient>
          <radialGradient id="tracerGlow" cx="50%" cy="50%" r="50%">
            <stop offset="0%"  stopColor="#FFF6E0" stopOpacity="1" />
            <stop offset="35%" stopColor="#F5E6C0" stopOpacity="0.7" />
            <stop offset="100%" stopColor="#F5E6C0" stopOpacity="0" />
          </radialGradient>
        </defs>

        {/* layer 1 — nebula bands (counter-drift) */}
        <g opacity="0.5" transform={`rotate(${nebulaRot.toFixed(2)} ${cx} ${cy})`}>
          <path d={`M ${-20} ${h * 0.30} Q ${w * 0.30} ${h * 0.22} ${w * 0.55} ${h * 0.34} T ${w + 20} ${h * 0.28}`}
                stroke="url(#nebA)" strokeWidth={70} fill="none" />
          <path d={`M ${-20} ${h * 0.70} Q ${w * 0.35} ${h * 0.78} ${w * 0.65} ${h * 0.66} T ${w + 20} ${h * 0.74}`}
                stroke="url(#nebB)" strokeWidth={90} fill="none" />
          <path d={`M ${-20} ${h * 0.52} Q ${w * 0.50} ${h * 0.42} ${w + 20} ${h * 0.56}`}
                stroke="url(#nebA)" strokeWidth={50} fill="none" opacity="0.6" />
        </g>

        {/* layer 2 — starfield (galaxy rotation) */}
        <g transform={`rotate(${galaxyRot.toFixed(2)} ${cx} ${cy})`}>
          {stars.map((s, i) => {
            const tw = 0.85 + Math.sin(tNow * 0.9 + s.twink) * 0.15;
            return (
              <circle
                key={i}
                cx={s.x.toFixed(1)}
                cy={s.y.toFixed(1)}
                r={s.r.toFixed(2)}
                fill={s.color}
                opacity={(s.op * tw).toFixed(3)}
              />
            );
          })}
        </g>

        {/* layer 3 — mesh edges (+ afterglow on last-turn tags) */}
        <g>
          {EDGES.map((e, i) => {
            const a = NODE_BY_ID[e.a];
            const b = NODE_BY_ID[e.b];
            const lit = litTags.has(e.tag);
            const turnAge = (renderNow - lastTurn.endedAt) / 1000;
            const inLastTurn = lastTurn.tags.has(e.tag) && turnAge < 5;
            const trail = inLastTurn ? Math.max(0, 1 - turnAge / 5) : 0;
            const baseStroke = lit ? '#3F4F7A' : '#2A3550';
            const stroke = trail > 0 ? '#7A1E2B' : baseStroke;
            const op = lit ? 0.95 : trail > 0 ? 0.45 + trail * 0.5 : 0.65;
            return (
              <line
                key={i}
                x1={px(a)} y1={py(a)}
                x2={px(b)} y2={py(b)}
                stroke={stroke}
                strokeWidth={1}
                opacity={op}
              />
            );
          })}
        </g>

        {/* layer 4 — core feed lines */}
        <g>
          {CORE_FEEDS.map((id) => {
            const n = NODE_BY_ID[id];
            return (
              <line
                key={id}
                x1={px(n)} y1={py(n)}
                x2={cx} y2={cy}
                stroke={coreC.halo}
                strokeWidth={1}
                opacity={state === 'standby' ? 0.25 : 0.45}
                strokeDasharray="2 3"
              />
            );
          })}
        </g>

        {/* layer 5 — rotating orbit ring */}
        <g transform={`rotate(${rotation.toFixed(2)} ${cx} ${cy})`}>
          {orbit.map((p, i) => {
            const x = cx + p.r * Math.cos(p.theta);
            const y = cy + p.r * Math.sin(p.theta);
            return (
              <circle
                key={i}
                cx={x.toFixed(2)} cy={y.toFixed(2)}
                r={p.size.toFixed(2)}
                fill={orbitTint(state, p.red)}
                opacity={(p.op * (state === 'standby' ? 0.55 : 1)).toFixed(2)}
              />
            );
          })}
        </g>

        {/* layer 6 — central core */}
        <g>
          <circle cx={cx} cy={cy} r={coreR * 2.0} fill="url(#coreHalo)" opacity={corePulse.toFixed(3)} />
          <circle cx={cx} cy={cy} r={coreR * 1.0} fill="url(#coreInner)" opacity={state === 'standby' ? 0.55 : 0.95} />
          <circle cx={cx} cy={cy} r={coreR * 0.32} fill={coreC.inner} opacity={state === 'standby' ? 0.55 : 0.92} />
          <circle cx={cx} cy={cy} r={coreR * 0.12} fill={coreC.hot} opacity={coreHotPulse.toFixed(3)} />
          <text
            x={cx} y={cy + coreR * 1.85}
            textAnchor="middle"
            fill={coreC.labelColor}
            fontFamily="JetBrains Mono, monospace"
            fontSize={Math.max(18, coreR * 0.72)}
            fontWeight={500}
            letterSpacing="0.28em"
            opacity={state === 'standby' ? 0.6 : 0.95}
          >
            {state.charAt(0).toUpperCase() + state.slice(1)}
          </text>
        </g>

        {/* layer 7 — nodes (state-tinted) */}
        <g>
          {ALL_NODES.map((n) => {
            const isHub = !!HUBS.find((h) => h.id === n.id);
            const isInner = ['n17', 'n18', 'n19', 'n20'].includes(n.id);
            const { outerFill, innerFill, glow, labelFill } = nodeTint(state, n.id, isHub, isInner);

            return (
              <g key={n.id}>
                {isHub && (
                  <circle cx={px(n)} cy={py(n)} r={n.r * 2.2} fill={glow} />
                )}
                <circle
                  cx={px(n)} cy={py(n)}
                  r={n.r}
                  fill={outerFill}
                  opacity={isHub ? 0.95 : 0.82}
                />
                {isHub && (
                  <circle cx={px(n)} cy={py(n)} r={n.r * 0.45} fill={innerFill} opacity={0.85} />
                )}
                {isHub && n.label && (
                  <text
                    x={px(n)} y={py(n) + n.r + 14}
                    textAnchor="middle"
                    fill={labelFill}
                    fontFamily="Inter, sans-serif"
                    fontSize={10}
                    fontWeight={500}
                    letterSpacing="0.02em"
                  >
                    {n.label}
                  </text>
                )}
              </g>
            );
          })}
        </g>

        {/* layer 8 — signal pulses (head + 7-segment trail) */}
        <g>
          {pulses.map((p, i) => {
            const edge = EDGES[p.edgeIdx];
            if (!edge) return null;
            const a = NODE_BY_ID[edge.a];
            const b = NODE_BY_ID[edge.b];
            const dx = px(b) - px(a);
            const dy = py(b) - py(a);
            const TRAIL = 7;
            const trailEls: React.ReactNode[] = [];
            for (let k = 1; k <= TRAIL; k++) {
              const tk = p.t - k * 0.028;
              if (tk < 0) break;
              const tt = p.reverse ? 1 - tk : tk;
              const tx = px(a) + dx * tt;
              const ty = py(a) + dy * tt;
              const fade = Math.sin(tk * Math.PI);
              const decay = 1 - k / (TRAIL + 1);
              trailEls.push(
                <circle
                  key={`tr-${i}-${k}`}
                  cx={tx.toFixed(2)} cy={ty.toFixed(2)}
                  r={(1.6 * decay).toFixed(2)}
                  fill={pulseStyle.dot}
                  opacity={(fade * decay * 0.55).toFixed(3)}
                />
              );
            }
            const tHead = p.reverse ? 1 - p.t : p.t;
            const x = px(a) + dx * tHead;
            const y = py(a) + dy * tHead;
            const fade = Math.sin(p.t * Math.PI);
            return (
              <g key={i}>
                {trailEls}
                <circle cx={x} cy={y} r={7} fill={pulseStyle.glow} opacity={fade * 0.95} />
                <circle cx={x} cy={y} r={2.0} fill={pulseStyle.dot} opacity={fade} />
              </g>
            );
          })}
        </g>

        {/* layer 9 — tracer (ivory, only during thinking) */}
        {tracer.active && tracer.path.length > 1 && (
          <TracerLayer path={tracer.path} t={tracer.t} px={px} py={py} />
        )}
      </svg>
    </div>
  );
}

function TracerLayer({
  path, t, px, py,
}: {
  path: string[];
  t: number;
  px: (n: NodeT) => number;
  py: (n: NodeT) => number;
}) {
  const segs = path.length - 1;
  const tGlobal = Math.max(0, Math.min(1, t));
  const tEased = tGlobal < 0.5
    ? 2 * tGlobal * tGlobal
    : 1 - Math.pow(-2 * tGlobal + 2, 2) / 2;
  const segPos = tEased * segs;
  const segIdx = Math.min(segs - 1, Math.floor(segPos));
  const segT = segPos - segIdx;
  const a = NODE_BY_ID[path[segIdx]];
  const b = NODE_BY_ID[path[segIdx + 1]];
  if (!a || !b) return null;
  const x = px(a) + (px(b) - px(a)) * segT;
  const y = py(a) + (py(b) - py(a)) * segT;

  const TRAIL_LEN = 22;
  const TRAIL_STEP = 0.012;
  const trailEls: React.ReactNode[] = [];
  for (let k = 1; k <= TRAIL_LEN; k++) {
    const tBack = tEased - k * TRAIL_STEP;
    if (tBack <= 0) break;
    const sp = tBack * segs;
    const si = Math.min(segs - 1, Math.floor(sp));
    const st = sp - si;
    const pa = NODE_BY_ID[path[si]];
    const pb = NODE_BY_ID[path[si + 1]];
    if (!pa || !pb) continue;
    const tx = px(pa) + (px(pb) - px(pa)) * st;
    const ty = py(pa) + (py(pb) - py(pa)) * st;
    const decay = 1 - k / (TRAIL_LEN + 1);
    trailEls.push(
      <circle
        key={`tracer-tr-${k}`}
        cx={tx.toFixed(2)} cy={ty.toFixed(2)}
        r={(2.4 * decay).toFixed(2)}
        fill="#F5E6C0"
        opacity={(decay * 0.6).toFixed(3)}
      />
    );
  }
  const headFade =
    tGlobal < 0.05 ? tGlobal / 0.05
    : tGlobal > 0.95 ? (1 - tGlobal) / 0.05
    : 1;

  return (
    <g>
      {trailEls}
      <circle cx={x} cy={y} r={18} fill="url(#tracerGlow)" opacity={0.7 * headFade} />
      <circle cx={x} cy={y} r={9}  fill="url(#tracerGlow)" opacity={0.95 * headFade} />
      {/* tracer head + pure-white nucleus per the detailed neural-graph spec.
         this is the ONLY place pure #FFFFFF is allowed — it's the universal
         contrast pixel that pops against carmesí/blue/gold cores. */}
      <circle cx={x} cy={y} r={5}  fill="#FFF6E0" opacity={headFade} />
      <circle cx={x} cy={y} r={2.2} fill="#FFFFFF" opacity={headFade} />
    </g>
  );
}

export { NODE_COUNT, EDGE_COUNT };
