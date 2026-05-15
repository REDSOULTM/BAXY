/* MemoryPanel — pinned facts CRUD. mirrors legacy MemoryDialog.PERSISTENT tab.
   add / delete / clear-all. items keyed by string, value is plain text.
   facts prefixed 'auto:' came from the LLM's auto-extraction. */

import { useCallback, useEffect, useState } from 'react';
import { Panel } from './Panel';
import { Icon } from './Icon';
import { toastError } from '../hooks/useToast';

interface MemoryItem {
  key: string;
  value: string;
  updated_at: string;
}

interface Props { onClose: () => void; }

export function MemoryPanel({ onClose }: Props) {
  const [items, setItems] = useState<MemoryItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  const refresh = useCallback(async () => {
    try {
      setLoading(true);
      const r = await fetch('/memory');
      if (!r.ok) { setErr(`server error ${r.status}`); return; }
      const data = (await r.json()) as { items?: MemoryItem[]; error?: string };
      if (data.error) setErr(data.error); else setErr(null);
      setItems(data.items ?? []);
    } catch (e) {
      setErr(String(e));
    } finally {
      setLoading(false);
    }
  }, []);

  // initial fetch on mount. we don't use the memoised `refresh` here because
  // eslint flags "setState in effect body" — duplicating the fetch keeps the
  // mount path setState-clean and `refresh` is reserved for user-triggered
  // reloads (after add/delete).
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const r = await fetch('/memory');
        if (cancelled) return;
        if (!r.ok) { setErr(`server error ${r.status}`); return; }
        const data = (await r.json()) as { items?: MemoryItem[]; error?: string };
        if (data.error) setErr(data.error);
        setItems(data.items ?? []);
      } catch (e) {
        if (!cancelled) setErr(String(e));
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, []);

  const addFact = async () => {
    const key = window.prompt('key (e.g. "user.name"):');
    if (!key || !key.trim()) return;
    const value = window.prompt(`value for "${key.trim()}":`);
    if (value === null) return;
    setPending(true);
    try {
      const r = await fetch('/memory', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ key: key.trim(), value: value }),
      });
      if (!r.ok) throw new Error(`status ${r.status}`);
      await refresh();
    } catch (e) {
      toastError(`memory add failed · ${String(e).replace(/^Error: /, '')}`);
    } finally { setPending(false); }
  };

  const deleteFact = async (key: string) => {
    if (!window.confirm(`delete memory "${key}"?`)) return;
    setPending(true);
    try {
      const r = await fetch(`/memory/${encodeURIComponent(key)}`, { method: 'DELETE' });
      if (!r.ok) throw new Error(`status ${r.status}`);
      if (selected === key) setSelected(null);
      await refresh();
    } catch (e) {
      toastError(`memory delete failed · ${String(e).replace(/^Error: /, '')}`);
    } finally { setPending(false); }
  };

  const clearAll = async () => {
    if (!window.confirm('delete ALL persistent memory entries?')) return;
    setPending(true);
    try {
      const r = await fetch('/memory/%2A', { method: 'DELETE' });
      if (!r.ok) throw new Error(`status ${r.status}`);
      setSelected(null);
      await refresh();
    } catch (e) {
      toastError(`memory clear failed · ${String(e).replace(/^Error: /, '')}`);
    } finally { setPending(false); }
  };

  return (
    <Panel title="memory · pinned facts" onClose={onClose} width={620}>
      <div className="session-list">
        {loading && <div className="muted" style={{ padding: 14 }}>loading memory…</div>}
        {!loading && items.length === 0 && (
          <div className="muted" style={{ padding: 14 }}>
            {err ? `error · ${err}` : 'memory empty · add a fact to start'}
          </div>
        )}
        {items.map((it) => {
          const isAuto = it.key.startsWith('auto:');
          const isSel = selected === it.key;
          return (
            <div
              key={it.key}
              className={`session-row${isSel ? ' selected' : ''}`}
              onClick={() => setSelected(it.key)}
              role="button"
              tabIndex={0}
              style={{ cursor: 'pointer', gridTemplateColumns: '160px 1fr auto' }}
            >
              <div className="session-id" style={{ color: isAuto ? 'var(--t-dim)' : 'var(--t-muted)' }}>
                {it.key}
              </div>
              <div className="session-label">{it.value || '(empty)'}</div>
              <div className="session-ts">{it.updated_at.slice(0, 16)}</div>
            </div>
          );
        })}
      </div>

      <div className="panel-footer" style={{ gap: 6, justifyContent: 'flex-start' }}>
        <button type="button" className="panel-btn" onClick={addFact} disabled={pending}>
          <Icon name="plus" size={12} />
          <span>add</span>
        </button>
        <button
          type="button"
          className="panel-btn ghost"
          onClick={() => selected && deleteFact(selected)}
          disabled={!selected || pending}
          style={selected ? { color: 'var(--carmine)' } : undefined}
        >delete</button>
        <span className="muted" style={{ marginLeft: 'auto' }}>{items.length} entries</span>
        <button
          type="button"
          className="panel-btn ghost"
          onClick={clearAll}
          disabled={pending || items.length === 0}
          style={{ color: 'var(--carmine)' }}
        >clear all</button>
      </div>
    </Panel>
  );
}
