import { useMemo } from 'react';
import { seededRng } from '../utils/seededRng';

/* tiny logo mark — 8 dots that rearrange on a state change (design components/cluster.jsx). */
type MarkState = 'idle' | 'standby' | 'listening' | 'thinking' | 'speaking';

const SEED: Record<MarkState, number> = { idle: 7, standby: 11, listening: 17, thinking: 23, speaking: 31 };
const COLOR: Record<MarkState, string> = {
  idle: '#B83A4A', standby: '#5B6580', listening: '#E55366', thinking: '#5B7FDB', speaking: '#C9A66B',
};

export function LogoMark({ size = 14, state = 'idle' }: { size?: number; state?: MarkState }) {
  const pts = useMemo(() => {
    const rng = seededRng(SEED[state]);
    return Array.from({ length: 8 }, () => ({ x: 2 + rng() * (size - 4), y: 2 + rng() * (size - 4), r: 0.9 + rng() * 0.5 }));
  }, [size, state]);
  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} aria-hidden="true">
      {pts.map((p, i) => (
        <circle
          key={i}
          cx={p.x.toFixed(2)}
          cy={p.y.toFixed(2)}
          r={p.r.toFixed(2)}
          fill={COLOR[state]}
          opacity={0.55 + (i % 3) * 0.15}
          style={{ transition: 'cx 600ms cubic-bezier(.4,1.4,.5,1), cy 600ms cubic-bezier(.4,1.4,.5,1), fill 400ms ease' }}
        />
      ))}
    </svg>
  );
}
