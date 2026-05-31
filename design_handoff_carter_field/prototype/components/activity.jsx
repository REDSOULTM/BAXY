/* right column — minimal: just the activity log, airy */

const SOURCE_CLASS = {
  TOOL: "tool",
  YOU: "you",
  GEMMA: "gemma",
  MEMORY: "memory",
  TRIGGER: "trigger",
  BOOT: "boot",
  THOUGHT: "thought",
  SYSTEM: "system",
  CONTEXT: "context",
};

function ActivityRow({ entry }) {
  return (
    <div className="act fade-in">
      <div className="meta">
        <span className="ts">{entry.ts}</span>
        <span className={"src " + (SOURCE_CLASS[entry.src] || "you")}>{entry.src}</span>
      </div>
      <div className="msg">{entry.msg}</div>
    </div>
  );
}

function ActivityPanel({
  entries, session, entryCount,
  settingsOpen, onSettings, onNewSession, onHelp,
  surfaces, activeSurface, onSurface, rightFooter,
}) {
  const scrollRef = React.useRef(null);
  React.useEffect(() => {
    if (scrollRef.current) scrollRef.current.scrollTop = 0;
  }, [entries.length]);

  return (
    <>
      {/* action row */}
      <div className="act-toolbar">
        <button className="ibtn xs" data-tip="new session" onClick={onNewSession}><Icon name="plus" size={13} /></button>
        <button className="ibtn xs" data-tip="shortcuts" onClick={onHelp}><Icon name="help" size={13} /></button>
        <button
          className={"ibtn xs labeled" + (settingsOpen ? " active" : "")}
          data-tip="settings · configure agent"
          onClick={onSettings}
        >
          <Icon name="settings" size={13} />
          <span>settings</span>
        </button>
      </div>

      {/* header */}
      <div className="sec-head">
        <span>activity</span>
        <span className="ref">{entryCount} entries · #{session}</span>
      </div>

      <div className="activity-scroll" ref={scrollRef}>
        {entries.map((e, i) => (
          <ActivityRow key={e.id || i} entry={e} />
        ))}
      </div>

      {/* surfaces */}
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
      <div className="right-footer">
        <span>{rightFooter.left}</span>
        <span className="v">{rightFooter.right}</span>
      </div>
    </>
  );
}

Object.assign(window, { ActivityPanel });
