import { useEffect, useState } from 'react';
import { Panel } from '../Panel';
import { Icon } from '../Icon';
import { getJson, send } from '../../api';

/* Sessions (design panels4.jsx BxSessions): the conversations kept on this PC (FieldSessionStore), opened, renamed or
   started anew. Opening one gives the model back that conversation as it was, calls and results included. */

interface SessionRow { id: string; label: string; ts: string; current: boolean; turn_count: number }

export function SessionsPanel({ onClose, onNew, revision }: { onClose: () => void; onNew: () => void; revision: string | undefined }) {
  const [list, setList] = useState<SessionRow[] | null | undefined>(undefined);
  const [ed, setEd] = useState<string | null>(null);
  const [val, setVal] = useState('');
  const [note, setNote] = useState<string | null>(null);
  useEffect(() => { void getJson<{ sessions: SessionRow[] }>('/sessions').then((r) => setList(r ? r.sessions : null)); }, [revision]);
  const reload = async () => { const r = await getJson<{ sessions: SessionRow[] }>('/sessions'); setList(r ? r.sessions : null); };
  const save = async () => {
    const id = ed;
    setEd(null);
    const title = val.trim();
    if (!id || !title) return;
    if (await send('POST', '/sessions/rename', { id, title }) === null) setNote('No se pudo renombrar.');
    await reload();
  };
  const open = async (id: string) => {
    if (await send('POST', '/sessions/load', { id }) === null) { setNote('No se pudo abrir: BAXY está ocupado o la sesión ya no existe.'); return; }
    onClose();
  };
  return (
    <Panel title="Sesiones" onClose={onClose} width={480}>
      <button className="panel-btn" style={{ marginBottom: 12 }} onClick={onNew}><Icon name="plus" size={11} /> Nueva conversación</button>
      {note ? <div className="bx-mem-empty">{note}</div> : null}
      {list === null ? <div className="bx-mem-empty">No se pudieron leer las sesiones.</div> : null}
      <div className="bx-mem">
        {list?.map((s) => (
          <div key={s.id} className={'bx-mem-row' + (s.current ? ' cur' : '')}>
            {ed === s.id
              ? <input className="st-input" autoFocus value={val} maxLength={80} aria-label="Nombre de la sesión" onChange={(e) => setVal(e.target.value)}
                onKeyDown={(e) => { if (e.key === 'Enter') void save(); if (e.key === 'Escape') { e.stopPropagation(); setEd(null); } }} onBlur={() => void save()} />
              : <button className="bx-sess-t" onClick={() => (s.current ? onClose() : void open(s.id))}>{s.label}</button>}
            <span className="acts">
              <span className="ts">{s.current ? 'Abierta' : s.ts}</span>
              {ed !== s.id ? <button className="bx-lnk" onClick={() => { setEd(s.id); setVal(s.label); }}>Renombrar</button> : null}
            </span>
          </div>
        ))}
      </div>
    </Panel>
  );
}
