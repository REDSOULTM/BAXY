/* particle cluster — organic constellation, density driven by value */

function seededRng(seed) {
  let s = seed >>> 0;
  return () => {
    s = (s * 1664525 + 1013904223) >>> 0;
    return s / 0xffffffff;
  };
}

/* generate base positions for a cluster (organic blob, not grid) */
function makeClusterPoints(seed, count, w, h) {
  const rng = seededRng(seed);
  const cx = w / 2, cy = h / 2;
  const pts = [];
  // a few hub anchors that bias the cloud
  const anchors = [];
  const anchorCount = 2 + Math.floor(rng() * 2);
  for (let i = 0; i < anchorCount; i++) {
    anchors.push({
      x: cx + (rng() - 0.5) * w * 0.5,
      y: cy + (rng() - 0.5) * h * 0.5,
    });
  }
  for (let i = 0; i < count; i++) {
    const a = anchors[Math.floor(rng() * anchors.length)];
    // gaussian-ish via sum of uniforms
    const dx = ((rng() + rng() + rng()) / 3 - 0.5) * w * 0.85;
    const dy = ((rng() + rng() + rng()) / 3 - 0.5) * h * 0.85;
    const x = Math.max(2, Math.min(w - 2, a.x + dx * 0.45));
    const y = Math.max(2, Math.min(h - 2, a.y + dy * 0.45));
    pts.push({ x, y, r: 0.8 + rng() * 0.9 });
  }
  return pts;
}

function ParticleCluster({ value = 0.5, seed = 1, size = 40, color = "#2E4BA0" }) {
  // value 0..1 maps to dot count and brightness
  const v = Math.max(0, Math.min(1, value));
  const baseCount = size >= 36 ? 18 : 14;
  const count = Math.round(baseCount * (0.55 + v * 0.55)); // ~12..18 (or 8..14 for small)
  const points = React.useMemo(
    () => makeClusterPoints(seed, count, size, size),
    [seed, count, size]
  );
  const brightness = 0.45 + v * 0.55;

  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} aria-hidden="true">
      {points.map((p, i) => {
        // each dot opacity drifts slightly by index so the cluster has texture
        const op = brightness * (0.55 + ((i * 37) % 100) / 220);
        return (
          <circle
            key={i}
            cx={p.x.toFixed(2)}
            cy={p.y.toFixed(2)}
            r={p.r.toFixed(2)}
            fill={color}
            opacity={Math.min(1, op).toFixed(3)}
          />
        );
      })}
    </svg>
  );
}

/* tiny logo mark — 8 dots in carmine, rearrange on state change */
function LogoMark({ size = 14, state = "idle" }) {
  const STATE_SEED = {
    idle: 7, standby: 11, listening: 17, thinking: 23, speaking: 31,
  };
  const STATE_COLOR = {
    idle: "#B83A4A", standby: "#5B6580",
    listening: "#E55366", thinking: "#5B7FDB", speaking: "#C9A66B",
  };
  const pts = React.useMemo(() => {
    const rng = seededRng(STATE_SEED[state] || 7);
    const out = [];
    for (let i = 0; i < 8; i++) {
      out.push({
        x: 2 + rng() * (size - 4),
        y: 2 + rng() * (size - 4),
        r: 0.9 + rng() * 0.5,
      });
    }
    return out;
  }, [size, state]);
  const fill = STATE_COLOR[state] || "#B83A4A";
  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
      {pts.map((p, i) => (
        <circle
          key={i}
          cx={p.x.toFixed(2)}
          cy={p.y.toFixed(2)}
          r={p.r.toFixed(2)}
          fill={fill}
          opacity={0.55 + (i % 3) * 0.15}
          style={{ transition: "cx 600ms cubic-bezier(.4,1.4,.5,1), cy 600ms cubic-bezier(.4,1.4,.5,1), fill 400ms ease" }}
        />
      ))}
    </svg>
  );
}

Object.assign(window, { ParticleCluster, LogoMark, seededRng });
