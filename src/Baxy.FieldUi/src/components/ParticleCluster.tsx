import { useMemo } from 'react';
import { seededRng } from '../utils/seededRng';

interface Props {
  /** 0..1 — drives dot count and brightness. */
  value?: number;
  /** seed for the deterministic rng; pick a unique int per metric row. */
  seed?: number;
  /** square SVG side, in px. */
  size?: number;
  color?: string;
}

interface Point { x: number; y: number; r: number; }

/** organic constellation around 2-3 anchors. matches prototype/components/cluster.jsx
 *  byte-for-byte so a substrate row visually matches across the two implementations. */
function makeClusterPoints(seed: number, count: number, w: number, h: number): Point[] {
  const rng = seededRng(seed);
  const cx = w / 2;
  const cy = h / 2;
  const anchors: { x: number; y: number }[] = [];
  const anchorCount = 2 + Math.floor(rng() * 2);
  for (let i = 0; i < anchorCount; i++) {
    anchors.push({
      x: cx + (rng() - 0.5) * w * 0.5,
      y: cy + (rng() - 0.5) * h * 0.5,
    });
  }
  const pts: Point[] = [];
  for (let i = 0; i < count; i++) {
    const a = anchors[Math.floor(rng() * anchors.length)];
    // sum of three uniforms approximates a gaussian
    const dx = ((rng() + rng() + rng()) / 3 - 0.5) * w * 0.85;
    const dy = ((rng() + rng() + rng()) / 3 - 0.5) * h * 0.85;
    const x = Math.max(2, Math.min(w - 2, a.x + dx * 0.45));
    const y = Math.max(2, Math.min(h - 2, a.y + dy * 0.45));
    pts.push({ x, y, r: 0.8 + rng() * 0.9 });
  }
  return pts;
}

export function ParticleCluster({
  value = 0.5,
  seed = 1,
  size = 40,
  color = '#2E4BA0',
}: Props) {
  const v = Math.max(0, Math.min(1, value));
  const baseCount = size >= 36 ? 18 : 14;
  const count = Math.round(baseCount * (0.55 + v * 0.55));
  const points = useMemo(() => makeClusterPoints(seed, count, size, size), [seed, count, size]);
  const brightness = 0.45 + v * 0.55;

  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} aria-hidden="true">
      {points.map((p, i) => {
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
