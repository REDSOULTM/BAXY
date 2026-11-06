import { useCallback, useEffect, useState } from 'react';
import { ConfirmRow, Panel, Toggle } from '../Panel';
import { getJson, send } from '../../api';
import { useT, type Words } from '../../i18n';

/* Memory (design panels4.jsx BxMemory4): what BAXY remembers, grouped, the sensitive data apart and hidden, forgetting
   with a confirmation in the same row. Every change runs the chat's own memory operation on the host (MemoryPanel.cs).
   A sensitive or secret value never leaves the encrypted store (LocalMemoryStore redacts it), so it is never shown. */

interface MemoryItem {
  key: string;
  label?: string;
  value: string;
  updated_at: string;
  kind?: 'fact' | 'preference' | 'context' | 'rule';
  sensitivity?: 'normal' | 'personal' | 'sensitive' | 'secret';
  retention?: 'persistent' | 'session' | 'temporary';
}

interface MemoryList { enabled?: boolean; total?: number | null; items?: MemoryItem[]; error?: string; unconfirmed?: boolean }

type Group = 'pref' | 'rule' | 'fact' | 'recent' | 'sens';
const GROUPS: [Exclude<Group, 'sens'>, Words][] = [
  ['pref', { es: 'Preferencias', en: 'Preferences' }], ['rule', { es: 'Reglas y costumbres', en: 'Rules and habits' }],
  ['fact', { es: 'Sobre ti', en: 'About you' }], ['recent', { es: 'Conversación reciente', en: 'Recent conversation' }],
];

function groupOf(m: MemoryItem): Group {
  if (m.sensitivity === 'sensitive' || m.sensitivity === 'secret') return 'sens';
  if (m.retention === 'session' || m.retention === 'temporary') return 'recent';
  if (m.kind === 'preference') return 'pref';
  if (m.kind === 'rule') return 'rule';
  return 'fact';
}

const ERRORS: Record<string, Words> = {
  agent_not_ready: { es: 'BAXY aún está arrancando.', en: 'BAXY is still starting.' },
  memory_unavailable: { es: 'No se pudo leer la memoria.', en: 'Couldn’t read the memory.' },
  memory_not_found: { es: 'Ese recuerdo ya no está.', en: 'That memory is no longer there.' },
};

export function MemoryPanel({ onClose, revision }: { onClose: () => void; revision: number }) {
  const t = useT();
  const [data, setData] = useState<MemoryList | null>(null);
  // what waits for its «¿Olvidar?»: 'all', or a row as 'key:' + its key (a memory may be called «all»)
  const [ask, setAsk] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState<string | null>(null);

  const load = useCallback(async () => {
    const r = await getJson<MemoryList>('/memory');
    setData(r ?? { error: 'memory_unavailable', items: [] });
  }, []);
  // a reading started before the memory changed again never covers the newer one, even if it answers last
  useEffect(() => {
    let stale = false;
    void getJson<MemoryList>('/memory').then((r) => { if (!stale) setData(r ?? { error: 'memory_unavailable', items: [] }); });
    return () => { stale = true; };
  }, [revision]);

  const run = async (call: () => Promise<MemoryList | null>, failure: string) => {
    setBusy(true);
    const r = await call();
    setBusy(false);
    setAsk(null);
    if (r === null) { setNote(failure); await load(); return; }
    setNote(r.unconfirmed ? t('No se pudo confirmar el cambio: esto es lo que hay ahora.', 'Couldn’t confirm the change: this is what’s there now.') : null);
    if (r.items) setData(r); else await load();
  };
  const forget = (key: string) => run(() => send<MemoryList>('DELETE', '/memory/' + encodeURIComponent(key)), t('No se pudo olvidar.', 'Couldn’t forget it.'));
  const forgetAll = () => run(() => send<MemoryList>('DELETE', '/memory', { scope: 'all' }), t('No se pudo olvidar todo.', 'Couldn’t forget everything.'));
  const setOn = (enabled: boolean) => run(() => send<MemoryList>('POST', '/memory/enabled', { enabled }), enabled ? t('No se pudo activar.', 'Couldn’t turn it on.') : t('No se pudo apagar.', 'Couldn’t turn it off.'));

  const items = data?.items ?? [];
  const on = data?.enabled !== false;
  const row = (m: MemoryItem) => {
    const sens = groupOf(m) === 'sens';
    return (
      <div key={m.key} className="bx-mem-row">
        <span className="t">{sens ? <><b>{m.label ?? m.key}</b> · ••••••</> : m.label ? <><b>{m.label}</b> · {m.value}</> : m.value}</span>
        {ask === 'key:' + m.key ? <ConfirmRow label={t('¿Olvidar?', 'Forget it?')} yes={t('Sí, olvidar', 'Yes, forget')} onYes={() => void forget(m.key)} onNo={() => setAsk(null)} /> : (
          <span className="acts"><button className="bx-lnk" disabled={busy} aria-label={t('Olvidar: ', 'Forget: ') + (sens ? m.label ?? m.key : m.label ?? m.value)} onClick={() => setAsk('key:' + m.key)}>{t('Olvidar', 'Forget')}</button></span>
        )}
      </div>
    );
  };
  const total = data?.total ?? items.length;
  return (
    <Panel title={t('Memoria · se guarda solo en este PC', 'Memory · kept only on this PC')} onClose={onClose} width={500}>
      <div className="bxs-row">
        <div className="bxs-l"><span>{t('Recordar cosas sobre ti', 'Remember things about you')}</span><span className="h">{t('Si lo apagas, BAXY no guarda nada nuevo. Lo que ya está se queda hasta que lo olvides.', 'If you turn it off, BAXY saves nothing new. What’s already there stays until you forget it.')}</span></div>
        <div className="bxs-c"><Toggle on={on} label={t('Recordar cosas sobre ti', 'Remember things about you')} locked={busy || !data || !!data.error} onChange={(v) => void setOn(v)} /></div>
      </div>
      {data?.error ? <div className="bx-mem-empty" role="status">{ERRORS[data.error] ? t.w(ERRORS[data.error]) : t('No se pudo leer la memoria.', 'Couldn’t read the memory.')}</div> : null}
      {note ? <div className="bx-mem-empty" role="status">{note}</div> : null}
      {data && !data.error ? (
        <div className={'bx-mem' + (on ? '' : ' off')}>
          {!on ? <div className="bx-mem-empty">{t('La memoria está apagada: BAXY no lee ni guarda recuerdos.', 'Memory is off: BAXY neither reads nor saves memories.')}</div> : null}
          {GROUPS.map(([g, l]) => {
            const list = items.filter((m) => groupOf(m) === g);
            return list.length ? <div key={g} className="bx-mem-g"><div className="panel-sec-head">{t.w(l)}</div>{list.map(row)}</div> : null;
          })}
          {on ? (
            <div className="bx-mem-g sens">
              <div className="panel-sec-head">{t('Datos sensibles', 'Sensitive data')} <span className="lock">{t('siempre ocultos · no salen del almacén cifrado', 'always hidden · never leave the encrypted store')}</span></div>
              {items.filter((m) => groupOf(m) === 'sens').map(row)}
              {!items.some((m) => groupOf(m) === 'sens') ? <div className="bx-mem-empty">{t('Nada guardado.', 'Nothing saved.')}</div> : null}
            </div>
          ) : null}
          {on && !items.length ? <div className="bx-mem-empty">{t('BAXY no recuerda nada.', 'BAXY doesn’t remember anything.')}</div> : null}
        </div>
      ) : null}
      <div className="panel-footer">
        <span>{data && !data.error && on ? total + (total === 1 ? t(' recuerdo', ' memory') : t(' recuerdos', ' memories')) : '—'}</span>
        {ask === 'all' ? <ConfirmRow label={t('¿Olvidar todo?', 'Forget everything?')} yes={t('Sí, olvidar', 'Yes, forget')} onYes={() => void forgetAll()} onNo={() => setAsk(null)} />
          : <button className="panel-btn ghost" disabled={busy || !items.length} onClick={() => setAsk('all')}>{t('Olvidar todo', 'Forget everything')}</button>}
      </div>
    </Panel>
  );
}
