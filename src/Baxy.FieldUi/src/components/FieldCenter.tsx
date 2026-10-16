import { useState } from 'react';
import type { ConvState } from '../types';
import type { MicMode } from '../App';
import type { AgentStatus } from '../hooks/useEventStream';
import { NeuralGraph } from './NeuralGraph';
import { Icon, type IconName } from './Icon';

interface Props {
  convState: ConvState;
  micMode: MicMode;
  /** true while /voice/start is loading the voice models on the backend.
   *  keeps the mic icon lit + pulsing so it doesn't flicker red→black. */
  micLoading: boolean;
  /** the voice's last trouble the host observed (its code), null when there is none. */
  voiceError: string | null;
  /** left click: cycle listening↔off (mute toggle). */
  onMicLeftClick: () => void;
  /** right click: start a request now, without the wake word (turning the voice on if it is off). */
  onMicRightClick: () => void;
  /** the shell's gate. while !ready, the chat input is disabled; a failure is shown by its code. */
  agent: AgentStatus;
}

const MIC_ICON: Record<MicMode, IconName> = {
  listening: 'mic',
  off: 'mic-off',
};

const MIC_TIP: Record<MicMode, string> = {
  listening: 'voice · say «Baxy» or right-click to speak now · left-click to mute',
  off: 'voice · off · left-click to listen for «Baxy» · right-click to speak now',
};

const MIC_ARIA: Record<MicMode, string> = {
  listening: 'microphone listening for «Baxy»',
  off: 'microphone off',
};

export function FieldCenter({
  convState, micMode, micLoading, voiceError, onMicLeftClick, onMicRightClick, agent,
}: Props) {
  const [draft, setDraft] = useState('');

  // chat is gated on the shell's readiness: !built → the engine is starting (or failed: its code is shown).
  // armed only matters once a turn is accepted.
  const ready = agent.ready;
  const armed = ready && draft.trim().length > 0;

  const placeholder = agent.built
    ? 'ask, instruct, or paste'
    : agent.failure ?? 'starting agent · loading tools…';

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!armed) return;
    try {
      await fetch('/turn', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: draft }),
      });
    } catch { /* ignore */ }
    setDraft('');
  };

  return (
    <div className="center-wrap">
      <NeuralGraph state={convState} />

      <div className="chat">
        <div className="turn-error" role="alert" aria-atomic="true">
          {agent.failure ?? null}
        </div>
        <form className={`line${ready ? '' : ' booting'}`} onSubmit={handleSubmit}>
          <span className="chev">›</span>
          <input
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            placeholder={placeholder}
            spellCheck={false}
            maxLength={4096}
            autoFocus
            disabled={!ready}
            aria-label="message input"
            aria-disabled={!ready}
          />
          <div className="chat-actions">
            <button
              type="button"
              className={`ibtn mic-btn${micMode !== 'off' ? ' active' : ''}${micLoading ? ' mic-loading' : ''}`}
              data-tip={micLoading ? 'voice · cargando modelos…' : voiceError ? `voice · ${voiceError}` : MIC_TIP[micMode]}
              onClick={onMicLeftClick}
              onContextMenu={(e) => { e.preventDefault(); onMicRightClick(); }}
              aria-label={MIC_ARIA[micMode]}
              aria-busy={micLoading}
            >
              <Icon name={MIC_ICON[micMode]} />
            </button>
            <button
              type="submit"
              className={`ibtn send${armed ? ' armed' : ''}`}
              data-tip="send"
              disabled={!armed}
              aria-label="send"
            >
              <Icon name="send" />
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
