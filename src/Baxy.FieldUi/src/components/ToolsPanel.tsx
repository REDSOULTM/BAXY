/* ToolsPanel — browse the agent's tool registry + execute any tool with
   custom args. mirrors the legacy ToolExplorer: search filter, schema
   preview (read-only), args JSON editor, RUN button, result viewer. */

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

  const [argsRaw, setArgsRaw] = useState('{"action": "status"}');
  const [result, setResult] = useState<string>('');
  const [running, setRunning] = useState(false);

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

  const run = async () => {
    if (!selected || running) return;
    let args: unknown;
    try {
      args = JSON.parse(argsRaw || '{}');
      if (typeof args !== 'object' || args === null || Array.isArray(args)) {
        throw new Error('args must be a JSON object');
      }
    } catch (e) {
      setResult(`args error: ${String(e)}`);
      return;
    }
    setRunning(true);
    setResult(`running ${selected}(${JSON.stringify(args)}) ...`);
    try {
      const r = await fetch('/tools/execute', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: selected, args }),
      });
      const data = await r.json();
      setResult(JSON.stringify(data, null, 2));
    } catch (e) {
      setResult(`request failed: ${String(e)}`);
    } finally {
      setRunning(false);
    }
  };

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

        {/* ---- right: schema + run form ---- */}
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
              <div className="muted" style={{ fontSize: 10, letterSpacing: '0.1em', textTransform: 'lowercase' }}>args · JSON object</div>
              <textarea
                className="st-textarea mono"
                value={argsRaw}
                onChange={(e) => setArgsRaw(e.target.value)}
                rows={4}
                spellCheck={false}
              />
              <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                <button
                  type="button"
                  className="panel-btn"
                  onClick={run}
                  disabled={running}
                >▶ run</button>
                <span className="muted" style={{ fontSize: 10 }}>
                  {running ? 'running…' : ' '}
                </span>
              </div>
              <div className="muted" style={{ fontSize: 10, letterSpacing: '0.1em', textTransform: 'lowercase' }}>result</div>
              <pre
                className="st-prompt"
                style={{ maxHeight: 260, overflow: 'auto', fontSize: 10 }}
              >
                {result || '(no run yet)'}
              </pre>
            </>
          )}
        </div>
      </div>
    </Panel>
  );
}
