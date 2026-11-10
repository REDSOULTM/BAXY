import { useEffect, useMemo, useState } from 'react';
import { getJson, sendTold } from '../../api';
import { useT, type Words } from '../../i18n';
import { useDraft } from '../../drafts';
import { radioKeys, rovingIndex } from '../../utils/radioKeys';
import { Fold } from './Fold';

/* Settings › Tools (owner's decision, 2026-11-08: ready-made tool profiles and a manual choice): how many of BAXY's tools the
   model sees (ToolProfile, GET/PUT /settings/tools; each tool's first profile is its level in GET /catalog). A preset
   applies at once; Personalizado is kept with its button. A tool off is not offered to the model and is refused if it
   names it; what asks for a yes asks the same in every profile. In the frame of the other tabs (interfaz-v5, INT17): the
   profile and the tool-by-tool choice are sections that fold, each with its summary. */

type Profile = 'esencial' | 'diario' | 'avanzado' | 'completo' | 'personalizado';
interface ToolsState { profile: Profile; on: string[]; switching?: boolean }
interface CatalogItem { name: string; title: string; level: number }
interface Catalog { total: number; groups: { name: string; items: CatalogItem[] }[] }

const PRESETS: [Exclude<Profile, 'personalizado'>, number, Words, Words][] = [
  ['esencial', 1, { es: 'Esencial', en: 'Essential' }, { es: 'Lo mínimo para manejar el PC: apps, ventanas, volumen, brillo, apagar, alarmas y recordatorios, buscar en la web', en: 'The least to run the PC: apps, windows, volume, brightness, shutting down, alarms and reminders, web search' }],
  ['diario', 2, { es: 'Diario', en: 'Everyday' }, { es: 'Además ficheros, navegador, música, memoria, notas y tareas, Wi-Fi y Bluetooth', en: 'Plus files, browser, music, memory, notes and tasks, Wi-Fi and Bluetooth' }],
  ['avanzado', 3, { es: 'Avanzado', en: 'Advanced' }, { es: 'Además hace clic y lee la pantalla en cualquier app, correo, mensajes, juegos y forzar el cierre de un programa', en: 'Plus clicking and reading the screen in any app, email, messages, games and forcing a program to close' }],
  ['completo', 4, { es: 'Completo', en: 'Complete' }, { es: 'Todo, como viene de fábrica: también instalar programas, la consola y copias de seguridad', en: 'Everything, as it comes: also installing programs, the console and backups' }],
];

export function ToolsSection() {
  const t = useT();
  const [state, setState] = useState<ToolsState | null | undefined>(undefined);
  const [catalog, setCatalog] = useState<Catalog | null>(null);
  // REV_VISTA V-05: the custom selection not saved yet outlives this tab (drafts.ts)
  const [kept, keep] = useDraft<string[] | null>('tools.custom', null);
  const draft = useMemo(() => (kept ? new Set(kept) : null), [kept]);
  const setDraft = (next: Set<string> | null) => keep(next ? [...next] : null);
  const [problem, setProblem] = useState<string | null>(null);
  useEffect(() => {
    void getJson<ToolsState>('/settings/tools').then((s) => setState(s?.profile ? s : null));
    void getJson<Catalog>('/catalog').then((c) => setCatalog(c?.groups ? c : null));
  }, []);
  // While the mind is relaunched with the new profile, its state is read every second.
  const busy = !!state?.switching;
  useEffect(() => {
    if (!busy) return undefined;
    const every = setInterval(() => { void getJson<ToolsState>('/settings/tools').then((s) => { if (s?.profile) setState(s); }); }, 1000);
    return () => clearInterval(every);
  }, [busy]);

  const items = useMemo(() => catalog?.groups.flatMap((g) => g.items) ?? [], [catalog]);
  const countAt = (level: number) => items.filter((i) => i.level <= level).length;
  const custom = draft !== null || state?.profile === 'personalizado';
  const on = draft ?? new Set(state?.on ?? []);

  const put = async (body: Record<string, unknown>) => {
    setProblem(null);
    const { value, refused } = await sendTold<ToolsState>('PUT', '/settings/tools', body);
    if (value?.profile) { setState(value); setDraft(null); return; }
    setProblem(refused ? t('No se guardó ese perfil', 'That profile wasn’t kept') : t('BAXY no respondió: inténtalo otra vez', 'BAXY didn’t answer: try again'));
  };
  const flip = (names: string[], wanted: boolean) => {
    const next = new Set(on);
    for (const n of names) { if (wanted) next.add(n); else next.delete(n); }
    setDraft(next);
  };
  // What a combination lets through anyway, said where it is chosen (study of 2026-11-08: a tool off can be done by another on).
  const warn = custom && on.has('shell.command.run') && !on.has('package.install')
    ? t('Con la consola encendida, BAXY puede instalar programas aunque «instalar» esté apagado.', 'With the console on, BAXY can install programs even with «install» off.')
    : custom && on.has('input.visible.click') && !on.has('input.visible.controls')
      ? t('Para hacer clic, BAXY mira antes los controles de la ventana: sin «ver los controles» los clics fallarán más.', 'To click, BAXY first looks at the window’s controls: without «see the controls» clicks will fail more.')
      : null;

  if (state === undefined) return null;
  // What the folded profile says: its name and how many tools the model sees with it.
  const preset = PRESETS.find(([id]) => id === state?.profile);
  const count = custom ? on.size : catalog && preset ? countAt(preset[1]) : null;
  const summary = (custom ? t('Personalizado', 'Custom') : preset ? t.w(preset[2]) : '—') + (count === null ? '' : ' · ' + t(`${count} herramientas`, `${count} tools`));
  if (state === null) return <div className="st-tip">{t('No se pudo leer este ajuste', 'This setting couldn’t be read')}</div>;
  return (
    <>
      <Fold id="herr-perfil" open title={t('Perfil', 'Profile')} summary={summary}>
      <div className="bxs-row"><div className="bxs-l"><span>{t('Herramientas que usa BAXY', 'Tools BAXY uses')}</span><span className="h">{t('Con menos herramientas el modelo lee un texto más corto y le queda más sitio para la conversación. Lo que apagues, BAXY lo dice en vez de intentarlo.', 'With fewer tools the model reads a shorter text and has more room for the conversation. What you turn off, BAXY says instead of trying it.')}</span></div></div>
      <div role="radiogroup" aria-label={t('Perfil de herramientas', 'Tool profile')} onKeyDown={radioKeys(false)} style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(150px, 1fr))', gap: 8, margin: '4px 0 12px' }}>
        {PRESETS.map(([id, level, name, line], i) => {
          const chosen = !custom && state.profile === id;
          return (
            <button key={id} role="radio" aria-checked={chosen} tabIndex={rovingIndex(i, custom ? PRESETS.length : PRESETS.findIndex(([x]) => x === state.profile))} className={'bxs-card' + (chosen ? ' on' : '')} disabled={busy}
              onClick={() => { if (!chosen) void put({ profile: id }); }}
              style={{ textAlign: 'left', padding: 10, minHeight: 96, display: 'flex', flexDirection: 'column', gap: 4 }}>
              <b>{t.w(name)}{id === 'completo' ? <em className="ro">{t('de fábrica', 'factory')}</em> : null}</b>
              <span className="h">{catalog ? t(`${countAt(level)} herramientas`, `${countAt(level)} tools`) : ''}</span>
              <span className="h">{t.w(line)}</span>
            </button>
          );
        })}
        <button role="radio" aria-checked={custom} tabIndex={custom ? 0 : -1} className={'bxs-card' + (custom ? ' on' : '')} disabled={busy || !catalog}
          onClick={() => { if (!custom) setDraft(new Set(state.on)); }}
          style={{ textAlign: 'left', padding: 10, minHeight: 96, display: 'flex', flexDirection: 'column', gap: 4 }}>
          <b>{t('Personalizado', 'Custom')}</b>
          <span className="h">{custom ? t(`${on.size} herramientas`, `${on.size} tools`) : t('tú eliges', 'you choose')}</span>
          <span className="h">{t('Enciende o apaga cada herramienta', 'Turn each tool on or off')}</span>
        </button>
      </div>
      {busy ? <div className="st-tip" role="status">{t('Cambiando de perfil: BAXY vuelve al acabar el turno en curso.', 'Changing profile: BAXY is back once the current turn ends.')}</div> : null}
      {problem ? <div className="st-tip" role="alert">{problem}</div> : null}
      </Fold>
      {custom && catalog ? (
        <Fold id="herr-una" open title={t('Una a una', 'One by one')} summary={t(`${on.size} encendidas`, `${on.size} on`)}>
          {catalog.groups.map((g) => {
            const free = g.items.filter((i) => i.level > 0);
            const allOn = free.every((i) => on.has(i.name));
            return (
              <fieldset key={g.name} className="bxs-tools" style={{ border: 0, padding: 0, margin: '0 0 10px' }}>
                <legend className="panel-sec-head" style={{ display: 'flex', gap: 8, alignItems: 'center', width: '100%' }}>
                  <span style={{ flex: 1 }}>{g.name}</span>
                  {free.length ? <button className="bx-ib plain" disabled={busy} onClick={() => flip(free.map((i) => i.name), !allOn)}>{allOn ? t('Apagar todas', 'Turn all off') : t('Encender todas', 'Turn all on')}</button> : null}
                </legend>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))', gap: '2px 12px' }}>
                  {g.items.map((i) => (
                    <label key={i.name} style={{ display: 'flex', gap: 8, alignItems: 'center', minHeight: 28 }}>
                      <input type="checkbox" checked={i.level === 0 || on.has(i.name)} disabled={busy || i.level === 0} onChange={(e) => flip([i.name], e.target.checked)} />
                      <span>{i.title}{i.level === 0 ? <em className="ro">{t('siempre', 'always')}</em> : null}</span>
                    </label>
                  ))}
                </div>
              </fieldset>
            );
          })}
          {warn ? <div className="st-tip" role="alert">{warn}</div> : null}
          <div style={{ display: 'flex', gap: 8, margin: '6px 0 12px' }}>
            <button className="bx-btn yes" disabled={busy || draft === null} onClick={() => void put({ profile: 'personalizado', on: [...on].filter((n) => items.some((i) => i.name === n && i.level > 0)) })}>{t('Guardar mi selección', 'Keep my selection')}</button>
            {draft !== null ? <button className="bx-btn" disabled={busy} onClick={() => setDraft(null)}>{t('Descartar', 'Discard')}</button> : null}
          </div>
        </Fold>
      ) : null}
      <div className="st-tip">{t('«Confirmación» no cambia: en modo Normal lo arriesgado pide el sí en todos los perfiles. Un perfil sólo quita herramientas. Al cambiarlo, BAXY se reinicia al terminar lo que hace; la primera vez con cada perfil tarda unos segundos más en leer sus herramientas. Un contexto menor de 53.248 elegido en Modelo vuelve a Automático, para que quepan las herramientas del perfil nuevo.','«Confirmation» doesn’t change: in Normal mode risky things ask for a yes in every profile. A profile only takes tools away. When you change it, BAXY restarts once it finishes what it’s doing; the first time with each profile it takes a few seconds more to read its tools. A context under 53,248 chosen in Model goes back to Automatic, so the new profile’s tools fit.')}</div>
    </>
  );
}
