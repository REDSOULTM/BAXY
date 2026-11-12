import { useCallback, useEffect, useState } from 'react';
import { ConfirmRow, Panel, Toggle } from '../Panel';
import { getJson, sendTold } from '../../api';
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

interface MemoryList { enabled?: boolean; total?: number | null; items?: MemoryItem[]; error?: string; unconfirmed?: boolean; routinesKept?: boolean }

interface Kept { conversations?: number; log?: boolean; routines?: number }
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
};

// VIS1: the list, or the host's reason for not giving it: the host refuses the reading with its code (MemoryPanel.cs
// answers 409 `agent_not_ready` whenever BAXY's core is not ready), and a refusal read as no answer never said which.
async function read(): Promise<MemoryList> {
  try {
    const r = await fetch('/memory');
    const body = await r.json() as MemoryList | null;
    if (r.ok && body) return body;
    return { error: typeof body?.error === 'string' ? body.error : 'memory_unavailable', items: [] };
  } catch {
    return { error: 'memory_unavailable', items: [] };
  }
}

export function MemoryPanel({ onClose, revision, ready, failed }: { onClose: () => void; revision: number; ready: boolean; failed: boolean }) {
  const t = useT();
  const [data, setData] = useState<MemoryList | null>(null);
  // what waits for its «¿Olvidar?»: 'all', or a row as 'key:' + its key (a memory may be called «all»)
  const [ask, setAsk] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState<string | null>(null);

  // PRV1 D7: what «Olvidar todo» takes besides the memories (FieldProductChannel.Kept): the kept conversations and the
  // conversation's log. With no memories the button was off, and nothing in the interface could delete those. RUT4: and
  // the person's routines, which the button names.
  const [kept, setKept] = useState<Kept | null>(null);
  const load = useCallback(async () => {
    setData(await read());
    setKept(await getJson<Kept>('/kept'));
  }, []);
  // a reading started before the memory changed again never covers the newer one, even if it answers last. It is read
  // again when BAXY becomes ready too: until then the host only says it is not, and nothing else would ask again.
  useEffect(() => {
    let stale = false;
    void read().then((r) => { if (!stale) setData(r); });
    void getJson<Kept>('/kept').then((k) => { if (!stale) setKept(k); });
    return () => { stale = true; };
  }, [revision, ready]);

  // VIS1: a change the host refused (with its code) was not done; one with no answer at all (field-native-bridge.js's 503)
  // the host may have done, and its own rule for an outcome it does not know (MemoryPanel.cs, Revisión M H8) is never to
  // tell it failed: what is there now is shown, unconfirmed.
  const run = async (call: () => Promise<{ value: MemoryList | null; refused: boolean }>, failure: string) => {
    setBusy(true);
    const { value: r, refused } = await call();
    setBusy(false);
    setAsk(null);
    const unconfirmed = t('No se pudo confirmar el cambio: esto es lo que hay ahora.', 'Couldn’t confirm the change: this is what’s there now.');
    if (r === null) { setNote(refused ? failure : unconfirmed); await load(); return; }
    // RUT9 (REV9 H5): «Olvidar todo» whose routines stayed (a task Windows did not let go) says so.
    setNote(r.routinesKept
      ? t('Se olvidó lo demás, pero las rutinas no se pudieron borrar: siguen en Rutinas.', 'Everything else was forgotten, but the routines couldn’t be deleted: they’re still in Routines.')
      : r.unconfirmed ? unconfirmed : null);
    if (r.items) { setData(r); setKept(await getJson<Kept>('/kept')); } else await load();
  };
  const forget = (key: string) => run(() => sendTold<MemoryList>('DELETE', '/memory/' + encodeURIComponent(key)), t('No se pudo olvidar.', 'Couldn’t forget it.'));
  const forgetAll = () => run(() => sendTold<MemoryList>('DELETE', '/memory', { scope: 'all' }), t('No se pudo olvidar todo.', 'Couldn’t forget everything.'));
  const setOn = (enabled: boolean) => run(() => sendTold<MemoryList>('POST', '/memory/enabled', { enabled }), enabled ? t('No se pudo activar.', 'Couldn’t turn it on.') : t('No se pudo apagar.', 'Couldn’t turn it off.'));

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
  // the host's `agent_not_ready` is also its answer when BAXY broke down: «starting» is said only while nothing failed
  const why = data?.error === 'agent_not_ready' && failed ? 'memory_unavailable' : data?.error;
  return (
    <Panel title={t('Memoria · se guarda solo en este PC', 'Memory · kept only on this PC')} onClose={onClose} width={500}>
      <div className="bxs-row">
        <div className="bxs-l"><span>{t('Recordar cosas sobre ti', 'Remember things about you')}</span><span className="h">{t('Si lo apagas, BAXY no guarda nada nuevo. Lo que ya está se queda hasta que lo olvides.', 'If you turn it off, BAXY saves nothing new. What’s already there stays until you forget it.')}</span></div>
        <div className="bxs-c"><Toggle on={on} label={t('Recordar cosas sobre ti', 'Remember things about you')} locked={busy || !data || !!data.error} onChange={(v) => void setOn(v)} /></div>
      </div>
      {why ? <div className="bx-mem-empty" role="status">{t.w(ERRORS[why] ?? ERRORS.memory_unavailable)}</div> : null}
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
          : <button className="panel-btn ghost" disabled={busy || !(items.length || kept?.conversations || kept?.log || kept?.routines)} onClick={() => setAsk('all')}
            title={t('Borra los recuerdos, las rutinas, las conversaciones guardadas y el registro de lo hablado', 'Deletes the memories, the routines, the kept conversations and the record of what was said')}>{t('Olvidar todo', 'Forget everything')}</button>}
      </div>
    </Panel>
  );
}
