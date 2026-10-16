import { useEffect, useState } from 'react';
import type { ConvState, ModelInfo, MetricSnapshot } from '../types';
import type { SurfacesCount } from '../hooks/useEventStream';
import { LogoMark } from './LogoMark';
import { Icon, type IconName } from './Icon';
import type { AccessMode, ConfirmationPolicy } from '../App';

type SurfaceId = 'sessions' | 'memory' | 'tools';

// the redesign splits the surfaces: tools lives on the LEFT (substrate),
// sessions/memory on the RIGHT (activity).
const SURFACES_LEFT: { id: SurfaceId; label: string; unit: string }[] = [
  { id: 'tools', label: 'tools', unit: 'wired' },
];

interface Props {
  convState: ConvState;
  wsModel: ModelInfo | null;
  accessMode: AccessMode;
  onAccessMode: (m: AccessMode) => void;
  /** the profile's confirmation policy; bypass is switched on only after the
   *  explicit confirmation below, and off with one press. */
  confirmation: ConfirmationPolicy;
  onConfirmation: (p: ConfirmationPolicy) => void;
  /** is the assistant alive (backend reachable)? Drives the voice row's tooltip.
   *  Independent of the mic: text mode keeps the app online with voice off. */
  online: boolean;
  /** is the mic loop up? Drives the voice toggle's on/off state. */
  voiceOn: boolean;
  /** left-click the voice toggle: mute/unmute the mic (listening↔off). */
  onToggleVoice: () => void;
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
  cpu: null, mem: null, gpu: null, dsk: null, uptime: null,
};

// A percentage as the row shows it, or «—» when the PC did not give it.
const shown = (value: number | null) => (value === null ? '—' : value.toFixed(0));

// The interface's mode (identity: central in the engine, a mode in the
// interface): normal or accessible, which changes only the presentation —
// larger text, high contrast, visible focus, no motion. Persisted in the
// profile (PUT /accessibility) and switched by chat as well.
const ACCESS_MODES: { id: AccessMode; label: string; icon: IconName }[] = [
  { id: 'normal', label: 'normal', icon: 'person' },
  { id: 'accessible', label: 'accesible', icon: 'eye-off' },
];

function fmtK(n: number): string {
  return `${(n / 1000).toFixed(1)}k`;
}

export function SubstratePanel({
  convState, wsModel, accessMode, onAccessMode, confirmation, onConfirmation,
  online, voiceOn, onToggleVoice, surfaces, activeSurface, onSurface,
}: Props) {
  const [model, setModel] = useState<ModelState>(INITIAL_MODEL);
  // the conscious gesture: switching bypass on asks here first.
  const [bypassAsked, setBypassAsked] = useState(false);
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

  // global "system %" — weighted average like the prototype; unknown without every reading.
  const systemPct = metrics.cpu === null || metrics.mem === null || metrics.gpu === null
    ? null
    : Math.round(metrics.cpu * 0.35 + metrics.mem * 0.25 + metrics.gpu * 0.40);

  // mem headline: gb used when the backend reports it, else the % figure; «—» when neither was read.
  const memUsedGb = metrics.mem_used_gb && metrics.mem_used_gb > 0 ? metrics.mem_used_gb : 0;
  const memText = memUsedGb > 0 ? memUsedGb.toFixed(1) : shown(metrics.mem);
  const memUnit = memUsedGb > 0 ? 'gb' : metrics.mem === null ? '' : '%';

  const norm = {
    cpu: Math.min(1, (metrics.cpu ?? 0) / 100),
    mem: Math.min(1, (metrics.mem ?? 0) / 100),
    gpu: Math.min(1, (metrics.gpu ?? 0) / 100),
    dsk: Math.min(1, (metrics.dsk ?? 0) / 100),
  };

  return (
    <>
      {/* ---- left header ---- */}
      <div className="left-header">
        <div className="row">
          <span className="mark"><LogoMark size={14} state={convState} /></span>
          <span className="name">
            {loaded ? loaded.family : <span className="dim">loading…</span>}
          </span>
        </div>
        <div className="sub">
          {loaded ? `${loaded.params} · ${loaded.runtime}` : '—'}
        </div>
      </div>

      {/* ---- voice toggle. Muting the mic does NOT power the app down: the row
           and its dot follow VOICE only, while the tooltip still reports
           whether the assistant is online (backend reachable), so text mode
           stays alive with the mic off. ---- */}
      <button
        type="button"
        className={`power-row ${voiceOn ? 'on' : 'off'}`}
        onClick={onToggleVoice}
        aria-pressed={voiceOn}
        aria-label={voiceOn ? 'voice on — click to mute' : 'voice off — click to listen'}
        data-tip={online ? 'asistente online' : 'asistente sin conexión'}
      >
        <span className="power-ic"><Icon name={voiceOn ? 'mic' : 'mic-off'} size={15} /></span>
        <span className="power-lbl">{voiceOn ? 'voz' : 'voz off'}</span>
        <span className="power-dot" />
      </button>

      {/* ---- system metrics (compact m-* lines, bar uses --bar-color) ---- */}
      <div className="min-block">
        <div className="sec-head"><span>system</span><span className="ref">{systemPct === null ? '—' : `${systemPct}%`}</span></div>
        <div className="m-list">
          <MetricLine label="cpu" unit={metrics.cpu === null ? '' : '%'} norm={norm.cpu} text={shown(metrics.cpu)} />
          <MetricLine label="mem" unit={memUnit} norm={norm.mem} text={memText} />
          <MetricLine label="gpu" unit={metrics.gpu === null ? '' : '%'} norm={norm.gpu} text={shown(metrics.gpu)} />
          <MetricLine label="dsk" unit={metrics.dsk === null ? '' : '%'} norm={norm.dsk} text={shown(metrics.dsk)} />
        </div>
      </div>

      {/* ---- interface mode (icon rows) ---- */}
      <div className="min-block">
        <div className="sec-head"><span>perfil</span></div>
        <div className="profile-list" role="radiogroup" aria-label="modo de la interfaz">
          {ACCESS_MODES.map((m) => {
            const selected = accessMode === m.id;
            return (
              <button
                key={m.id}
                type="button"
                role="radio"
                aria-checked={selected}
                className={`prow${selected ? ' on' : ''}`}
                onClick={() => onAccessMode(m.id)}
              >
                <span className="prow-ic"><Icon name={m.icon} size={14} /></span>
                <span className="prow-lbl">{m.label}</span>
              </button>
            );
          })}
        </div>
      </div>

      {/* ---- confirmations: normal, or bypass after an explicit yes here ---- */}
      <div className="min-block">
        <div className="sec-head"><span>confirmaciones</span></div>
        {confirmation === 'bypass' ? (
          <button
            type="button"
            className="prow bypass on"
            aria-pressed={true}
            aria-label="modo bypass encendido: no pido confirmación en lo que me pides; lo que te proponga por mi cuenta sigue esperando tu sí y borrar en el panel de memoria sigue pidiendo confirmar. pulsa para apagarlo"
            onClick={() => onConfirmation('normal')}
          >
            <span className="prow-ic"><Icon name="bolt" size={14} /></span>
            <span className="prow-lbl">bypass · apagar</span>
          </button>
        ) : bypassAsked ? (
          <div
            className="bypass-ask"
            role="alertdialog"
            aria-labelledby="bypass-ask-q"
            aria-describedby="bypass-ask-d"
          >
            <p id="bypass-ask-q" className="bypass-ask-q">¿encender bypass?</p>
            <p id="bypass-ask-d" className="bypass-ask-d">
              no te pediré confirmación en lo que me pidas: ni para borrar o mandar a la Papelera,
              sobrescribir o cerrar sin guardar, ni para instalar o desinstalar, comprar,
              enviar mensajes o correos, publicar, unirte a una llamada, crear eventos en tu
              calendario o ejecutar comandos que cambian algo, hasta que lo apagues aquí.
              lo que yo propongo por mi cuenta sigue esperando tu sí, y borrar en el panel de
              memoria sigue pidiendo confirmar.
            </p>
            <div className="bypass-ask-actions">
              <button
                type="button"
                className="prow bypass"
                onClick={() => { setBypassAsked(false); onConfirmation('bypass'); }}
              >
                encender bypass
              </button>
              <button type="button" className="prow" autoFocus onClick={() => setBypassAsked(false)}>
                cancelar
              </button>
            </div>
          </div>
        ) : (
          <button
            type="button"
            className="prow"
            aria-pressed={false}
            aria-label="confirmaciones normales: pregunto antes de lo que destruye datos, sale al mundo o instala. pulsa para encender el modo bypass"
            onClick={() => setBypassAsked(true)}
          >
            <span className="prow-ic"><Icon name="lock" size={14} /></span>
            <span className="prow-lbl">normal · pido confirmación</span>
          </button>
        )}
      </div>

      {/* ---- surfaces (tools — the left one) ---- */}
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
                  <span className="unit"> {s.unit}</span>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* ---- left footer ---- */}
      <div className="left-footer">
        <KvRow k="uptime" v={metrics.uptime ?? '—'} />
        {loaded && <KvRow k="ctx" v={fmtK(loaded.context_size)} />}
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
}

function MetricLine({ label, text, unit, norm }: MetricLineProps) {
  const pct = Math.round(Math.min(1, Math.max(0, norm)) * 100);
  return (
    <div className="m-line">
      <div className="m-head">
        <span className="m-label">{label}</span>
        <span className="m-val">
          {text}<span className="m-unit">{unit}</span>
        </span>
      </div>
      <div className="m-bar" aria-hidden="true">
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
