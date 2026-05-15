import type { SessionInfo } from '../hooks/useEventStream';

interface Props {
  clock: string;
  date: string;
  session: SessionInfo | null;
}

export function BottomBar({ clock, date, session }: Props) {
  return (
    <div className="bar bottom">
      <div className="left">
        <span className="muted">local</span>
        {session ? (
          <>
            <span className="muted">·</span>
            <span className="muted">session #{session.id.slice(0, 8)}</span>
          </>
        ) : null}
      </div>
      <div className="right">
        <span className="muted">{date}</span>
        <span className="muted">·</span>
        <span className="clock">{clock}</span>
      </div>
    </div>
  );
}
