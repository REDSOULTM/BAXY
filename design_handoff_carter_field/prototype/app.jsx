/* gemma 4 · field — app shell */

const { useState, useEffect, useRef, useMemo, useCallback } = React;

/* ---------- helpers ---------- */
function pad2(n) { return n < 10 ? "0" + n : "" + n; }
function nowTs() {
  const d = new Date();
  return pad2(d.getHours()) + ":" + pad2(d.getMinutes()) + ":" + pad2(d.getSeconds());
}
function nowClock() {
  const d = new Date();
  return pad2(d.getHours()) + ":" + pad2(d.getMinutes());
}
function nowDate() {
  const d = new Date();
  const dows = ["sun","mon","tue","wed","thu","fri","sat"];
  const mos  = ["jan","feb","mar","apr","may","jun","jul","aug","sep","oct","nov","dec"];
  return dows[d.getDay()] + " " + pad2(d.getDate()) + " " + mos[d.getMonth()];
}

/* drifting metric — wanders around a target with bounded noise */
function useDriftingMetric(seed, target, range) {
  const [v, setV] = useState(target);
  useEffect(() => {
    const id = setInterval(() => {
      setV((prev) => {
        const drift = (Math.random() - 0.5) * range * 0.18;
        const pull  = (target - prev) * 0.08;
        const next = prev + drift + pull;
        return Math.max(target - range, Math.min(target + range, next));
      });
    }, 900 + seed * 11);
    return () => clearInterval(id);
  }, [target, range, seed]);
  return v;
}

/* uptime since mount, hh:mm:ss */
function useUptime() {
  const [n, setN] = useState(0);
  useEffect(() => {
    const start = Date.now() - (54 * 60 + 12) * 1000; // pretend we've been up ~54 minutes
    const id = setInterval(() => setN(Math.floor((Date.now() - start) / 1000)), 1000);
    return () => clearInterval(id);
  }, []);
  const h = Math.floor(n / 3600);
  const m = Math.floor((n % 3600) / 60);
  const s = n % 60;
  return pad2(h) + ":" + pad2(m) + ":" + pad2(s);
}

/* ---------- seed activity ---------- */
const INITIAL_ENTRIES = [
  { src: "BOOT",    msg: "weights resident · 7.21b · q4_k_m quant · 8.3 gb mapped.", ts: "21:47:02" },
  { src: "SYSTEM",  msg: "llama-server reachable on :8080 · 62 tools loaded.",        ts: "21:47:05" },
  { src: "CONTEXT", msg: "session resumed · 8 prior sessions in scope · 18,420 tokens cached.", ts: "21:47:14" },
  { src: "TOOL",    msg: "filesystem · ~/research mounted read+write · 1,284 files indexed.", ts: "21:47:18" },
  { src: "MEMORY",  msg: "128 pinned traces recalled into focus tier.",               ts: "21:47:20" },
  { src: "TRIGGER", msg: "watch · coil temp ≥ 81 °c will pause inference.",           ts: "21:47:21" },
  { src: "GEMMA",   msg: "ready. field is idle. waiting for your voice or text.",    ts: "21:47:24" },
  { src: "YOU",     msg: "compare the two embedding strategies in scratchpad/",       ts: "22:35:53" },
  { src: "THOUGHT", msg: "reading 14 files from local workspace.",                    ts: "22:36:28" },
  { src: "TOOL",    msg: "fs.read · scratchpad/embed_v1.py",                          ts: "22:36:36" },
  { src: "TOOL",    msg: "fs.read · scratchpad/embed_v2.py",                          ts: "22:36:38" },
  { src: "SYSTEM",  msg: "response generated · 412 tokens.",                          ts: "22:36:59" },
  { src: "YOU",     msg: "ok try v2 on the full corpus.",                             ts: "22:37:53" },
  { src: "THOUGHT", msg: "scheduling background job · est. 4m 20s.",                  ts: "22:37:56" },
  { src: "TOOL",    msg: "process.spawn · python -m embed.run --v2",                  ts: "22:37:59" },
];

const SURFACES = [
  { id: "sessions", label: "sessions", count: "16", unit: "cached" },
  { id: "memory",   label: "memory",   count: "1",  unit: "pinned" },
  { id: "triggers", label: "triggers", count: "6",  unit: "active" },
  { id: "tools",    label: "tools",    count: "68", unit: "wired" },
];
const SURFACES_RIGHT = SURFACES.slice(0, 2); // sessions, memory
const SURFACES_LEFT  = SURFACES.slice(2, 4); // triggers, tools

const REPLIES = [
  "noted. let me pull what we have on that and arrange it.",
  "i'd lean toward the second option — the first conflicts with thursday's note.",
  "one sec — checking the vault and the latency study together.",
  "drafted three variants. the middle one matches your tone from last tuesday.",
  "the field is quiet on that topic. want me to pull external sources?",
  "i logged it. if it crosses the trigger threshold i'll surface it again.",
  "running v2 on the full corpus · should be ready before the standup.",
];

/* ============================================================ */
function App() {
  const [convState, setConvState] = useState("idle");
  const [profile, setProfile] = useState("normal");
  const [activeSurface, setActiveSurface] = useState("memory");
  const [entries, setEntries] = useState(() => [...INITIAL_ENTRIES].reverse());
  const [clock, setClock] = useState(nowClock());
  const [date]            = useState(nowDate());
  const [openPanel, setOpenPanel] = useState(null); // 'settings' | 'sessions' | null
  const [theme, setTheme] = useState("carmine");
  const [micEnabled, setMicEnabled] = useState(true);
  const [powered, setPowered] = useState(true);
  const poweredRef = useRef(true);
  useEffect(() => { poweredRef.current = powered; }, [powered]);
  const uptime = useUptime();

  /* power toggle — when off, the whole field goes standby */
  React.useEffect(() => {
    if (!powered) {
      setConvState("standby");
    } else {
      setConvState((s) => (s === "standby" ? "idle" : s));
    }
  }, [powered]);

  const onTogglePower = () => {
    setPowered((p) => {
      const next = !p;
      pushEntry("SYSTEM", next ? "field powered on · agent online." : "field on standby · agent paused.");
      return next;
    });
  };

  useEffect(() => {
    const id = setInterval(() => setClock(nowClock()), 1000);
    return () => clearInterval(id);
  }, []);

  /* mic enabled controls listening posture. when off → standby. */
  React.useEffect(() => {
    if (!micEnabled) {
      setConvState("standby");
      clearTurn();
    } else {
      setConvState((s) => (s === "standby" ? "idle" : s));
    }
  }, [micEnabled]);

  /* idle ambient log */
  useEffect(() => {
    if (convState !== "idle") return;
    const id = setInterval(() => {
      if (Math.random() < 0.32) {
        const pool = [
          { src: "TOOL",    msg: "background index swept · 4 new files." },
          { src: "MEMORY",  msg: "consolidated 6 short-term traces into long-term." },
          { src: "TRIGGER", msg: "calendar · no pending alerts." },
          { src: "SYSTEM",  msg: "vram reclaimed · 1.2 gb returned to pool." },
          { src: "GEMMA",   msg: "watching · nothing demands attention." },
        ];
        const p = pool[Math.floor(Math.random() * pool.length)];
        pushEntry(p.src, p.msg);
      }
    }, 9500);
    return () => clearInterval(id);
  }, [convState]);

  const pushEntry = (src, msg) => {
    setEntries((prev) => [
      { id: Math.random().toString(36).slice(2), src, msg, ts: nowTs() },
      ...prev,
    ].slice(0, 80));
  };

  /* metrics */
  const profileBias = { normal: 0.6, novidente: 0.55, movilidad: 0.5 }[profile] || 0.6;
  const cpu  = useDriftingMetric(1, 26 + profileBias * 28, 7);
  const mem  = useDriftingMetric(2, 9.6 + profileBias * 6, 1.4);
  const gpu  = useDriftingMetric(3, 15 + profileBias * 30, 8);
  const net  = useDriftingMetric(4, 2.4 + profileBias * 6, 1.3);
  const dsk  = useDriftingMetric(5, 38, 4);
  const tmp  = useDriftingMetric(6, 56 + profileBias * 8, 3);

  const activeBoost = convState === "thinking" ? 22 : convState === "speaking" ? 12 : 0;
  const cpuShow = Math.max(0, Math.min(100, cpu + activeBoost));
  const gpuShow = Math.max(0, Math.min(100, gpu + activeBoost * 1.4));
  const tmpShow = Math.max(0, Math.min(95, tmp + activeBoost * 0.18));

  const metrics = {
    cpu: { norm: cpuShow / 100,         text: cpuShow.toFixed(0) },
    mem: { norm: mem / 32,              text: mem.toFixed(1) },
    gpu: { norm: gpuShow / 100,         text: gpuShow.toFixed(0) },
    net: { norm: Math.min(1, net / 10), text: net.toFixed(1) },
    dsk: { norm: dsk / 100,             text: dsk.toFixed(0) },
    tmp: { norm: Math.min(1, tmpShow / 90),  text: tmpShow.toFixed(0), hot: tmpShow > 76 },
  };

  // overall system % — weighted average
  const systemPct = Math.round(cpuShow * 0.35 + (mem / 32) * 100 * 0.25 + gpuShow * 0.4);

  /* ctx + tokens */
  const [tokensTotal, setTokensTotal] = useState(18420);
  useEffect(() => {
    if (convState !== "thinking" && convState !== "speaking") return;
    const id = setInterval(() => {
      setTokensTotal((t) => t + Math.floor(8 + Math.random() * 24));
    }, 700);
    return () => clearInterval(id);
  }, [convState]);

  const ctxUsed  = 12200 + Math.floor((mem / 32) * 8400);
  const ctxTotal = 34000;

  const fieldMetrics = [
    { k: "entropy",     v: (0.40 + (cpuShow / 100) * 0.18).toFixed(2) },
    { k: "temperature", v: "0.7" },
    { k: "ctx · used",  v: ((ctxUsed / ctxTotal) * 100).toFixed(0) + " %" },
    { k: "tokens/s",    v: convState === "thinking" ? (42 + Math.random() * 6).toFixed(1)
                         : convState === "speaking" ? (24 + Math.random() * 4).toFixed(1)
                         : "0.0" },
    { k: "draw · w",    v: (60 + profileBias * 28 + activeBoost * 0.4).toFixed(0) },
  ];

  /* conversation turn */
  const turnTimers = useRef([]);
  const clearTurn = () => { turnTimers.current.forEach(clearTimeout); turnTimers.current = []; };

  const onSubmit = (text) => {
    if (!micEnabled) {
      // skip listening stage when in standby — user is typing, no voice in.
      clearTurn();
      pushEntry("YOU", text);
      setConvState("thinking");
      turnTimers.current.push(setTimeout(() => {
        pushEntry("THOUGHT", "text-only path · voice channel disabled.");
      }, 900));
      turnTimers.current.push(setTimeout(() => {
        pushEntry("TOOL", "router · routing through agent (text-only).");
      }, 1900));
      turnTimers.current.push(setTimeout(() => {
        setConvState("speaking");
        pushEntry("GEMMA", REPLIES[Math.floor(Math.random() * REPLIES.length)]);
      }, 3600));
      turnTimers.current.push(setTimeout(() => {
        setConvState("standby");
      }, 6400));
      return;
    }
    clearTurn();
    pushEntry("YOU", text);
    setConvState("listening");
    turnTimers.current.push(setTimeout(() => {
      setConvState("thinking");
      pushEntry("THOUGHT", "scanning context · routing through agent.");
      if (Math.random() < 0.9) {
        const pool = [
          "memory · scanning 128 pinned items for matches.",
          "fs.read · ~/research/digest/47.md",
          "tools · web fetch suspended · using local cache.",
          "router · routing through agent · tools sub-graph.",
          "context · 14 files pulled from local workspace.",
        ];
        turnTimers.current.push(setTimeout(() => {
          pushEntry("TOOL", pool[Math.floor(Math.random() * pool.length)]);
        }, 1100));
        turnTimers.current.push(setTimeout(() => {
          pushEntry("THOUGHT", "ranking three plausible responses by salience.");
        }, 2200));
      }
    }, 1300));
    turnTimers.current.push(setTimeout(() => {
      setConvState("speaking");
      pushEntry("GEMMA", REPLIES[Math.floor(Math.random() * REPLIES.length)]);
    }, 4400));
    turnTimers.current.push(setTimeout(() => {
      setConvState("idle");
    }, 7000));
  };

  const onToggleMic = () => {
    setMicEnabled((m) => {
      const next = !m;
      pushEntry("SYSTEM", next
        ? "voice channel enabled · ambient listening on · wake word ‘gemma’."
        : "voice channel disabled · standby mode · type to engage."
      );
      return next;
    });
  };

  useEffect(() => () => clearTurn(), []);

  /* drive the traveling border light — ramps speed up/down with power */
  useEffect(() => {
    const frame = document.querySelector(".app-frame");
    if (!frame) return;
    let raf, last = performance.now();
    let angle = 0;
    let speed = 1;              // 0..1 fraction of full speed
    const FULL = 360 / 3.4;     // deg per second at full speed
    const loop = (now) => {
      const dt = Math.min(0.05, (now - last) / 1000);
      last = now;
      const target = poweredRef.current ? 1 : 0;
      // ease current speed toward target (acceleration on, deceleration off)
      speed += (target - speed) * Math.min(1, dt * 2.6);
      if (target === 0 && speed < 0.012) speed = 0;
      angle = (angle + speed * FULL * dt) % 360;
      frame.style.setProperty("--bd-angle", angle.toFixed(2) + "deg");
      raf = requestAnimationFrame(loop);
    };
    raf = requestAnimationFrame(loop);
    return () => cancelAnimationFrame(raf);
  }, []);

  /* recolor the traveling border light per state */
  useEffect(() => {
    const frame = document.querySelector(".app-frame");
    if (!frame) return;
    const SET = {
      standby:   { base: "#2a2f3a", mid: "#5B6580", hi: "#8B95A8", peak: "#D8DCE6", glow: "rgba(139,149,168,0.75)", bar: "#5B6580" },
      idle:      { base: "#5a1a22", mid: "#B83A4A", hi: "#FF4D63", peak: "#FFE3E7", glow: "rgba(255,77,99,0.9)",    bar: "#5B7FDB" },
      listening: { base: "#7A1E2B", mid: "#E55366", hi: "#FF6677", peak: "#FFFFFF", glow: "rgba(255,102,119,0.95)", bar: "#6FA8B0" },
      thinking:  { base: "#1B2A5E", mid: "#2E4BA0", hi: "#5B7FDB", peak: "#C8D6F5", glow: "rgba(91,127,219,0.9)",   bar: "#C9A66B" },
      speaking:  { base: "#6B5A2F", mid: "#C9A66B", hi: "#E8C98E", peak: "#F8EED2", glow: "rgba(232,201,142,0.9)",  bar: "#7B95D9" },
    };
    const c = SET[convState] || SET.idle;
    frame.style.setProperty("--bd-base", c.base);
    frame.style.setProperty("--bd-mid",  c.mid);
    frame.style.setProperty("--bd-hi",   c.hi);
    frame.style.setProperty("--bd-peak", c.peak);
    frame.style.setProperty("--bd-glow", c.glow);
    frame.style.setProperty("--bar-color", c.bar);
    // chrome accent (mic, online, profiles, settings, input, surfaces, log tags):
    // stays the ORIGINAL red at rest, only takes the contrast color during an
    // active conversation state, then returns to red.
    const active = convState === "listening" || convState === "thinking" || convState === "speaking";
    frame.style.setProperty("--carmine", active ? c.bar : "#B83A4A");
  }, [convState]);

  return (
    <div className="app-frame">
    <div className="shell">
      {/* POPOVERS */}
      {openPanel === "settings" ? (
        <SettingsPanel
          theme={theme}
          onTheme={setTheme}
          profile={profile}
          onProfile={setProfile}
          onClose={() => setOpenPanel(null)}
        />
      ) : null}

      {/* COLUMNS */}
      <div className="cols">
        <div className="col left">
          <SubstratePanel
            metrics={metrics}
            profile={profile}
            onProfile={setProfile}
            field={fieldMetrics}
            systemPct={systemPct}
            ctxUsed={ctxUsed}
            ctxTotal={ctxTotal}
            uptime={uptime}
            tokens={tokensTotal.toLocaleString()}
            peers={"0"}
            state={convState}
            powered={powered}
            onTogglePower={onTogglePower}
            surfaces={SURFACES_LEFT}
            activeSurface={activeSurface}
            onSurface={setActiveSurface}
          />
        </div>
        <div className="col center">
          <FieldCenter
            state={convState}
            onSubmit={onSubmit}
            nodeCount={NODE_COUNT}
            edgeCount={EDGE_COUNT}
            micEnabled={micEnabled}
            onToggleMic={onToggleMic}
          />
        </div>
        <div className="col right">
          <ActivityPanel
            entries={entries}
            session={"526fefd4afd7"}
            entryCount={entries.length}
            settingsOpen={openPanel === "settings"}
            onSettings={() => setOpenPanel(openPanel === "settings" ? null : "settings")}
            onNewSession={() => { pushEntry("SYSTEM", "new session started · context cleared."); setEntries([]); }}
            onHelp={() => pushEntry("SYSTEM", "shortcuts · enter sends · / focuses · ⌘k history.")}
            surfaces={SURFACES_RIGHT}
            activeSurface={activeSurface}
            onSurface={setActiveSurface}
            rightFooter={{ left: "local · no telemetry", right: clock }}
          />
        </div>
      </div>
    </div>
    </div>
  );
}

ReactDOM.createRoot(document.getElementById("root")).render(<App />);
