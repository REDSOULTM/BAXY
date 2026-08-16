import type { ConvState } from '../types';
import type { VisionThreshold } from '../hooks/useEventStream';
import { Icon } from './Icon';

interface Props {
  convState: ConvState;
  clock: string;
  connected?: boolean;
  onOpenSettings: () => void;
  onOpenSessions: () => void;
  onNewSession: () => void;
  onHelp: () => void;
  /** Mostrar banner amber arriba con accion "recycle llama-server" cuando
   *  el counter de imagenes cruza el threshold del mmproj leak (#21690). */
  visionThreshold?: VisionThreshold | null;
  onRecycleServer?: () => void;
  onDismissVisionWarning?: () => void;
}

/* topbar action set per spec: sessions / + new / settings (labeled) / help.
   the mic toggle lives in the chat-row of FieldCenter — keeping it out of
   here matches the prototype's interaction model. */
export function TopBar({
  convState, clock, connected,
  onOpenSettings, onOpenSessions,
  onNewSession, onHelp,
  visionThreshold, onRecycleServer, onDismissVisionWarning,
}: Props) {
  return (
    <>
      {visionThreshold && (
        <div
          className="vision-banner"
          role="alert"
          aria-live="polite"
        >
          <span className="vision-banner-msg">
            vision leak · <b>{visionThreshold.imageCount}/{visionThreshold.threshold}</b>{' '}
            imagenes procesadas · recyclar llama-server recomendado{' '}
            <span className="vision-banner-issue">({visionThreshold.issue})</span>
          </span>
          {onRecycleServer && (
            <button
              type="button"
              className="vision-banner-btn"
              onClick={onRecycleServer}
            >
              recycle now
            </button>
          )}
          {onDismissVisionWarning && (
            <button
              type="button"
              className="vision-banner-dismiss"
              onClick={onDismissVisionWarning}
              aria-label="dismiss warning"
            >
              ×
            </button>
          )}
        </div>
      )}
    <div className="bar top">
      <div className="left">
        <span className="title">
          field <span className="dim">·</span> <span className="accent">{convState}</span>
        </span>
      </div>
      <div className="right">
        <span className="seg hot"><span className="k">core</span><span className="v">active</span></span>
        <span className="seg"><span className="k">net</span><span className="v">{connected ? 'live' : 'local'}</span></span>
        <span className="seg"><span className="k">build</span><span className="v">carter</span></span>

        <div className="topbar-actions">
          <button
            className="ibtn"
            onClick={onOpenSessions}
            aria-label="sessions"
            data-tip="sessions"
          >
            <Icon name="sessions" size={14} />
          </button>
          <button
            className="ibtn"
            onClick={onNewSession}
            aria-label="new session"
            data-tip="new session"
          >
            <Icon name="plus" size={14} />
          </button>
          <button
            className="ibtn labeled"
            onClick={onOpenSettings}
            aria-label="settings"
            data-tip="settings · configure agent"
          >
            <Icon name="settings" size={14} />
            <span>settings</span>
          </button>
          <button className="ibtn" onClick={onHelp} aria-label="help" data-tip="help">
            <Icon name="help" size={14} />
          </button>
        </div>

        <span className="clock">{clock}</span>
      </div>
    </div>
    </>
  );
}
