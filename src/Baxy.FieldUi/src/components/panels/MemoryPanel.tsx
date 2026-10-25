import { useCallback, useEffect, useState } from 'react';
import { ConfirmRow, Panel, Toggle } from '../Panel';
import { getJson, send } from '../../api';

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
const GROUPS: [Exclude<Group, 'sens'>, string][] = [
  ['pref', 'Preferencias'], ['rule', 'Reglas y costumbres'], ['fact', 'Sobre ti'], ['recent', 'Conversación reciente'],
];

function groupOf(m: MemoryItem): Group {
  if (m.sensitivity === 'sensitive' || m.sensitivity === 'secret') return 'sens';
  if (m.retention === 'session' || m.retention === 'temporary') return 'recent';
  if (m.kind === 'preference') return 'pref';
  if (m.kind === 'rule') return 'rule';
  return 'fact';
}

const ERRORS: Record<string, string> = {
  agent_not_ready: 'BAXY aún está arrancando.',
  memory_unavailable: 'No se pudo leer la memoria.',
  memory_not_found: 'Ese recuerdo ya no está.',
};

export function MemoryPanel({ onClose, revision }: { onClose: () => void; revision: number }) {
  const [data, setData] = useState<MemoryList | null>(null);
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
    setNote(r.unconfirmed ? 'No se pudo confirmar el cambio: esto es lo que hay ahora.' : null);
    if (r.items) setData(r); else await load();
  };
  const forget = (key: string) => run(() => send<MemoryList>('DELETE', '/memory/' + encodeURIComponent(key)), 'No se pudo olvidar.');
  const forgetAll = () => run(() => send<MemoryList>('DELETE', '/memory', { scope: 'all' }), 'No se pudo olvidar todo.');
  const setOn = (enabled: boolean) => run(() => send<MemoryList>('POST', '/memory/enabled', { enabled }), enabled ? 'No se pudo activar.' : 'No se pudo apagar.');

  const items = data?.items ?? [];
  const on = data?.enabled !== false;
  const row = (m: MemoryItem) => {
    const sens = groupOf(m) === 'sens';
    return (
      <div key={m.key} className="bx-mem-row">
        <span className="t">{sens ? <><b>{m.label ?? m.key}</b> · ••••••</> : m.label ? <><b>{m.label}</b> · {m.value}</> : m.value}</span>
        {ask === m.key ? <ConfirmRow label="¿Olvidar?" yes="Sí, olvidar" onYes={() => void forget(m.key)} onNo={() => setAsk(null)} /> : (
          <span className="acts"><button className="bx-lnk" disabled={busy} onClick={() => setAsk(m.key)}>Olvidar</button></span>
        )}
      </div>
    );
  };
  const total = data?.total ?? items.length;
  return (
    <Panel title="Memoria · se guarda solo en este PC" onClose={onClose} width={500}>
      <div className="bxs-row">
        <div className="bxs-l"><span>Recordar cosas sobre ti</span><span className="h">Si lo apagas, BAXY no guarda nada nuevo. Lo que ya está se queda hasta que lo olvides.</span></div>
        <div className="bxs-c"><Toggle on={on} label="Recordar cosas sobre ti" locked={busy || !data || !!data.error} onChange={(v) => void setOn(v)} /></div>
      </div>
      {data?.error ? <div className="bx-mem-empty">{ERRORS[data.error] ?? 'No se pudo leer la memoria.'}</div> : null}
      {note ? <div className="bx-mem-empty">{note}</div> : null}
      {data && !data.error ? (
        <div className={'bx-mem' + (on ? '' : ' off')}>
          {!on ? <div className="bx-mem-empty">La memoria está apagada: BAXY no lee ni guarda recuerdos.</div> : null}
          {GROUPS.map(([g, l]) => {
            const list = items.filter((m) => groupOf(m) === g);
            return list.length ? <div key={g} className="bx-mem-g"><div className="panel-sec-head">{l}</div>{list.map(row)}</div> : null;
          })}
          {on ? (
            <div className="bx-mem-g sens">
              <div className="panel-sec-head">Datos sensibles <span className="lock">siempre ocultos · no salen del almacén cifrado</span></div>
              {items.filter((m) => groupOf(m) === 'sens').map(row)}
              {!items.some((m) => groupOf(m) === 'sens') ? <div className="bx-mem-empty">Nada guardado.</div> : null}
            </div>
          ) : null}
          {on && !items.length ? <div className="bx-mem-empty">BAXY no recuerda nada.</div> : null}
        </div>
      ) : null}
      <div className="panel-footer">
        <span>{data && !data.error && on ? total + (total === 1 ? ' recuerdo' : ' recuerdos') : '—'}</span>
        {ask === 'all' ? <ConfirmRow label="¿Olvidar todo?" yes="Sí, olvidar" onYes={() => void forgetAll()} onNo={() => setAsk(null)} />
          : <button className="panel-btn ghost" disabled={busy || !items.length} onClick={() => setAsk('all')}>Olvidar todo</button>}
      </div>
    </Panel>
  );
}
