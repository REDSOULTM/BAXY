import { useEffect, useMemo, useRef, useState } from 'react';
import type { ActivityEntry, SourceTag } from '../types';
import type { SessionInfo, SurfacesCount } from '../hooks/useEventStream';

const INITIAL_ENTRIES: ActivityEntry[] = [
  { id: 'b1', src: 'BOOT',    msg: 'weights resident · mapped from disk.',                ts: '00:00:01' },
  { id: 'b2', src: 'SYSTEM',  msg: 'llama-server reachable · tools loaded.',              ts: '00:00:03' },
  { id: 'b3', src: 'CONTEXT', msg: 'session resumed · prior history available in scope.', ts: '00:00:04' },
  { id: 'b4', src: 'MEMORY',  msg: 'pinned traces recalled into focus tier.',             ts: '00:00:05' },
  { id: 'b5', src: 'GEMMA',   msg: 'ready. field is idle. waiting for your voice or text.', ts: '00:00:06' },
];

type SurfaceId = 'sessions' | 'memory' | 'triggers' | 'tools';

interface SurfaceCard {
  id: SurfaceId;
  label: string;
  unit: string;
}

const SURFACES: SurfaceCard[] = [
  { id: 'sessions', label: 'sessions', unit: 'cached' },
  { id: 'memory',   label: 'memory',   unit: 'pinned' },
  { id: 'triggers', label: 'triggers', unit: 'active' },
  { id: 'tools',    label: 'tools',    unit: 'wired' },
];

interface Props {
  entries: ActivityEntry[];
  session: SessionInfo | null;
  surfaces: SurfacesCount | null;
  activeSurface: SurfaceId;
  onSurface: (id: SurfaceId) => void;
  clock: string;
}

export function ActivityPanel({
  entries, session, surfaces, activeSurface, onSurface, clock,
}: Props) {
  const scrollRef = useRef<HTMLDivElement | null>(null);
  // poll /surfaces every 5s for counts that aren't on the WS bus yet.
  // when the agent updates them (after a tool/memory write), the next poll
  // picks them up.
  const [polled, setPolled] = useState<SurfacesCount | null>(null);
  useEffect(() => {
    let cancelled = false;
    const fetchSurfaces = async () => {
      try {
        const r = await fetch('/surfaces');
        if (cancelled || !r.ok) return;
        setPolled((await r.json()) as SurfacesCount);
      } catch { /* ignore */ }
    };
    fetchSurfaces();
    const id = window.setInterval(fetchSurfaces, 5000);
    return () => { cancelled = true; window.clearInterval(id); };
  }, []);

  const ordered = useMemo(
    () => (entries.length > 0 ? entries : [...INITIAL_ENTRIES].reverse()),
    [entries],
  );

  useEffect(() => {
    if (scrollRef.current) scrollRef.current.scrollTop = 0;
  }, [entries.length]);

  // WS event wins when present (it's authoritative and fresher); fall back
  // to the polled snapshot for steady-state counts.
  const live = surfaces ?? polled;
  const surfaceCount = (id: SurfaceId): string => live ? String(live[id]) : '—';
  const entryCount = entries.length > 0 ? entries.length : INITIAL_ENTRIES.length;
  const sessionId = session?.id ?? '847';

  return (
    <>
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
        {ordered.map((e) => <ActivityRow key={e.id} entry={e} />)}
      </div>

      <div className="surfaces-wrap">
        <div className="sec-head"><span>surfaces</span></div>
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
                  <span className="unit">{s.unit}</span>
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

function ActivityRow({ entry }: { entry: ActivityEntry }) {
  return (
    <div className="act fade-in">
      <div className="meta">
        <span className="ts">{entry.ts}</span>
        <span className={`src ${entry.src.toLowerCase() as Lowercase<SourceTag>}`}>
          {entry.src}
        </span>
      </div>
      <div className="msg">{entry.msg}</div>
    </div>
  );
}
