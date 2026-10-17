import { useEffect, useState } from 'react';
import { ConfirmRow, Panel } from '../Panel';
import { getJson, send } from '../../api';

/* Triggers (design parts.jsx BxModulePanel «triggers»): only what the person created — BAXY's alarms and reminders in
   Windows' Task Scheduler (schedule.alarms, read and cancelled with the chat's own operation). Windows keeps no
   paused state for them, so a trigger is cancelled with a confirmation in its row, never switched off and on. */

interface Trigger { kind: 'alarm' | 'reminder'; title: string | null; next_local: string | null; state: string | null }
interface Triggers { count: number; items: Trigger[]; truncated: boolean }

export function TriggersPanel({ onClose }: { onClose: () => void }) {
  const [data, setData] = useState<Triggers | null | undefined>(undefined);
  const [ask, setAsk] = useState<number | null>(null);
  const [note, setNote] = useState<string | null>(null);
  useEffect(() => { void getJson<Triggers>('/triggers').then(setData); }, []);
  const cancel = async (t: Trigger) => {
    setAsk(null);
    const r = await send<Triggers>('POST', '/triggers/cancel', { at: t.next_local, kind: t.kind });
    if (r === null) { setNote('No se pudo cancelar.'); return; }
    setNote(null);
    setData(r);
  };
  return (
    <Panel title="Triggers · solo los que tú creaste" onClose={onClose} width={460}>
      {data === null ? <div className="bx-mem-empty">No se pudieron leer las alarmas y recordatorios.</div> : null}
      {note ? <div className="bx-mem-empty">{note}</div> : null}
      <div className="bx-mem">
        {data?.items.map((t, i) => (
          <div key={i} className={'bx-trig' + (t.state && t.state !== 'Ready' ? ' off' : '')}>
            <div className="b">
              <span className="w">{(t.kind === 'alarm' ? 'Alarma' : 'Recordatorio') + (t.next_local ? ' · ' + t.next_local : '')}</span>
              <span className="d">{t.title ?? (t.kind === 'alarm' ? 'Suena en este PC' : 'Te aviso en este PC')}</span>
            </div>
            {ask === i ? <ConfirmRow label="¿Cancelar?" yes="Sí, cancelar" onYes={() => void cancel(t)} onNo={() => setAsk(null)} />
              : t.next_local ? <button className="bx-lnk" onClick={() => setAsk(i)}>Cancelar</button> : null}
          </div>
        ))}
        {data && !data.items.length ? <div className="bx-mem-empty">No has creado alarmas ni recordatorios. Pídeselos a BAXY.</div> : null}
        {data?.truncated ? <div className="bx-mem-empty">Se muestran {data.items.length} de {data.count}.</div> : null}
      </div>
    </Panel>
  );
}
