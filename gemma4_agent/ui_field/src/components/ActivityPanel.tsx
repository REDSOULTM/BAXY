import { useEffect, useMemo, useRef, useState } from 'react';
import type { ActivityEntry, SourceTag } from '../types';
import type { SessionInfo, SurfacesCount } from '../hooks/useEventStream';

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

  const ordered = useMemo(() => entries, [entries]);

  useEffect(() => {
    if (scrollRef.current) scrollRef.current.scrollTop = 0;
  }, [entries.length]);

  // WS event wins when present (it's authoritative and fresher); fall back
  // to the polled snapshot for steady-state counts.
  const live = surfaces ?? polled;
  const surfaceCount = (id: SurfaceId): string => live ? String(live[id]) : '—';
  const entryCount = entries.length;
  const sessionId = session?.id ?? 'none';

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
        {ordered.length > 0 ? (
          ordered.map((e) => <ActivityRow key={e.id} entry={e} />)
        ) : (
          <div className="activity-empty">waiting for live activity</div>
        )}
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
