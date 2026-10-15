import { useState } from 'react';
import type { ConvState } from '../types';
import type { MicMode } from '../App';
import type { AgentStatus } from '../hooks/useEventStream';
import { NeuralGraph } from './NeuralGraph';
import { Icon, type IconName } from './Icon';

interface Props {
  convState: ConvState;
  /** if non-null, render the debug chip row. clicking a chip flips the state. */
  onDebugState: ((s: ConvState) => void) | null;
  micMode: MicMode;
  /** true while /voice/start is loading the voice models on the backend.
   *  keeps the mic icon lit + pulsing so it doesn't flicker red→black. */
  micLoading: boolean;
  /** left click: cycle listening↔off (mute toggle). */
  onMicLeftClick: () => void;
  /** right click: toggle push-to-talk vs the previous on-mode. */
  onMicRightClick: () => void;
  /** boot lifecycle of the agent. while !ready, the chat input is disabled
   *  and the placeholder shows a hint of what's happening. */
  agent: AgentStatus;
}

const MIC_ICON: Record<MicMode, IconName> = {
  listening: 'mic',
  ptt: 'mic-ptt',
  off: 'mic-off',
};

const MIC_TIP: Record<MicMode, string> = {
  listening: 'voice · always listening · right-click for push-to-talk · left-click to mute',
  ptt: 'voice · push-to-talk · right-click again to arm capture · left-click to mute',
  off: 'voice · off · left-click to enable always-listen · right-click to enable push-to-talk',
};

const MIC_ARIA: Record<MicMode, string> = {
  listening: 'microphone always listening',
  ptt: 'microphone push-to-talk',
  off: 'microphone off',
};

const DEBUG_STATES: ConvState[] = ['standby', 'idle', 'listening', 'thinking', 'speaking'];

export function FieldCenter({
  convState, onDebugState, micMode, micLoading, onMicLeftClick, onMicRightClick, agent,
}: Props) {
  const [draft, setDraft] = useState('');

  // chat is gated on agent readiness: !built → still loading tools/memory,
  // built but !healthy → llama-server isn't responding. armed only matters
  // once the agent is ready to accept the prompt.
  const ready = agent.ready;
  const armed = ready && draft.trim().length > 0;

  const placeholder = (ready || (agent.built && agent.healthy)
      ? 'ask, instruct, or paste'
      : !agent.built
      ? 'starting agent · loading tools…'
      : !agent.healthy
      ? 'llama-server offline · waiting for connection…'
      : 'starting up…');

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
          {convState === 'error' ? 'Response error' : null}
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
              className={`ibtn mic-btn mic-${micMode}${micMode !== 'off' ? ' active' : ''}${micLoading ? ' mic-loading' : ''}`}
              data-tip={micLoading ? 'voice · cargando modelos…' : MIC_TIP[micMode]}
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

        {onDebugState && (
          <div className="profile-chips" style={{ marginTop: 8 }} aria-label="debug state switcher">
            {DEBUG_STATES.map((s) => (
              <button
                key={s}
                type="button"
                className={`chip${convState === s ? ' on' : ''}`}
                onClick={() => onDebugState(s)}
              >
                {s}
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
