/* center column: state line, neural graph, readout, chat w/ actions */

const STATE_READOUT = {
  standby:    "field offline · voice channel muted",
  idle:       "field stable · listening for wake word",
  listening:  "field receptive · capturing voice",
  thinking:   "field traversing · 47 paths active",
  speaking:   "field emitting · voice channel open",
};

const FOCAL_DESCR = {
  standby:    "—",
  idle:       "voice · ambient",
  listening:  "voice · agent",
  thinking:   "router · memory · context",
  speaking:   "voice · tools",
};

const STATE_VERB = {
  standby: "offline",
  idle: "stable",
  listening: "receptive",
  thinking: "traversing",
  speaking: "emitting",
};

function FieldCenter({ state, onSubmit, nodeCount, edgeCount, micEnabled, onToggleMic }) {
  const [draft, setDraft] = React.useState("");
  const [attachments, setAttachments] = React.useState([]);
  const fileInputRef = React.useRef(null);
  const tokens = Math.min(4096, Math.ceil(draft.length / 4));
  const armed = draft.trim().length > 0;

  const submit = () => {
    if (!armed) return;
    onSubmit(draft.trim() + (attachments.length ? "  ·  " + attachments.length + " attachments" : ""));
    setDraft("");
    setAttachments([]);
  };
  const onKey = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      submit();
    }
  };

  const onFiles = (e) => {
    const files = [...(e.target.files || [])];
    setAttachments((prev) => [
      ...prev,
      ...files.map((f) => ({ name: f.name, size: f.size })),
    ]);
    e.target.value = "";
  };
  const removeAttachment = (i) => {
    setAttachments((prev) => prev.filter((_, idx) => idx !== i));
  };

  return (
    <div className="center-wrap">
      <NeuralGraph state={state} />

      <div className="chat">
        <div className="line">
          <span className="chev">›</span>
          <input
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={onKey}
            placeholder="ask, instruct, or paste"
            spellCheck={false}
            autoFocus
          />
          <span className="tokens">{tokens} / 4k</span>
          <div className="chat-actions">
            <button
              className={"ibtn mic-btn" + (micEnabled ? " active" : "")}
              data-tip={micEnabled ? "disable voice (standby)" : "enable voice (always-listen)"}
              onClick={onToggleMic}
            ><Icon name={micEnabled ? "mic" : "mic-off"} /></button>
            <button
              className={"ibtn" + (attachments.length ? " active" : "")}
              data-tip="attach"
              onClick={() => fileInputRef.current && fileInputRef.current.click()}
            >
              <Icon name="attach" />
              {attachments.length > 0 ? <span className="badge">{attachments.length}</span> : null}
            </button>
            <input
              type="file"
              multiple
              ref={fileInputRef}
              onChange={onFiles}
              style={{ display: "none" }}
            />
            <button
              className={"ibtn send" + (armed ? " armed" : "")}
              data-tip="send"
              onClick={submit}
              disabled={!armed}
            ><Icon name="send" /></button>
          </div>
        </div>

        <div className="chat-bottom">
          <div className="attachments">
            {attachments.length === 0 ? (
              <span className="muted">no attachments</span>
            ) : (
              <div className="att-list">
                {attachments.map((a, i) => (
                  <span className="att-pill" key={i}>
                    <Icon name="attach" size={11} />
                    <span className="att-name">{a.name}</span>
                    <span className="att-size">{(a.size / 1024).toFixed(1)} kb</span>
                    <button className="att-x" onClick={() => removeAttachment(i)}>
                      <Icon name="x" size={10} />
                    </button>
                  </span>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

Object.assign(window, { FieldCenter });
