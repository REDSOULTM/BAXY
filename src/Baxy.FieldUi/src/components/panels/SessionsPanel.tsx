import { useEffect, useState } from 'react';
import { Panel } from '../Panel';
import { Icon } from '../Icon';
import { getJson, send } from '../../api';
import { useT } from '../../i18n';

/* Sessions (design panels4.jsx BxSessions): the conversations kept on this PC (FieldSessionStore), opened, renamed or
   started anew. Opening one gives the model back that conversation as it was, calls and results included. */

interface SessionRow { id: string; label: string; ts: string; current: boolean; turn_count: number }
interface SessionsReply { sessions: SessionRow[]; unsaved?: boolean }

export function SessionsPanel({ onClose, onNew, revision }: { onClose: () => void; onNew: () => void; revision: string | undefined }) {
  const t = useT();
  const [list, setList] = useState<SessionRow[] | null | undefined>(undefined);
  // the conversation on screen did not reach the disk at its last save (REV_APP ASY-b, 2026-11-09)
  const [unsaved, setUnsaved] = useState(false);
  const [ed, setEd] = useState<string | null>(null);
  const [val, setVal] = useState('');
  const [note, setNote] = useState<string | null>(null);
  // a list read before the session changed again never covers the newer one, even if it answers last
  useEffect(() => {
    let stale = false;
    void getJson<SessionsReply>('/sessions').then((r) => { if (!stale) { setList(r ? r.sessions : null); setUnsaved(r?.unsaved === true); } });
    return () => { stale = true; };
  }, [revision]);
  const reload = async () => { const r = await getJson<SessionsReply>('/sessions'); setList(r ? r.sessions : null); setUnsaved(r?.unsaved === true); };
  const save = async () => {
    const id = ed;
    setEd(null);
    const title = val.trim();
    if (!id || !title) return;
    if (await send('POST', '/sessions/rename', { id, title }) === null) setNote(t('No se pudo renombrar.', 'Couldn’t rename it.'));
    await reload();
  };
  const open = async (id: string) => {
    if (await send('POST', '/sessions/load', { id }) === null) { setNote(t('No se pudo abrir: BAXY está ocupado o la sesión ya no existe.', 'Couldn’t open it: BAXY is busy or the session no longer exists.')); return; }
    onClose();
  };
  return (
    <Panel title={t('Historial de conversaciones', 'Conversation history')} onClose={onClose} width={480}>
      <button className="panel-btn" style={{ marginBottom: 12 }} onClick={onNew}><Icon name="plus" size={11} /> {t('Nueva conversación', 'New conversation')}</button>
      {note ? <div className="bx-mem-empty" role="status">{note}</div> : null}
      {unsaved ? <div className="bx-mem-empty" role="status">{t('No pude guardar esta conversación en el disco. Sigue en pantalla y lo intento de nuevo con cada respuesta; mientras no se guarde, se puede perder al cerrar BAXY o al abrir otra.', 'I couldn’t save this conversation to disk. It stays on screen and I try again with each answer; until it is saved, closing BAXY or opening another one can lose it.')}</div> : null}
      {list === null ? <div className="bx-mem-empty" role="status">{t('No se pudieron leer las sesiones.', 'Couldn’t read the sessions.')}</div> : null}
      <div className="bx-mem">
        {list?.map((s) => (
          <div key={s.id} className={'bx-mem-row' + (s.current ? ' cur' : '')}>
            {ed === s.id
              ? <input className="st-input" autoFocus value={val} maxLength={80} aria-label={t('Nombre de la sesión', 'Session name')} onChange={(e) => setVal(e.target.value)}
                onKeyDown={(e) => { if (e.key === 'Enter') void save(); if (e.key === 'Escape') { e.stopPropagation(); setEd(null); } }} onBlur={() => void save()} />
              : <button className="bx-sess-t" onClick={() => (s.current ? onClose() : void open(s.id))}>{s.label}</button>}
            <span className="acts">
              <span className="ts">{s.current ? t('Abierta', 'Open') : s.ts}</span>
              {ed !== s.id ? <button className="bx-lnk" aria-label={t('Renombrar ', 'Rename ') + s.label} onClick={() => { setEd(s.id); setVal(s.label); }}>{t('Renombrar', 'Rename')}</button> : null}
            </span>
          </div>
        ))}
      </div>
    </Panel>
  );
}
