import { useEffect, useState } from 'react';
import type { ConvState, ModelInfo, MetricSnapshot } from '../types';
import type { CtxBudget, SurfacesCount } from '../hooks/useEventStream';
import { LogoMark } from './LogoMark';
import { Icon, type IconName } from './Icon';

type SurfaceId = 'sessions' | 'memory' | 'triggers' | 'tools';

// the redesign splits the four surfaces: triggers/tools live on the LEFT
// (substrate), sessions/memory on the RIGHT (activity).
const SURFACES_LEFT: { id: SurfaceId; label: string; unit: string }[] = [
  { id: 'triggers', label: 'triggers', unit: 'active' },
  { id: 'tools', label: 'tools', unit: 'wired' },
];

interface Props {
  convState: ConvState;
  wsModel: ModelInfo | null;
  ctx: CtxBudget | null;
  tokens: number;
  accessMode: string;
  onAccessMode: (m: string) => void;
  /** online/standby toggle — maps to mic on/off (drives the field standby). */
  powered: boolean;
  onTogglePower: () => void;
  /** live surface counts (shared with the activity column). */
  surfaces: SurfacesCount | null;
  activeSurface: SurfaceId;
  onSurface: (id: SurfaceId) => void;
}

interface ModelState {
  status: 'loading' | 'ready' | 'error';
  info?: ModelInfo;
}

const INITIAL_MODEL: ModelState = { status: 'loading' };
const INITIAL_METRICS: MetricSnapshot = {
  cpu: 0, mem: 0, gpu: 0, net: 0, dsk: 0, tmp: 0, uptime: '00:00:00',
};

// Accessibility profile (B5) — the prototype's "perfil" column is exactly this:
// normal (person) / no vidente (eye-off) / movilidad (wheelchair). Persisted by
// the backend (PUT /accessibility); also settable by voice. The VRAM profile
// (vram4/standby) is no longer shown here — it lives in Settings + the power row.
const ACCESS_MODES: { id: string; label: string; icon: IconName }[] = [
  { id: 'normal', label: 'normal', icon: 'person' },
  { id: 'no_vidente', label: 'no vidente', icon: 'eye-off' },
  { id: 'movilidad', label: 'movilidad', icon: 'wheelchair' },
];

function fmtK(n: number): string {
  return `${(n / 1000).toFixed(1)}k`;
}

export function SubstratePanel({
  convState, wsModel, ctx, tokens, accessMode, onAccessMode, powered, onTogglePower,
  surfaces, activeSurface, onSurface,
}: Props) {
  const [model, setModel] = useState<ModelState>(INITIAL_MODEL);
  const [metrics, setMetrics] = useState<MetricSnapshot>(INITIAL_METRICS);

  // poll real system metrics every 1.5s (same endpoint as before the reskin).
  useEffect(() => {
    let cancelled = false;
    const fetchMetrics = async () => {
      try {
        const r = await fetch('/metrics');
        if (cancelled || !r.ok) return;
        setMetrics((await r.json()) as MetricSnapshot);
      } catch { /* ignore */ }
    };
    fetchMetrics();
    const id = window.setInterval(fetchMetrics, 1500);
    return () => { cancelled = true; window.clearInterval(id); };
  }, []);

  // model info: WS event wins; otherwise poll /model until ready.
  useEffect(() => {
    if (wsModel) return;
    let cancelled = false;
    const fetchModel = async () => {
      try {
        const r = await fetch('/model');
        if (cancelled) return;
        if (r.status === 503) { setModel({ status: 'loading' }); return; }
        if (!r.ok) { setModel({ status: 'error' }); return; }
        setModel({ status: 'ready', info: (await r.json()) as ModelInfo });
      } catch {
        if (!cancelled) setModel({ status: 'error' });
      }
    };
    fetchModel();
    const id = window.setInterval(fetchModel, 5000);
    return () => { cancelled = true; window.clearInterval(id); };
  }, [wsModel]);

  const info: ModelInfo | undefined = wsModel ?? model.info;
  const loaded = info && (wsModel !== null || model.status === 'ready') ? info : null;
  const isMock = info?.runtime === 'mock';

  // global "system %" — weighted average like the prototype.
  const systemPct = Math.round(metrics.cpu * 0.35 + metrics.mem * 0.25 + metrics.gpu * 0.40);

  // mem headline: gb used when the backend reports it, else the % figure.
  const memUsedGb = metrics.mem_used_gb && metrics.mem_used_gb > 0 ? metrics.mem_used_gb : 0;
  const memText = memUsedGb > 0 ? memUsedGb.toFixed(1) : metrics.mem.toFixed(0);
  const memUnit = memUsedGb > 0 ? 'gb' : '%';

  const norm = {
    cpu: Math.min(1, metrics.cpu / 100),
    mem: Math.min(1, metrics.mem / 100),
    gpu: Math.min(1, metrics.gpu / 100),
    net: Math.min(1, metrics.net / 100),
    dsk: Math.min(1, metrics.dsk / 100),
    tmp: Math.min(1, metrics.tmp / 90),
  };
  const tmpHot = metrics.tmp > 76;

  const ctxUsed = ctx?.used ?? 0;
  const ctxTotal = ctx?.budget ?? loaded?.context_size ?? 16384;
  const ctxPct = Math.min(100, Math.round((ctxUsed / Math.max(1, ctxTotal)) * 100));

  return (
    <>
      {/* ---- left header ---- */}
      <div className="left-header">
        <div className="row">
          <span className="mark"><LogoMark size={14} state={convState} /></span>
          <span className="name">
            {loaded ? loaded.family : <span className="dim">loading…</span>}
          </span>
          <span className="dots">···</span>
          {isMock && (
            <span className="muted" style={{ fontSize: 9, letterSpacing: '0.14em' }}>MOCK</span>
          )}
        </div>
        <div className="sub">
          {loaded ? `${loaded.params} · ${loaded.runtime} · ${loaded.quant}` : '—'}
        </div>
      </div>

      {/* ---- power / standby toggle (mic on/off) ---- */}
      <button
        type="button"
        className={`power-row ${powered ? 'on' : 'off'}`}
        onClick={onTogglePower}
        aria-pressed={powered}
      >
        <span className="power-ic"><Icon name="power" size={15} /></span>
        <span className="power-lbl">{powered ? 'online' : 'standby'}</span>
        <span className="power-dot" />
      </button>

      {/* ---- system metrics (compact m-* lines, bar uses --bar-color) ---- */}
      <div className="min-block">
        <div className="sec-head"><span>system</span><span className="ref">{systemPct}%</span></div>
        <div className="m-list">
          <MetricLine label="cpu" unit="%" norm={norm.cpu} text={metrics.cpu.toFixed(0)} />
          <MetricLine label="mem" unit={memUnit} norm={norm.mem} text={memText} />
          <MetricLine label="gpu" unit="%" norm={norm.gpu} text={metrics.gpu.toFixed(0)} />
          <MetricLine label="net" unit="mb/s" norm={norm.net} text={metrics.net.toFixed(1)} />
          <MetricLine label="dsk" unit="%" norm={norm.dsk} text={metrics.dsk.toFixed(0)} />
          <MetricLine label="tmp" unit="°c" norm={norm.tmp} text={metrics.tmp.toFixed(0)} hot={tmpHot} />
        </div>
      </div>

      {/* ---- accessibility profile (icon rows) ---- */}
      <div className="min-block">
        <div className="sec-head"><span>perfil</span></div>
        <div className="profile-list" role="radiogroup" aria-label="accessibility mode">
          {ACCESS_MODES.map((m) => (
            <button
              key={m.id}
              type="button"
              role="radio"
              aria-checked={accessMode === m.id}
              className={`prow${accessMode === m.id ? ' on' : ''}`}
              onClick={() => onAccessMode(m.id)}
            >
              <span className="prow-ic"><Icon name={m.icon} size={14} /></span>
              <span className="prow-lbl">{m.label}</span>
            </button>
          ))}
        </div>
      </div>

      {/* ---- ctx budget ---- */}
      <div className="min-block">
        <div className="m-list">
          <MetricLine label="ctx" unit={` / ${fmtK(ctxTotal)}`} norm={ctxPct / 100} text={fmtK(ctxUsed)} />
        </div>
      </div>

      {/* ---- surfaces (triggers / tools — left half of the four) ---- */}
      <div className="surfaces-wrap">
        <div className="surfaces">
          {SURFACES_LEFT.map((s) => {
            const active = activeSurface === s.id;
            return (
              <div
                key={s.id}
                className={`scard${active ? ' active' : ''}`}
                onClick={() => onSurface(s.id)}
                role="button"
                tabIndex={0}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onSurface(s.id); }
                }}
                aria-pressed={active}
              >
                <div className="lbl">{s.label}</div>
                <div className="count">
                  {surfaces ? String(surfaces[s.id]) : '—'}
                  <span className="unit">{s.unit}</span>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* ---- left footer ---- */}
      <div className="left-footer">
        <KvRow k="uptime" v={metrics.uptime ?? '00:00:00'} />
        <KvRow k="tokens" v={tokens.toLocaleString()} />
      </div>
    </>
  );
}

/* ---------- internal ---------- */

interface MetricLineProps {
  label: string;
  text: string;
  unit: string;
  norm: number;
  hot?: boolean;
}

function MetricLine({ label, text, unit, norm, hot }: MetricLineProps) {
  const pct = Math.round(Math.min(1, Math.max(0, norm)) * 100);
  return (
    <div className="m-line">
      <div className="m-head">
        <span className="m-label">{label}</span>
        <span className={`m-val${hot ? ' hot' : ''}`}>
          {text}<span className="m-unit">{unit}</span>
        </span>
      </div>
      <div className={`m-bar${hot ? ' hot' : ''}`} aria-hidden="true">
        <span style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}

function KvRow({ k, v }: { k: string; v: string }) {
  return (
    <div className="kv-row">
      <span className="k">{k}</span>
      <span className="v">{v}</span>
    </div>
  );
}
