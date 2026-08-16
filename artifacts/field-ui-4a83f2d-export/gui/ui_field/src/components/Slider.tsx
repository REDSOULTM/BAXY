/* prototype-style range slider. visually shows a carmine fill on the left
   side of the thumb via a css gradient driven by --fill. used for
   temperature/top_p/top_k/etc. in the sampling tab. */

interface Props {
  value: number;
  onChange: (v: number) => void;
  min: number;
  max: number;
  step?: number;
  ariaLabel?: string;
}

export function Slider({ value, onChange, min, max, step = 1, ariaLabel }: Props) {
  const range = Math.max(0.0001, max - min);
  const fillPct = Math.max(0, Math.min(100, ((value - min) / range) * 100));
  return (
    <input
      type="range"
      className="slider"
      value={Number.isFinite(value) ? value : min}
      min={min}
      max={max}
      step={step}
      aria-label={ariaLabel}
      onChange={(e) => {
        const n = parseFloat(e.target.value);
        if (!Number.isNaN(n)) onChange(n);
      }}
      style={{ '--fill': `${fillPct}%` } as React.CSSProperties}
    />
  );
}
