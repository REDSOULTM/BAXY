/* SessionsPanel — full CRUD over ~/.gemma4/sessions matching the legacy GUI.
   load (single click) / new / rename / delete with confirm. */

import { useCallback, useEffect, useState } from 'react';
import { Panel } from './Panel';
import { Icon } from './Icon';
import { toastError } from '../hooks/useToast';

interface SessionRow {
  id: string;
  label: string;
  ts: string;
  turn_count?: number;
  current?: boolean;
}

interface Props {
  onClose: () => void;
}

export function SessionsPanel({ onClose }: Props) {
  const [filter, setFilter] = useState('');
  const [rows, setRows] = useState<SessionRow[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  const refresh = useCallback(async () => {
    try {
      setLoading(true);
      const r = await fetch('/sessions');
      if (!r.ok) {
        setErr(`server error ${r.status}`);
        return;
      }
      const data = (await r.json()) as { sessions: SessionRow[]; error?: string };
      if (data.error) setErr(data.error);
      else setErr(null);
      setRows(data.sessions ?? []);
    } catch (e) {
      setErr(String(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const r = await fetch('/sessions');
        if (cancelled) return;
        if (!r.ok) { setErr(`server error ${r.status}`); return; }
        const data = (await r.json()) as { sessions: SessionRow[]; error?: string };
        if (data.error) setErr(data.error);
        setRows(data.sessions ?? []);
      } catch (e) {
        if (!cancelled) setErr(String(e));
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, []);

  const list = rows.filter((s) =>
    !filter || s.label.toLowerCase().includes(filter.toLowerCase())
  );

  const loadSession = async (id: string) => {
    if (pending) return;
    setPending(true);
    try {
      const r = await fetch('/sessions/load', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ id }),
      });
      if (!r.ok) throw new Error(`status ${r.status}`);
      onClose();
    } catch (e) {
      toastError(`session load failed · ${String(e).replace(/^Error: /, '')}`);
    } finally { setPending(false); }
  };

  const newSession = async () => {
    if (pending) return;
    setPending(true);
    try {
      const r = await fetch('/sessions/new', { method: 'POST' });
      if (!r.ok) throw new Error(`status ${r.status}`);
      onClose();
    } catch (e) {
      toastError(`new session failed · ${String(e).replace(/^Error: /, '')}`);
    } finally { setPending(false); }
  };

  const renameSession = async (id: string, currentTitle: string) => {
    // browser prompt is cheap and matches the QInputDialog the legacy used
    const next = window.prompt('new session title:', currentTitle);
    if (next === null) return;
    const title = next.trim();
    if (!title) return;
    setPending(true);
    try {
      const r = await fetch('/sessions/rename', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ id, title }),
      });
      if (!r.ok) throw new Error(`status ${r.status}`);
      await refresh();
    } catch (e) {
      toastError(`rename failed · ${String(e).replace(/^Error: /, '')}`);
    } finally { setPending(false); }
  };

  const deleteSession = async (id: string, label: string) => {
    if (!window.confirm(`delete session "${label}"?`)) return;
    setPending(true);
    try {
      const r = await fetch(`/sessions/${encodeURIComponent(id)}`, { method: 'DELETE' });
      if (!r.ok) throw new Error(`status ${r.status}`);
      if (selected === id) setSelected(null);
      await refresh();
    } catch (e) {
      toastError(`delete failed · ${String(e).replace(/^Error: /, '')}`);
    } finally { setPending(false); }
  };

  return (
    <Panel title="sessions" onClose={onClose}>
      <div className="session-search">
        <Icon name="search" size={13} />
        <input
          autoFocus
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          placeholder="filter sessions"
          aria-label="filter sessions"
        />
      </div>

      <div className="session-list">
        {loading && <div className="muted" style={{ padding: 14 }}>loading sessions…</div>}
        {!loading && list.length === 0 && (
          <div className="muted" style={{ padding: 14 }}>
            {err ? `error · ${err}` : 'no sessions yet · start chatting to create one'}
          </div>
        )}
        {list.map((s) => {
          const isSel = selected === s.id;
          return (
            <div
              key={s.id}
              className={`session-row${s.current ? ' current' : ''}${isSel ? ' selected' : ''}`}
              onClick={() => setSelected(s.id)}
              onDoubleClick={() => loadSession(s.id)}
              role="button"
              tabIndex={0}
              onKeyDown={(e) => {
                if (e.key === 'Enter') { e.preventDefault(); loadSession(s.id); }
              }}
              style={{ cursor: 'pointer' }}
            >
              <div className="session-id">#{s.id.slice(0, 8)}</div>
              <div className="session-label">{s.label}</div>
              <div className="session-ts">{s.ts}</div>
              {s.current ? <div className="session-cur">current</div> : null}
            </div>
          );
        })}
      </div>

      <div className="panel-footer" style={{ gap: 6, justifyContent: 'flex-start' }}>
        <button
          type="button"
          className="panel-btn"
          onClick={() => {
            // fallback to the first row when the user hasn't selected one;
            // avoids the "load button does nothing" foot-gun.
            const id = selected ?? rows[0]?.id;
            if (id) loadSession(id);
          }}
          disabled={rows.length === 0 || pending}
        >load</button>
        <button
          type="button"
          className="panel-btn ghost"
          onClick={() => {
            const row = rows.find((r) => r.id === selected) ?? rows[0];
            if (row) renameSession(row.id, row.label);
          }}
          disabled={rows.length === 0 || pending}
        >rename</button>
        <button
          type="button"
          className="panel-btn ghost"
          onClick={() => {
            const row = rows.find((r) => r.id === selected) ?? rows[0];
            if (row) deleteSession(row.id, row.label);
          }}
          disabled={rows.length === 0 || pending}
          style={{ color: 'var(--carmine)' }}
        >delete</button>
        <span className="muted" style={{ marginLeft: 'auto' }}>
          {list.length} sessions · all local
        </span>
        <button type="button" className="panel-btn" onClick={newSession} disabled={pending}>
          <Icon name="plus" size={12} />
          <span>new session</span>
        </button>
      </div>
    </Panel>
  );
}
