/* full settings panel with tabs — matches PyQt6 subsystems */

const SETTINGS_TABS = [
  { id: "connection", label: "connection" },
  { id: "agent",      label: "agent" },
  { id: "sampling",   label: "sampling" },
  { id: "behaviour",  label: "behaviour" },
  { id: "transcript", label: "transcript" },
  { id: "voice",      label: "voice" },
  { id: "profiles",   label: "profiles" },
  { id: "toggles",    label: "toggles" },
  { id: "paths",      label: "paths" },
  { id: "prompt",     label: "prompt" },
  { id: "about",      label: "about" },
];

const DEFAULT_CONFIG = {
  // connection
  llamaUrl: "http://127.0.0.1:8080",
  modelAlias: "",
  ggufPath: "",
  ctxSize: 16384,
  maxTokens: 1280,
  // agent
  agentMode: "auto",
  persona: "default",
  maxTurns: 8,
  safetyFilter: true,
  // sampling
  temperature: 1.00,
  topP: 0.95,
  topK: 64,
  minP: 0.00,
  repeatPenalty: 1.00,
  seed: -1,
  allowCoT: true,
  parallelTools: true,
  // behaviour
  summarizationCooldown: 6,
  factCooldown: 5,
  phraseTriggerTimeout: 30,
  llmTimeout: 180,
  maxExpRecords: 5000,
  // transcript
  sttProvider: "whisper.cpp (local)",
  sttModel: "ggml-base.bin",
  sttLanguage: "auto",
  ttsProvider: "piper (local)",
  ttsVoice: "es_AR-daniela-high",
  ttsRate: 1.00,
  wakeWord: "gemma",
  wakeWordEnabled: true,
  // voice
  voiceEnabled: true,
  wakeBeep: true,
  wakeHudBlink: true,
  wakeTts: false,
  inputDevice: "1: Micrófono (3- USB PnP Audio Dev)",
  followUpWindow: 5,
  followUpClosePhrases: "gracias\nlisto\nya está\ncancelar",
  muteTts: false,
  // profiles
  autoSwitch: false,
  autoSwitchGame: true,
  autoSwitchGpu: false,
  autoSwitchRam: false,
  autoSwitchTo: "light",
  autoSwitchBack: "balanced",
  gameProcesses: "steam.exe\nRobloxPlayer.exe\njavaw.exe",
  vramDetected: 16380,
  recommendedProfile: "performance",
  // toggles (env vars)
  factExtraction: false,
  crossEncoderRerank: true,
  parallelToolExec: false,
  autoLoadCtx: false,
  persistentSessions: true,
  toolTimeline: true,
  summarization: true,
  tracing: true,
  // paths (placeholders)
  memoryJson: "~/gemma4/data/memory.json",
  stateJson:  "~/gemma4/data/state.json",
  traceJsonl: "~/gemma4/data/traces.jsonl",
  sessionsDir: "~/.gemma4/sessions",
  timelineDir: "~/.gemma4/timeline",
};

/* ============================================================
   small form primitives
   ============================================================ */
function Field({ label, hint, children, wide }) {
  return (
    <div className={"sf" + (wide ? " wide" : "")}>
      <label className="sf-label">{label}</label>
      <div className="sf-ctl">{children}</div>
      {hint ? <div className="sf-hint">{hint}</div> : null}
    </div>
  );
}

function STInput({ value, onChange, placeholder, mono = true, type = "text" }) {
  return (
    <input
      type={type}
      className={"st-input" + (mono ? " mono" : "")}
      value={value}
      placeholder={placeholder}
      onChange={(e) => onChange(type === "number" ? parseFloat(e.target.value) : e.target.value)}
      spellCheck={false}
    />
  );
}

function STNumber({ value, onChange, min, max, step }) {
  return (
    <input
      type="number"
      className="st-input mono num"
      value={value}
      min={min} max={max} step={step}
      onChange={(e) => onChange(parseFloat(e.target.value))}
    />
  );
}

function STText({ value, onChange, rows = 4, mono = true }) {
  return (
    <textarea
      className={"st-textarea" + (mono ? " mono" : "")}
      value={value}
      rows={rows}
      onChange={(e) => onChange(e.target.value)}
      spellCheck={false}
    />
  );
}

function STCheck({ value, onChange, label, hint }) {
  return (
    <div className="sf-check" onClick={() => onChange(!value)}>
      <span className={"check-box" + (value ? " on" : "")} aria-pressed={value}>
        {value ? <Icon name="check" size={9} /> : null}
      </span>
      <div className="check-body">
        <span className="check-label">{label}</span>
        {hint ? <span className="check-hint">{hint}</span> : null}
      </div>
    </div>
  );
}

function STBrowse({ value, onChange, placeholder }) {
  return (
    <div className="st-browse">
      <STInput value={value} onChange={onChange} placeholder={placeholder} />
      <button className="st-browse-btn" title="browse"><Icon name="folder" size={12} /></button>
    </div>
  );
}

function STTip({ children }) {
  return <div className="st-tip">{children}</div>;
}

function STSection({ title, children }) {
  return (
    <div className="st-section">
      {title ? <div className="st-section-head">{title}</div> : null}
      {children}
    </div>
  );
}

/* ============================================================
   tab content
   ============================================================ */
function ConnectionTab({ c, set }) {
  return (
    <STSection>
      <Field label="llama-server url">
        <STInput value={c.llamaUrl} onChange={set("llamaUrl")} placeholder="http://127.0.0.1:8080" />
      </Field>
      <Field label="model alias">
        <STInput value={c.modelAlias} onChange={set("modelAlias")} placeholder="optional alias — e.g. gemma-3-e4b-it.Q6_K" />
      </Field>
      <Field label="gguf path">
        <STBrowse value={c.ggufPath} onChange={set("ggufPath")} placeholder=".gguf path — passed to launcher / used by agent.config" />
      </Field>
      <Field label="context size (tokens)">
        <STNumber value={c.ctxSize} onChange={set("ctxSize")} min={1024} max={131072} step={1024} />
      </Field>
      <Field label="max tokens per reply">
        <STNumber value={c.maxTokens} onChange={set("maxTokens")} min={64} max={8192} step={32} />
      </Field>
      <STTip>
        the agent talks to a llama-server you start separately. changes here require <b className="bone">restart agent</b> to take effect.
      </STTip>
    </STSection>
  );
}

function AgentTab({ c, set }) {
  return (
    <STSection>
      <Field label="agent mode">
        <STInput value={c.agentMode} onChange={set("agentMode")} />
      </Field>
      <Field label="persona">
        <STInput value={c.persona} onChange={set("persona")} />
      </Field>
      <Field label="max turns per request">
        <STNumber value={c.maxTurns} onChange={set("maxTurns")} min={1} max={64} step={1} />
      </Field>
      <Field label=" ">
        <STCheck
          value={c.safetyFilter}
          onChange={set("safetyFilter")}
          label="safety filter on"
        />
      </Field>
      <STTip warn>
        safety <b className="carmine">off</b> means destructive tools (filesystem.delete, terminal
        with risky commands, registry add/delete, system shutdown, package install/uninstall, etc.)
        run <b className="carmine">without</b> confirmation. recommended on for unattended sessions;
        off only if you trust every prompt you give and you watch every turn.
      </STTip>
    </STSection>
  );
}

function SamplingTab({ c, set }) {
  return (
    <STSection>
      <STTip>
        sampling parameters passed to llama-server. lower temperature gives more deterministic
        output; top_p + top_k narrow the candidate pool; min_p prunes low-probability tokens
        after temperature.
      </STTip>
      <Field label="temperature">
        <STNumber value={c.temperature} onChange={set("temperature")} min={0} max={2} step={0.01} />
      </Field>
      <Field label="top_p">
        <STNumber value={c.topP} onChange={set("topP")} min={0} max={1} step={0.01} />
      </Field>
      <Field label="top_k">
        <STNumber value={c.topK} onChange={set("topK")} min={1} max={1000} step={1} />
      </Field>
      <Field label="min_p (0 = disabled)">
        <STNumber value={c.minP} onChange={set("minP")} min={0} max={1} step={0.01} />
      </Field>
      <Field label="repeat penalty">
        <STNumber value={c.repeatPenalty} onChange={set("repeatPenalty")} min={0.8} max={2} step={0.01} />
      </Field>
      <Field label="seed">
        <STInput value={c.seed} onChange={set("seed")} placeholder="-1 (random)" />
      </Field>
      <Field label=" ">
        <STCheck value={c.allowCoT} onChange={set("allowCoT")} label="allow gemma to expose chain-of-thought" hint="slower" />
      </Field>
      <Field label=" ">
        <STCheck value={c.parallelTools} onChange={set("parallelTools")} label="let model emit multiple tool_calls per turn" />
      </Field>
    </STSection>
  );
}

function BehaviourTab({ c, set }) {
  return (
    <STSection>
      <STTip>
        higher-level behaviour knobs that the agent actually reads. strict honesty and auto-replan
        are always on (built into the loop).
      </STTip>
      <Field label="summarization cooldown (turns)">
        <STNumber value={c.summarizationCooldown} onChange={set("summarizationCooldown")} min={0} max={50} step={1} />
      </Field>
      <Field label="fact extraction cooldown">
        <STNumber value={c.factCooldown} onChange={set("factCooldown")} min={0} max={50} step={1} />
      </Field>
      <Field label="phrase-trigger step timeout (s)">
        <STNumber value={c.phraseTriggerTimeout} onChange={set("phraseTriggerTimeout")} min={1} max={600} step={1} />
      </Field>
      <Field label="llm request timeout (s)">
        <STNumber value={c.llmTimeout} onChange={set("llmTimeout")} min={10} max={1800} step={1} />
      </Field>
      <Field label="max experience records">
        <STNumber value={c.maxExpRecords} onChange={set("maxExpRecords")} min={0} max={100000} step={100} />
      </Field>
      <STTip>
        honesty guards (unverified detection, phrase-confirm, plan status) are always on.
        auto-replan triggers after 2+ tool failures when an explicit plan exists; toggling
        it off is not exposed.
      </STTip>
    </STSection>
  );
}

function TranscriptTab({ c, set }) {
  return (
    <STSection>
      <STTip>
        speech-to-text (stt) and text-to-speech (tts) settings. voice is not enabled yet —
        these prepare the backend for when audio mode ships. all providers below are local
        when applicable.
      </STTip>
      <Field label="stt provider">
        <STInput value={c.sttProvider} onChange={set("sttProvider")} />
      </Field>
      <Field label="stt model">
        <STInput value={c.sttModel} onChange={set("sttModel")} />
      </Field>
      <Field label="stt language">
        <STInput value={c.sttLanguage} onChange={set("sttLanguage")} />
      </Field>
      <Field label="tts provider">
        <STInput value={c.ttsProvider} onChange={set("ttsProvider")} />
      </Field>
      <Field label="tts voice">
        <STInput value={c.ttsVoice} onChange={set("ttsVoice")} />
      </Field>
      <Field label="tts speech rate">
        <STNumber value={c.ttsRate} onChange={set("ttsRate")} min={0.5} max={2} step={0.05} />
      </Field>
      <Field label="wake word">
        <STInput value={c.wakeWord} onChange={set("wakeWord")} />
      </Field>
      <Field label=" ">
        <STCheck value={c.wakeWordEnabled} onChange={set("wakeWordEnabled")} label="wake word enabled" hint="passive listening" />
      </Field>
      <STTip>voice runtime not wired yet — settings are persisted for future activation.</STTip>
    </STSection>
  );
}

function VoiceTab({ c, set }) {
  return (
    <STSection>
      <STTip>
        local voice — vosk (wake) + faster-whisper (stt) + piper (tts). all cpu. changes
        require toggle off/on to take effect. models download on first use with your
        consent.
      </STTip>
      <Field label=" ">
        <STCheck value={c.voiceEnabled} onChange={set("voiceEnabled")} label="enable voice" hint="master switch" />
      </Field>
      <Field label="wake words" hint="'gemma' AND 'hey gemma' (both active)">
        <span className="muted mono">gemma · hey gemma</span>
      </Field>
      <Field label="wake feedback">
        <div className="check-row">
          <STCheck value={c.wakeBeep}     onChange={set("wakeBeep")}     label="beep" />
          <STCheck value={c.wakeHudBlink} onChange={set("wakeHudBlink")} label="hud blink" />
          <STCheck value={c.wakeTts}      onChange={set("wakeTts")}      label="tts 'sí'" />
        </div>
      </Field>
      <Field label="input device">
        <STInput value={c.inputDevice} onChange={set("inputDevice")} />
      </Field>
      <Field label="stt model (cpu)">
        <STInput value="auto" onChange={() => {}} />
      </Field>
      <Field label="tts voice">
        <STInput value={c.ttsVoice} onChange={set("ttsVoice")} />
      </Field>
      <Field label="follow-up window (s)">
        <STNumber value={c.followUpWindow} onChange={set("followUpWindow")} min={1} max={60} step={1} />
      </Field>
      <Field label="follow-up close phrases" hint="one per line">
        <STText value={c.followUpClosePhrases} onChange={set("followUpClosePhrases")} rows={5} />
      </Field>
      <Field label=" ">
        <STCheck value={c.muteTts} onChange={set("muteTts")} label="mute tts" hint="wake + stt keep working" />
      </Field>
      <STTip>
        voice controller auto-starts/stops on profile change:
        <span className="mono"> perf</span> &amp;
        <span className="mono"> bal</span> → on,
        <span className="mono"> light</span> &amp;
        <span className="mono"> standby</span> → off.
        your manual override via <b className="bone">enable voice</b> persists until you toggle it again.
      </STTip>
    </STSection>
  );
}

function ProfilesTab({ c, set, profile, onProfile }) {
  const PROFILE_TABLE = [
    { row: "ctx",          perf: "32 768",  bal: "16 384",  light: "4 096" },
    { row: "tools",        perf: "62",      bal: "48",      light: "12" },
    { row: "tts",          perf: "on",      bal: "on",      light: "off" },
    { row: "wake",         perf: "on",      bal: "on",      light: "on" },
    { row: "vram cap",     perf: "16 gb",   bal: "10 gb",   light: "3 gb" },
  ];
  return (
    <STSection>
      <div className="st-sub-head">hardware detection</div>
      <div className="kv" style={{ marginBottom: 12 }}>
        <div className="kv-row"><span className="k">vram detected</span><span className="v">{c.vramDetected.toLocaleString()} mb</span></div>
        <div className="kv-row"><span className="k">recommended profile</span><span className="v">{c.recommendedProfile}</span></div>
      </div>
      <button className="st-redetect"><Icon name="restart" size={11} /> re-detect</button>

      <div className="st-sub-head" style={{ marginTop: 18 }}>auto-switch (opt-in)</div>
      <STCheck
        value={c.autoSwitch}
        onChange={set("autoSwitch")}
        label="change profile automatically when…"
      />
      <STCheck value={c.autoSwitchGame} onChange={set("autoSwitchGame")} label="a game is detected" hint="process in watchlist" />
      <STCheck value={c.autoSwitchGpu}  onChange={set("autoSwitchGpu")}  label="gpu > 70% for more than 30s" hint="excluding gemma 4" />
      <STCheck value={c.autoSwitchRam}  onChange={set("autoSwitchRam")}  label="ram > 85%" />
      <div style={{ display: "flex", gap: 12, marginTop: 8 }}>
        <Field label="switch to"><STInput value={c.autoSwitchTo} onChange={set("autoSwitchTo")} /></Field>
        <Field label="return to"><STInput value={c.autoSwitchBack} onChange={set("autoSwitchBack")} /></Field>
      </div>
      <Field label="watchlist processes" hint="one per line">
        <STText value={c.gameProcesses} onChange={set("gameProcesses")} rows={4} />
      </Field>

      <div className="st-sub-head" style={{ marginTop: 18 }}>active profile</div>
      <div className="profile-chips" style={{ marginBottom: 12 }}>
        {["perf", "bal", "light", "stdby"].map((p) => (
          <button key={p} className={"chip" + (profile === p ? " on" : "")} onClick={() => onProfile(p)}>{p}</button>
        ))}
      </div>

      <div className="st-sub-head">profile capabilities</div>
      <table className="st-table">
        <thead>
          <tr><th></th><th>perf</th><th>bal</th><th>light</th></tr>
        </thead>
        <tbody>
          {PROFILE_TABLE.map((r) => (
            <tr key={r.row}>
              <td className="row-label">{r.row}</td>
              <td>{r.perf}</td>
              <td>{r.bal}</td>
              <td>{r.light}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <STTip>
        hotkey <span className="mono">ctrl+shift+g</span> cycles perf → bal → light → stdby.
        light uses the gguf you set in <b className="bone">model</b> above; if empty it uses the
        primary model with context = 4 096.
      </STTip>
    </STSection>
  );
}

function TogglesTab({ c, set }) {
  const TOGGLES = [
    { key: "factExtraction",     label: "fact extraction (post-turn)",     env: "GEMMA4_AGENT_FACT_EXTRACTION" },
    { key: "crossEncoderRerank", label: "cross-encoder rerank in knowledge.search", env: "GEMMA4_KNOWLEDGE_RERANK" },
    { key: "parallelToolExec",   label: "parallel tool execution",          env: "GEMMA4_AGENT_PARALLEL_TOOLS" },
    { key: "autoLoadCtx",        label: "auto-load project context",        env: "GEMMA4_AGENT_PROJECT_CONTEXT" },
    { key: "persistentSessions", label: "persistent chat sessions",         env: "GEMMA4_AGENT_SESSIONS" },
    { key: "toolTimeline",       label: "tool timeline jsonl export",       env: "GEMMA4_AGENT_TIMELINE" },
    { key: "summarization",      label: "llm-summarization compaction",     env: "GEMMA4_AGENT_SUMMARIZATION" },
    { key: "tracing",            label: "tracing to jsonl (trace.jsonl)",   env: "GEMMA4_AGENT_TRACING" },
  ];
  return (
    <STSection>
      <STTip>feature toggles. env vars applied at next agent restart.</STTip>
      <div className="toggle-list">
        {TOGGLES.map((t) => (
          <div key={t.key} className="toggle-list-row">
            <STCheck value={c[t.key]} onChange={set(t.key)} label={t.label} />
            <span className="env mono">{t.env}</span>
          </div>
        ))}
      </div>
    </STSection>
  );
}

function PathsTab({ c, set }) {
  return (
    <STSection>
      <Field label="memory.json"><STBrowse value={c.memoryJson} onChange={set("memoryJson")} /></Field>
      <Field label="state.json"><STBrowse value={c.stateJson} onChange={set("stateJson")} /></Field>
      <Field label="trace.jsonl"><STBrowse value={c.traceJsonl} onChange={set("traceJsonl")} /></Field>
      <Field label="sessions dir"><STBrowse value={c.sessionsDir} onChange={set("sessionsDir")} /></Field>
      <Field label="timeline dir"><STBrowse value={c.timelineDir} onChange={set("timelineDir")} /></Field>
    </STSection>
  );
}

const SYSTEM_PROMPT = `you are a local agent powered by gemma 4.

speak the user's language by default. be brief, concrete, and honest.
for general knowledge, identity, explanations, pop culture, definitions, and
normal conversation, answer directly without tools. do not say "no tengo
herramienta para eso" for questions like "quién es batman", "qué es python",
or "quién eres" — tools are only needed for live pc state or actions.

you control the computer only through the tools provided in the api 'tools'
parameter. when the user asks for an action and a relevant tool exists, call
the tool. do not describe a tool call as text. use the native tool_call
mechanism.

multi-step missions are allowed and expected. if the user asks "do a, then b,
then c", execute the steps in order using multiple tool calls across turns.
do not stop after the first successful tool if there are pending steps. keep
going until the requested sequence is complete, a tool fails, or you need a
missing argument.`;

function PromptTab() {
  return (
    <STSection>
      <div className="st-sub-head">system prompt <span className="muted">· read-only preview of current core prompt</span></div>
      <pre className="st-prompt">{SYSTEM_PROMPT}</pre>
      <STTip>
        override by editing <span className="mono">gemma4_agent/agent.py</span>{" "}
        <span className="mono">SYSTEM_PROMPT</span>. persona and project_context hints are
        appended automatically at runtime.
      </STTip>
    </STSection>
  );
}

function AboutTab() {
  return (
    <STSection>
      <div className="st-about-title">gemma 4 · field</div>
      <div className="st-about-sub">local ai agent · carter build · runs entirely offline</div>
      <div className="hair" style={{ margin: "16px 0" }} />
      <div className="kv">
        <div className="kv-row"><span className="k">python</span><span className="v">3.10.11</span></div>
        <div className="kv-row"><span className="k">settings file</span><span className="v">~/.gemma4/gui.json</span></div>
        <div className="kv-row"><span className="k">agent module</span><span className="v">~/gemma4_agent</span></div>
        <div className="kv-row"><span className="k">build</span><span className="v">carter · 2026.05</span></div>
        <div className="kv-row"><span className="k">runtime</span><span className="v">llama.cpp · cuda 12</span></div>
      </div>
      <STTip>all inference is local. no telemetry. no external network calls.</STTip>
    </STSection>
  );
}

/* ============================================================
   panel shell
   ============================================================ */
function SettingsPanel({ theme, onTheme, profile, onProfile, onClose }) {
  const [tab, setTab] = React.useState("connection");
  const [config, setConfig] = React.useState(DEFAULT_CONFIG);

  const set = (key) => (val) => setConfig((c) => ({ ...c, [key]: val }));
  const reset = () => setConfig(DEFAULT_CONFIG);

  return (
    <div className="panel-shroud" onClick={onClose}>
      <div
        className="panel settings-panel"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="panel-head">
          <div className="panel-head-left">
            <span className="panel-title">configuration</span>
            <span className="muted">·</span>
            <span className="panel-subtitle">all subsystems</span>
          </div>
          <button className="ibtn" onClick={onClose} data-tip="close">
            <Icon name="x" />
          </button>
        </div>

        <div className="settings-tabs">
          {SETTINGS_TABS.map((t) => (
            <button
              key={t.id}
              className={"settings-tab" + (tab === t.id ? " on" : "")}
              onClick={() => setTab(t.id)}
            >{t.label}</button>
          ))}
        </div>

        <div className="panel-body settings-body">
          {tab === "connection" ? <ConnectionTab c={config} set={set} /> : null}
          {tab === "agent"      ? <AgentTab      c={config} set={set} /> : null}
          {tab === "sampling"   ? <SamplingTab   c={config} set={set} /> : null}
          {tab === "behaviour"  ? <BehaviourTab  c={config} set={set} /> : null}
          {tab === "transcript" ? <TranscriptTab c={config} set={set} /> : null}
          {tab === "voice"      ? <VoiceTab      c={config} set={set} /> : null}
          {tab === "profiles"   ? <ProfilesTab   c={config} set={set} profile={profile} onProfile={onProfile} /> : null}
          {tab === "toggles"    ? <TogglesTab    c={config} set={set} /> : null}
          {tab === "paths"      ? <PathsTab      c={config} set={set} /> : null}
          {tab === "prompt"     ? <PromptTab /> : null}
          {tab === "about"      ? <AboutTab /> : null}
        </div>

        <div className="settings-footer">
          <div className="footer-left">
            <button className="panel-btn ghost" onClick={reset}>
              <Icon name="restart" size={11} />
              <span>restart agent</span>
            </button>
          </div>
          <div className="footer-right">
            <button className="panel-btn ghost" onClick={onClose}>cancel</button>
            <button className="panel-btn" onClick={onClose}>apply</button>
          </div>
        </div>
      </div>
    </div>
  );
}

Object.assign(window, { SettingsPanel });
