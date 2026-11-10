import { useEffect, useState, type ReactNode } from 'react';
import { Toggle } from '../Panel';
import { getJson, send } from '../../api';
import { useT } from '../../i18n';
import { GIB } from '../../size';
import { UPDATE_FAILED } from '../../updateErrors';

/* Settings › General › Versión (actualizar-ordenes-app, owner 2026-11-09: «un botón de actualizar»). The host answers with
   the chat's own baxy.update (GET /update checks, POST /update/install is the person's yes). GitHub: BAXY downloads its
   installer, checks it with the SHA-256 GitHub published and closes while it is replaced; Steam and itch.io update BAXY
   themselves, so the button only opens their page. Nothing updates without «Actualizar».
   APP1 (UPD-f, review of the App 2026-11-09): the install is a long operation the host keeps the state of, as a model's
   download is (the installer's ~80 MB outlive the 30 s the bridge gives a request, and the view said «No pude buscar ahora»
   while the host went on and BAXY closed). POST /update/install starts it, or joins the one running, and answers at once;
   GET /update/install says what it is doing («installing», its phase and bytes) or how the last one ended, and the view
   reads it each second while it runs. A request with no answer is never told as a failed check: the state is read. */

interface Found {
  ok: boolean;
  error?: string;
  channel?: 'github' | 'steam' | 'itch' | 'development';
  installed?: string;
  latest?: string | null;
  newer?: boolean;
  downloadBytes?: number | null;
  /** false when the installer started and the App was not there to be asked to exit. */
  appExitRequested?: boolean;
  /** the install runs (the host's state): no end is said, and no button asks for another. */
  installing?: boolean;
  phase?: 'downloading' | 'checking';
  /** bytes of the installer on disk; null when the host could not read them. */
  downloadedBytes?: number | null;
}

// In the view's one unit (size.ts): 2²⁰ bytes to the MB, as Windows writes them.
const MIB = GIB / 1024;

function Row({ label, hint, children }: { label: string; hint?: string; children?: ReactNode }) {
  return (
    <div className="bxs-row">
      <div className="bxs-l"><span>{label}</span>{hint ? <span className="h">{hint}</span> : null}</div>
      <div className="bxs-c">{children}</div>
    </div>
  );
}

export function UpdateSection({ notice, onNotice, locked }: { notice: boolean; onNotice: (v: boolean) => void; locked?: boolean }) {
  const t = useT();
  const [found, setFound] = useState<Found | null>(null);
  const [busy, setBusy] = useState<'check' | 'install' | null>(null);
  const [last, setLast] = useState<'check' | 'install' | null>(null);
  // The install while it runs, as the host says it. It goes on with this panel closed: opening it reads the state.
  const [running, setRunning] = useState<Found | null>(null);
  const installing = running !== null;
  useEffect(() => {
    let alive = true;
    void getJson<Found>('/update/install').then((r) => { if (alive && r?.installing) setRunning(r); });
    return () => { alive = false; };
  }, []);
  useEffect(() => {
    if (!installing) return;
    let alive = true;
    const every = setInterval(() => {
      void getJson<Found>('/update/install').then((r) => {
        // no answer is no end: the next read asks again
        if (!alive || r === null) return;
        if (r.installing) setRunning(r);
        else { setRunning(null); setFound(r); setLast('install'); }
      });
    }, 1000);
    return () => { alive = false; clearInterval(every); };
  }, [installing]);
  const check = async () => {
    setBusy('check');
    setFound(await getJson<Found>('/update') ?? { ok: false, error: 'unreachable' });
    setLast('check');
    setBusy(null);
  };
  const install = async () => {
    setBusy('install');
    // The host may have taken a request that got no answer (the bridge's 503): what it is doing is read, not guessed.
    const told = await send<Found>('POST', '/update/install') ?? await getJson<Found>('/update/install');
    if (told?.installing) setRunning(told);
    else setFound(told && 'ok' in told ? told : { ok: false, error: 'install_unanswered' });
    setLast('install');
    setBusy(null);
  };
  const store = found?.channel === 'steam' ? 'Steam' : found?.channel === 'itch' ? 'itch.io' : null;
  const mb = found?.downloadBytes ? Math.round(found.downloadBytes / MIB) : null;
  const what = running?.latest ? `BAXY ${running.latest}` : 'BAXY';
  const said = (): string => {
    if (running) {
      if (running.phase === 'checking') return t(`Comprobando el instalador de ${what}…`, `Checking the ${what} installer…`);
      const total = running.downloadBytes ?? 0;
      const here = running.downloadedBytes;
      if (total <= 0 || here == null) return t(`Bajando el instalador de ${what}…`, `Downloading the ${what} installer…`);
      // Never 100 % before it ends: the last bytes still have to arrive and be checked (as DownloadBar).
      const percent = Math.min(Math.floor((here / total) * 100), 99);
      return t(`Bajando el instalador de ${what}: ${percent} % (${Math.round(here / MIB)} de ${Math.round(total / MIB)} MB)`,
        `Downloading the ${what} installer: ${percent} % (${Math.round(here / MIB)} of ${Math.round(total / MIB)} MB)`);
    }
    if (busy === 'check') return t('Buscando…', 'Checking…');
    if (busy === 'install') return store ? t(`Abriendo ${store}…`, `Opening ${store}…`) : t('Empezando la actualización…', 'Starting the update…');
    if (!found) return '';
    if (found.error && UPDATE_FAILED[found.error]) return t.w(UPDATE_FAILED[found.error]); // REV_VISTA V-09: updateErrors.ts
    // LEG1 §5: the itch.io agreement's own words (documentacion/itchio/LEGAL.md §5): only its app updates it (here, apart from
    // Versión's own lines, which APP1 changes: the merge stays clean)
    if (found.channel === 'itch' && !found.error && last !== 'install') return t('BAXY instalado con la app de itch.io lo actualiza esa app. Si lo bajaste de la página de itch.io sin su app, nada lo actualiza solo: tampoco pregunta a GitHub, y la versión nueva se baja de esa misma página.',
      'BAXY installed with the itch app is updated by that app. If you downloaded it from the itch.io page without its app, nothing updates it by itself: it does not ask GitHub either, and you download the new version from that same page.');
    switch (found.error) {
      case undefined: break;
      case 'baxy_update_development_build': return t('Esta copia es de desarrollo: se actualiza con git', 'This is a development copy: it updates with git');
      case 'baxy_update_already_latest': return t(`Ya tienes la última versión (${found.installed})`, `You have the latest version (${found.installed})`);
      case 'baxy_update_unreachable': return t('No pude buscar ahora', 'I couldn’t check now');
      // The view's own: the host answered nothing in the time a request has. It is not a check that failed.
      case 'unreachable': return t('BAXY no contestó a tiempo', 'BAXY didn’t answer in time');
      case 'install_unanswered': return t('BAXY no contestó: no sé si la actualización empezó', 'BAXY didn’t answer: I don’t know whether the update started');
      case 'engine_not_ready': return t('El motor de BAXY todavía no está listo', 'BAXY’s engine isn’t ready yet');
      case 'baxy_update_hash_mismatch': return t('El instalador bajado no era el publicado: lo borré y no lo abrí', 'The downloaded installer wasn’t the published one: I deleted it and didn’t open it');
      case 'baxy_update_download_failed': return t('La descarga del instalador se cortó; BAXY sigue como estaba', 'The installer’s download was cut off; BAXY stays as it was');
      case 'baxy_update_installer_not_started': return t('Bajé el instalador y Windows no lo abrió; BAXY sigue como estaba', 'I downloaded the installer and Windows didn’t open it; BAXY stays as it was');
      case 'baxy_update_installer_missing': return t('Esa versión no trae instalador', 'That version has no installer');
      case 'update_outcome_unknown': return t('El motor de BAXY dejó de contestar: no sé si el instalador llegó a abrirse', 'BAXY’s engine stopped answering: I don’t know whether the installer opened');
      default: return t(`No pude: ${found.error}`, `I couldn’t: ${found.error}`);
    }
    if (last === 'install') return store
      ? t(`Abrí ${store}: ahí se ve si hay una versión nueva`, `I opened ${store}: it shows there whether a new version is out`)
      // The engine asks the App to exit as «Salir» does; when the App did not hear it, the installer waits for the person.
      : found.appExitRequested === false
        ? t('El instalador ya está abierto: cierra BAXY para que la reemplace; tus datos se quedan', 'The installer is open: close BAXY so it replaces it; your data stays')
        : t('BAXY se cierra y el instalador la reemplaza; tus datos se quedan', 'BAXY closes and the installer replaces it; your data stays');
    if (store) return t(`${store} mantiene BAXY al día y la actualiza solo`, `${store} keeps BAXY up to date by itself`);
    if (found.newer) return t(`Hay una versión nueva: ${found.latest}${mb ? ` (instalador de ${mb} MB)` : ''}`, `A new version is out: ${found.latest}${mb ? ` (${mb} MB installer)` : ''}`);
    return t(`Ya tienes la última versión (${found.installed})`, `You have the latest version (${found.installed})`);
  };
  return (
    <>
      <Row label={t('Versión', 'Version')} hint={said() || (found?.installed ?? undefined)}>
        {running
          ? <button className="panel-btn" disabled>{running.latest ? t(`Actualizando a ${running.latest}…`, `Updating to ${running.latest}…`) : t('Actualizando…', 'Updating…')}</button>
          : found?.newer && found.channel === 'github'
          ? <button className="panel-btn" disabled={busy !== null} onClick={() => void install()}>{t(`Actualizar a ${found.latest}`, `Update to ${found.latest}`)}</button>
          : store
            ? <button className="panel-btn ghost" disabled={busy !== null} onClick={() => void install()}>{t(`Abrir en ${store}`, `Open in ${store}`)}</button>
            : <button className="panel-btn ghost" disabled={busy !== null} onClick={() => void check()}>{t('Buscar actualizaciones', 'Check for updates')}</button>}
      </Row>
      <Row label={t('Avisar de versiones nuevas', 'Tell me about new versions')} hint={t('Mira una vez al arrancar dónde se publicó BAXY. Buscar una versión nueva no manda nada de lo que dices ni de tus archivos: sólo la versión de BAXY, desde tu IP', 'Looks once at start where BAXY was published. Looking for a new version sends nothing you say and none of your files: only BAXY’s version, from your IP')}>
        <Toggle on={notice} label={t('Avisar de versiones nuevas', 'Tell me about new versions')} locked={locked} onChange={onNotice} />
      </Row>
    </>
  );
}
