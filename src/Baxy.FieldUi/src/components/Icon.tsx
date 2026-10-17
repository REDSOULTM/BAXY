/* monoline icon set — 1.25 stroke, currentColor, viewBox 16x16, ported from the design's components/icons.jsx; the
   three window glyphs are the shell's own (the window has no system frame). */

export type IconName =
  | 'attach' | 'send' | 'mic' | 'mic-off' | 'settings' | 'plus' | 'bolt' | 'search' | 'check' | 'person' | 'power'
  | 'eye-off' | 'wheelchair' | 'x' | 'wave' | 'win-min' | 'win-max' | 'win-restore';

interface Props {
  name: IconName;
  size?: number;
  strokeWidth?: number;
}

export function Icon({ name, size = 14, strokeWidth = 1.25 }: Props) {
  const p = {
    width: size,
    height: size,
    viewBox: '0 0 16 16',
    fill: 'none',
    stroke: 'currentColor',
    strokeWidth,
    strokeLinecap: 'round' as const,
    strokeLinejoin: 'round' as const,
    'aria-hidden': true as const,
  };
  switch (name) {
    case 'attach':
      return <svg {...p}><path d="M 11.2 4.5 L 5.2 10.5 Q 4 11.7 5.2 12.9 Q 6.4 14.1 7.6 12.9 L 13 7.5 Q 14.5 6 13 4.5 Q 11.5 3 10 4.5 L 5 9.5" /></svg>;
    case 'send':
      return <svg {...p}><path d="M 3 8 L 13 8" /><path d="M 9.5 4.5 L 13 8 L 9.5 11.5" /></svg>;
    case 'mic':
      return <svg {...p}><rect x="6" y="2.5" width="4" height="7" rx="2" /><path d="M 3.5 8 Q 3.5 12 8 12 Q 12.5 12 12.5 8" /><path d="M 8 12 L 8 14" /><path d="M 6 14 L 10 14" /></svg>;
    case 'mic-off':
      return <svg {...p}><rect x="6" y="2.5" width="4" height="7" rx="2" /><path d="M 3.5 8 Q 3.5 12 8 12 Q 12.5 12 12.5 8" /><path d="M 8 12 L 8 14" /><path d="M 6 14 L 10 14" /><path d="M 2 2 L 14 14" /></svg>;
    case 'settings':
      return (
        <svg {...p}>
          <path d="M12.53 6.12 L12.83 7.16 L14.26 7.31 L14.26 8.69 L12.83 8.84 L12.53 9.88 L12.01 10.82 L12.92 11.94 L11.94 12.92 L10.82 12.01 L9.88 12.53 L8.84 12.83 L8.69 14.26 L7.31 14.26 L7.16 12.83 L6.12 12.53 L5.18 12.01 L4.06 12.92 L3.08 11.94 L3.99 10.82 L3.47 9.88 L3.17 8.84 L1.74 8.69 L1.74 7.31 L3.17 7.16 L3.47 6.12 L3.99 5.18 L3.08 4.06 L4.06 3.08 L5.18 3.99 L6.12 3.47 L7.16 3.17 L7.31 1.74 L8.69 1.74 L8.84 3.17 L9.88 3.47 L10.82 3.99 L11.94 3.08 L12.92 4.06 L12.01 5.18 Z" />
          <circle cx="8" cy="8" r="2.1" />
        </svg>
      );
    case 'plus':
      return <svg {...p}><path d="M 8 3.5 L 8 12.5" /><path d="M 3.5 8 L 12.5 8" /></svg>;
    case 'bolt':
      return <svg {...p}><path d="M 9 1.5 L 4 9 L 8 9 L 7 14.5 L 12 7 L 8 7 L 9 1.5 Z" /></svg>;
    case 'search':
      return <svg {...p}><circle cx="7" cy="7" r="4" /><path d="M 10 10 L 13 13" /></svg>;
    case 'check':
      return <svg {...p}><path d="M 3 8 L 6.5 11.5 L 13 4" /></svg>;
    case 'person':
      return <svg {...p}><circle cx="8" cy="5" r="2.4" /><path d="M 3.5 13 Q 3.5 8.5 8 8.5 Q 12.5 8.5 12.5 13" /></svg>;
    case 'power':
      return <svg {...p}><path d="M 8 2 L 8 8" /><path d="M 5 4.2 Q 2.5 6 2.5 9 Q 2.5 13.5 8 13.5 Q 13.5 13.5 13.5 9 Q 13.5 6 11 4.2" /></svg>;
    case 'eye-off':
      return <svg {...p}><path d="M 2 8 Q 5 4 8 4 Q 11 4 14 8 Q 11 12 8 12 Q 5 12 2 8 Z" /><circle cx="8" cy="8" r="1.6" /><path d="M 3 3 L 13 13" /></svg>;
    case 'wheelchair':
      return <svg {...p}><circle cx="7.5" cy="10.5" r="3.4" /><circle cx="6" cy="3.2" r="1.1" fill="currentColor" stroke="none" /><path d="M 6 5 L 6 8 L 9.5 8" /><path d="M 9.5 8 L 11 13" /></svg>;
    case 'x':
      return <svg {...p}><path d="M 4 4 L 12 12" /><path d="M 12 4 L 4 12" /></svg>;
    case 'wave':
      return <svg {...p}><path d="M 2 8 Q 4 4 6 8 Q 8 12 10 8 Q 12 4 14 8" /></svg>;
    case 'win-min':
      return <svg {...p}><path d="M 3.5 9 L 12.5 9" /></svg>;
    case 'win-max':
      return <svg {...p}><rect x="3.5" y="3.5" width="9" height="9" rx="0.5" /></svg>;
    case 'win-restore':
      return <svg {...p}><rect x="3" y="5" width="8" height="8" rx="0.5" /><path d="M 5.5 5 L 5.5 3 L 13 3 L 13 10.5 L 11 10.5" /></svg>;
    default:
      return null;
  }
}

/** the globe of «Salió a internet». */
export function Globe({ s = 11 }: { s?: number }) {
  return (
    <svg width={s} height={s} viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.3" aria-hidden="true">
      <circle cx="8" cy="8" r="6" />
      <path d="M2 8h12M8 2q3 3 0 12M8 2q-3 3 0 12" />
    </svg>
  );
}
