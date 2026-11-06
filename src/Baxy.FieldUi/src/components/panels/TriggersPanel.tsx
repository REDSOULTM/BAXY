import { useEffect, useState } from 'react';
import { ConfirmRow, Panel } from '../Panel';
import { getJson, send } from '../../api';
import { useT } from '../../i18n';

/* Triggers (design parts.jsx BxModulePanel «triggers»): only what the person created — BAXY's alarms and reminders in
   Windows' Task Scheduler (schedule.alarms, read and cancelled with the chat's own operation). Windows keeps no
   paused state for them, so a trigger is cancelled with a confirmation in its row, never switched off and on. */

interface Trigger { kind: 'alarm' | 'reminder'; title: string | null; next_local: string | null; state: string | null }
interface Triggers { count: number; items: Trigger[]; truncated: boolean }

export function TriggersPanel({ onClose }: { onClose: () => void }) {
  const t = useT();
  const [data, setData] = useState<Triggers | null | undefined>(undefined);
  const [ask, setAsk] = useState<number | null>(null);
  const [note, setNote] = useState<string | null>(null);
  useEffect(() => { void getJson<Triggers>('/triggers').then(setData); }, []);
  const cancel = async (x: Trigger) => {
    setAsk(null);
    const r = await send<Triggers>('POST', '/triggers/cancel', { at: x.next_local, kind: x.kind });
    if (r === null) { setNote(t('No se pudo cancelar.', 'Couldn’t cancel it.')); return; }
    setNote(null);
    setData(r);
  };
  return (
    <Panel title={t('Triggers · solo los que tú creaste', 'Triggers · only the ones you created')} onClose={onClose} width={460}>
      {data === null ? <div className="bx-mem-empty" role="status">{t('No se pudieron leer las alarmas y recordatorios.', 'Couldn’t read the alarms and reminders.')}</div> : null}
      {note ? <div className="bx-mem-empty" role="status">{note}</div> : null}
      <div className="bx-mem">
        {data?.items.map((x, i) => (
          <div key={i} className={'bx-trig' + (x.state && x.state !== 'Ready' ? ' off' : '')}>
            <div className="b">
              <span className="w">{(x.kind === 'alarm' ? t('Alarma', 'Alarm') : t('Recordatorio', 'Reminder')) + (x.next_local ? ' · ' + x.next_local : '')}</span>
              <span className="d">{x.title ?? (x.kind === 'alarm' ? t('Suena en este PC', 'Rings on this PC') : t('Aviso en este PC', 'Shows a notice on this PC'))}</span>
            </div>
            {ask === i ? <ConfirmRow label={t('¿Cancelar?', 'Cancel it?')} yes={t('Sí, cancelar', 'Yes, cancel')} onYes={() => void cancel(x)} onNo={() => setAsk(null)} />
              : x.next_local ? <button className="bx-lnk" aria-label={x.kind === 'alarm' ? t('Cancelar la alarma de ', 'Cancel the alarm at ') + x.next_local : t('Cancelar el recordatorio de ', 'Cancel the reminder at ') + x.next_local} onClick={() => setAsk(i)}>{t('Cancelar', 'Cancel')}</button> : null}
          </div>
        ))}
        {data && !data.items.length ? <div className="bx-mem-empty">{t('No has creado alarmas ni recordatorios. Pídeselos a BAXY.', 'You haven’t created any alarms or reminders. Ask BAXY for one.')}</div> : null}
        {data?.truncated ? <div className="bx-mem-empty">{t('Se muestran ', 'Showing ')}{data.items.length}{t(' de ', ' of ')}{data.count}.</div> : null}
      </div>
    </Panel>
  );
}
