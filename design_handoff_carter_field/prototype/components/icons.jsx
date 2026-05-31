/* SVG icon set — minimal line-art glyphs, currentColor stroke */

function Icon({ name, size = 14, strokeWidth = 1.25 }) {
  const props = {
    width: size,
    height: size,
    viewBox: "0 0 16 16",
    fill: "none",
    stroke: "currentColor",
    strokeWidth,
    strokeLinecap: "round",
    strokeLinejoin: "round",
    "aria-hidden": "true",
  };

  switch (name) {
    case "attach":
      return (
        <svg {...props}>
          <path d="M 11.2 4.5 L 5.2 10.5 Q 4 11.7 5.2 12.9 Q 6.4 14.1 7.6 12.9 L 13 7.5 Q 14.5 6 13 4.5 Q 11.5 3 10 4.5 L 5 9.5" />
        </svg>
      );
    case "send":
      return (
        <svg {...props}>
          <path d="M 3 8 L 13 8" />
          <path d="M 9.5 4.5 L 13 8 L 9.5 11.5" />
        </svg>
      );
    case "mic":
      return (
        <svg {...props}>
          <rect x="6" y="2.5" width="4" height="7" rx="2" />
          <path d="M 3.5 8 Q 3.5 12 8 12 Q 12.5 12 12.5 8" />
          <path d="M 8 12 L 8 14" />
          <path d="M 6 14 L 10 14" />
        </svg>
      );
    case "mic-off":
      return (
        <svg {...props}>
          <rect x="6" y="2.5" width="4" height="7" rx="2" />
          <path d="M 3.5 8 Q 3.5 12 8 12 Q 12.5 12 12.5 8" />
          <path d="M 8 12 L 8 14" />
          <path d="M 6 14 L 10 14" />
          <path d="M 2 2 L 14 14" stroke="currentColor" />
        </svg>
      );
    case "settings":
      return (
        <svg {...props}>
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
    case "sessions":
      return (
        <svg {...props}>
          <rect x="3" y="3.5" width="10" height="2" rx="0.5" />
          <rect x="3" y="7"   width="10" height="2" rx="0.5" />
          <rect x="3" y="10.5" width="10" height="2" rx="0.5" />
        </svg>
      );
    case "plus":
      return (
        <svg {...props}>
          <path d="M 8 3.5 L 8 12.5" />
          <path d="M 3.5 8 L 12.5 8" />
        </svg>
      );
    case "help":
      return (
        <svg {...props}>
          <circle cx="8" cy="8" r="6" />
          <path d="M 6 6.5 Q 6 5 8 5 Q 10 5 10 6.5 Q 10 7.5 8 8.3 L 8 9.2" />
          <circle cx="8" cy="11.2" r="0.4" fill="currentColor" stroke="none" />
        </svg>
      );
    case "bolt":
      return (
        <svg {...props}>
          <path d="M 9 1.5 L 4 9 L 8 9 L 7 14.5 L 12 7 L 8 7 L 9 1.5 Z" />
        </svg>
      );
    case "search":
      return (
        <svg {...props}>
          <circle cx="7" cy="7" r="4" />
          <path d="M 10 10 L 13 13" />
        </svg>
      );
    case "check":
      return (
        <svg {...props}>
          <path d="M 3 8 L 6.5 11.5 L 13 4" />
        </svg>
      );
    case "folder":
      return (
        <svg {...props}>
          <path d="M 2 4 L 7 4 L 8.5 5.5 L 14 5.5 L 14 12 L 2 12 Z" />
        </svg>
      );
    case "restart":
      return (
        <svg {...props}>
          <path d="M 13 5 Q 11.5 2.5 8 2.5 Q 3 2.5 3 8 Q 3 13.5 8 13.5 Q 11 13.5 12.5 11" />
          <path d="M 13 2 L 13 5 L 10 5" />
        </svg>
      );
    case "person":
      return (
        <svg {...props}>
          <circle cx="8" cy="5" r="2.4" />
          <path d="M 3.5 13 Q 3.5 8.5 8 8.5 Q 12.5 8.5 12.5 13" />
        </svg>
      );
    case "power":
      return (
        <svg {...props}>
          <path d="M 8 2 L 8 8" />
          <path d="M 5 4.2 Q 2.5 6 2.5 9 Q 2.5 13.5 8 13.5 Q 13.5 13.5 13.5 9 Q 13.5 6 11 4.2" />
        </svg>
      );
    case "eye-off":
      return (
        <svg {...props}>
          <path d="M 2 8 Q 5 4 8 4 Q 11 4 14 8 Q 11 12 8 12 Q 5 12 2 8 Z" />
          <circle cx="8" cy="8" r="1.6" />
          <path d="M 3 3 L 13 13" />
        </svg>
      );
    case "wheelchair":
      return (
        <svg {...props}>
          <circle cx="7.5" cy="10.5" r="3.4" />
          <circle cx="6" cy="3.2" r="1.1" fill="currentColor" stroke="none" />
          <path d="M 6 5 L 6 8 L 9.5 8" />
          <path d="M 9.5 8 L 11 13" />
        </svg>
      );
    case "x":
      return (
        <svg {...props}>
          <path d="M 4 4 L 12 12" />
          <path d="M 12 4 L 4 12" />
        </svg>
      );
    case "ghost":
      return (
        <svg {...props}>
          <path d="M 3 8 Q 3 3 8 3 Q 13 3 13 8 L 13 13 L 11 11.5 L 9 13 L 7 11.5 L 5 13 L 3 11.5 Z" />
          <circle cx="6.5" cy="7.5" r="0.6" fill="currentColor" stroke="none" />
          <circle cx="9.5" cy="7.5" r="0.6" fill="currentColor" stroke="none" />
        </svg>
      );
    case "trigger":
      return (
        <svg {...props}>
          <path d="M 8 1.5 L 4 9 L 8 9 L 7 14.5" />
        </svg>
      );
    case "wave":
      return (
        <svg {...props}>
          <path d="M 2 8 Q 4 4 6 8 Q 8 12 10 8 Q 12 4 14 8" />
        </svg>
      );
    default:
      return null;
  }
}

Object.assign(window, { Icon });
