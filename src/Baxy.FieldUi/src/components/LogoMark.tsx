import { useMemo } from 'react';
import { seededRng } from '../utils/seededRng';
import type { ConvState } from '../types';

interface Props {
  size?: number;
  state: ConvState;
}

const STATE_SEED: Record<ConvState, number> = {
  idle: 7,
  standby: 11,
  listening: 17,
  thinking: 23,
  speaking: 31,
};

const STATE_COLOR: Record<ConvState, string> = {
  idle: '#B83A4A',
  standby: '#5B6580',
  listening: '#E55366',
  thinking: '#5B7FDB',
  speaking: '#C9A66B',
};

interface Point { x: number; y: number; r: number; }

export function LogoMark({ size = 14, state }: Props) {
  // recompute positions every state change so dots bounce to the new layout
  // via the css transition on cx/cy. memoize per (size, state) tuple.
  const pts = useMemo<Point[]>(() => {
    const rng = seededRng(STATE_SEED[state]);
    const out: Point[] = [];
    for (let i = 0; i < 8; i++) {
      out.push({
        x: 2 + rng() * (size - 4),
        y: 2 + rng() * (size - 4),
        r: 0.9 + rng() * 0.5,
      });
    }
    return out;
  }, [size, state]);

  const fill = STATE_COLOR[state];

  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} aria-hidden="true">
      {pts.map((p, i) => (
        <circle
          key={i}
          cx={p.x.toFixed(2)}
          cy={p.y.toFixed(2)}
          r={p.r.toFixed(2)}
          fill={fill}
          opacity={0.55 + (i % 3) * 0.15}
          style={{
            transition:
              'cx 600ms cubic-bezier(.4,1.4,.5,1), cy 600ms cubic-bezier(.4,1.4,.5,1), fill 400ms ease',
          }}
        />
      ))}
    </svg>
  );
}
