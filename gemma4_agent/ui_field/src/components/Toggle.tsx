/* prototype-style toggle switch (28x16 with sliding knob).
   the prototype's CSS class is `.toggle` + `.toggle.on .knob`. used in the
   settings panel for binary feature flags. */

interface Props {
  value: boolean;
  onChange: (v: boolean) => void;
  ariaLabel?: string;
}

export function Toggle({ value, onChange, ariaLabel }: Props) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={value}
      aria-label={ariaLabel}
      className={`toggle${value ? ' on' : ''}`}
      onClick={() => onChange(!value)}
    >
      <span className="knob" aria-hidden="true" />
    </button>
  );
}
