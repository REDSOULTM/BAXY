/* left column — minimal: header + metrics + ctx + profiles + uptime */

const SUBSTRATE_MIN = [
  { id: "cpu", label: "cpu", unit: "%"    },
  { id: "mem", label: "mem", unit: "gb"   },
  { id: "gpu", label: "gpu", unit: "%"    },
  { id: "net", label: "net", unit: "mb/s" },
  { id: "dsk", label: "dsk", unit: "%"    },
  { id: "tmp", label: "tmp", unit: "°c"   },
];

const PROFILES = [
  { id: "normal",    label: "normal",     icon: "person" },
  { id: "novidente", label: "no vidente", icon: "eye-off" },
  { id: "movilidad", label: "movilidad",  icon: "wheelchair" },
];

function MetricLine({ label, m, unit }) {
  const pct = Math.round(m.norm * 100);
  return (
    <div className="m-line">
      <div className="m-head">
        <span className="m-label">{label}</span>
        <span className={"m-val" + (m.hot ? " hot" : "")}>
          {m.text}<span className="m-unit">{unit}</span>
        </span>
      </div>
      <div className={"m-bar" + (m.hot ? " hot" : "")}>
        <span style={{ width: pct + "%" }} />
      </div>
    </div>
  );
}

function CtxBudget({ used, total }) {
  const pct = Math.min(100, Math.round((used / total) * 100));
  const k = (n) => (n / 1000).toFixed(1) + "k";
  return (
    <div className="m-line">
      <div className="m-head">
        <span className="m-label">ctx</span>
        <span className="m-val">{k(used)}<span className="m-unit">/ {k(total)}</span></span>
      </div>
      <div className="m-bar"><span style={{ width: pct + "%" }} /></div>
    </div>
  );
}

function SubstratePanel({
  metrics, profile, onProfile,
  systemPct, ctxUsed, ctxTotal, uptime, state,
  powered, onTogglePower,
  surfaces, activeSurface, onSurface,
}) {
  return (
    <>
      {/* header */}
      <div className="left-header">
        <div className="row">
          <span className="mark"><LogoMark size={14} state={state} /></span>
          <span className="name">gemma 4</span>
        </div>
        <div className="sub">7.2b · local</div>
      </div>

      {/* power / standby toggle */}
      <button
        className={"power-row" + (powered ? " on" : " off")}
        onClick={onTogglePower}
      >
        <span className="power-ic"><Icon name="power" size={15} /></span>
        <span className="power-lbl">{powered ? "online" : "standby"}</span>
        <span className="power-dot" />
      </button>

      {/* system metrics */}
      <div className="min-block">
        <div className="sec-head"><span>system</span><span className="ref">{systemPct}%</span></div>
        <div className="m-list">
          {SUBSTRATE_MIN.map((r) => (
            <MetricLine key={r.id} label={r.label} unit={r.unit} m={metrics[r.id]} />
          ))}
        </div>
      </div>

      {/* profiles with icons */}
      <div className="min-block">
        <div className="sec-head"><span>perfil</span></div>
        <div className="profile-list">
          {PROFILES.map((p) => (
            <button
              key={p.id}
              className={"prow" + (profile === p.id ? " on" : "")}
              onClick={() => onProfile(p.id)}
            >
              <span className="prow-ic"><Icon name={p.icon} size={14} /></span>
              <span className="prow-lbl">{p.label}</span>
            </button>
          ))}
        </div>
      </div>

      {/* ctx budget — below profiles */}
      <div className="min-block">
        <div className="m-list">
          <CtxBudget used={ctxUsed} total={ctxTotal} />
        </div>
      </div>

      {/* surfaces (2 of 4) */}
      <div className="surfaces-wrap">
        <div className="surfaces">
          {surfaces.map((s) => (
            <div
              key={s.id}
              className={"scard" + (activeSurface === s.id ? " active" : "")}
              onClick={() => onSurface(s.id)}
            >
              <div className="lbl">{s.label}</div>
              <div className="count">{s.count}<span className="unit"> {s.unit}</span></div>
            </div>
          ))}
        </div>
      </div>

      {/* footer */}
      <div className="left-footer">
        <div className="kv-row"><span className="k">uptime</span><span className="v">{uptime}</span></div>
      </div>
    </>
  );
}

Object.assign(window, { SubstratePanel });
