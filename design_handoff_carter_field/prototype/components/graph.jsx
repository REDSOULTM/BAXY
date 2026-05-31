/* neural graph — organic mesh orbiting a glowing red core,
   on a starfield+nebula background. animated signal pulses. */

/* hubs orbit the center; nothing crosses through the core zone. */
const HUBS = [
  { id: "context", x: 0.50, y: 0.13, label: "context", r: 9 },
  { id: "router",  x: 0.16, y: 0.32, label: "router",  r: 9 },
  { id: "agent",   x: 0.84, y: 0.28, label: "agent",   r: 9 },
  { id: "tools",   x: 0.88, y: 0.58, label: "tools",   r: 9 },
  { id: "memory",  x: 0.04, y: 0.56, label: "memory",  r: 9 },
  { id: "voice",   x: 0.58, y: 0.88, label: "voice",   r: 10 },
];

const SMALL = [
  // upper arc (router ↔ context ↔ agent)
  { id: "n1",  x: 0.30, y: 0.20 },
  { id: "n2",  x: 0.40, y: 0.08 },
  { id: "n3",  x: 0.62, y: 0.10 },
  { id: "n4",  x: 0.72, y: 0.18 },
  // right arc (agent ↔ tools)
  { id: "n5",  x: 0.94, y: 0.42 },
  // lower-right (tools ↔ voice)
  { id: "n6",  x: 0.82, y: 0.74 },
  { id: "n7",  x: 0.72, y: 0.84 },
  // lower-left (voice ↔ memory)
  { id: "n8",  x: 0.40, y: 0.94 },
  { id: "n9",  x: 0.28, y: 0.84 },
  // left arc (memory ↔ router)
  { id: "n10", x: 0.06, y: 0.52 },
  { id: "n11", x: 0.10, y: 0.42 },
  // periphery (sparse)
  { id: "n12", x: 0.04, y: 0.20 },
  { id: "n13", x: 0.96, y: 0.18 },
  { id: "n14", x: 0.96, y: 0.78 },
  { id: "n15", x: 0.20, y: 0.70 },
  { id: "n16", x: 0.50, y: 0.04 },
  // inner orbital ring (closer to core, feed pulses inward)
  { id: "n17", x: 0.30, y: 0.46 },
  { id: "n18", x: 0.66, y: 0.40 },
  { id: "n19", x: 0.34, y: 0.66 },
  { id: "n20", x: 0.68, y: 0.62 },
];

const ALL_NODES = [...HUBS, ...SMALL].map((n) => ({ ...n }));
ALL_NODES.forEach((n, i) => {
  if (!HUBS.find((h) => h.id === n.id)) {
    n.r = 4 + (((i * 13) % 5) === 0 ? 1.5 : 0);
  }
});
const NODE_BY_ID = Object.fromEntries(ALL_NODES.map((n) => [n.id, n]));

/* edges — coherent triangulated mesh; nothing crosses the core */
const EDGES = [
  // upper arc (context cluster)
  ["context", "n1",     "context"],
  ["context", "n2",     "context"],
  ["context", "n3",     "context"],
  ["context", "n4",     "context"],
  ["context", "n16",    "context"],
  ["n2",      "n1",     "context"],
  ["n2",      "n3",     "context"],
  ["n2",      "n16",    "context"],
  ["n3",      "n4",     "context"],
  ["n1",      "router", "context"],
  ["n4",      "agent",  "context"],
  // right arc (agent → tools)
  ["agent",   "n5",     "agent"],
  ["agent",   "n13",    "agent"],
  ["n5",      "tools",  "tools"],
  ["agent",   "tools",  "core"],
  ["tools",   "n14",    "tools"],
  // tools → voice
  ["tools",   "n6",     "tools"],
  ["n6",      "voice",  "voice"],
  ["n6",      "n7",     "voice"],
  ["n7",      "voice",  "voice"],
  ["tools",   "n7",     "tools"],
  // voice → memory
  ["voice",   "n8",     "voice"],
  ["voice",   "n9",     "voice"],
  ["n9",      "memory", "memory"],
  ["n8",      "n9",     "voice"],
  ["memory",  "n15",    "memory"],
  // memory → router (left arc)
  ["memory",  "n10",    "memory"],
  ["memory",  "n11",    "memory"],
  ["n10",     "n11",    "memory"],
  ["n10",     "router", "memory"],
  ["n11",     "router", "core"],
  ["router",  "n12",    "core"],
  ["n12",     "n11",    "core"],
  // inner orbital ring (n17..n20) — orbit the core
  ["n17",     "n18",    "core"],
  ["n18",     "n20",    "core"],
  ["n20",     "n19",    "core"],
  ["n19",     "n17",    "core"],
  // inner ring → hubs
  ["n17",     "router", "core"],
  ["n17",     "context","core"],
  ["n18",     "context","core"],
  ["n18",     "agent",  "core"],
  ["n20",     "tools",  "core"],
  ["n20",     "voice",  "voice"],
  ["n19",     "voice",  "voice"],
  ["n19",     "memory", "memory"],
].map(([a, b, tag]) => ({ a, b, tag }));

/* edges that feed the core itself (visually drawn into the center) */
const CORE_FEEDS = ["n17", "n18", "n19", "n20"];

/* state subgraph + spawn rates */
const STATE_EDGES = {
  standby:   EDGES.slice(0, 0),
  idle:      EDGES,
  listening: EDGES.filter((e) => e.tag === "voice" || e.tag === "core"),
  thinking:  EDGES.filter((e) => e.tag === "core" || e.tag === "memory" || e.tag === "context" || e.tag === "agent"),
  speaking:  EDGES.filter((e) => e.tag === "voice" || e.tag === "tools" || e.tag === "core"),
};
const STATE_SPAWN_RATE = {
  standby: 0,
  idle: 0.8,
  listening: 5,
  thinking: 12,
  speaking: 7,
};

const NODE_COUNT = ALL_NODES.length;
const EDGE_COUNT = EDGES.length;

/* state-driven core palette */
const CORE_COLORS = {
  standby:   { halo: "#3F4860",  mid: "#5B6580",  inner: "#8B95A8", hot: "#D8DCE6", labelColor: "#5B6580", pulseSpeed: 0.8 },
  idle:      { halo: "#7A1E2B",  mid: "#B83A4A",  inner: "#E55366", hot: "#F5C6CC", labelColor: "#7A1E2B", pulseSpeed: 1.1 },
  listening: { halo: "#B83A4A",  mid: "#E55366",  inner: "#F5C6CC", hot: "#FFE9EC", labelColor: "#B83A4A", pulseSpeed: 2.4 },
  thinking:  { halo: "#1B2A5E",  mid: "#2E4BA0",  inner: "#5B7FDB", hot: "#B8C6E8", labelColor: "#2E4BA0", pulseSpeed: 3.4 },
  speaking:  { halo: "#6B5A2F",  mid: "#C9A66B",  inner: "#E8C98E", hot: "#F5E6C0", labelColor: "#8A7A4A", pulseSpeed: 2.2 },
};

function orbitTint(state, isRed) {
  if (state === "standby")   return isRed ? "#5B6580" : "#3F4860";
  if (state === "thinking")  return isRed ? "#5B7FDB" : "#2E4BA0";
  if (state === "speaking")  return isRed ? "#C9A66B" : "#8A7A4A";
  if (state === "listening") return isRed ? "#E55366" : "#B83A4A";
  return isRed ? "#B83A4A" : "#5B7FDB";
}

function pulseTint(state) {
  if (state === "thinking") return { glow: "url(#pulseGlowBlue)", dot: "#7B95D9" };
  if (state === "speaking") return { glow: "url(#pulseGlowGold)", dot: "#E8C98E" };
  return { glow: "url(#pulseGlow)", dot: "#E55366" };
}

/* state-driven nebula tint — contrasts with core */
const NEBULA_TINT = {
  standby:   { a: "#3F4860", b: "#5B6580" },
  idle:      { a: "#1B2A5E", b: "#7A1E2B" },  // blue + faint red — cool around hot core
  listening: { a: "#6B5A2F", b: "#1B2A5E" },  // amber + blue — contrast w/ bright red
  thinking:  { a: "#7A1E2B", b: "#6B5A2F" },  // red + amber — warm against blue core
  speaking:  { a: "#1B2A5E", b: "#7A1E2B" },  // blue + red — cool against gold core
};

/* ---------- starfield + nebula (memoized, sized to viewport) ---------- */
function useStars(w, h) {
  return React.useMemo(() => {
    const rng = seededRng(91);
    const stars = [];
    // generate over a larger area than the viewport so rotation never reveals empty corners
    const reach = Math.max(w, h) * 1.5;
    const cx = w / 2, cy = h / 2;
    const n = Math.round((reach * reach) / 2400);
    for (let i = 0; i < n; i++) {
      const t = rng();
      const dx = (rng() - 0.5) * 2 * reach;
      const dy = (rng() - 0.5) * 2 * reach;
      stars.push({
        x: cx + dx,
        y: cy + dy,
        r: 0.25 + rng() * 0.85,
        op: 0.12 + rng() * 0.55,
        color: t < 0.10 ? "#B83A4A"
             : t < 0.18 ? "#5B7FDB"
             : "#D8DCE6",
        twink: rng() * 6.28,
        // each star has its own slight radial drift speed (parallax-ish)
        speedFactor: 0.85 + rng() * 0.3,
      });
    }
    return stars;
  }, [w, h]);
}

/* ---------- orbit ring particles (rotate around core) ---------- */
function useOrbitRing(cx, cy, minR, maxR) {
  return React.useMemo(() => {
    const rng = seededRng(311);
    const arr = [];
    const n = 64;
    for (let i = 0; i < n; i++) {
      const theta = rng() * Math.PI * 2;
      const r = minR + rng() * (maxR - minR);
      arr.push({
        theta,
        r,
        size: 0.8 + rng() * 1.3,
        op: 0.45 + rng() * 0.45,
        red: rng() < 0.7,
      });
    }
    return arr;
  }, [cx, cy, minR, maxR]);
}

/* ============================================================ */
function NeuralGraph({ state }) {
  const wrapRef = React.useRef(null);
  const [size, setSize] = React.useState({ w: 720, h: 480 });
  const pulsesRef = React.useRef([]);
  const rotationRef = React.useRef(0);
  const galaxyRotRef = React.useRef(0);
  const nebulaRotRef = React.useRef(0);
  const corePulseRef = React.useRef(0);
  const prevStateRef = React.useRef("idle");
  const lastTurnRef  = React.useRef({ endedAt: 0, tags: new Set() });
  const tracerRef    = React.useRef({ active: false, t: 0, startedAt: 0, path: [] });
  const meshOpRef    = React.useRef(1);
  const [, force] = React.useReducer((x) => x + 1, 0);
  const lastSpawnRef = React.useRef(0);
  const rafRef = React.useRef(0);

  React.useEffect(() => {
    if (!wrapRef.current) return;
    const measure = () => {
      const cr = wrapRef.current.getBoundingClientRect();
      setSize({ w: Math.max(200, cr.width), h: Math.max(160, cr.height) });
    };
    const ro = new ResizeObserver(measure);
    ro.observe(wrapRef.current);
    // initial measure after layout settles
    measure();
    requestAnimationFrame(measure);
    window.addEventListener("resize", measure);
    return () => { ro.disconnect(); window.removeEventListener("resize", measure); };
  }, []);

  React.useEffect(() => {
    const prev = prevStateRef.current;
    if ((state === "idle" || state === "standby") && (prev === "speaking" || prev === "thinking")) {
      lastTurnRef.current = {
        endedAt: performance.now(),
        tags: new Set(["core", "memory", "context", "agent", "voice", "tools"]),
      };
    }
    // fire the tracer when the agent transitions into thinking — it'll travel the path
    // through context → router → memory → agent → tools → voice over the active turn.
    if (state === "thinking" && prev !== "thinking") {
      tracerRef.current = {
        active: true,
        t: 0,
        startedAt: performance.now(),
        path: ["voice", "router", "context", "n4", "memory", "n11", "router", "agent", "n7", "tools", "n6", "voice"],
      };
    }
    prevStateRef.current = state;
  }, [state]);

  React.useEffect(() => {
    let prev = performance.now();
    const tick = (now) => {
      const dt = Math.min(0.05, (now - prev) / 1000);
      prev = now;

      // pulses
      const next = [];
      const arr = pulsesRef.current;
      for (let i = 0; i < arr.length; i++) {
        const p = arr[i];
        p.t += p.speed * dt;
        if (p.t < 1) next.push(p);
      }
      pulsesRef.current = next;

      // tracer — big highlight pulse following the agent's path
      if (tracerRef.current.active) {        // ~5 seconds to traverse the full path (path length ≈ 11 segments → ~0.45s per leg)
        tracerRef.current.t += dt / 5.0;
        if (tracerRef.current.t >= 1) {
          tracerRef.current.active = false;
        }
      }

      const rate = STATE_SPAWN_RATE[state] || 0.5;
      lastSpawnRef.current += dt * rate;
      while (lastSpawnRef.current >= 1) {
        lastSpawnRef.current -= 1;
        const pool = STATE_EDGES[state] || EDGES;
        const edge = pool[Math.floor(Math.random() * pool.length)];
        const idx = EDGES.indexOf(edge);
        if (idx >= 0) {
          pulsesRef.current.push({
            edgeIdx: idx,
            t: 0,
            speed: 0.45 + Math.random() * 0.55,
            reverse: Math.random() < 0.35,
          });
        }
      }

      // orbit rotation
      const rotSpeed =
        state === "standby"   ? 1.5
        : state === "idle"      ? 4
        : state === "listening" ? 9
        : state === "thinking"  ? 22
        : state === "speaking"  ? 14 : 4;
      rotationRef.current = (rotationRef.current + rotSpeed * dt) % 360;

      // mesh fade — neurons dissolve in standby, grow back when online
      {
        const target = state === "standby" ? 0 : 1;
        meshOpRef.current += (target - meshOpRef.current) * Math.min(1, dt * 2.2);
        if (Math.abs(target - meshOpRef.current) < 0.002) meshOpRef.current = target;
      }

      // galaxy (starfield) rotation — very slow, like a real galaxy
      const galSpeed =
        state === "standby"   ? 0.15
        : state === "idle"      ? 0.30
        : state === "listening" ? 0.55
        : state === "thinking"  ? 1.20
        : state === "speaking"  ? 0.70 : 0.30;
      galaxyRotRef.current = (galaxyRotRef.current + galSpeed * dt) % 360;

      // nebula counter-drifts at half speed for parallax
      nebulaRotRef.current = (nebulaRotRef.current - galSpeed * 0.4 * dt) % 360;

      corePulseRef.current = now / 1000;

      force();
      rafRef.current = requestAnimationFrame(tick);
    };
    rafRef.current = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(rafRef.current);
  }, [state]);

  const { w, h } = size;
  const pad = 14;
  const inW = w - pad * 2;
  const inH = h - pad * 2;
  const px = (n) => pad + n.x * inW;
  const py = (n) => pad + n.y * inH;

  const cx = pad + 0.5 * inW;
  const cy = pad + 0.5 * inH;
  // core radius scales with stage
  const coreR = Math.max(48, Math.min(112, Math.min(inW, inH) * 0.18));
  const ringInner = coreR * 2.4;
  const ringOuter = coreR * 3.6;

  const stars = useStars(w, h);
  const orbit = useOrbitRing(cx, cy, ringInner, ringOuter);

  const litTags = {
    standby: new Set(),
    idle: new Set(),
    listening: new Set(["voice"]),
    thinking: new Set(["core", "memory", "context", "agent"]),
    speaking: new Set(["voice", "tools", "core"]),
  }[state] || new Set();

  const coreC = CORE_COLORS[state] || CORE_COLORS.idle;
  const nebC  = NEBULA_TINT[state] || NEBULA_TINT.idle;
  const meshOp = meshOpRef.current;

  // core pulse magnitude (slow throb)
  const tNow = corePulseRef.current;
  const corePulse = state === "standby"
    ? 0.35 + Math.sin(tNow * coreC.pulseSpeed) * 0.05
    : 0.55 + Math.sin(tNow * coreC.pulseSpeed) * 0.18;
  const coreHotPulse = state === "standby"
    ? 0.4 + Math.sin(tNow * 1.5) * 0.1
    : 0.7 + Math.sin(tNow * coreC.pulseSpeed * 1.8) * 0.25;
  const pulseStyle = pulseTint(state);

  return (
    <div className="field-stage" ref={wrapRef}>
      <svg width={w} height={h} style={{ display: "block" }}>
        <defs>
          {/* nebula bands — dynamic stops based on state */}
          <linearGradient id="nebA" x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%"  stopColor={nebC.a} stopOpacity="0" />
            <stop offset="50%" stopColor={nebC.a} stopOpacity="0.22" />
            <stop offset="100%" stopColor={nebC.a} stopOpacity="0" />
          </linearGradient>
          <linearGradient id="nebB" x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%"  stopColor={nebC.b} stopOpacity="0" />
            <stop offset="50%" stopColor={nebC.b} stopOpacity="0.18" />
            <stop offset="100%" stopColor={nebC.b} stopOpacity="0" />
          </linearGradient>
          {/* core glows — dynamic stops based on state */}
          <radialGradient id="coreHalo" cx="50%" cy="50%" r="50%">
            <stop offset="0%"  stopColor={coreC.inner} stopOpacity="0.7" />
            <stop offset="30%" stopColor={coreC.mid}   stopOpacity="0.45" />
            <stop offset="65%" stopColor={coreC.halo}  stopOpacity="0.2" />
            <stop offset="100%" stopColor={coreC.halo} stopOpacity="0" />
          </radialGradient>
          <radialGradient id="coreInner" cx="50%" cy="50%" r="50%">
            <stop offset="0%"  stopColor={coreC.hot}   stopOpacity="0.95" />
            <stop offset="40%" stopColor={coreC.inner} stopOpacity="0.6" />
            <stop offset="100%" stopColor={coreC.mid}  stopOpacity="0" />
          </radialGradient>
          <radialGradient id="nodeGlow" cx="50%" cy="50%" r="50%">
            <stop offset="0%" stopColor="#5B7FDB" stopOpacity="0.45" />
            <stop offset="60%" stopColor="#2E4BA0" stopOpacity="0.15" />
            <stop offset="100%" stopColor="#2E4BA0" stopOpacity="0" />
          </radialGradient>
          <radialGradient id="hubRedGlow" cx="50%" cy="50%" r="50%">
            <stop offset="0%" stopColor="#E55366" stopOpacity="0.55" />
            <stop offset="60%" stopColor="#B83A4A" stopOpacity="0.18" />
            <stop offset="100%" stopColor="#B83A4A" stopOpacity="0" />
          </radialGradient>
          <radialGradient id="hubGoldGlow" cx="50%" cy="50%" r="50%">
            <stop offset="0%" stopColor="#E8C98E" stopOpacity="0.55" />
            <stop offset="60%" stopColor="#8A7A4A" stopOpacity="0.18" />
            <stop offset="100%" stopColor="#8A7A4A" stopOpacity="0" />
          </radialGradient>
          <radialGradient id="nodeStandbyGlow" cx="50%" cy="50%" r="50%">
            <stop offset="0%" stopColor="#8B95A8" stopOpacity="0.35" />
            <stop offset="60%" stopColor="#5B6580" stopOpacity="0.10" />
            <stop offset="100%" stopColor="#5B6580" stopOpacity="0" />
          </radialGradient>
          <radialGradient id="pulseGlow" cx="50%" cy="50%" r="50%">
            <stop offset="0%"  stopColor="#E55366" stopOpacity="0.85" />
            <stop offset="100%" stopColor="#B83A4A" stopOpacity="0" />
          </radialGradient>
          <radialGradient id="pulseGlowBlue" cx="50%" cy="50%" r="50%">
            <stop offset="0%"  stopColor="#7B95D9" stopOpacity="0.85" />
            <stop offset="100%" stopColor="#2E4BA0" stopOpacity="0" />
          </radialGradient>
          <radialGradient id="pulseGlowGold" cx="50%" cy="50%" r="50%">
            <stop offset="0%"  stopColor="#E8C98E" stopOpacity="0.85" />
            <stop offset="100%" stopColor="#8A7A4A" stopOpacity="0" />
          </radialGradient>
          {/* tracer: big universal-contrast pulse — ivory core, halo opposite of state */}
          <radialGradient id="tracerGlow" cx="50%" cy="50%" r="50%">
            <stop offset="0%"  stopColor="#FFF6E0" stopOpacity="1" />
            <stop offset="35%" stopColor="#F5E6C0" stopOpacity="0.7" />
            <stop offset="100%" stopColor="#F5E6C0" stopOpacity="0" />
          </radialGradient>
        </defs>

        {/* LAYER 1 — nebula bands (wavy translucent streaks) — slow counter-drift */}
        <g opacity="0.5" transform={`rotate(${nebulaRotRef.current.toFixed(2)} ${cx} ${cy})`}>
          <path d={`M ${-20} ${h * 0.30} Q ${w * 0.30} ${h * 0.22} ${w * 0.55} ${h * 0.34} T ${w + 20} ${h * 0.28}`}
                stroke="url(#nebA)" strokeWidth={70} fill="none" />
          <path d={`M ${-20} ${h * 0.70} Q ${w * 0.35} ${h * 0.78} ${w * 0.65} ${h * 0.66} T ${w + 20} ${h * 0.74}`}
                stroke="url(#nebB)" strokeWidth={90} fill="none" />
          <path d={`M ${-20} ${h * 0.52} Q ${w * 0.50} ${h * 0.42} ${w + 20} ${h * 0.56}`}
                stroke="url(#nebA)" strokeWidth={50} fill="none" opacity="0.6" />
        </g>

        {/* LAYER 2 — starfield — rotates slowly like a galaxy */}
        <g transform={`rotate(${galaxyRotRef.current.toFixed(2)} ${cx} ${cy})`}>
          {stars.map((s, i) => {
            // very slight twinkle
            const tw = 0.85 + Math.sin(tNow * 0.9 + s.twink) * 0.15;
            return (
              <circle
                key={i}
                cx={s.x.toFixed(1)}
                cy={s.y.toFixed(1)}
                r={s.r.toFixed(2)}
                fill={s.color}
                opacity={(s.op * tw).toFixed(3)}
              />
            );
          })}
        </g>

        {/* LAYER 3 — edges (faint mesh + recent-path highlight) */}
        <g opacity={meshOp}>
          {EDGES.map((e, i) => {
            const a = NODE_BY_ID[e.a];
            const b = NODE_BY_ID[e.b];
            const lit = litTags.has(e.tag);
            // recent-turn glow: edges from the last turn stay faintly lit for ~5s after it ends
            const turnAge = (performance.now() - lastTurnRef.current.endedAt) / 1000;
            const inLastTurn = lastTurnRef.current.tags.has(e.tag) && turnAge < 5;
            const trail = inLastTurn ? Math.max(0, 1 - turnAge / 5) : 0;
            // base stroke / opacity, with carmine trail blend if in last turn
            const baseStroke = lit ? "#3F4F7A" : "#2A3550";
            const stroke = trail > 0 ? "#7A1E2B" : baseStroke;
            const op = lit ? 0.95 : (trail > 0 ? 0.45 + trail * 0.5 : 0.65);
            return (
              <line
                key={i}
                x1={px(a)} y1={py(a)}
                x2={px(b)} y2={py(b)}
                stroke={stroke}
                strokeWidth={1}
                opacity={op}
              />
            );
          })}
        </g>

        {/* LAYER 4 — core feed lines (inner ring → center) */}
        <g opacity={meshOp}>
          {CORE_FEEDS.map((id) => {
            const n = NODE_BY_ID[id];
            return (
              <line
                key={id}
                x1={px(n)} y1={py(n)}
                x2={cx} y2={cy}
                stroke={coreC.halo}
                strokeWidth={1}
                opacity={state === "standby" ? 0.25 : 0.45}
                strokeDasharray="2 3"
              />
            );
          })}
        </g>

        {/* LAYER 5 — rotating orbit particles around core */}
        <g opacity={meshOp} transform={`rotate(${rotationRef.current.toFixed(2)} ${cx} ${cy})`}>
          {orbit.map((p, i) => {
            const x = cx + p.r * Math.cos(p.theta);
            const y = cy + p.r * Math.sin(p.theta);
            return (
              <circle
                key={i}
                cx={x.toFixed(2)} cy={y.toFixed(2)}
                r={p.size.toFixed(2)}
                fill={orbitTint(state, p.red)}
                opacity={(p.op * (state === "standby" ? 0.55 : 1)).toFixed(2)}
              />
            );
          })}
        </g>

        {/* LAYER 6 — central CORE */}
        <g>
          {/* outer halo */}
          <circle cx={cx} cy={cy} r={coreR * 2.0} fill="url(#coreHalo)" opacity={corePulse.toFixed(3)} />
          {/* mid disc */}
          <circle cx={cx} cy={cy} r={coreR * 1.0} fill="url(#coreInner)" opacity={state === "standby" ? 0.55 : 0.95} />
          {/* dense nucleus */}
          <circle cx={cx} cy={cy} r={coreR * 0.32} fill={coreC.inner} opacity={state === "standby" ? 0.55 : 0.92} />
          {/* hot pixel */}
          <circle cx={cx} cy={cy} r={coreR * 0.12} fill={coreC.hot} opacity={coreHotPulse.toFixed(3)} />
          {/* state label BELOW core — in the empty space between core and voice hub */}
          <text
            x={cx} y={cy + coreR * 1.85}
            textAnchor="middle"
            fill={coreC.labelColor}
            fontFamily="JetBrains Mono, monospace"
            fontSize={Math.max(18, coreR * 0.72)}
            fontWeight={500}
            letterSpacing="0.28em"
            opacity={state === "standby" ? 0.6 : 0.95}
          >
            {state.charAt(0).toUpperCase() + state.slice(1)}
          </text>
        </g>

        {/* LAYER 7 — nodes (state-tinted) */}
        <g opacity={meshOp}>
          {ALL_NODES.map((n) => {
            const isHub = HUBS.find((h) => h.id === n.id);
            const isInner = ["n17", "n18", "n19", "n20"].includes(n.id);

            // base colors
            let outerFill = "#2E4BA0";
            let innerFill = "#5B7FDB";
            let glow = "url(#nodeGlow)";
            let labelFill = "#5B6580";

            // state-tinted node colors
            if (state === "thinking") {
              outerFill = isInner ? "#1B2A5E" : "#2E4BA0";
              innerFill = "#7B95D9";
              glow = "url(#nodeGlow)";
              labelFill = isHub ? "#7B95D9" : "#5B6580";
            } else if (state === "speaking") {
              outerFill = isInner ? "#6B5A2F" : "#8A7A4A";
              innerFill = "#E8C98E";
              glow = "url(#hubGoldGlow)";
              labelFill = isHub ? "#C9A66B" : "#5B6580";
            } else if (state === "listening") {
              outerFill = isInner ? "#7A1E2B" : "#B83A4A";
              innerFill = "#E55366";
              glow = "url(#hubRedGlow)";
              labelFill = isHub ? "#E55366" : "#5B6580";
            } else if (state === "standby") {
              outerFill = isInner ? "#3F4860" : "#5B6580";
              innerFill = "#8B95A8";
              glow = "url(#nodeStandbyGlow)";
              labelFill = "#3F4860";
            } else {
              // idle — keep hubs voice/memory red, others blue
              const hubRed = isHub && (n.id === "voice" || n.id === "memory");
              outerFill = isInner ? "#7A1E2B" : hubRed ? "#B83A4A" : "#2E4BA0";
              innerFill = hubRed ? "#E55366" : "#5B7FDB";
              glow = hubRed ? "url(#hubRedGlow)" : "url(#nodeGlow)";
              labelFill = hubRed ? "#B83A4A" : "#5B6580";
            }

            return (
              <g key={n.id}>
                {isHub && (
                  <circle
                    cx={px(n)} cy={py(n)}
                    r={n.r * 2.2}
                    fill={glow}
                  />
                )}
                <circle
                  cx={px(n)} cy={py(n)}
                  r={n.r}
                  fill={outerFill}
                  opacity={isHub ? 0.95 : 0.82}
                />
                {isHub && (
                  <circle
                    cx={px(n)} cy={py(n)}
                    r={n.r * 0.45}
                    fill={innerFill}
                    opacity={0.85}
                  />
                )}
                {isHub && (
                  <text
                    x={px(n)} y={py(n) + n.r + 14}
                    textAnchor="middle"
                    fill={labelFill}
                    fontFamily="Inter, sans-serif"
                    fontSize={10}
                    fontWeight={500}
                    letterSpacing="0.02em"
                  >
                    {n.label}
                  </text>
                )}
              </g>
            );
          })}
        </g>

        {/* LAYER 8 — signal pulses (head + tail trail) */}
        <g opacity={meshOp}>
          {pulsesRef.current.map((p, i) => {
            const edge = EDGES[p.edgeIdx];
            if (!edge) return null;
            const a = NODE_BY_ID[edge.a];
            const b = NODE_BY_ID[edge.b];
            const dx = px(b) - px(a);
            const dy = py(b) - py(a);
            // trail dots — 7 segments behind the head, fading + shrinking
            const TRAIL = 7;
            const trailEls = [];
            for (let k = 1; k <= TRAIL; k++) {
              const tk = p.t - k * 0.028;
              if (tk < 0) break;
              const tt = p.reverse ? 1 - tk : tk;
              const tx = px(a) + dx * tt;
              const ty = py(a) + dy * tt;
              const fade = Math.sin(tk * Math.PI);
              const decay = 1 - k / (TRAIL + 1);
              trailEls.push(
                <circle
                  key={`tr-${i}-${k}`}
                  cx={tx.toFixed(2)} cy={ty.toFixed(2)}
                  r={(1.6 * decay).toFixed(2)}
                  fill={pulseStyle.dot}
                  opacity={(fade * decay * 0.55).toFixed(3)}
                />
              );
            }
            const tHead = p.reverse ? 1 - p.t : p.t;
            const x = px(a) + dx * tHead;
            const y = py(a) + dy * tHead;
            const fade = Math.sin(p.t * Math.PI);
            return (
              <g key={i}>
                {trailEls}
                <circle cx={x} cy={y} r={7} fill={pulseStyle.glow} opacity={fade * 0.95} />
                <circle cx={x} cy={y} r={2.0} fill={pulseStyle.dot} opacity={fade} />
              </g>
            );
          })}
        </g>

        {/* LAYER 9 — TRACER: big high-contrast pulse following the agent's solution path */}
        {tracerRef.current.active && tracerRef.current.path.length > 1 ? (() => {
          const path = tracerRef.current.path;
          const segs = path.length - 1;
          const tGlobal = Math.max(0, Math.min(1, tracerRef.current.t));
          // smooth ease-in-out across the full path
          const tEased = tGlobal < 0.5
            ? 2 * tGlobal * tGlobal
            : 1 - Math.pow(-2 * tGlobal + 2, 2) / 2;
          const segPos = tEased * segs;
          const segIdx = Math.min(segs - 1, Math.floor(segPos));
          const segT = segPos - segIdx;
          const a = NODE_BY_ID[path[segIdx]];
          const b = NODE_BY_ID[path[segIdx + 1]];
          if (!a || !b) return null;
          const x = px(a) + (px(b) - px(a)) * segT;
          const y = py(a) + (py(b) - py(a)) * segT;

          // long trail — sample positions backward along the path
          const TRAIL_LEN = 22;
          const TRAIL_STEP = 0.012;
          const trailEls = [];
          for (let k = 1; k <= TRAIL_LEN; k++) {
            const tBack = tEased - k * TRAIL_STEP;
            if (tBack <= 0) break;
            const sp = tBack * segs;
            const si = Math.min(segs - 1, Math.floor(sp));
            const st = sp - si;
            const pa = NODE_BY_ID[path[si]];
            const pb = NODE_BY_ID[path[si + 1]];
            if (!pa || !pb) continue;
            const tx = px(pa) + (px(pb) - px(pa)) * st;
            const ty = py(pa) + (py(pb) - py(pa)) * st;
            const decay = 1 - k / (TRAIL_LEN + 1);
            trailEls.push(
              <circle
                key={"tracer-tr-" + k}
                cx={tx.toFixed(2)} cy={ty.toFixed(2)}
                r={(2.4 * decay).toFixed(2)}
                fill="#F5E6C0"
                opacity={(decay * 0.6).toFixed(3)}
              />
            );
          }

          // fade-in at start, fade-out at end
          const headFade =
            tGlobal < 0.05 ? tGlobal / 0.05
            : tGlobal > 0.95 ? (1 - tGlobal) / 0.05
            : 1;

          return (
            <g>
              {trailEls}
              {/* outer halo */}
              <circle cx={x} cy={y} r={18} fill="url(#tracerGlow)" opacity={0.7 * headFade} />
              {/* mid */}
              <circle cx={x} cy={y} r={9} fill="url(#tracerGlow)" opacity={0.95 * headFade} />
              {/* solid bright head — high-contrast ivory, much bigger than normal pulses */}
              <circle cx={x} cy={y} r={5} fill="#FFF6E0" opacity={headFade} />
              {/* nucleus dot */}
              <circle cx={x} cy={y} r={2.2} fill="#FFFFFF" opacity={headFade} />
            </g>
          );
        })() : null}
      </svg>
    </div>
  );
}

Object.assign(window, { NeuralGraph, NODE_COUNT, EDGE_COUNT });
