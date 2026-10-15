/* ToolsPanel — browse the tools the model is offered: search filter, each
   tool's description and schema (read-only). Only the model calls them. */

import { useEffect, useMemo, useState } from 'react';
import { Panel } from './Panel';
import { Icon } from './Icon';

interface ToolRow {
  name: string;
  description: string;
  schema: Record<string, unknown>;
}

interface Props { onClose: () => void; }

export function ToolsPanel({ onClose }: Props) {
  const [rows, setRows] = useState<ToolRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);
  const [filter, setFilter] = useState('');
  const [selected, setSelected] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const r = await fetch('/tools');
        if (cancelled) return;
        if (!r.ok) { setErr(`server error ${r.status}`); return; }
        const data = (await r.json()) as { items?: ToolRow[]; error?: string };
        if (data.error) setErr(data.error);
        setRows(data.items ?? []);
      } catch (e) {
        if (!cancelled) setErr(String(e));
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, []);

  const list = useMemo(() => {
    if (!filter) return rows;
    const q = filter.toLowerCase();
    return rows.filter((r) =>
      r.name.toLowerCase().includes(q) || r.description.toLowerCase().includes(q)
    );
  }, [rows, filter]);

  const sel = useMemo(() => rows.find((r) => r.name === selected) ?? null, [rows, selected]);

  return (
    <Panel title="tools · explorer" onClose={onClose} width={860}>
      <div style={{ display: 'grid', gridTemplateColumns: '260px 1fr', gap: 12, padding: 12, minHeight: 0 }}>
        {/* ---- left: list ---- */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6, minWidth: 0 }}>
          <div className="session-search" style={{ marginBottom: 0 }}>
            <Icon name="search" size={13} />
            <input
              value={filter}
              onChange={(e) => setFilter(e.target.value)}
              placeholder="filter tools…"
              aria-label="filter tools"
            />
          </div>
          <div className="session-list" style={{ flex: 1, overflowY: 'auto', maxHeight: 480 }}>
            {loading && <div className="muted" style={{ padding: 8 }}>loading tools…</div>}
            {!loading && list.length === 0 && (
              <div className="muted" style={{ padding: 8 }}>
                {err ? `error · ${err}` : 'no tools match'}
              </div>
            )}
            {list.map((t) => {
              const isSel = selected === t.name;
              return (
                <div
                  key={t.name}
                  className={`session-row${isSel ? ' selected' : ''}`}
                  onClick={() => setSelected(t.name)}
                  role="button"
                  tabIndex={0}
                  style={{ cursor: 'pointer', gridTemplateColumns: '1fr' }}
                >
                  <div className="session-label" style={{ fontFamily: 'var(--mono)' }}>
                    {t.name}
                  </div>
                </div>
              );
            })}
          </div>
          <div className="muted" style={{ fontSize: 10 }}>{list.length} of {rows.length} tools</div>
        </div>

        {/* ---- right: description + schema ---- */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8, minWidth: 0 }}>
          {!sel ? (
            <div className="muted" style={{ padding: 14 }}>select a tool on the left</div>
          ) : (
            <>
              <div className="muted" style={{ fontSize: 10, lineHeight: 1.5 }}>
                {sel.description || '(no description)'}
              </div>
              <div className="muted" style={{ fontSize: 10, letterSpacing: '0.1em', textTransform: 'lowercase' }}>schema</div>
              <pre
                className="st-prompt"
                style={{ maxHeight: 200, overflow: 'auto', fontSize: 10 }}
              >
                {JSON.stringify(sel.schema, null, 2)}
              </pre>
            </>
          )}
        </div>
      </div>
    </Panel>
  );
}
