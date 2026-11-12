import { useEffect, useRef, useState } from 'react';
import { ConfirmRow, Panel, Toggle } from '../Panel';
import { getJson, sendTold } from '../../api';
import { useT } from '../../i18n';
import { blocked, read, what, when, type Routine, type Shown } from '../../routines';

/* Routines (RUT3; RUT1's contract, documentacion/RUTINAS.md): what the person made by talking — a word of their own that
   runs some of BAXY's actions, or a time when BAXY says something once. Here they are seen, switched on or off and deleted
   without talking; creating and changing them is said to BAXY. What a row shows is what the App confirmed (GET /routines,
   and the routine each PUT or DELETE answers with), never what was pressed. A step is named with the title the history's
   cards use (GET /catalog), and a step whose tool is off in the tool profile (GET /settings/tools «on») or that BAXY no
   longer has is marked with why the routine will not run.
   RUT7 (RUTINAS.md §5 d): a new one is made with BAXY's guided path, which asks one thing at a time; «Nueva rutina» says
   its fixed order to BAXY as a written request (`onNew`), and the questions are answered where BAXY talks. */

export function RoutinesPanel({ onClose, onNew }: { onClose: () => void; onNew: () => void }) {
  const t = useT();
  const [shown, setShown] = useState<Shown | null | undefined>(undefined);
  const [ask, setAsk] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [note, setNote] = useState<string | null>(null);
  // after a row is deleted, the keyboard goes to the switch now at its place (or the one before it), never to nowhere
  const focusAt = useRef<number | null>(null);
  const listRef = useRef<HTMLDivElement>(null);
  useEffect(() => { void read().then(setShown); }, []);
  useEffect(() => {
    if (focusAt.current === null) return;
    const switches = listRef.current?.querySelectorAll<HTMLElement>('[role="switch"]');
    (switches?.[Math.min(focusAt.current, switches.length - 1)] ?? listRef.current?.closest('.panel')?.querySelector<HTMLElement>('.panel-head button'))?.focus();
    focusAt.current = null;
  }, [shown]);

  const again = (said: string | null) => {
    setNote(said);
    void read().then((s) => { if (s) setShown(s); });
  };
  // what the App confirmed: the routine as it was saved, or the one deleted; the rail's counter is the App's, read again
  const confirmed = (list: Routine[]) => {
    setNote(null);
    setShown((s) => (s ? { ...s, list } : s));
    void getJson('/surfaces');
  };

  const toggle = async (x: Routine) => {
    if (busy) return;
    setBusy(x.id);
    const r = await sendTold<Routine>('PUT', '/routines/' + encodeURIComponent(x.id), { action: x.active ? 'disable' : 'enable' });
    setBusy(null);
    if (r.value) {
      const got = r.value;
      if (got.id === x.id && typeof got.active === 'boolean') confirmed((shown?.list ?? []).map((y) => (y.id === x.id ? got : y)));
      else again(null);
      return;
    }
    if (!r.refused) { again(t('BAXY no contestó: no sé si cambió. Esta es la lista de ahora.', 'BAXY didn’t answer: I don’t know whether it changed. This is the list as it is now.')); return; }
    if (r.code === 'not_found') { again(t('Esa rutina ya no estaba guardada.', 'That routine was no longer saved.')); return; }
    setNote(r.code === 'duplicate_phrase' ? t('Otra rutina activa ya usa esa frase: desactívala antes de activar esta.', 'Another active routine already uses that phrase: switch it off before switching this one on.')
      : r.code === 'tool_off_in_profile' ? t('Un paso usa una acción apagada en tu perfil de herramientas: enciéndela en Ajustes › Herramientas para activar esta rutina.', 'A step uses an action that is off in your tool profile: turn it on in Settings › Tools to switch this routine on.')
        : t('No se pudo cambiar: sigue como estaba.', 'Couldn’t change it: it is as it was.'));
  };

  const remove = async (x: Routine, i: number) => {
    setAsk(null);
    const r = await sendTold('DELETE', '/routines/' + encodeURIComponent(x.id));
    if (r.value) {
      focusAt.current = i;
      confirmed((shown?.list ?? []).filter((y) => y.id !== x.id));
      return;
    }
    if (!r.refused) { again(t('BAXY no contestó: no sé si se borró. Esta es la lista de ahora.', 'BAXY didn’t answer: I don’t know whether it was deleted. This is the list as it is now.')); return; }
    if (r.code === 'not_found') { again(t('Esa rutina ya no estaba guardada.', 'That routine was no longer saved.')); return; }
    setNote(t('No se pudo borrar: sigue guardada.', 'Couldn’t delete it: it is still saved.'));
  };

  return (
    <Panel title={t('Rutinas · las que creaste hablando con BAXY', 'Routines · the ones you made by talking to BAXY')} onClose={onClose} width={520}>
      {shown === undefined ? <div className="bx-mem-empty" role="status">{t('Leyendo tus rutinas…', 'Reading your routines…')}</div> : null}
      {shown === null ? <div className="bx-mem-empty" role="status">{t('No se pudieron leer las rutinas.', 'Couldn’t read the routines.')}</div> : null}
      {note ? <div className="bx-mem-empty" role="status">{note}</div> : null}
      <div className="bx-rut-new">
        <button className="bx-btn" onClick={onNew}>{t('Nueva rutina', 'New routine')}</button>
        <span>{t('BAXY te pregunta paso a paso; contestas hablando o escribiendo.', 'BAXY asks you step by step; you answer by speaking or typing.')}</span>
      </div>
      <div className="bx-mem" role="list" ref={listRef} aria-label={t('Tus rutinas', 'Your routines')}>
        {shown?.list.map((x, i) => {
          const why = blocked(t, x.steps, shown);
          return (
            <div key={x.id} role="listitem" className={'bx-trig bx-rut' + (x.active ? '' : ' off') + (why ? ' warn' : '')}>
              <div className="b">
                <span className="w">{x.name}{x.active ? null : <span className="tag">{t(' · inactiva', ' · off')}</span>}</span>
                <span className="d">{when(t, x.trigger)}</span>
                <span className="d">{what(t, x.steps, shown.titles, x.order)}</span>
                {why ? <span className="why">{why}</span> : null}
              </div>
              <div className="c">
                {ask === x.id ? <ConfirmRow label={t('¿Borrar «', 'Delete “') + x.name + t('»?', '”?')} yes={t('Sí, borrar', 'Yes, delete')} onYes={() => void remove(x, i)} onNo={() => setAsk(null)} />
                  : <>
                    <Toggle on={x.active} label={t('Rutina «', 'Routine “') + x.name + t('» activa', '” on')} onChange={() => void toggle(x)} />
                    <button className="bx-lnk" aria-label={t('Borrar la rutina «', 'Delete the routine “') + x.name + t('»', '”')} onClick={() => setAsk(x.id)}>{t('Borrar', 'Delete')}</button>
                  </>}
              </div>
            </div>
          );
        })}
        {shown && !shown.list.length ? (
          <div className="bx-mem-empty bx-rut-empty">
            <span>{t('Aún no tienes rutinas. Créalas hablando con BAXY: dile «crea una rutina», o de una vez, por ejemplo:', 'You have no routines yet. Make them by talking to BAXY: say “create a routine”, or all at once, for example:')}</span>
            <span className="ex">{t('“Cuando te diga audífonos, cambia el sonido a los audífonos.”', '“When I say headphones, switch the sound to the headphones.”')}</span>
            <span className="ex">{t('“Todos los días a las 10, dime buen día.”', '“Every day at 10, say good morning to me.”')}</span>
          </div>
        ) : null}
      </div>
    </Panel>
  );
}
