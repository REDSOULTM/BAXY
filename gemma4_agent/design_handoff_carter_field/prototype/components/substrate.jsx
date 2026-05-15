/* left column — substrate, profile, field metrics + system header + ctx + footer */

const SUBSTRATE_TOP = [
  { id: "cpu", label: "cpu", spec: "ryzen · 16c",   unit: "%",    seed: 11 },
  { id: "mem", label: "mem", spec: "ddr5 · 32 gb",  unit: "gb",   seed: 23 },
  { id: "gpu", label: "gpu", spec: "rtx · 24 gb",   unit: "%",    seed: 37 },
];

const SUBSTRATE_SMALL = [
  { id: "net", label: "net", unit: "mb/s", seed: 51 },
  { id: "dsk", label: "dsk", unit: "%",    seed: 67 },
  { id: "tmp", label: "tmp", unit: "°c",   seed: 83 },
];

const PROFILES = ["perf", "bal", "light", "stdby"];

function MetricRow({ row, m, big }) {
  const pct = Math.round(m.norm * 100);
  return (
    <div className={"metric" + (big ? " big" : "") + (m.hot ? " hot" : "")}>
      <ParticleCluster
        value={m.norm}
        seed={row.seed}
        size={big ? 36 : 30}
      />
      <div className="body">
        <div className="row1">
          <span className="label">{row.label}</span>
          <span className="value">
            {m.text}
            <span className="unit">{row.unit}</span>
          </span>
        </div>
        {big && row.spec ? <div className="spec">{row.spec}</div> : null}
        <div className="bar" style={{ "--fill": pct + "%" }} />
      </div>
    </div>
  );
}

function CtxBudget({ used, total }) {
  const pct = Math.min(100, Math.round((used / total) * 100));
  const k = (n) => (n / 1000).toFixed(1) + "k";
  return (
    <div className="ctx-panel">
      <div className="ctx-row">
        <span className="k">ctx · budget</span>
        <span className="v">{k(used)} / {k(total)}</span>
      </div>
      <div className="ctx-bar" style={{ "--fill": pct + "%" }} />
    </div>
  );
}

function SubstratePanel({
  metrics, profile, onProfile, field,
  systemPct, ctxUsed, ctxTotal,
  uptime, tokens, peers,
  state,
}) {
  return (
    <>
      {/* header */}
      <div className="left-header">
        <div className="row">
          <span className="mark"><LogoMark size={14} state={state} /></span>
          <span className="name">gemma 4</span>
          <span className="dots">···</span>
        </div>
        <div className="sub">7.2b · local · q4_k_m</div>
      </div>

      {/* substrate */}
      <div className="sec-head">
        <span>substrate</span>
        <span className="ref">{systemPct}%</span>
      </div>
      <div>
        {SUBSTRATE_TOP.map((r) => (
          <MetricRow key={r.id} row={r} m={metrics[r.id]} big />
        ))}
      </div>
      <div style={{ height: 2 }} />
      <div>
        {SUBSTRATE_SMALL.map((r) => (
          <MetricRow key={r.id} row={r} m={metrics[r.id]} />
        ))}
      </div>

      <div className="hair" />

      {/* ctx budget */}
      <CtxBudget used={ctxUsed} total={ctxTotal} />

      <div className="hair" />

      {/* profile chips (single row, 4 chips) */}
      <div className="sec-head"><span>profile</span><span className="ref">{profile}</span></div>
      <div className="profile-chips">
        {PROFILES.map((p) => (
          <button
            key={p}
            className={"chip" + (profile === p ? " on" : "")}
            onClick={() => onProfile(p)}
          >{p}</button>
        ))}
      </div>

      <div className="hair" />

      {/* field key-values */}
      <div className="sec-head"><span>field</span></div>
      <div className="kv">
        {field.map((row) => (
          <div className="kv-row" key={row.k}>
            <span className="k">{row.k}</span>
            <span className="v">{row.v}</span>
          </div>
        ))}
      </div>

      {/* footer */}
      <div className="left-footer">
        <div className="kv-row"><span className="k">uptime</span><span className="v">{uptime}</span></div>
        <div className="kv-row"><span className="k">tokens</span><span className="v">{tokens}</span></div>
        <div className="kv-row"><span className="k">peers</span><span className="v">{peers}</span></div>
      </div>
    </>
  );
}

Object.assign(window, { SubstratePanel });
