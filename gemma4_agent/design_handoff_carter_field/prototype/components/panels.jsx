/* floating popover panels — sessions only (settings has own file) */

const SETTINGS_SESSIONS = [
  { id: "847", label: "field · ready · sept stack",       ts: "23:08", current: true },
  { id: "846", label: "embedding strategy comparison",     ts: "22:36" },
  { id: "845", label: "weekly digest · research notes",    ts: "21:51" },
  { id: "844", label: "trigger watch · coil temperature",  ts: "yesterday" },
  { id: "843", label: "voice calibration · vosk + piper",  ts: "yesterday" },
  { id: "842", label: "vault decant · ~/research/sept",    ts: "2 days ago" },
];

function Panel({ title, onClose, width, children }) {
  return (
    <div className="panel-shroud" onClick={onClose}>
      <div
        className="panel"
        style={width ? { width } : undefined}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="panel-head">
          <span className="panel-title">{title}</span>
          <button className="ibtn" onClick={onClose} data-tip="close">
            <Icon name="x" />
          </button>
        </div>
        <div className="panel-body">{children}</div>
      </div>
    </div>
  );
}

function SessionsPanel({ onClose }) {
  const [filter, setFilter] = React.useState("");
  const list = SETTINGS_SESSIONS.filter((s) =>
    !filter || s.label.toLowerCase().includes(filter.toLowerCase())
  );

  return (
    <Panel title="sessions" onClose={onClose} width={480}>
      <div className="session-search">
        <Icon name="search" size={13} />
        <input
          autoFocus
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          placeholder="filter sessions"
        />
      </div>

      <div className="session-list">
        {list.map((s) => (
          <div key={s.id} className={"session-row" + (s.current ? " current" : "")}>
            <div className="session-id">#{s.id}</div>
            <div className="session-label">{s.label}</div>
            <div className="session-ts">{s.ts}</div>
            {s.current ? <div className="session-cur">current</div> : null}
          </div>
        ))}
      </div>

      <div className="panel-footer">
        <span className="muted">{list.length} sessions · all local</span>
        <button className="panel-btn">
          <Icon name="plus" size={12} />
          <span>new session</span>
        </button>
      </div>
    </Panel>
  );
}

Object.assign(window, { Panel, SessionsPanel });
