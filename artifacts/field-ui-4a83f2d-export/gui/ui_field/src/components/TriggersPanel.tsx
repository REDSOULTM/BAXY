/* TriggersPanel — phrase-trigger CRUD via the 'routine' tool.
   matches legacy TriggersDialog: list / create / EDIT / delete / run_now.
   the form is the same widget for create and edit — `editingId` toggles
   the behaviour (POST /triggers vs PUT /triggers/{id}). */

import { useCallback, useEffect, useState } from 'react';
import { Panel } from './Panel';
import { Icon } from './Icon';
import { toastError, pushToast } from '../hooks/useToast';

interface TriggerRow {
  id: string;
  label: string;
  phrase: string;
  type: string;
  enabled: boolean;
  steps: unknown[];
}

interface Props { onClose: () => void; }

const EXAMPLE_STEPS = `[
  {"tool": "audio", "args": {"action": "set_volume", "level": 20}}
]`;

export function TriggersPanel({ onClose }: Props) {
  const [rows, setRows] = useState<TriggerRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const [selected, setSelected] = useState<string | null>(null);

  // form state — shared between create and edit. `editingId` non-null means
  // we're editing an existing trigger and the submit button does PUT.
  const [editingId, setEditingId] = useState<string | null>(null);
  const [label, setLabel] = useState('');
  const [phrase, setPhrase] = useState('');
  const [stepsRaw, setStepsRaw] = useState(EXAMPLE_STEPS);
  const [enabled, setEnabled] = useState(true);
  const [formErr, setFormErr] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      setLoading(true);
      const r = await fetch('/triggers');
      if (!r.ok) { setErr(`server error ${r.status}`); return; }
      const data = (await r.json()) as { items?: TriggerRow[]; error?: string };
      if (data.error) setErr(data.error); else setErr(null);
      setRows(data.items ?? []);
    } catch (e) {
      setErr(String(e));
    } finally {
      setLoading(false);
    }
  }, []);

  // initial fetch on mount; user-triggered reloads use `refresh` after CRUD.
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const r = await fetch('/triggers');
        if (cancelled) return;
        if (!r.ok) { setErr(`server error ${r.status}`); return; }
        const data = (await r.json()) as { items?: TriggerRow[]; error?: string };
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

  const resetForm = () => {
    setEditingId(null);
    setLabel('');
    setPhrase('');
    setStepsRaw(EXAMPLE_STEPS);
    setEnabled(true);
    setFormErr(null);
  };

  const loadIntoForm = (row: TriggerRow) => {
    setEditingId(row.id);
    setLabel(row.label);
    setPhrase(row.phrase);
    setEnabled(row.enabled);
    try {
      setStepsRaw(JSON.stringify(row.steps ?? [], null, 2));
    } catch {
      setStepsRaw('[]');
    }
    setFormErr(null);
  };

  const submitForm = async () => {
    if (!label.trim() || !phrase.trim()) {
      setFormErr('label and phrase required');
      return;
    }
    let steps: unknown;
    try {
      steps = JSON.parse(stepsRaw || '[]');
      if (!Array.isArray(steps)) throw new Error('steps must be an array');
    } catch (e) {
      setFormErr(`invalid steps JSON: ${String(e)}`);
      return;
    }
    setFormErr(null);
    setPending(true);
    try {
      const body = {
        label: label.trim(),
        phrase: phrase.trim(),
        type: 'on_phrase',
        steps,
        enabled,
      };
      const url = editingId ? `/triggers/${encodeURIComponent(editingId)}` : '/triggers';
      const method = editingId ? 'PUT' : 'POST';
      const r = await fetch(url, {
        method,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      const data = await r.json();
      if (!data?.ok) {
        setFormErr(String(data?.error ?? `${method.toLowerCase()} failed`));
        return;
      }
      resetForm();
      await refresh();
    } catch (e) {
      setFormErr(String(e));
    } finally {
      setPending(false);
    }
  };

  const remove = async (id: string, lbl: string) => {
    if (!window.confirm(`delete trigger "${lbl}"?`)) return;
    setPending(true);
    try {
      const r = await fetch(`/triggers/${encodeURIComponent(id)}`, { method: 'DELETE' });
      if (!r.ok) throw new Error(`status ${r.status}`);
      if (selected === id) setSelected(null);
      if (editingId === id) resetForm();
      await refresh();
    } catch (e) {
      toastError(`trigger delete failed · ${String(e).replace(/^Error: /, '')}`);
    } finally { setPending(false); }
  };

  const runNow = async (id: string) => {
    setPending(true);
    try {
      const r = await fetch(`/triggers/${encodeURIComponent(id)}/run`, { method: 'POST' });
      if (!r.ok) throw new Error(`status ${r.status}`);
      const data = await r.json();
      if (data && typeof data === 'object' && 'ok' in data && !data.ok) {
        toastError(`trigger run failed · ${data.error ?? 'unknown'}`);
      } else {
        pushToast({ kind: 'success', msg: `trigger fired · ${id.slice(0, 8)}` });
      }
    } catch (e) {
      toastError(`trigger run failed · ${String(e).replace(/^Error: /, '')}`);
    } finally { setPending(false); }
  };

  const selectedRow = rows.find((r) => r.id === selected);

  return (
    <Panel title="triggers · phrase routines" onClose={onClose} width={720}>
      {/* ---- list ---- */}
      <div className="session-list">
        {loading && <div className="muted" style={{ padding: 14 }}>loading triggers…</div>}
        {!loading && rows.length === 0 && (
          <div className="muted" style={{ padding: 14 }}>
            {err ? `error · ${err}` : 'no triggers yet · use the form below to create one'}
          </div>
        )}
        {rows.map((t) => {
          const isSel = selected === t.id;
          const isEditing = editingId === t.id;
          return (
            <div
              key={t.id}
              className={`session-row${isSel ? ' selected' : ''}${isEditing ? ' current' : ''}`}
              onClick={() => {
                setSelected(t.id);
                loadIntoForm(t);
              }}
              role="button"
              tabIndex={0}
              style={{ cursor: 'pointer', gridTemplateColumns: '20px 1fr 1fr auto' }}
              title="click to edit"
            >
              <div className="session-id" style={{ color: t.enabled ? 'var(--carmine)' : 'var(--t-dim)' }}>
                {t.enabled ? '✓' : '✗'}
              </div>
              <div className="session-label">{t.label}</div>
              <div className="session-ts" style={{ fontFamily: 'var(--mono)' }}>
                "{t.phrase}"
              </div>
              <div className="session-ts">{(t.steps as unknown[]).length} steps</div>
            </div>
          );
        })}
      </div>

      <div className="panel-footer" style={{ gap: 6, justifyContent: 'flex-start' }}>
        <button
          type="button"
          className="panel-btn"
          onClick={() => {
            // fallback to the first row when nothing is selected — avoids
            // the "edit does nothing" foot-gun when the user hasn't clicked
            // a row first.
            const target = selectedRow ?? rows[0];
            if (target) {
              setSelected(target.id);
              loadIntoForm(target);
            }
          }}
          disabled={rows.length === 0 || pending}
        >edit</button>
        <button
          type="button"
          className="panel-btn"
          onClick={() => selected && runNow(selected)}
          disabled={!selected || pending}
        >▶ run now</button>
        <button
          type="button"
          className="panel-btn ghost"
          onClick={() => selectedRow && remove(selectedRow.id, selectedRow.label)}
          disabled={!selected || pending}
          style={selected ? { color: 'var(--carmine)' } : undefined}
        >delete</button>
        <span className="muted" style={{ marginLeft: 'auto' }}>{rows.length} triggers</span>
      </div>

      {/* ---- create / edit form ---- */}
      <div style={{ borderTop: '1px solid var(--hair)', padding: '12px 14px 8px', display: 'flex', flexDirection: 'column', gap: 8 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
          <div className="muted" style={{ fontSize: 10, letterSpacing: '0.1em', textTransform: 'lowercase' }}>
            {editingId
              ? `editing · ${editingId.slice(0, 8)}`
              : 'create new trigger'}
          </div>
          {editingId && (
            <button
              type="button"
              className="panel-btn ghost"
              onClick={resetForm}
              disabled={pending}
              style={{ fontSize: 10, padding: '2px 8px' }}
            >cancel edit</button>
          )}
        </div>
        <input
          className="st-input"
          placeholder="label (display name)"
          value={label}
          onChange={(e) => setLabel(e.target.value)}
        />
        <input
          className="st-input mono"
          placeholder="phrase the user will say"
          value={phrase}
          onChange={(e) => setPhrase(e.target.value)}
        />
        <textarea
          className="st-textarea mono"
          rows={5}
          value={stepsRaw}
          onChange={(e) => setStepsRaw(e.target.value)}
          placeholder="steps: JSON array of {tool, args}"
          spellCheck={false}
        />
        <label
          className="sf-check"
          style={{ alignSelf: 'flex-start' }}
          onClick={() => setEnabled((v) => !v)}
        >
          <span className={`check-box${enabled ? ' on' : ''}`} aria-hidden="true" />
          <div className="check-body">
            <span className="check-label">enabled</span>
          </div>
        </label>
        {formErr && (
          <div style={{ color: 'var(--carmine)', fontSize: 10, fontFamily: 'var(--mono)' }}>
            {formErr}
          </div>
        )}
        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 6 }}>
          <button
            type="button"
            className="panel-btn"
            onClick={submitForm}
            disabled={pending}
          >
            {editingId ? (
              <>
                <Icon name="check" size={12} />
                <span>save changes</span>
              </>
            ) : (
              <>
                <Icon name="plus" size={12} />
                <span>save trigger</span>
              </>
            )}
          </button>
        </div>
      </div>
    </Panel>
  );
}
