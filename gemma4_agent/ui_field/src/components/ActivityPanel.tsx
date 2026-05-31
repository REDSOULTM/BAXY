import { useEffect, useMemo, useRef } from 'react';
import type { ActivityEntry, SourceTag } from '../types';
import type { SessionInfo, SurfacesCount } from '../hooks/useEventStream';
import { Icon } from './Icon';

type SurfaceId = 'sessions' | 'memory' | 'triggers' | 'tools';

interface SurfaceCard {
  id: SurfaceId;
  label: string;
  unit: string;
}

// the redesign splits the four surfaces: sessions/memory live on the RIGHT
// (activity); triggers/tools moved to the LEFT (substrate).
const SURFACES: SurfaceCard[] = [
  { id: 'sessions', label: 'sessions', unit: 'cached' },
  { id: 'memory',   label: 'memory',   unit: 'pinned' },
];

interface Props {
  entries: ActivityEntry[];
  session: SessionInfo | null;
  surfaces: SurfacesCount | null;
  activeSurface: SurfaceId;
  onSurface: (id: SurfaceId) => void;
  clock: string;
  /** toolbar actions relocated here from the removed TopBar (prototype model). */
  settingsOpen: boolean;
  onSettings: () => void;
  onNewSession: () => void;
  onHelp: () => void;
}

export function ActivityPanel({
  entries, session, surfaces, activeSurface, onSurface, clock,
  settingsOpen, onSettings, onNewSession, onHelp,
}: Props) {
  const scrollRef = useRef<HTMLDivElement | null>(null);

  const ordered = useMemo(() => entries, [entries]);

  useEffect(() => {
    if (scrollRef.current) scrollRef.current.scrollTop = 0;
  }, [entries.length]);

  // surface counts arrive pre-merged from App (WS event ?? /surfaces poll).
  const surfaceCount = (id: SurfaceId): string => (surfaces ? String(surfaces[id]) : '—');
  const entryCount = entries.length;
  const sessionId = session?.id ?? 'none';

  return (
    <>
      {/* action toolbar — relocated from the removed TopBar (prototype model) */}
      <div className="act-toolbar">
        <button className="ibtn xs" data-tip="new session" onClick={onNewSession} aria-label="new session">
          <Icon name="plus" size={13} />
        </button>
        <button className="ibtn xs" data-tip="shortcuts" onClick={onHelp} aria-label="shortcuts">
          <Icon name="help" size={13} />
        </button>
        <button
          className={`ibtn xs labeled${settingsOpen ? ' active' : ''}`}
          data-tip="settings · configure agent"
          onClick={onSettings}
          aria-label="settings"
        >
          <Icon name="settings" size={13} />
          <span>settings</span>
        </button>
      </div>

      <div className="sec-head">
        <span>activity</span>
        <span className="ref">{entryCount} entries · #{sessionId}</span>
      </div>

      <div
        className="activity-scroll"
        ref={scrollRef}
        role="log"
        aria-live="polite"
        aria-atomic="false"
      >
        {ordered.length > 0 ? (
          ordered.map((e) => <ActivityRow key={e.id} entry={e} />)
        ) : (
          <div className="activity-empty">waiting for live activity</div>
        )}
      </div>

      <div className="surfaces-wrap">
        <div className="surfaces">
          {SURFACES.map((s) => {
            const active = activeSurface === s.id;
            return (
              <div
                key={s.id}
                className={`scard${active ? ' active' : ''}`}
                onClick={() => onSurface(s.id)}
                role="button"
                tabIndex={0}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    onSurface(s.id);
                  }
                }}
                aria-pressed={active}
              >
                <div className="lbl">{s.label}</div>
                <div className="count">
                  {surfaceCount(s.id)}
                  <span className="unit"> {s.unit}</span>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      <div className="right-footer">
        <span>local · no telemetry</span>
        <span className="v">{clock}</span>
      </div>
    </>
  );
}

// maps a source tag to its CSS color class; unknown tags fall back to `you`
// (var(--tag-you)) exactly like the handoff, instead of an unstyled class.
const SOURCE_CLASS: Record<SourceTag, string> = {
  TOOL: 'tool', YOU: 'you', GEMMA: 'gemma', MEMORY: 'memory', TRIGGER: 'trigger',
  BOOT: 'boot', THOUGHT: 'thought', SYSTEM: 'system', CONTEXT: 'context',
};

function ActivityRow({ entry }: { entry: ActivityEntry }) {
  const cls = SOURCE_CLASS[entry.src] ?? 'you';
  return (
    <div className="act fade-in">
      <div className="meta">
        <span className="ts">{entry.ts}</span>
        <span className={`src ${cls}`}>{entry.src}</span>
      </div>
      <div className="msg">{entry.msg}</div>
    </div>
  );
}
