/* native <select> styled to match the settings panel inputs. carmesí focus,
   bg-base background, mono optional. used by AgentTab + TranscriptTab for
   discrete choices. plain <select> means the OS picker handles long lists
   correctly (keyboard, screen readers, mobile) without us reinventing it. */

import type { ChangeEvent } from 'react';

export interface SelectOption {
  value: string;
  label: string;
  /** small muted suffix shown after the label (e.g. "downloaded" / "~470 MB"). */
  hint?: string;
}

interface Props {
  value: string;
  onChange: (v: string) => void;
  options: SelectOption[];
  mono?: boolean;
  ariaLabel?: string;
}

export function Select({ value, onChange, options, mono = true, ariaLabel }: Props) {
  return (
    <select
      className={`st-input st-select${mono ? ' mono' : ''}`}
      value={value}
      onChange={(e: ChangeEvent<HTMLSelectElement>) => onChange(e.target.value)}
      aria-label={ariaLabel}
    >
      {options.map((opt) => (
        <option key={opt.value} value={opt.value}>
          {opt.hint ? `${opt.label} · ${opt.hint}` : opt.label}
        </option>
      ))}
    </select>
  );
}
