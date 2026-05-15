import { useEffect, useState } from 'react';
import type { ConvState, ModelInfo, MetricSnapshot, HardwareInfo } from '../types';
import type { FieldReadout, CtxBudget } from '../hooks/useEventStream';
import { LogoMark } from './LogoMark';
import { ParticleCluster } from './ParticleCluster';

interface Props {
  convState: ConvState;
  wsModel: ModelInfo | null;
  field: FieldReadout | null;
  ctx: CtxBudget | null;
  tokens: number;
  profile: string;
  onProfile: (p: string) => void;
}

interface ModelState {
  status: 'loading' | 'ready' | 'error';
  info?: ModelInfo;
}

const INITIAL_MODEL: ModelState = { status: 'loading' };
const INITIAL_METRICS: MetricSnapshot = {
  cpu: 0, mem: 0, gpu: 0, net: 0, dsk: 0, tmp: 0, uptime: '00:00:00',
};
const INITIAL_HARDWARE: HardwareInfo = {
  cpu: 'unknown', cpu_cores: 0,
  mem: 'unknown', mem_total_gb: 0,
  gpu: 'unknown', gpu_vram_gb: 0,
};

// `bal8` = balanced_8gb (E4B UD-Q4_K_XL, ctx 16K, ~7.2 GB VRAM).
// Orden de mas a menos VRAM. El backend acepta los aliases tal cual o
// expandidos (profiles.set_active_profile mapea `bal8` -> `balanced_8gb`).
const PROFILES = ['perf', 'bal8', 'bal', 'light', 'stdby'] as const;

function fmtK(n: number): string {
  return `${(n / 1000).toFixed(1)}k`;
}

export function SubstratePanel({
  convState, wsModel, field, ctx, tokens, profile, onProfile,
}: Props) {
  const [model, setModel] = useState<ModelState>(INITIAL_MODEL);
  const [metrics, setMetrics] = useState<MetricSnapshot>(INITIAL_METRICS);
  const [hardware, setHardware] = useState<HardwareInfo>(INITIAL_HARDWARE);

  useEffect(() => {
    let cancelled = false;
    const fetchMetrics = async () => {
      try {
        const r = await fetch('/metrics');
        if (cancelled || !r.ok) return;
        const data = (await r.json()) as MetricSnapshot;
        setMetrics(data);
      } catch { /* ignore */ }
    };
    fetchMetrics();
    const id = window.setInterval(fetchMetrics, 1500);
    return () => { cancelled = true; window.clearInterval(id); };
  }, []);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const r = await fetch('/hardware');
        if (cancelled || !r.ok) return;
        setHardware((await r.json()) as HardwareInfo);
      } catch { /* ignore */ }
    })();
    return () => { cancelled = true; };
  }, []);

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

  // global "substrate %" — weighted average like the prototype:
  // 0.35 cpu + 0.25 mem + 0.4 gpu, clamped to 0..100.
  const systemPct = Math.round(
    metrics.cpu * 0.35 + metrics.mem * 0.25 + metrics.gpu * 0.40,
  );

  // mem headline: gb used (matches prototype which divides mem by 32gb total)
  const memUsedGb = metrics.mem_used_gb && metrics.mem_used_gb > 0
    ? metrics.mem_used_gb : 0;
  const memText = memUsedGb > 0 ? memUsedGb.toFixed(1) : metrics.mem.toFixed(0);
  const memUnit = memUsedGb > 0 ? 'gb' : '%';

  // normalized 0..1 values feed the particle cluster intensity
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
          <span className="mark">
            <LogoMark size={14} state={convState} />
          </span>
          <span className="name">
            {loaded ? loaded.family : <span className="dim">loading…</span>}
          </span>
          <span className="dots">···</span>
          {isMock && <span className="muted" style={{ fontSize: 9, letterSpacing: '0.14em' }}>MOCK</span>}
        </div>
        <div className="sub">
          {loaded ? `${loaded.params} · ${loaded.runtime} · ${loaded.quant}` : '—'}
        </div>
      </div>

      {/* ---- substrate header + 6 metric rows ---- */}
      <div className="sec-head">
        <span>substrate</span>
        <span className="ref">{systemPct}%</span>
      </div>
      <div>
        <MetricRow
          big seed={11} label="cpu" spec={hardware.cpu}
          value={metrics.cpu.toFixed(0)} unit="%" norm={norm.cpu}
        />
        <MetricRow
          big seed={23} label="mem" spec={hardware.mem}
          value={memText} unit={memUnit} norm={norm.mem}
        />
        <MetricRow
          big seed={37} label="gpu" spec={hardware.gpu}
          value={metrics.gpu.toFixed(0)} unit="%" norm={norm.gpu}
        />
      </div>
      <div style={{ height: 2 }} />
      <div>
        <MetricRow
          seed={51} label="net"
          value={metrics.net.toFixed(1)} unit="mb/s" norm={norm.net}
        />
        <MetricRow
          seed={67} label="dsk"
          value={metrics.dsk.toFixed(0)} unit="%" norm={norm.dsk}
        />
        <MetricRow
          seed={83} label="tmp" hot={tmpHot}
          value={metrics.tmp.toFixed(0)} unit="°c" norm={norm.tmp}
        />
      </div>

      <div className="hair" />

      {/* ---- ctx budget ---- */}
      <div className="ctx-panel">
        <div className="ctx-row">
          <span className="k">ctx · budget</span>
          <span className="v">{fmtK(ctxUsed)} / {fmtK(ctxTotal)}</span>
        </div>
        <div className="ctx-bar" style={{ '--fill': `${ctxPct}%` } as React.CSSProperties} />
      </div>

      <div className="hair" />

      {/* ---- profile chips ---- */}
      <div className="sec-head">
        <span>profile</span>
        <span className="ref">{profile}</span>
      </div>
      <div className="profile-chips" role="radiogroup" aria-label="vram profile">
        {PROFILES.map((p) => (
          <button
            key={p}
            type="button"
            role="radio"
            aria-checked={profile === p}
            className={`chip${profile === p ? ' on' : ''}`}
            onClick={() => onProfile(p)}
          >
            {p}
          </button>
        ))}
      </div>

      <div className="hair" />

      {/* ---- field key/value ----
            we only render the rows the backend actually produces. ctx is
            always available (from cfg + WS); the rest (`entropy`, `temp`,
            `tokens_per_s`, `draw_w`) need a live `field` event — until that
            wires up they'd just be "—" forever, so we skip them. */}
      <div className="sec-head"><span>field</span></div>
      <div className="kv">
        <KvRow k="ctx · used" v={ctx ? `${ctxPct} %` : '—'} />
        {field && (
          <>
            <KvRow k="entropy"     v={field.entropy.toFixed(2)} />
            <KvRow k="temperature" v={field.temperature.toFixed(2)} />
            <KvRow k="tokens/s"    v={field.tokens_per_s.toFixed(1)} />
            <KvRow k="draw · w"    v={String(field.draw_w)} />
          </>
        )}
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

interface MetricRowProps {
  label: string;
  value: string;
  unit: string;
  norm: number;
  seed: number;
  big?: boolean;
  hot?: boolean;
  spec?: string;
}

function MetricRow({ label, value, unit, norm, seed, big, hot, spec }: MetricRowProps) {
  const pct = Math.round(norm * 100);
  const clusterColor = hot ? 'var(--carmine)'
    : label === 'cpu' ? 'var(--carmine)'
    : label === 'gpu' ? 'var(--p-blue-hi)'
    : label === 'tmp' ? 'var(--tag-mem)'
    : 'var(--p-blue)';
  return (
    <div className={`metric${big ? ' big' : ''}${hot ? ' hot' : ''}`}>
      <ParticleCluster
        value={norm}
        seed={seed}
        size={big ? 36 : 30}
        color={clusterColor}
      />
      <div className="body">
        <div className="row1">
          <span className="label">{label}</span>
          <span className="value">
            {value}
            <span className="unit">{unit}</span>
          </span>
        </div>
        {big && spec ? <div className="spec">{spec}</div> : null}
        <div
          className="bar"
          style={{ '--fill': `${pct}%` } as React.CSSProperties}
          aria-hidden="true"
        />
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
