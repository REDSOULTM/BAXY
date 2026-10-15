/* monoline icon set — 1.25 stroke, currentColor, viewBox 16x16. ported 1:1
   from prototype/components/icons.jsx so the visual matches. */

export type IconName =
  | 'send' | 'mic' | 'mic-off' | 'mic-ptt' | 'settings' | 'plus'
  | 'help' | 'bolt' | 'search' | 'x' | 'person' | 'eye-off' | 'lock'
  | 'win-min' | 'win-max' | 'win-restore';

interface Props {
  name: IconName;
  size?: number;
  strokeWidth?: number;
}

export function Icon({ name, size = 14, strokeWidth = 1.25 }: Props) {
  const common = {
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
    case 'send':
      return (
        <svg {...common}>
          <path d="M 3 8 L 13 8" />
          <path d="M 9.5 4.5 L 13 8 L 9.5 11.5" />
        </svg>
      );
    case 'mic':
      return (
        <svg {...common}>
          <rect x="6" y="2.5" width="4" height="7" rx="2" />
          <path d="M 3.5 8 Q 3.5 12 8 12 Q 12.5 12 12.5 8" />
          <path d="M 8 12 L 8 14" />
          <path d="M 6 14 L 10 14" />
        </svg>
      );
    case 'mic-off':
      return (
        <svg {...common}>
          <rect x="6" y="2.5" width="4" height="7" rx="2" />
          <path d="M 3.5 8 Q 3.5 12 8 12 Q 12.5 12 12.5 8" />
          <path d="M 8 12 L 8 14" />
          <path d="M 6 14 L 10 14" />
          <path d="M 2 2 L 14 14" />
        </svg>
      );
    case 'mic-ptt':
      // mic with a small filled dot bottom-right — indicates manual / push-to-talk
      return (
        <svg {...common}>
          <rect x="6" y="2.5" width="4" height="7" rx="2" />
          <path d="M 3.5 8 Q 3.5 12 8 12 Q 12.5 12 12.5 8" />
          <path d="M 8 12 L 8 14" />
          <path d="M 6 14 L 10 14" />
          <circle cx="12.5" cy="3.5" r="1.4" fill="currentColor" stroke="none" />
        </svg>
      );
    case 'settings':
      return (
        <svg {...common}>
          <circle cx="8" cy="8" r="2.4" />
          <path d="M 8 1.2 L 8 3.2" />
          <path d="M 8 12.8 L 8 14.8" />
          <path d="M 1.2 8 L 3.2 8" />
          <path d="M 12.8 8 L 14.8 8" />
          <path d="M 3.2 3.2 L 4.6 4.6" />
          <path d="M 11.4 11.4 L 12.8 12.8" />
          <path d="M 3.2 12.8 L 4.6 11.4" />
          <path d="M 11.4 4.6 L 12.8 3.2" />
        </svg>
      );
    case 'plus':
      return (
        <svg {...common}>
          <path d="M 8 3.5 L 8 12.5" />
          <path d="M 3.5 8 L 12.5 8" />
        </svg>
      );
    case 'help':
      return (
        <svg {...common}>
          <circle cx="8" cy="8" r="6" />
          <path d="M 6 6.5 Q 6 5 8 5 Q 10 5 10 6.5 Q 10 7.5 8 8.3 L 8 9.2" />
          <circle cx="8" cy="11.2" r="0.4" fill="currentColor" stroke="none" />
        </svg>
      );
    case 'bolt':
      return (
        <svg {...common}>
          <path d="M 9 1.5 L 4 9 L 8 9 L 7 14.5 L 12 7 L 8 7 L 9 1.5 Z" />
        </svg>
      );
    case 'search':
      return (
        <svg {...common}>
          <circle cx="7" cy="7" r="4" />
          <path d="M 10 10 L 13 13" />
        </svg>
      );
    case 'person':
      return (
        <svg {...common}>
          <circle cx="8" cy="5" r="2.4" />
          <path d="M 3.5 13 Q 3.5 8.5 8 8.5 Q 12.5 8.5 12.5 13" />
        </svg>
      );
    case 'eye-off':
      return (
        <svg {...common}>
          <path d="M 2 8 Q 5 4 8 4 Q 11 4 14 8 Q 11 12 8 12 Q 5 12 2 8 Z" />
          <circle cx="8" cy="8" r="1.6" />
          <path d="M 3 3 L 13 13" />
        </svg>
      );
    case 'lock':
      return (
        <svg {...common}>
          <rect x="3.5" y="7" width="9" height="6.5" rx="1" />
          <path d="M 5.5 7 L 5.5 5 Q 5.5 2.8 8 2.8 Q 10.5 2.8 10.5 5 L 10.5 7" />
          <path d="M 8 9.2 L 8 11.2" />
        </svg>
      );
    case 'x':
      return (
        <svg {...common}>
          <path d="M 4 4 L 12 12" />
          <path d="M 12 4 L 4 12" />
        </svg>
      );
    case 'win-min':
      // window minimize — a single horizontal rule centered low, like the OS chrome
      return (
        <svg {...common}>
          <path d="M 3.5 9 L 12.5 9" />
        </svg>
      );
    case 'win-max':
      // window maximize — an empty square
      return (
        <svg {...common}>
          <rect x="3.5" y="3.5" width="9" height="9" rx="0.5" />
        </svg>
      );
    case 'win-restore':
      // window restore — two stacked squares (offset), shown when maximized
      return (
        <svg {...common}>
          <rect x="3" y="5" width="8" height="8" rx="0.5" />
          <path d="M 5.5 5 L 5.5 3 L 13 3 L 13 10.5 L 11 10.5" />
        </svg>
      );
    default:
      return null;
  }
}
