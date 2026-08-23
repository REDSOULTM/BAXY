import { useRef, useState } from 'react';
import type { ConvState } from '../types';
import type { MicMode } from '../App';
import type { AgentStatus, BootStage, CtxBudget } from '../hooks/useEventStream';
import { NeuralGraph } from './NeuralGraph';
import { Icon, type IconName } from './Icon';

interface Props {
  convState: ConvState;
  /** if non-null, render the debug chip row. clicking a chip flips the state. */
  onDebugState: ((s: ConvState) => void) | null;
  ctx: CtxBudget | null;
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
  /** what specifically is loading right now. Drives the placeholder text
   *  while !ready, and the inline retry button when error is non-null. */
  bootStage: BootStage | null;
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

interface Attachment {
  id: string;
  name: string;
  size: number;
  // populated once the file is uploaded to /upload. while uploading the
  // pill shows a "…" suffix and the send button stays disabled.
  path: string | null;
  uploading: boolean;
  file: File;
}

function fmtKb(n: number): string {
  return `${(n / 1024).toFixed(1)} kb`;
}

export function FieldCenter({
  convState, onDebugState, ctx, micMode, micLoading, onMicLeftClick, onMicRightClick, agent,
  bootStage,
}: Props) {
  const [draft, setDraft] = useState('');
  const [attachments, setAttachments] = useState<Attachment[]>([]);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  // chat is gated on agent readiness: !built → still loading tools/memory,
  // built but !healthy → llama-server isn't responding. armed only matters
  // once the agent is ready to accept the prompt. we also block sending
  // while any attachment is still uploading — otherwise the agent would
  // get a path that doesn't exist yet.
  const ready = agent.ready;
  const anyUploading = attachments.some((a) => a.uploading);
  const armed = ready && draft.trim().length > 0 && !anyUploading;

  // placeholder doubles as a status indicator while booting. When a real
  // boot_stage is available it wins over the generic agent.built/healthy
  // fallback — the stage label is more specific (e.g. "offloaded 30/43
  // layers to GPU"). Once the agent is ready we always show the normal
  // chat prompt.
  const bootMsg = (() => {
    if (!bootStage || bootStage.stage === 'ready') return null;
    if (!bootStage.label) return null;
    if (bootStage.progress !== null) {
      return `${bootStage.label} · ${bootStage.progress.toFixed(0)}%`;
    }
    return bootStage.label;
  })();
  const placeholder = bootMsg
    ?? (ready || (agent.built && agent.healthy)
      ? 'ask, instruct, or paste'
      : !agent.built
      ? 'starting agent · loading tools…'
      : !agent.healthy
      ? 'llama-server offline · waiting for connection…'
      : 'starting up…');

  // surface a retry button inline in the state-line whenever the most recent
  // boot_stage carried an error AND the agent is still not ready. clicking
  // posts /agent/restart and lets the runner emit fresh boot_stage events.
  const showRetry = Boolean(bootStage?.error) && !ready;
  const retryAgent = async () => {
    try {
      await fetch('/agent/restart', { method: 'POST' });
    } catch { /* the WS will surface any failure as a fresh boot_stage error */ }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!armed) return;
    // only ship paths that the upload actually returned. anything still
    // uploading is excluded by `armed` above, and anything that failed
    // (path === null) is silently skipped so the turn still goes through.
    const paths = attachments
      .map((a) => a.path)
      .filter((p): p is string => typeof p === 'string' && p.length > 0);
    try {
      await fetch('/turn', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: draft, attachments: paths }),
      });
    } catch { /* ignore */ }
    setDraft('');
    setAttachments([]);
  };

  const onFiles = (files: FileList | null) => {
    if (!files) return;
    const next: Attachment[] = Array.from(files).map((f) => ({
      id: `${f.name}-${f.size}-${Math.random().toString(36).slice(2, 8)}`,
      name: f.name,
      size: f.size,
      path: null,
      uploading: true,
      file: f,
    }));
    setAttachments((prev) => [...prev, ...next]);
    // start the upload for each new attachment. updates the matching row
    // by id when the server responds — the user can keep typing while
    // these requests are in flight.
    next.forEach((att) => {
      const fd = new FormData();
      fd.append('file', att.file);
      fetch('/upload', { method: 'POST', body: fd })
        .then(async (r) => {
          if (!r.ok) throw new Error(`status ${r.status}`);
          return r.json() as Promise<{ ok?: boolean; path?: string }>;
        })
        .then((data) => {
          if (!data.ok || !data.path) throw new Error('no path');
          setAttachments((prev) =>
            prev.map((a) => a.id === att.id ? { ...a, path: data.path!, uploading: false } : a)
          );
        })
        .catch(() => {
          // mark failed so the pill turns red and send still works
          // without the broken attachment.
          setAttachments((prev) =>
            prev.map((a) => a.id === att.id ? { ...a, uploading: false, path: null } : a)
          );
        });
    });
  };

  // estimated tokens of the draft vs the model's ctx budget — same heuristic
  // as the prototype: ~4 chars per token, capped at 4096 so the counter
  // visually fits without scientific notation.
  const ctxBudget = ctx?.budget ?? 4096;
  const tokensCap = Math.min(4096, ctxBudget);
  const tokens = Math.min(tokensCap, Math.ceil(draft.length / 4));

  return (
    <div className="center-wrap">
      {/* Boot-error recovery — only mounts on a real boot failure. At rest
          (the design's idle layout) this renders nothing, so the center column
          matches the handoff prototype exactly; it appears only when the agent
          actually fails to boot, surfacing a retry the user would otherwise
          lack. */}
      {showRetry && (
        <div className="boot-banner" role="alert" aria-live="polite">
          <span className="boot-err" title={bootStage?.error ?? undefined}>
            {bootStage?.error ? `agent boot failed · ${bootStage.error}` : 'agent boot failed'}
          </span>
          <button
            type="button"
            className="boot-retry"
            onClick={retryAgent}
            aria-label="retry agent boot"
            data-tip="restart agent"
          >
            <Icon name="restart" size={11} />
            <span>retry</span>
          </button>
        </div>
      )}

      <NeuralGraph state={convState} />

      <div className="chat">
        <form className={`line${ready ? '' : ' booting'}`} onSubmit={handleSubmit}>
          <span className="chev">›</span>
          <input
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            placeholder={placeholder}
            spellCheck={false}
            autoFocus
            disabled={!ready}
            aria-label="message input"
            aria-disabled={!ready}
          />
          <span className="tokens">{tokens} / 4k</span>
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
              type="button"
              className={`ibtn${attachments.length > 0 ? ' active' : ''}`}
              data-tip="attach"
              onClick={() => fileInputRef.current?.click()}
              aria-label="attach files"
            >
              <Icon name="attach" />
              {attachments.length > 0 && (
                <span className="badge">{attachments.length}</span>
              )}
            </button>
            <input
              ref={fileInputRef}
              type="file"
              multiple
              hidden
              onChange={(e) => { onFiles(e.target.files); e.target.value = ''; }}
            />
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

        <div className="chat-bottom">
          <div className="attachments">
            {attachments.length === 0 ? (
              <span className="muted">no attachments</span>
            ) : (
              <div className="att-list">
                {attachments.map((a) => {
                  const failed = !a.uploading && a.path === null;
                  return (
                    <span
                      className="att-pill"
                      key={a.id}
                      style={failed ? { color: 'var(--carmine)' } : undefined}
                      title={a.uploading ? 'uploading…' : failed ? 'upload failed' : a.path ?? a.name}
                    >
                      <Icon name="attach" size={11} />
                      <span className="att-name">{a.name}</span>
                      <span className="att-size">
                        {a.uploading ? 'uploading…' : failed ? 'failed' : fmtKb(a.size)}
                      </span>
                      <button
                        type="button"
                        className="att-x"
                        onClick={() => setAttachments((p) => p.filter((x) => x.id !== a.id))}
                        aria-label={`remove ${a.name}`}
                      >
                        <Icon name="x" size={10} />
                      </button>
                    </span>
                  );
                })}
              </div>
            )}
          </div>
        </div>

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
