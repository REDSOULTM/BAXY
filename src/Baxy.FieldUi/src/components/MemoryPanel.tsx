/* MemoryPanel — lo que BAXY recuerda: ver / editar / borrar / borrar todo.
   cada recuerdo se muestra con su nombre en palabras de la persona (label, del host) y su valor; el selector
   guardado (key) sólo nombra la petición. el shell corre cada cambio como la misma operación de memoria del chat
   (núcleo + diario); los datos nuevos se guardan pidiéndoselo a BAXY en el chat. */

import { useCallback, useEffect, useState } from 'react';
import { Panel } from './Panel';
import { toastError } from '../hooks/useToast';

interface MemoryItem {
  key: string;
  label?: string;
  value: string;
  updated_at: string;
}

// revision: the store's last change by chat, carried by the counter's event (encargo I2: the open panel listed 3 while
// the counter said 4); the list is read again with it.
interface Props { onClose: () => void; revision?: number; }

export function MemoryPanel({ onClose, revision = 0 }: Props) {
  const [items, setItems] = useState<MemoryItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  // la persona confirma un borrado aquí, en el propio panel (un segundo toque), nunca en un diálogo del navegador.
  const [armed, setArmed] = useState<'one' | 'all' | null>(null);
  // la edición se escribe dentro del panel (estabilización M2: antes era un window.prompt en inglés).
  const [editing, setEditing] = useState<string | null>(null);
  const [draft, setDraft] = useState('');
  const [total, setTotal] = useState(0);

  const refresh = useCallback(async () => {
    try {
      setLoading(true);
      const r = await fetch('/memory');
      if (!r.ok) { setErr(`error del servidor ${r.status}`); return; }
      const data = (await r.json()) as { items?: MemoryItem[]; error?: string; total?: number };
      if (data.error) setErr(data.error); else setErr(null);
      setItems(data.items ?? []);
      setTotal(data.total ?? (data.items ?? []).length);
    } catch (e) {
      setErr(String(e));
    } finally {
      setLoading(false);
    }
  }, []);

  // fetch on mount and again on every chat change of the store (revision). we don't use the memoised `refresh` here
  // because eslint flags "setState in effect body" — duplicating the fetch keeps the effect setState-clean and
  // `refresh` is reserved for user-triggered reloads (after add/delete).
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const r = await fetch('/memory');
        if (cancelled) return;
        if (!r.ok) { setErr(`error del servidor ${r.status}`); return; }
        const data = (await r.json()) as { items?: MemoryItem[]; error?: string; total?: number };
        if (data.error) setErr(data.error);
        setItems(data.items ?? []);
        setTotal(data.total ?? (data.items ?? []).length);
      } catch (e) {
        if (!cancelled) setErr(String(e));
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [revision]);

  // every change is read back from the store: a change whose outcome the shell could not confirm is shown as the
  // store holds it ("sin confirmar"), never as failed.
  const change = async (verb: string, path: string, init: RequestInit) => {
    setPending(true);
    try {
      const r = await fetch(path, init);
      const data = (await r.json().catch(() => ({}))) as { error?: string; unconfirmed?: boolean };
      if (!r.ok) toastError(`no pude ${verb} · ${data.error ?? `estado ${r.status}`}`);
      else if (data.unconfirmed) toastError(`no pude confirmar si se pudo ${verb} · muestro lo guardado`);
    } catch (e) {
      toastError(`no pude ${verb} · ${String(e).replace(/^Error: /, '')}`);
    } finally {
      setArmed(null);
      setPending(false);
      await refresh();
    }
  };

  const startEdit = (key: string) => {
    const current = items.find((it) => it.key === key);
    setArmed(null);
    setDraft(current?.value ?? '');
    setEditing(key);
  };

  const saveEdit = async () => {
    const key = editing;
    const value = draft.trim();
    if (key === null || !value) return;
    setEditing(null);
    await change('cambiar el recuerdo', '/memory', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ key, value }),
    });
  };

  const deleteFact = async (key: string) => {
    if (armed !== 'one') { setArmed('one'); return; }
    await change('borrar el recuerdo', `/memory/${encodeURIComponent(key)}`, { method: 'DELETE' });
    setSelected(null);
  };

  const clearAll = async () => {
    if (armed !== 'all') { setArmed('all'); return; }
    await change('borrar todo', '/memory', {
      method: 'DELETE',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ scope: 'all' }),
    });
    setSelected(null);
  };

  return (
    <Panel title="memoria · lo que recuerdo" onClose={onClose} width={620}>
      <div className="session-list">
        {loading && <div className="muted" style={{ padding: 14 }}>cargando la memoria…</div>}
        {!loading && items.length === 0 && (
          <div className="muted" style={{ padding: 14 }}>
            {err ? `error · ${err}` : 'no recuerdo nada todavía · pídeme en el chat que recuerde algo'}
          </div>
        )}
        {items.map((it) => {
          const isSel = selected === it.key;
          const name = it.label || it.key;
          return (
            <div
              key={it.key}
              className={`session-row${isSel ? ' selected' : ''}`}
              onClick={() => { if (editing !== it.key) { setSelected(it.key); setArmed(null); setEditing(null); } }}
              role="button"
              tabIndex={0}
              aria-label={`${name}: ${it.value}`}
              style={{ cursor: 'pointer', gridTemplateColumns: '160px 1fr auto' }}
            >
              <div className="session-id" style={{ color: 'var(--t-muted)' }}>
                {name}
              </div>
              {editing === it.key ? (
                <input
                  autoFocus
                  type="text"
                  className="st-input"
                  value={draft}
                  aria-label={`nuevo valor de ${name}`}
                  onChange={(e) => setDraft(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') { e.preventDefault(); void saveEdit(); }
                    if (e.key === 'Escape') { e.preventDefault(); setEditing(null); }
                  }}
                  spellCheck={false}
                />
              ) : (
                <div className="session-label">{it.value || '(vacío)'}</div>
              )}
              <div className="session-ts">{it.updated_at.slice(0, 16)}</div>
            </div>
          );
        })}
      </div>

      <div className="panel-footer" style={{ gap: 6, justifyContent: 'flex-start' }}>
        {editing ? (
          <>
            <button
              type="button"
              className="panel-btn"
              onClick={() => void saveEdit()}
              disabled={pending || !draft.trim()}
            >guardar</button>
            <button type="button" className="panel-btn ghost" onClick={() => setEditing(null)} disabled={pending}>
              cancelar
            </button>
          </>
        ) : (
          <button
            type="button"
            className="panel-btn"
            onClick={() => selected && startEdit(selected)}
            disabled={!selected || pending}
          >editar</button>
        )}
        <button
          type="button"
          className="panel-btn ghost"
          onClick={() => selected && deleteFact(selected)}
          disabled={!selected || pending || editing !== null}
          style={selected ? { color: 'var(--carmine)' } : undefined}
        >{armed === 'one' ? 'confirmar borrado' : 'borrar'}</button>
        {armed && (
          <button type="button" className="panel-btn ghost" onClick={() => setArmed(null)} disabled={pending}>
            cancelar
          </button>
        )}
        <span className="muted" style={{ marginLeft: 'auto' }}>
          {total > items.length ? `${items.length} de ${total} recuerdos` : `${items.length} recuerdos`}
        </span>
        <button
          type="button"
          className="panel-btn ghost"
          onClick={clearAll}
          disabled={pending || items.length === 0 || editing !== null}
          style={{ color: 'var(--carmine)' }}
        >{armed === 'all' ? `confirmar: olvidar los ${items.length}` : 'borrar todo'}</button>
      </div>
    </Panel>
  );
}
