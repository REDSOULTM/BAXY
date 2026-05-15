/* right column — activity log (vertical entries) + surfaces grid + right footer */

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
  surfaces, activeSurface, onSurface,
  rightFooter,
}) {
  const scrollRef = React.useRef(null);
  React.useEffect(() => {
    if (scrollRef.current) scrollRef.current.scrollTop = 0;
  }, [entries.length]);

  return (
    <>
      <div className="sec-head">
        <span>activity</span>
        <span className="ref">{entryCount} entries · #{session}</span>
      </div>

      <div className="activity-scroll" ref={scrollRef}>
        {entries.map((e, i) => (
          <ActivityRow key={e.id || i} entry={e} />
        ))}
      </div>

      <div className="surfaces-wrap">
        <div className="sec-head"><span>surfaces</span></div>
        <div className="surfaces">
          {surfaces.map((s) => (
            <div
              key={s.id}
              className={"scard" + (activeSurface === s.id ? " active" : "")}
              onClick={() => onSurface(s.id)}
            >
              <div className="lbl">{s.label}</div>
              <div className="count">
                {s.count}
                <span className="unit">{s.unit}</span>
              </div>
            </div>
          ))}
        </div>
      </div>

      <div className="right-footer">
        <span>{rightFooter.left}</span>
        <span className="v">{rightFooter.right}</span>
      </div>
    </>
  );
}

Object.assign(window, { ActivityPanel });
