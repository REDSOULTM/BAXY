import { useCallback, useEffect, useRef, useState, type ReactNode } from 'react';
import { Icon, Globe } from '../Icon';
import { Pick, Seg, Toggle } from '../Panel';
import { getJson, send, sendTold } from '../../api';
import { spoken } from '../../duration';
import { useDialogFocus, useInnerDialog } from '../../utils/dialogFocus';
import { radioKeys, rovingIndex, tabKeys } from '../../utils/radioKeys';
import { cardShortText, PROFILE_NAME, TUNED_PROBLEM, type FailureCard } from '../../causes';
import { useT, type LangChoice, type Words } from '../../i18n';
import { translatorSaid } from '../../externalErrors';
import { draftTab, forgetDraft, savesOnBlur, useDraft, useDraftKeys } from '../../drafts';
import { ProposalsSection } from './ProposalsSection';
import { MemoryBreakdown } from './MemoryBreakdown';
import { Fold } from './Fold';
import { OverlaySection } from './OverlaySection';
import { ToolsSection } from './ToolsSection';
import { DownloadBar } from './DownloadBar';
import { GIB, size } from '../../size';
import { UpdateSection } from './UpdateSection';
import { Marked } from '../../markdown';
import { LOOK_DEFAULT, type Look } from '../../look';
import type { GeneralSettings, Metrics, MicMode, NetEntry, ProposalSettings } from '../../types';
import { num } from '../../numbers';

/* Settings (design settings.jsx BxSettings). The theme, text size and contrast are this view's own presentation; the
   rest is the host's (GET/PUT /settings/general, /confirmation, /accessibility) and changes what BAXY does. */

/* interfaz v5 (V5.md §6): the sections in a list at the side with a search, so they never overflow a row of tabs; each
   carries the words its settings are found by. */
const TABS: [Tab, Words, Words][] = [
  ['general', { es: 'General', en: 'General' }, { es: 'tema claro oscuro idioma inglés español arrancar windows bandeja cerrar minimizar versión actualizar actualizaciones', en: 'theme light dark language spanish english start windows tray close version update updates' }],
  ['personalizacion', { es: 'Personalización', en: 'Personalization' }, { es: 'tamaño texto letra respuestas mensajes chat conversación ancho pasos subtítulos medidores borde luz rgb color overlay esquina', en: 'size text font replies messages chat conversation width steps captions readings' }],
  ['modelo', { es: 'Modelo', en: 'Model' }, { es: 'modelo api clave ollama hugging face buscar descargar memoria vídeo ram ajustado contexto', en: 'model api key ollama hugging face search download memory video ram tuned context' }],
  ['herramientas', { es: 'Herramientas', en: 'Tools' }, { es: 'herramientas perfil esencial diario avanzado completo personalizado activar desactivar', en: 'tools profile essential everyday advanced complete custom turn on off' }],
  ['comportamiento', { es: 'Comportamiento', en: 'Behavior' }, { es: 'prompts personalidad carácter instrucciones propuestas interrumpir silenciar', en: 'prompts personality character instructions proposals interrupt mute' }],
  ['confirmacion', { es: 'Confirmación', en: 'Confirmation' }, { es: 'confirmar preguntar sin frenos bypass normal riesgo', en: 'confirm ask no brakes bypass normal risk' }],
  ['voz', { es: 'Voz', en: 'Voice' }, { es: 'micrófono palabra activación escuchar hablar silenciar sonido', en: 'microphone wake word listen speak mute sound' }],
  ['accesibilidad', { es: 'Accesibilidad', en: 'Accessibility' }, { es: 'texto grande contraste modo accesible', en: 'text large contrast accessible mode' }],
  ['privacidad', { es: 'Privacidad', en: 'Privacy' }, { es: 'internet web clima pantalla memoria salidas registro', en: 'internet web weather screen memory log' }],
  ['extras', { es: 'Extras no oficiales', en: 'Unofficial extras' }, { es: 'modelo ajustado no oficial', en: 'tuned model unofficial' }],
];
type Tab = 'general' | 'personalizacion' | 'herramientas' | 'comportamiento' | 'confirmacion' | 'voz' | 'accesibilidad' | 'privacidad' | 'modelo' | 'extras';
export type SettingsTab = Tab;

export interface A11y { on: boolean; size: 'm' | 'l' | 'xl'; contrast: boolean }

function Row({ label, hint, children, ro }: { label: string; hint?: string; children?: ReactNode; ro?: boolean }) {
  const t = useT();
  return (
    <div className="bxs-row">
      <div className="bxs-l"><span>{label}{ro ? <em className="ro">{t('solo lectura', 'read-only')}</em> : null}</span>{hint ? <span className="h">{hint}</span> : null}</div>
      <div className="bxs-c">{children}</div>
    </div>
  );
}

/** a memory reading in GB with one decimal in the language's own format, or «—» when it could not be read */
function gbOf(v: number | null | undefined, locale: string): string {
  return typeof v === 'number' && Number.isFinite(v) ? num(v, locale, 1) + ' GB' : '—';
}


/* A model behind a company's API, with the person's own key, or another model on this PC behind a local server (ExternalModel
   in the App), off until the person turns it on.
   With BAXY_API_EXTERNA=0 the host does not answer this route and this section does not exist. */
interface ExternalModel {
  provider: string;
  providers: { id: string; label: string; hasKey: boolean; model: string }[];
  model: string;
  url: string;
  enabled: boolean;
  hasKey: boolean;
  active: boolean;
  activeModel: string | null;
  activeLocal: boolean;
  /** the context the model in use connected with (the person's, or the one recommended for the card) */
  activeContext?: number | null;
  apiThisRun: boolean;
  switching: boolean;
  problem: string | null;
  lastError: string | null;
  spentUsd: number;
  ceilingUsd: number | null;
  ceilingHolds: boolean;
  context: number | null;
  /* problem «no_cabe_vram»: the model was not loaded because its estimate at this context is over the free VRAM */
  vramShort?: { context: number; needBytes: number; freeBytes: number; fittingContext: number | null; partialPossible: boolean } | null;
  open?: OpenState;
  /* whether the model in use takes images: false is known, null is not known (ExternalModel.Sees) */
  sees?: boolean | null;
  /* VIVO2 F15: «model» was asked with the tool profile «profile» and did not connect, and the App put back the one the person
     had («back»; null when it was none of the named ones) */
  profileBack?: { model: string; profile: string; back: string | null } | null;
  /* what the chosen tool profile's prompt takes (ExternalModel.NeededNow less a turn's room) */
  promptTokens?: number;
}

/* Ollama's own install and a model's download from Settings (OpenModels in the App). */
interface OpenState {
  ollamaVersion: string;
  ollamaBytes: number;
  ollamaOwn: boolean;
  ollamaRunning: string | null;
  ollamaInstalling: boolean;
  ollamaDownloadedBytes: number;
  ollamaBytesPerSecond?: number | null;
  ollamaSecondsLeft?: number | null;
  ollamaProblem: string | null;
  pulling: string | null;
  pullTotal: number;
  pullDone: number;
  pullBytesPerSecond?: number | null;
  pullSecondsLeft?: number | null;
  /** the last download that stopped before it ended: asked again, it goes on from there */
  pullStopped?: string | null;
  pullProblem: string | null;
}

/* What Hugging Face has under the words the person wrote (POST /settings/external-model/search), each with the VRAM it
   takes with BAXY's default context (ModelMemory in the App, from its file's header) against what is free on the card. */
interface Found {
  repo: string;
  file: string;
  quant: string;
  /* the model alone (POST /settings/external-model/install), and with its vision (the pull of visionName), if it has one */
  name: string;
  visionName: string | null;
  sha256: string;
  bytes: number;
  projectorBytes: number;
  /* what its vision adds on the card, if the person adds it (ModelMemory.ProjectorGpuBytes) */
  projectorVramBytes?: number;
  license: string | null;
  context: number;
  tools: boolean;
  vramBytes?: number | null;
  vramContext?: number;
  /* its context by the estimate (ModelMemory): what its file declares, what this card takes with its vision, and why */
  contexts?: { native: number; recommended: number | null; why: 'nativo' | 'tarjeta' | 'minimo_baxy' | 'no_cabe' | null };
  /* no_cabe_ram: it fits the card, but not what Windows can promise to connect it (ramBytes against the answer's ramFreeBytes) */
  fit: 'cabe' | 'no_cabe' | 'no_cabe_ram' | 'desconocido';
  ramBytes?: number;
  why: 'sin_herramientas' | 'poco_contexto' | null;
  /* VIVO2 F13: the tool profile with the most tools whose prompt fits what this model declares, when the chosen one does not:
     it is installed and used with it (the App changes the profile once the model is here). */
  profile?: string | null;
}

const OPEN_PROBLEM: Record<string, Words> = {
  sin_red: { es: 'No logré conectarme para bajarlo. Revisa tu conexión y vuelve a intentarlo: lo ya bajado no se pierde', en: 'I couldn’t connect to download it. Check your connection and try again: what was downloaded isn’t lost' },
  sin_espacio: { es: 'Falta espacio en el disco', en: 'There isn’t enough disk space' },
  danado: { es: 'Llegó dañado y no lo voy a usar. Vuelve a intentarlo', en: 'It arrived damaged and I won’t use it. Try again' },
  no_disponible: { es: 'El servidor no lo entregó. Vuelve a intentarlo más tarde', en: 'The server didn’t serve it. Try again later' },
  sin_permiso: { es: 'Windows no me dejó guardarlo', en: 'Windows didn’t let me save it' },
  // REV_APP DL-c: the disk failed, not the line (it said «No logré conectarme» or «La descarga se cortó»)
  sin_disco: { es: 'Windows dio un error al guardarlo en el disco: puede que otro programa tenga el archivo abierto. Vuelve a intentarlo', en: 'Windows gave an error saving it to the disk: another program may have the file open. Try again' },
  sin_ollama: { es: 'Ollama no arrancó: instálalo primero', en: 'Ollama didn’t start: install it first' },
  no_existe: { es: 'Hugging Face no tiene ese archivo para Ollama', en: 'Hugging Face doesn’t have that file for Ollama' },
  ollama_fallo: { es: 'Ollama no pudo bajarlo', en: 'Ollama couldn’t download it' },
  cortado: { es: 'La descarga se cortó: vuelve a pedirla y sigue desde ahí', en: 'The download was cut: ask again and it goes on from there' },
};

/* Why the App did not start an install or a download (OpenModels' refusals; FieldProductChannel's for a body it cannot read). */
const NOT_STARTED: Record<string, Words> = {
  open_models_busy: { es: 'ya hay una descarga en curso. Espera a que termine o detenla', en: 'a download is already running. Wait for it to end or stop it' },
  open_models_no_space: { es: 'falta espacio en el disco', en: 'there isn’t enough disk space' },
  open_models_invalid_name: { es: 'ese nombre no sirve para Ollama. Busca el modelo otra vez', en: 'that name doesn’t work for Ollama. Find the model again' },
  invalid_settings: { es: 'a BAXY le faltó un dato del modelo. Búscalo otra vez', en: 'BAXY was missing a detail of the model. Find it again' },
};

/* Why Ollama's model was not uninstalled (OpenModels.RemoveAsync's refusals). */
const NOT_REMOVED: Record<string, Words> = {
  open_models_in_use: { es: 'Está en uso: elige otro antes de desinstalarlo', en: 'It’s in use: choose another before uninstalling it' },
  open_models_busy: { es: 'No se desinstaló: hay una descarga en curso. Espera a que termine o detenla', en: 'It wasn’t uninstalled: a download is running. Wait for it to end or stop it' },
  open_models_no_ollama: { es: 'No se desinstaló: Ollama no respondió', en: 'It wasn’t uninstalled: Ollama didn’t answer' },
  open_models_not_found: { es: 'Ollama ya no tenía ese modelo: no había nada que desinstalar', en: 'Ollama no longer had that model: there was nothing to uninstall' },
  open_models_failed: { es: 'No se desinstaló: Ollama no pudo borrarlo', en: 'It wasn’t uninstalled: Ollama couldn’t delete it' },
  open_models_invalid_name: { es: 'No se desinstaló: ese nombre no sirve para Ollama', en: 'It wasn’t uninstalled: that name doesn’t work for Ollama' },
};

const FIT: Record<Found['fit'], Words> = {
  cabe: { es: 'cabe en tu tarjeta', en: 'fits your card' },
  no_cabe: { es: 'no cabe en tu tarjeta: no lo conectaré sin preguntarte; en parte en la RAM iría mucho más lento', en: 'doesn’t fit your card: I won’t connect it without asking you; partly in RAM it would run much more slowly' },
  no_cabe_ram: { es: 'cabe en tu tarjeta, pero falta RAM libre para conectarlo', en: 'it fits your card, but there isn’t enough free RAM to connect it' },
  desconocido: { es: 'no sé si cabe en tu tarjeta', en: 'I don’t know whether it fits your card' },
};

/* Settings → Model → Local: install Ollama if it is missing, then write a name, choose what Hugging Face has under it, and
   «Instalar y usar» downloads it in Ollama and connects it (the App's Pulled). The stock model comes back with the switch off.
   Each result says the VRAM it takes with BAXY's default context, and «Sólo los que caben en mi tarjeta» (on by default)
   leaves out what does not fit the VRAM free on the card (owner, 2026-11-08). */
function OpenModelSearch({ value, onChange, onInstalled, noOllama, ollamaKnown }: { value: ExternalModel; onChange: (v: ExternalModel) => void; onInstalled: () => void; noOllama: boolean; ollamaKnown: boolean }) {
  const t = useT();
  const gb = (bytes: number) => size(bytes, t.locale);
  // The card's memory as Windows' Task Manager and nvidia-smi say it (and the rest of this tab): in units of 2^30 bytes.
  const vram = gb;
  const open = value.open;
  const [words, setWords] = useState('');
  const [found, setFound] = useState<Found[] | null>(null);
  const [card, setCard] = useState<{ total?: number; free?: number | null; ram?: number | null } | null>(null);
  // What the chosen tool profile's prompt and a turn take (the search's needContext), for a model that declares less.
  const [need, setNeed] = useState<number | null>(null);
  const [onlyFitting, setOnlyFitting] = useState(true);
  const [searching, setSearching] = useState(false);
  const [failed, setFailed] = useState<string | null>(null);
  const working = !!open?.ollamaInstalling || !!open?.pulling;
  const wasWorking = useRef(false);
  // While something downloads, the panel asks its progress every second (SettingsPanel, wherever the person looks); once it
  // ends, the list of models is asked again.
  useEffect(() => {
    if (wasWorking.current && !working) onInstalled();
    wasWorking.current = working;
  }, [working, onInstalled]);
  const post = async (path: string, body: Record<string, unknown>) => {
    try {
      const r = await fetch(path, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
      const answer = await r.json() as ExternalModel & { results?: Found[]; error?: string; needContext?: number; vramTotalBytes?: number; vramFreeBytes?: number | null; ramFreeBytes?: number | null };
      return r.ok ? answer : null;
    } catch { return null; }
  };
  const search = async () => {
    if (!words.trim()) return;
    setSearching(true);
    setFailed(null);
    const answer = await post('/settings/external-model/search', { q: words });
    setSearching(false);
    if (answer?.results) {
      setFound(answer.results);
      setNeed(answer.needContext ?? null);
      setCard(answer.vramTotalBytes ? { total: answer.vramTotalBytes, free: answer.vramFreeBytes, ram: answer.ramFreeBytes } : null);
    } else setFailed(answer?.error === 'limite' ? t('Hugging Face pidió esperar unos minutos antes de buscar otra vez', 'Hugging Face asked to wait a few minutes before searching again') : t('No pude buscar: revisa tu conexión', 'I couldn’t search: check your connection'));
  };
  // REV_VISTA V-10: what the App refuses is said with its own cause (it said «ya hay una descarga en curso o falta espacio»
  // for every one), and a request that got no answer is not said as a refusal: the App may have taken it.
  const act = async (path: string, body: Record<string, unknown> = {}, stopping = false) => {
    setFailed(null);
    const { value: answer, refused, code } = await sendTold<ExternalModel>('POST', path, body);
    if (answer?.providers) { onChange(answer); return; }
    if (refused) { setFailed(t('No se pudo empezar', 'It couldn’t start') + (NOT_STARTED[code ?? ''] ? ': ' + t.w(NOT_STARTED[code!]) : '')); return; }
    setFailed(stopping ? t('No supe si se detuvo: BAXY no respondió', 'I couldn’t tell whether it stopped: BAXY didn’t answer')
      : t('No supe si empezó: BAXY no respondió. Mira si aparece la descarga antes de pedirla otra vez', 'I couldn’t tell whether it started: BAXY didn’t answer. See whether the download shows up before asking for it again'));
    // What the App did with it is read at once: the download shows, or goes, by itself.
    void getJson<ExternalModel>('/settings/external-model').then((v) => { if (v?.providers) onChange(v); });
  };
  // A notice is of the request it answered: once a download starts or ends, what the App says of it is what is shown (kept, it
  // hid the download's own problem behind «No supe si…»).
  const [seenWorking, setSeenWorking] = useState(working);
  if (seenWorking !== working) {
    setSeenWorking(working);
    setFailed(null);
  }
  if (!open) return null;
  const problem = open.pullProblem ?? open.ollamaProblem;
  // An Ollama older than the one BAXY installs may not load today's models.
  const older = (a: string, b: string) => { const x = a.split('.').map(Number); const y = b.split('.').map(Number); for (let i = 0; i < 3; i++) { if ((x[i] || 0) !== (y[i] || 0)) return (x[i] || 0) < (y[i] || 0); } return false; };
  const outdated = !open.ollamaOwn && !!open.ollamaRunning && older(open.ollamaRunning, open.ollamaVersion);
  // The filter is only offered once the free VRAM is known; what does not say its VRAM is not hidden by it.
  const filtering = onlyFitting && card?.free != null;
  const shown = found?.filter((m) => !filtering || (m.fit !== 'no_cabe' && m.fit !== 'no_cabe_ram')) ?? null;
  const hidden = (found?.length ?? 0) - (shown?.length ?? 0);
  const stopped = !working && open.pullStopped ? open.pullStopped : null;
  // The profile a found model is offered with, by its name, when the App said one that this view knows.
  const lesser = (m: Found) => (!m.why && m.profile && PROFILE_NAME[m.profile] ? t.w(PROFILE_NAME[m.profile]) : null);
  const withProfile = (m: Found) => (lesser(m) ? { profile: m.profile } : {});
  return (<>
    {noOllama || outdated || open.ollamaInstalling || open.ollamaProblem ? (
      <Row label="Ollama" hint={(outdated ? t(`Tienes Ollama ${open.ollamaRunning}, y los modelos nuevos pueden no cargar en él. `, `You have Ollama ${open.ollamaRunning}, and new models may not load on it. `) : '') + t(`Corre los modelos en este PC. Se descarga de GitHub (${gb(open.ollamaBytes)}, versión ${open.ollamaVersion}; su código es MIT y trae bibliotecas CUDA de NVIDIA con su propia licencia) y se comprueba con SHA-256. BAXY lo abre sin ventana solo cuando lo usas, y no queda en el inicio de Windows`,
          `It runs the models on this PC. It downloads from GitHub (${gb(open.ollamaBytes)}, version ${open.ollamaVersion}; its code is MIT and it brings NVIDIA CUDA libraries under their own license) and is checked with SHA-256. BAXY opens it with no window only while you use it, and it doesn’t stay in Windows startup`)}>
        {open.ollamaInstalling ? null : <button className="panel-btn" disabled={working} onClick={() => void act('/settings/external-model/ollama')}>{t('Instalar Ollama', 'Install Ollama')}</button>}
      </Row>
    ) : null}
    {open.ollamaInstalling ? (
      <DownloadBar what={`Ollama ${open.ollamaVersion}`} done={open.ollamaDownloadedBytes} total={open.ollamaBytes}
        bytesPerSecond={open.ollamaBytesPerSecond} secondsLeft={open.ollamaSecondsLeft} onStop={() => void act('/settings/external-model/cancel', {}, true)} />
    ) : null}
    <Row label={t('Buscar un modelo', 'Find a model')} hint={t('Escribe su nombre, como «qwen3.5 4b», «gemma 4» o «llama 3.2». Lo que escribas se busca en Hugging Face', 'Type its name, such as “qwen3.5 4b”, “gemma 4” or “llama 3.2”. What you type is searched on Hugging Face')}>
      <input className="st-input" value={words} maxLength={100} aria-label={t('Nombre del modelo a buscar', 'Name of the model to find')} placeholder={t('Nombre del modelo', 'Model name')}
        onChange={(e) => setWords(e.target.value)} onKeyDown={(e) => { if (e.key === 'Enter') void search(); }} />
      <button className="panel-btn ghost" disabled={searching || !words.trim()} onClick={() => void search()}>{searching ? t('Buscando…', 'Searching…') : t('Buscar', 'Search')}</button>
    </Row>
    {open.pulling || stopped ? (
      <DownloadBar what={(open.pulling ?? stopped ?? '').replace(/^hf\.co\//, '')} done={open.pullDone} total={open.pullTotal}
        bytesPerSecond={open.pullBytesPerSecond} secondsLeft={open.pullSecondsLeft} stopped={!!stopped}
        onStop={() => void act('/settings/external-model/cancel', {}, true)}
        onResume={noOllama || !ollamaKnown ? undefined : () => void act('/settings/external-model/pull', { name: stopped, bytes: open.pullTotal })} />
    ) : null}
    {failed || (problem && OPEN_PROBLEM[problem] && !stopped) ? <div className="st-tip" role="alert">{failed ?? t.w(OPEN_PROBLEM[problem!])}</div> : null}
    {found && card?.free != null ? (
      <label className="st-check">
        <input type="checkbox" checked={onlyFitting} onChange={(e) => setOnlyFitting(e.target.checked)} />
        {t(`Sólo los que caben en mi tarjeta (${vram(card.free)} libres de ${vram(card.total ?? 0)})`, `Only the ones that fit my card (${vram(card.free)} free of ${vram(card.total ?? 0)})`)}
      </label>
    ) : null}
    {shown ? (shown.length ? (
      <ul aria-label={t('Modelos encontrados', 'Models found')} style={{ listStyle: 'none', margin: 0, padding: 0 }}>
        {shown.map((m) => (
          <li key={m.name}>
            <Row label={`${m.repo} · ${m.quant}`} hint={[
              gb(m.bytes),
              m.vramBytes ? t(`usa unos ${vram(m.vramBytes)} de VRAM con ${num((m.vramContext ?? 0), t.locale)} tokens de contexto`, `uses about ${vram(m.vramBytes)} of VRAM with ${num((m.vramContext ?? 0), t.locale)} tokens of context`) : '',
              m.projectorBytes ? t(`visión aparte, opcional: ${gb(m.projectorBytes)} más` + (m.projectorVramBytes ? ` y unos ${vram(m.projectorVramBytes)} más de VRAM` : ''), `vision apart, optional: ${gb(m.projectorBytes)} more` + (m.projectorVramBytes ? ` and about ${vram(m.projectorVramBytes)} more VRAM` : '')) : t('sin visión', 'no vision'),
              m.license ? t(`licencia ${m.license}`, `${m.license} license`) : t('sin licencia declarada', 'no license stated'),
              // AMD2: BAXY's least context is never recommended above what the model takes (poco_contexto): only its maximum
              m.contexts?.recommended && m.contexts.recommended <= m.contexts.native ? t(`contexto máximo ${num(m.contexts.native, t.locale)} tokens, recomendado ${num(m.contexts.recommended, t.locale)} en tu tarjeta`, `context up to ${num(m.contexts.native, t.locale)} tokens, ${num(m.contexts.recommended, t.locale)} recommended on your card`)
                : m.contexts?.native ? t(`contexto máximo ${num(m.contexts.native, t.locale)} tokens`, `context up to ${num(m.contexts.native, t.locale)} tokens`)
                  : m.context ? t(`admite ${num(m.context, t.locale)} tokens`, `takes ${num(m.context, t.locale)} tokens`) : '',
              m.why === 'sin_herramientas' ? t('no sabe usar herramientas: BAXY no puede usarlo', 'it can’t use tools: BAXY can’t use it')
                : m.why === 'poco_contexto' ? t('admite muy poco contexto para BAXY: ni el perfil de herramientas más pequeño le cabe', 'it takes too little context for BAXY: not even the smallest tool profile fits it')
                  : m.fit === 'no_cabe_ram' && m.ramBytes && card?.ram != null
                    ? t(`cabe en tu tarjeta, pero para conectarlo Windows debe poder reservar unos ${vram(m.ramBytes)} de RAM y archivo de paginación, y hay ${vram(card.ram)}`, `it fits your card, but to connect it Windows must be able to promise about ${vram(m.ramBytes)} of RAM and page file, and there are ${vram(card.ram)}`)
                    : t.w(FIT[m.fit]),
              lesser(m) ? t(`sólo le cabe el perfil ${lesser(m)} de herramientas` + (need ? `: el que tienes elegido necesita unos ${num(need, t.locale)} tokens` : '') + '. Al instalarlo paso a ese perfil',
                `only the ${lesser(m)} tool profile fits it` + (need ? `: the one you have chosen needs about ${num(need, t.locale)} tokens` : '') + '. Installing it switches me to that profile') : '',
            ].filter(Boolean).join(' · ')}>
              <button className="panel-btn ghost" disabled={!!m.why || working || noOllama || !ollamaKnown}
                onClick={() => void act('/settings/external-model/install', { repo: m.repo, file: m.file, sha256: m.sha256, bytes: m.bytes, quant: m.quant, ...withProfile(m) })}>{lesser(m) ? t(`Instalar y usar con ${lesser(m)}`, `Install and use with ${lesser(m)}`) : t('Instalar y usar', 'Install and use')}</button>
              {m.visionName ? <button className="panel-btn ghost" disabled={!!m.why || working || noOllama || !ollamaKnown}
                onClick={() => void act('/settings/external-model/pull', { name: m.visionName, bytes: m.bytes + m.projectorBytes, ...withProfile(m) })}>{t('Añadir visión', 'Add vision')}</button> : null}
            </Row>
          </li>
        ))}
      </ul>
    ) : <div className="st-tip">{hidden ? t('Ninguno de los encontrados cabe en este PC (en la tarjeta o en la RAM libre). Quita el filtro para verlos', 'None of the ones found fits this PC (its card or its free RAM). Turn the filter off to see them') : t('No encontré modelos para Ollama con ese nombre. Prueba con menos palabras', 'I found no models for Ollama with that name. Try fewer words')}</div>) : null}
    {shown?.length && hidden ? <div className="st-tip">{t(`${hidden} más no caben en este PC`, `${hidden} more don’t fit this PC`)}</div> : null}
    {found?.length ? <div className="st-tip">{t('La VRAM se calcula con la forma del modelo (sus capas y su caché) y se comprobó contra tarjetas reales: en todas salió igual o mayor que lo que de verdad ocupaba. Es la del modelo solo, que es lo que se instala; su visión, si la añades, suma lo que dice aparte. Lo libre es lo que queda en tu tarjeta sin contar el modelo que BAXY usa ahora, que se va al cambiar.', 'The VRAM is worked out from the model’s shape (its layers and cache) and it was checked against real cards: on every one it came out equal to or above what it really took. It’s the model’s alone, which is what gets installed; its vision, if you add it, adds what it says apart. What’s free is what’s left on your card not counting the model BAXY uses now, which goes when you switch.')}</div> : null}
  </>);
}
/* The context sizes for the chosen Ollama model and the memory of each (GET /settings/external-model/estimate). */
interface ContextEstimate {
  contextLength?: number;
  recommended?: number;
  options?: { context: number; bytes: number | null }[];
  vramTotalBytes?: number;
  vramFreeBytes?: number;
  commitFreeBytes?: number | null;
  /* where the options' bytes come from: the model's files (BAXY's estimate; what does not fit waits for the person) or Ollama's count */
  bytesFrom?: 'cabecera' | 'ollama';
  /* what the chosen tool profile's prompt takes (VIVO2): what is left for the conversation is counted from it */
  promptTokens?: number;
  error?: string;
}

/* What BAXY sends a model before any conversation (external_model in the mind), when the host does not say it for the chosen profile. */
const PROMPT_TOKENS = 49000;
/* The translator's RAM check (external_model.memory_problem; documentacion/VRAM_ESTIMADA.md): what it leaves free for everything
   else; whole on the card, what the process holds beside the model; partly in RAM, what it takes per byte. */
const MEMORY_RESERVE = 3 * GIB;
const COMMIT_HOST = 2.75 * GIB;
const COMMIT_PER_BYTE_PARTIAL = 1.7;
/* Partly in RAM only past the free VRAM and on Ollama (past what the model declares, BAXY's own server keeps it whole); with the
   free VRAM not known, the larger of the two, as the translator (connect_memory_problem, ExternalModel.MemoryArguments). */
const shortOfMemory = (estimate: ContextEstimate, option: { context: number; bytes: number | null }) => {
  if (!option.bytes || !estimate.commitFreeBytes) return false;
  const whole = option.bytes + COMMIT_HOST;
  const split = option.bytes * COMMIT_PER_BYTE_PARTIAL;
  const engine = !!estimate.contextLength && option.context > estimate.contextLength;
  const need = engine ? whole : estimate.vramFreeBytes === undefined ? Math.max(whole, split) : option.bytes > estimate.vramFreeBytes ? split : whole;
  return need + MEMORY_RESERVE > estimate.commitFreeBytes;
};

/* What this key or this PC can use (GET /settings/external-model/models). */
interface ModelList {
  models?: { id: string; label: string; fits: boolean; why?: string | null }[];
  error?: string;
  needsKey?: boolean;
  needsUrl?: boolean;
  ollama?: string;
}

const EXTERNAL_PROBLEM: Record<string, Words> = {
  falta_traductor: { es: 'No se encontró el traductor: BAXY sigue con su modelo', en: 'The translator wasn’t found: BAXY stays on its own model' },
  clave_ilegible: { es: 'No se pudo abrir la clave guardada: vuelve a pegarla', en: 'The saved key couldn’t be opened: paste it again' },
  traductor_no_arranca: { es: 'El traductor no arrancó: BAXY sigue con su modelo', en: 'The translator didn’t start: BAXY stays on its own model' },
  traductor_caido: { es: 'El traductor se cerró: apaga esta opción y vuelve a activarla', en: 'The translator closed: turn this option off and on again' },
  no_cabe_vram: { es: 'no cabe en la VRAM libre con ese contexto, y no lo cargué', en: 'it doesn’t fit the free VRAM with that context, and I didn’t load it' },
};

const EXTERNAL_REFUSED: Record<string, Words> = {
  external_model_no_key: { es: 'Primero guarda la clave', en: 'Save the key first' },
  external_model_no_model: { es: 'Primero elige el modelo', en: 'Choose the model first' },
  external_model_no_url: { es: 'Primero escribe la dirección de la API', en: 'Type the API address first' },
  external_model_invalid_url: { es: 'Escribe solo la dirección, con https://, sin clave ni parámetros', en: 'Type only the address, with https://, no key or parameters' },
  external_model_invalid_key: { es: 'Esa clave no sirve', en: 'That key doesn’t work' },
  external_model_invalid_ceiling: { es: 'El tope debe estar entre 0 y 1.000 USD', en: 'The cap must be between 0 and 1,000 USD' },
  external_model_invalid_context: { es: 'Ese contexto no sirve', en: 'That context doesn’t work' },
  external_model_invalid_model: { es: 'Ese nombre de modelo no sirve', en: 'That model name doesn’t work' },
  // REV_VISTA V-01: a name that only another place listed, asked for without saying its place (ExternalModel.Apply)
  external_model_other_provider: { es: 'Ese modelo no es del proveedor elegido: elígelo desde su propia lista', en: 'That model isn’t the chosen provider’s: choose it from its own list' },
};
const NOT_SAVED: Words = { es: 'No se pudo guardar', en: 'It couldn’t be saved' };

/* Settings › Model › Local or API (design board 13 to 16): the choice of where BAXY thinks is the tab's one picker, so this
   section has no switch of its own; choosing a model here turns it on, and «De serie» above turns it off. */
function ExternalModelSection({ value, onChange, onSaved, mode }: { value: ExternalModel; onChange: (v: ExternalModel) => void; onSaved: () => void; mode: 'local' | 'api' }) {
  const t = useT();
  const tokens = (n: number) => num(n, t.locale);
  const gigabytes = (bytes: number) => size(bytes, t.locale);
  // REV_VISTA V-05: what is written here and not saved yet outlives this box (drafts.ts): another tab, Escape or a click
  // outside no longer takes it
  const [key, setKey] = useDraft('external.key.' + value.provider, '');
  const [model, setModel] = useDraft('external.model.' + value.provider, value.model);
  const [url, setUrl] = useDraft('external.url.' + value.provider, value.url);
  const [ceiling, setCeiling] = useDraft('external.ceiling', value.ceilingUsd === null ? '' : String(value.ceilingUsd));
  const [refused, setRefused] = useState<string | null>(null);
  // What was written follows what the host now says (react.dev/learn/you-might-not-need-an-effect, «Adjusting some state when a
  // prop changes»): set while rendering, not in an effect, so nothing renders first with the old words.
  const shown = `${value.provider}|${value.model}|${value.url}`;
  const [seen, setSeen] = useState(shown);
  if (seen !== shown) {
    setSeen(shown);
    setModel(value.model);
    setUrl(value.url);
    setKey('');
  }
  const [seenCeiling, setSeenCeiling] = useState(value.ceilingUsd);
  if (seenCeiling !== value.ceilingUsd) {
    setSeenCeiling(value.ceilingUsd);
    setCeiling(value.ceilingUsd === null ? '' : String(value.ceilingUsd));
  }
  const [asked, setAsked] = useState(0);
  const refresh = useCallback(() => setAsked((n) => n + 1), []);
  // Asked when the provider, the key or the address changes, and when the panel opens: what this key can use is its own. An
  // answer counts only for what it was asked for: until the new one arrives, the list is being asked.
  const listFor = `${value.provider}|${value.hasKey}|${value.url}|${asked}`;
  const [listed, setListed] = useState<{ for: string; list: ModelList | null } | null>(null);
  useEffect(() => {
    let current = true;
    void getJson<ModelList>('/settings/external-model/models').then((l) => {
      if (!current) return;
      setListed({ for: listFor, list: l });
      // Asking the list may have opened Ollama: its version is known only now (an older one offers BAXY's).
      void getJson<ExternalModel>('/settings/external-model').then((v) => { if (current && v?.providers) onChange(v); });
    });
    return () => { current = false; };
  }, [listFor, onChange]);
  const list = listed?.for !== listFor ? null : listed.list ?? { error: t('no se pudo preguntar la lista', 'the list couldn’t be asked for') };
  // Asked for the model chosen: the first time, Ollama loads it for some seconds to measure it. And again on connecting: BAXY's
  // own model is gone by then, and the memory it held with it.
  const estimateFor = value.provider === 'local' && value.model ? `${value.model}|${value.active}` : null;
  const [estimated, setEstimated] = useState<{ for: string; estimate: ContextEstimate | null } | null>(null);
  useEffect(() => {
    if (estimateFor === null) return undefined;
    let current = true;
    void getJson<ContextEstimate>('/settings/external-model/estimate').then((e) => { if (current) setEstimated({ for: estimateFor, estimate: e }); });
    return () => { current = false; };
  }, [estimateFor]);
  const estimate = estimateFor === null || estimated?.for !== estimateFor ? null : estimated.estimate ?? { error: t('no se pudo calcular', 'it couldn’t be worked out') };
  const put = async (body: Record<string, unknown>) => {
    let answer: (ExternalModel & { error?: string }) | null = null;
    let ok = false;
    try {
      const r = await fetch('/settings/external-model', { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
      ok = r.ok;
      answer = await r.json() as ExternalModel & { error?: string };
    } catch { /* said below */ }
    if (!ok || !answer?.providers) {
      setRefused(t.w(EXTERNAL_REFUSED[answer?.error ?? ''] ?? NOT_SAVED));
      return;
    }
    setRefused(null);
    if (body.key) { setAsked((n) => n + 1); setKey(''); }
    onChange(answer);
    onSaved();
  };
  const local = value.provider === 'local';
  const compatible = value.provider === 'compatible';
  const models = list?.models ?? [];
  const chosen = models.find((m) => m.id === value.model);
  const listNote = list === null ? (local ? t('Buscando tus modelos de Ollama…', 'Looking for your Ollama models…') : t('Buscando los modelos disponibles…', 'Looking for the available models…'))
    : list.ollama === 'missing' ? t('No encontré Ollama en este PC: instálalo aquí abajo y busca un modelo', 'I didn’t find Ollama on this PC: install it below and find a model')
      : list.needsKey ? t('Guarda tu clave y aquí aparecerán los modelos que puedes usar', 'Save your key and the models you can use will show up here')
        : list.needsUrl ? t('Escribe la dirección de la API y aquí aparecerán sus modelos', 'Type the API address and its models will show up here')
          : list.error ? t('No se pudo leer la lista: ', 'The list couldn’t be read: ') + list.error
            : !models.length ? (local ? t('Ollama no tiene modelos. Descarga uno y aparecerá aquí', 'Ollama has no models. Download one and it will show up here') : t('Esta clave no tiene modelos disponibles', 'This key has no models available'))
              : t('Al elegir uno, BAXY lo carga y se conecta', 'When you choose one, BAXY loads it and connects');
  const contextNow = value.context ?? estimate?.recommended ?? 0;
  const contextOption = estimate?.options?.find((o) => o.context === contextNow);
  const prompt = estimate?.promptTokens ?? value.promptTokens ?? PROMPT_TOKENS;
  const room = contextNow - prompt;
  const beyond = !!estimate?.contextLength && contextNow > estimate.contextLength;
  const contextNote = estimate === null ? t('Calculando cuánta VRAM usa: la primera vez, Ollama lo carga unos segundos', 'Working out how much VRAM it uses: the first time, Ollama loads it for a few seconds')
    : !estimate.options?.length ? (estimate.contextLength ? t(`Admite ${tokens(estimate.contextLength)} tokens y BAXY necesita más de ${tokens(prompt)}`, `It takes ${tokens(estimate.contextLength)} tokens and BAXY needs more than ${tokens(prompt)}`) : t('No se pudo calcular: ', 'It couldn’t be worked out: ') + (estimate.error ?? t('Ollama no respondió', 'Ollama didn’t answer')))
      : [
        t(`Deja unos ${tokens(room)} tokens para la conversación`, `It leaves about ${tokens(room)} tokens for the conversation`),
        estimate.vramTotalBytes ? t(`Tu tarjeta tiene ${gigabytes(estimate.vramTotalBytes)}`, `Your card has ${gigabytes(estimate.vramTotalBytes)}`) + (estimate.vramFreeBytes !== undefined ? t(` y hay ${gigabytes(estimate.vramFreeBytes)} libres`, ` and ${gigabytes(estimate.vramFreeBytes)} are free`) : '') : '',
        contextOption?.bytes && estimate.vramFreeBytes !== undefined && contextOption.bytes > estimate.vramFreeBytes
          ? (beyond ? t('No cabe: elige menos contexto', 'It doesn’t fit: choose less context') : estimate.bytesFrom === 'cabecera' ? t('No cabe entero: no lo conectaré sin preguntarte; en parte en la RAM iría mucho más lento', 'It doesn’t all fit: I won’t connect it without asking you; partly in RAM it would run much more slowly')
            : t('No cabe entero: lo demás irá a la RAM y responderá más lento', 'It doesn’t all fit: the rest goes to RAM and it will answer more slowly')) : '',
        contextOption && estimate.commitFreeBytes && shortOfMemory(estimate, contextOption)
          ? t(`Este PC tiene ${gigabytes(estimate.commitFreeBytes)} de RAM libre (con el archivo de paginación): no se conectará con este contexto`, `This PC has ${gigabytes(estimate.commitFreeBytes)} of RAM free (with the paging file): it won’t connect with this context`) : '',
        beyond ? t(`El modelo declara ${tokens(estimate.contextLength!)}: BAXY le amplía el límite y lo corre con su propio motor`, `The model declares ${tokens(estimate.contextLength!)}: BAXY raises the limit and runs it with its own engine`) : '',
        estimate.error ? t('No se pudo calcular la VRAM: ', 'The VRAM couldn’t be worked out: ') + estimate.error : '',
      ].filter(Boolean).join('. ');
  // REV_VISTA V-11: what BAXY sends a model before any conversation, with the chosen tool profile's own figure (the App's
  // promptTokens); it said «unos 49.000 tokens… el contexto parte en 64.000» for every profile.
  const sent: Words = value.promptTokens
    ? { es: `BAXY le envía unos ${tokens(value.promptTokens)} tokens con sus instrucciones y las herramientas del perfil elegido, así que el contexto no puede ser menor.`,
      en: `BAXY sends it about ${tokens(value.promptTokens)} tokens with its instructions and the chosen profile’s tools, so the context can’t be smaller.` }
    : { es: 'BAXY le envía sus instrucciones y las herramientas del perfil elegido antes de la conversación, así que el contexto no puede ser menor que ellas.',
      en: 'BAXY sends it its instructions and the chosen profile’s tools before the conversation, so the context can’t be smaller than them.' };
  // REV_VISTA V-08: why the model did not connect, or refuses its turns, is said once, with the model in use (ModelTab); here
  // only what is this section's own to mend: the spending cap, set below.
  const capped = !value.switching && value.lastError?.startsWith('TOPE');
  return (<>
    {capped ? <div className="st-tip" role="alert">{t('Llegaste al tope de gasto: súbelo o bórralo abajo, o apaga esta opción para volver al modelo de este PC', 'You reached the spending cap: raise or clear it below, or turn this option off to go back to this PC’s model')}</div> : null}
    {mode === 'api' ? <Row label={t('Usar con BAXY', 'Use with BAXY')} hint={value.enabled ? t('En uso. Para volver al modelo de este PC, elige «De serie» arriba', 'In use. To go back to this PC’s model, choose “Stock” above') : t('Con la clave y el modelo, BAXY pasa a pensar con esta empresa', 'With the key and the model, BAXY starts thinking with this company')}>
      {value.enabled ? <span className="bx-tag on">{t('En uso', 'In use')}</span>
        : <button className="panel-btn" onClick={() => void put({ provider: value.provider, ...(key.trim() ? { key } : {}), model, url, enabled: true })}>{t('Usar esta API', 'Use this API')}</button>}
    </Row> : null}
    {mode === 'api' ? <Row label={t('Empresa', 'Company')}><Seg label={t('Empresa', 'Company')} value={value.provider} onChange={(v) => void put({ provider: v })} options={value.providers.filter((p) => p.id !== 'local').map((p) => [p.id, p.id === 'compatible' ? t('Otra', 'Other') : p.label] as [string, string])} /></Row> : null}
    {compatible ? (
      <Row label={t('Dirección de la API', 'API address')} hint={t('Debe hablar el formato de chat de OpenAI. Una dirección de este PC no necesita clave', 'It must speak OpenAI’s chat format. An address on this PC needs no key')}>
        <input className="st-input" value={url} maxLength={200} aria-label={t('Dirección de la API', 'API address')} placeholder="https://" onChange={(e) => setUrl(e.target.value)}
          onBlur={(e) => { if (savesOnBlur(e) && url.trim() !== value.url) void put({ url }); }} />
      </Row>
    ) : null}
    {local ? null : <Row label={t('Clave', 'Key')} hint={value.hasKey ? t('Guardada y protegida en este PC. No se vuelve a mostrar', 'Saved and protected on this PC. It isn’t shown again') : t('Se guarda protegida en este PC', 'It’s saved protected on this PC')}>
      <input className="st-input" type="password" autoComplete="off" spellCheck={false} value={key} maxLength={512} aria-label={t('Clave de la API', 'API key')}
        placeholder={value.hasKey ? '••••••••' : t('Pega tu clave', 'Paste your key')} onChange={(e) => setKey(e.target.value)} />
      <button className="panel-btn ghost" disabled={!key.trim()} onClick={() => void put({ key })}>{t('Guardar', 'Save')}</button>
      {value.hasKey ? <button className="panel-btn ghost" onClick={() => void put({ forgetKey: true })}>{t('Borrar', 'Delete')}</button> : null}
    </Row>}
    <Row label={t('Modelo', 'Model')} hint={listNote}>
      {models.length ? (
        <select className="st-input" value={chosen ? value.model : ''} aria-label={t('Modelo', 'Model')} onChange={(e) => { if (e.target.value) void put({ provider: value.provider, model: e.target.value, enabled: true }); }}>
          <option value="">{t('Elige un modelo', 'Choose a model')}</option>
          {models.map((m) => <option key={m.id} value={m.id} disabled={!m.fits}>{m.label}{m.fits ? '' : ' · ' + m.why}</option>)}
        </select>
      ) : (
        !local && list?.error ? <input className="st-input" value={model} maxLength={200} aria-label={t('Modelo', 'Model')} placeholder={t('Nombre del modelo', 'Model name')} onChange={(e) => setModel(e.target.value)}
          onBlur={(e) => { if (savesOnBlur(e) && model.trim() !== value.model) void put({ provider: value.provider, model }); }} /> : null
      )}
      <button className="panel-btn ghost" onClick={refresh}>{t('Actualizar', 'Refresh')}</button>
    </Row>
    {/* Medido en vivo 2026-11-08: Qwen3.5-2B por Ollama respondió «5» a «2 más 2». Said, never blocked nor filtered. */}
    {local ? <div className="st-tip" role="note">{t('Los modelos más pequeños que el de serie aciertan menos y pueden equivocarse.', 'Models smaller than the stock one get fewer things right and can be wrong.')}</div> : null}
    {/* VIVO2 F14: connected, the box of the model in use already says it */}
    {value.sees === false && !value.active ? <div className="st-tip" role="note">{t('Este modelo no ve: BAXY no describirá capturas ni buscará botones por su imagen, y lee el texto de la pantalla igual.', 'This model doesn’t see: BAXY won’t describe screenshots or find buttons by their image, and reads the screen’s text all the same.')}</div> : null}
    {local ? <Fold id="buscar" open title={t('Buscar y descargar', 'Find and download')} summary={pullPercent(value.open) !== null ? t(`Bajando · ${pullPercent(value.open)} %`, `Downloading · ${pullPercent(value.open)} %`) : value.open?.pullStopped ? t('En pausa', 'Paused') : t('Hugging Face', 'Hugging Face')}>
      <OpenModelSearch value={value} onChange={onChange} onInstalled={refresh} noOllama={list?.ollama === 'missing'} ollamaKnown={list !== null} />
    </Fold> : null}
    {local && value.model ? (
      <Fold id="contexto" open title={t('Contexto', 'Context')} summary={contextNow ? `${tokens(contextNow)} tokens` : undefined}>
      <Row label={t('Contexto', 'Context')} hint={contextNote}>
        <select className="st-input" style={{ width: 350, flexShrink: 0 }} value={contextNow || ''} disabled={!estimate?.options?.length} aria-label={t('Contexto', 'Context')} onChange={(e) => void put({ context: Number(e.target.value) })}>
          {estimate?.options?.length ? null : <option value="">{t('Calculando…', 'Working it out…')}</option>}
          {estimate?.options?.map((o) => (
            <option key={o.context} value={o.context}>
              {tokens(o.context)} tokens{o.bytes ? t(` · unos ${gigabytes(o.bytes)} de VRAM`, ` · about ${gigabytes(o.bytes)} of VRAM`) : ''}{shortOfMemory(estimate, o) ? t(' · sin memoria', ' · no memory') : ''}{o.context === estimate.recommended ? t(' · recomendado', ' · recommended') : ''}
            </option>
          ))}
        </select>
      </Row>
      </Fold>
    ) : null}
    {refused ? <div className="st-tip" role="alert">{refused}</div> : null}
    {local ? null : <Fold id="gasto" open title={t('Gasto', 'Spending')} summary={value.ceilingHolds ? `${num(value.spentUsd, t.locale, 2)} USD` : undefined}>{value.ceilingHolds
      ? <>
        <Row label={t('Gastado', 'Spent')} ro hint={t('Lo que costó con esta clave en este perfil, según los precios que BAXY conoce', 'What it cost with this key on this profile, by the prices BAXY knows')}><span className="bxs-fixed">{num(value.spentUsd, t.locale, 2)} USD</span></Row>
        <Row label={t('Tope de gasto en USD', 'Spending cap in USD')} hint={t('Opcional. Vacío, no hay tope. Con un número, deja de llamar a la API al llegar a ese total', 'Optional. Empty means no cap. With a number, it stops calling the API on reaching that total')}>
          <input className="st-input" type="number" min={0} max={1000} step={1} value={ceiling} placeholder={t('Sin tope', 'No cap')} aria-label={t('Tope de gasto en USD', 'Spending cap in USD')} onChange={(e) => setCeiling(e.target.value)}
            onBlur={(e) => { const v = ceiling.trim() ? Number(ceiling) : null; if (savesOnBlur(e) && v !== value.ceilingUsd) void put({ ceilingUsd: v }); }} />
        </Row>
      </>
      : <Row label={t('Gastado', 'Spent')} ro hint={t('BAXY no conoce los precios de este modelo: pon tu límite en la consola de esa empresa', 'BAXY doesn’t know this model’s prices: set your limit in that company’s console')}><span className="bxs-fixed">—</span></Row>}</Fold>}
    {local
      ? <div className="st-tip">{t('El modelo corre en Ollama y ', 'The model runs in Ollama and ')}<b className="bone">{t('la conversación no sale de este PC', 'the conversation doesn’t leave this PC')}</b>{t(`, sin gasto por uso. BAXY abre Ollama si hace falta. Los modelos de Ollama que corren en su nube no se pueden elegir, porque saldrían de este PC. El modelo debe saber usar herramientas. ${sent.es} Con más contexto recuerda más conversación y usa más VRAM. Si no cabe en la memoria, BAXY lo dice y sigue con su modelo. BAXY está ajustada para su propio modelo, así que otro puede rendir distinto.`, `, with no cost per use. BAXY opens Ollama if needed. Ollama models that run in its cloud can’t be chosen, because they’d leave this PC. The model must know how to use tools. ${sent.en} With more context it remembers more of the conversation and uses more VRAM. If it doesn’t fit in memory, BAXY says so and stays on its own model. BAXY is tuned for its own model, so another one may perform differently.`)}</div>
      : <div className="st-tip">{t('Con esto activo, lo que le pases a BAXY ', 'With this on, what you give BAXY ')}<b className="bone">{t('sale de este PC hacia esa empresa', 'leaves this PC for that company')}</b>{t(': lo que digas, lo que lea de tu pantalla, archivos y páginas, y las capturas de pantalla. Eso incluye también la conversación que ya tuviste con BAXY antes de activarlo. Lo paga tu cuenta de esa empresa, aparte de BAXY.', ': what you say, what it reads from your screen, files and pages, and screenshots. That also includes the conversation you already had with BAXY before turning it on. Your account with that company pays for it, separately from BAXY.')}</div>}
  </>);
}

/* Settings → Model → Context (LocalContext in the App): the context BAXY's own model runs with, stock or tuned, from fixed
   presets, each with the video memory estimated from what was measured and the room it leaves beside the instructions and
   tools. «Automático» is the factory's. A change restarts the model once what it is doing ends. */
interface LocalContextOption { context: number; vramBytes: number | null; vision?: boolean; slower: boolean; room: number | null; fits: boolean }
/* MOD1 V-07: a file of BAXY's own (the stock model's, the tuned one's): its weight on disk, and the video memory it takes with
   the context a mind would start it with (null on the processor, or while that context is not known). */
interface OwnModelFile { bytes: number; vramBytes: number | null; vramContext: number | null }
interface LocalContextState {
  chosen: number | null;
  /** what the mind takes with nothing chosen on this graphics card; null until it said its backend */
  automatic: number | null;
  prefixTokens: number | null;
  /** the person's graphics card's memory, or BAXY's 4 GB budget while it is not known (cardKnown) */
  cardBytes: number;
  cardKnown?: boolean;
  options: LocalContextOption[];
  switching: boolean;
  /** the stock model's file whichever model runs, and the tuned one's once installed: for their rows in «Modelos en este PC» */
  stock?: OwnModelFile | null;
  tuned?: OwnModelFile | null;
  /** MOD1 D5: what this PC took the last time the model read its instructions and tools whole (PrefixRead in the App); null before any */
  lastRead?: { tokens: number; seconds: number } | null;
  /** VRAM4: «Automático» on a card whose free video memory did not hold the profile's cells whole when the model started */
  cardShort?: FailureCard | null;
}

/* MOD1 D5: from a minute of reading on, a change of context asks first (once started it cannot be stopped, and BAXY does not
   answer meanwhile); under it, the line below the list says the wait and the change applies at once (00_IDENTIDAD, «Velocidad»:
   what takes long is said before, what takes little is not asked). */
const ASK_FROM_SECONDS = 60;

const LOCAL_CONTEXT_REFUSED: Record<string, Words> = {
  local_context_too_small: { es: 'No deja sitio para sus instrucciones y herramientas', en: 'It leaves no room for its instructions and tools' },
  local_context_not_saved: { es: 'Windows no me dejó guardarlo', en: 'Windows didn’t let me save it' },
};

function LocalContextRow({ value, onChange, tuned, ownRuns }: { value: LocalContextState; onChange: (v: LocalContextState) => void; tuned: boolean; ownRuns: boolean }) {
  const t = useT();
  const tokens = (n: number) => num(n, t.locale);
  const gigabytes = (bytes: number) => size(bytes, t.locale);
  const [refused, setRefused] = useState<string | null>(null);
  const put = async (context: number | null) => {
    let answer: (LocalContextState & { error?: string }) | null = null;
    try {
      const r = await fetch('/settings/local-context', { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ context }) });
      answer = await r.json() as LocalContextState & { error?: string };
      if (!r.ok) answer = { ...value, error: answer?.error ?? 'refused' };
    } catch { /* said below */ }
    if (!answer?.options || answer.error) {
      const known = answer?.error ? LOCAL_CONTEXT_REFUSED[answer.error] : undefined;
      setRefused(known ? t.w(known) : t('Ese contexto no sirve', 'That context doesn’t work'));
      return;
    }
    setRefused(null);
    onChange(answer);
  };
  const label = (o: LocalContextOption) => tokens(o.context) + ' tokens'
    + (o.vramBytes ? t(` · unos ${gigabytes(o.vramBytes)} de VRAM`, ` · about ${gigabytes(o.vramBytes)} of VRAM`) + (o.vision ? t(' con la visión', ' with vision') : '') : '')
    + (!o.fits ? t(' · no caben sus herramientas', ' · its tools don’t fit')
      // VIVO1: said before it is chosen, not only under the one chosen (the hint below); «puede»: the estimate is never under
      // what it takes, and 196,608 tokens estimated at 6.6 GB ran in 5.7 GiB on a 6 GB card
      : value.cardKnown && o.vramBytes && o.vramBytes > value.cardBytes ? t(' · puede no caber en tu tarjeta', ' · may not fit your card')
        : o.slower ? t(' · más lento', ' · slower') : '');
  // MOD1 D5 (AMD2 §5: 754 s on an RX 7600 after a change of context, with nothing said before; back to the one before, 9-10 s):
  // another context is another prompt cache, so the model reads its instructions and tools again. Said with what this PC
  // took the last time it read them whole, when the App measured it.
  const read = value.lastRead?.seconds ?? null;
  const readTook = read === null ? null
    : read < 90 ? t(`unos ${read} segundos`, `about ${read} seconds`) : t(`unos ${Math.round(read / 60)} minutos`, `about ${Math.round(read / 60)} minutes`);
  const [asking, setAsking] = useState<{ context: number | null } | null>(null);
  const askRef = useInnerDialog<HTMLDivElement>(() => setAsking(null));
  // With another model running, nothing restarts now: the choice is for when BAXY's own model runs again.
  const change = (context: number | null) => {
    if (ownRuns && read !== null && read >= ASK_FROM_SECONDS) setAsking({ context });
    else void put(context);
  };
  const automatic = value.options.find((o) => o.context === value.automatic);
  const now = value.options.find((o) => o.context === (value.chosen ?? value.automatic));
  const hint = value.switching ? t('Cambiando: el modelo se reinicia al acabar el turno en curso', 'Switching: the model restarts once the current turn ends')
    : refused ?? ([
      value.chosen === null && value.cardShort ? cardShortText(value.cardShort, t).replace(/\.$/, '') : '',
      now?.room != null ? t(`Deja unos ${tokens(now.room)} tokens para la conversación`, `It leaves about ${tokens(now.room)} tokens for the conversation`) : '',
      now?.vramBytes && now.vramBytes > value.cardBytes ? (value.cardKnown ? t(`No cabe en tu tarjeta de ${gigabytes(value.cardBytes)}: lo que sobre irá a la memoria compartida, mucho más lento`, `It doesn’t fit your ${gigabytes(value.cardBytes)} card: what’s left over goes to shared memory, much more slowly`) : t('Puede no caber en una tarjeta de 4 GB', 'It may not fit on a 4 GB card')) : '',
      now?.slower ? t('En tarjetas AMD o Intel, con más de 61.440 tokens se midió unas 4 veces más lento', 'On AMD or Intel cards, with more than 61,440 tokens it was measured about 4 times slower') : '',
    ].filter(Boolean).join('. ') || t('Con más contexto recuerda más conversación y usa más VRAM', 'With more context it remembers more of the conversation and uses more VRAM'));
  return (<>
    <Row label={t('Contexto', 'Context')} hint={hint}>
      <select className="st-input" style={{ width: 350, flexShrink: 0 }} value={value.chosen ?? ''} disabled={value.switching} aria-label={t('Contexto', 'Context')}
        onChange={(e) => change(e.target.value ? Number(e.target.value) : null)}>
        <option value="">{t('Automático (de fábrica)', 'Automatic (factory)')}{automatic ? ' · ' + label(automatic) : ''}</option>
        {value.options.map((o) => <option key={o.context} value={o.context} disabled={!o.fits}>{label(o)}</option>)}
      </select>
    </Row>
    {asking ? (
      <div ref={askRef} className="bxs-ask" role="dialog" aria-label={t('Cambiar el contexto', 'Change the context')}>
        <span><b>{asking.context === null ? t('¿Volver al contexto automático?', 'Go back to the automatic context?') : t(`¿Cambiar el contexto a ${tokens(asking.context)} tokens?`, `Change the context to ${tokens(asking.context)} tokens?`)}</b> {t(`El modelo se reinicia y lee otra vez sus instrucciones y herramientas: la última vez este PC tardó ${readTook}, y hasta que termine BAXY no responde. Si es el contexto que usó justo antes, no las relee.`,
          `The model restarts and reads its instructions and tools again: last time this PC took ${readTook}, and BAXY doesn’t answer until it ends. If it’s the context it used just before, it doesn’t read them again.`)}</span>
        <span className="btns"><button className="panel-btn ghost" onClick={() => setAsking(null)} data-cancel>{t('Cancelar', 'Cancel')}</button>
          <button className="panel-btn" onClick={() => { const next = asking.context; setAsking(null); void put(next); }}>{t('Sí, cambiar', 'Yes, change it')}</button></span>
      </div>
    ) : null}
    <div className="st-tip">{tuned ? t('Vale para el modelo de serie y para el ajustado. ', 'It applies to the stock model and the tuned one. ') : ''}{t('La VRAM se calcula con la forma del modelo (sus capas y su caché) y en una RTX 3060 y una RTX 4060 Ti salió igual o mayor que lo medido. Incluye la lectura de la pantalla cuando cabe en tu tarjeta, que la pone ahí. Cambiarlo reinicia el modelo al acabar el turno en curso, y antes de responder lee otra vez sus instrucciones y herramientas, salvo que vuelvas al contexto de justo antes: ', 'The VRAM is worked out from the model’s shape (its layers and cache) and on an RTX 3060 and an RTX 4060 Ti it came out equal to or above what was measured. It includes reading the screen when your card has room for it, which puts it there. Changing it restarts the model once the current turn ends, and before it answers it reads its instructions and tools again, unless you go back to the context from just before: ')}{readTook ? t(`la última vez este PC tardó ${readTook} en leerlas.`, `last time this PC took ${readTook} to read them.`) : t('en una tarjeta lenta son minutos.', 'on a slow card that takes minutes.')}</div>
  </>);
}

/* QWB2: BAXY's tuned model, which the package offers and does not carry (TunedModel in the App): downloaded only when the
   person presses Install, after the notice; used only once its SHA-256 is the one the package names. Without the offer
   (a development copy) the host says available: false and this section does not exist. */
interface TunedModel {
  available: boolean;
  file?: string;
  bytes?: number;
  license?: string;
  source?: string;
  repo?: string;
  installed?: boolean;
  use?: boolean;
  active?: boolean;
  problem?: string | null;
  downloading?: boolean;
  downloadedBytes?: number;
  /* while it downloads: its speed and the time left, as a model's download says them (DownloadRate in the App) */
  downloadBytesPerSecond?: number | null;
  downloadSecondsLeft?: number | null;
  downloadProblem?: string | null;
  needBytes?: number;
  switching?: boolean;
}

/* The installer's own words for the same failures (Baxy.Installer/Texts.cs). */
const TUNED_DOWNLOAD: Record<string, Words> = {
  sin_red: { es: 'No logré conectarme a internet para bajarlo. Revisa tu conexión y vuelve a intentarlo. Lo que ya bajé no se pierde', en: 'I couldn’t connect to the internet to download it. Check your connection and try again. What I already downloaded isn’t lost' },
  sin_espacio: { es: 'Falta espacio en el disco. Libera espacio y vuelve a intentarlo. Lo que ya bajé no se pierde', en: 'There isn’t enough disk space. Free some space and try again. What I already downloaded isn’t lost' },
  danado: { es: 'Llegó dañado y no lo voy a usar. Vuelve a intentarlo y lo bajo de nuevo', en: 'It arrived damaged and I won’t use it. Try again and I’ll download it again' },
  no_disponible: { es: 'Hugging Face no lo entregó. Vuelve a intentarlo más tarde', en: 'Hugging Face didn’t serve it. Try again later' },
  sin_permiso: { es: 'Windows no me dejó guardarlo', en: 'Windows didn’t let me save it' },
  sin_disco: { es: 'Windows dio un error al guardarlo en el disco: puede que otro programa tenga el archivo abierto. Vuelve a intentarlo', en: 'Windows gave an error saving it to the disk: another program may have the file open. Try again' },
};

/* D6 (owner, 2026-11-09): the tuned model's download with the bar of every other download here; it said «Llevo X de Y». */
function TunedDownloadBar({ value, onStop }: { value: TunedModel; onStop: () => void }) {
  const t = useT();
  return (
    <DownloadBar what={t('BAXY ajustado', 'Tuned BAXY')} done={value.downloadedBytes ?? 0} total={value.bytes ?? 0}
      bytesPerSecond={value.downloadBytesPerSecond} secondsLeft={value.downloadSecondsLeft} onStop={onStop} />
  );
}

function TunedModelSection({ value, onChange, onSaved }: { value: TunedModel; onChange: (v: TunedModel) => void; onSaved: () => void }) {
  const t = useT();
  const gb = (bytes: number | undefined) => size(bytes ?? 0, t.locale);
  const [asking, setAsking] = useState(false);
  const noticeRef = useInnerDialog<HTMLDivElement>(() => setAsking(false));
  const [refused, setRefused] = useState<string | null>(null);
  const busy = !!value.downloading || !!value.switching;
  const send = async (method: 'PUT' | 'POST', path: string, body?: Record<string, unknown>) => {
    // REV_VISTA V-10: a refusal with its cause, and a request that got no answer not said as one (the App may have taken it).
    const { value: answer, refused: said, code } = await sendTold<TunedModel>(method, path, body ?? {});
    if (!answer?.file) {
      setRefused(!said ? t('No supe si se hizo: BAXY no respondió', 'I couldn’t tell whether it was done: BAXY didn’t answer')
        : code === 'tuned_model_no_space' ? t.w(TUNED_DOWNLOAD.sin_espacio) : code === 'tuned_model_not_installed' ? t('Primero instálalo', 'Install it first')
          // REV_APP TUN-a: the file to replace is still held (the model that is closing, another program)
          : code === 'tuned_model_file_busy' ? t('El archivo anterior todavía está en uso: espera un momento y vuelve a intentarlo', 'The earlier file is still in use: wait a moment and try again')
            : t('No se pudo hacer', 'It couldn’t be done'));
      return;
    }
    setRefused(null);
    onChange(answer);
    onSaved();
  };
  const [removing, setRemoving] = useState(false);
  const removeRef = useInnerDialog<HTMLDivElement>(() => setRemoving(false));
  const install = () => { setAsking(false); void send('POST', '/settings/tuned-model/install'); };
  const remove = () => { setRemoving(false); void send('PUT', '/settings/tuned-model', { remove: true }); };
  // the state is a small tag by the title (owner, 2026-11-08: a boxed «Cambiando…» beside the switch looked bad)
  const [tag, now] = value.switching ? ['busy', t('Cambiando…', 'Switching…')] : value.active ? ['on', t('En uso', 'In use')]
    : value.installed ? ['', t('Instalado, sin usar', 'Installed, not in use')] : ['', t('Sin instalar', 'Not installed')];
  const partial = !value.downloading && (value.downloadedBytes ?? 0) > 0 && !value.installed;
  const hint = value.downloading ? t('Al terminar se comprueba con SHA-256', 'When it ends it’s checked with SHA-256')
    : value.downloadProblem && TUNED_DOWNLOAD[value.downloadProblem] ? t.w(TUNED_DOWNLOAD[value.downloadProblem])
      : value.problem && TUNED_PROBLEM[value.problem] ? t.w(TUNED_PROBLEM[value.problem])
        : partial ? t(`Bajé ${gb(value.downloadedBytes)} de ${gb(value.bytes)}: sigue desde ahí`, `I downloaded ${gb(value.downloadedBytes)} of ${gb(value.bytes)}: it goes on from there`)
          : value.installed ? t('Comprobado con SHA-256. Se aplica al momento', 'Checked with SHA-256. It applies at once') : t('Opcional. No viene con BAXY: se descarga solo si lo pides', 'Optional. It doesn’t come with BAXY: it’s downloaded only if you ask');
  // INT11 (owner's order of 2026-11-08): BAXY uses the stock model; the tuned one is an unofficial extra, said before anything.
  return (<>
    <div className="panel-sec-head" style={{ marginTop: 16 }}>{t('Extras no oficiales', 'Unofficial extras')}</div>
    <div className="st-tip">{t('El modelo ajustado no forma parte del producto oficial ni de lo que se vende: lo publica el autor aparte en Hugging Face y usarlo es opcional.', 'The tuned model isn’t part of the official product or of what is sold: its author publishes it separately on Hugging Face, and using it is optional.')}</div>
    <div className="bxs-row">
      <div className="bxs-l">
        <span><span>{t('Modelo ajustado a BAXY (extra no oficial)', 'Model tuned for BAXY (unofficial extra)')}</span><em className={'bx-tag ' + tag} role="status">{now}</em></span>
        <span className="h">{hint}</span>
      </div>
      <div className="bxs-c">
        {value.installed
          ? <Toggle on={!!value.use} label={t('Usar el modelo ajustado', 'Use the tuned model')} locked={busy} onChange={(v) => void send('PUT', '/settings/tuned-model', { use: v })} />
          : value.downloading ? null
            : <button className="panel-btn ghost" onClick={() => setAsking(true)}>{partial ? t('Seguir instalando', 'Go on installing') : t('Instalar', 'Install')}</button>}
      </div>
    </div>
    {value.downloading && !value.installed ? <TunedDownloadBar value={value} onStop={() => void send('PUT', '/settings/tuned-model', { cancel: true })} /> : null}
    {value.installed ? (
      <div className="bxs-sub">
        <span>{t(`Ocupa ${gb(value.bytes)} en este PC`, `It takes ${gb(value.bytes)} on this PC`)}</span>
        <button className="bxs-link" disabled={busy || removing} onClick={() => setRemoving(true)}>{t('Quitar del PC', 'Remove from this PC')}</button>
      </div>
    ) : null}
    {removing ? (
      <div ref={removeRef} className="bxs-ask" role="dialog" aria-label={t('Quitar el modelo ajustado', 'Remove the tuned model')}>
        {t(`Se borra el archivo de ${gb(value.bytes)}. BAXY vuelve al modelo de serie; si lo quieres otra vez, hay que bajarlo de nuevo.`, `The ${gb(value.bytes)} file is deleted. BAXY goes back to the stock model; to have it again, it must be downloaded again.`)}
        <div className="btns">
          <button className="panel-btn ghost" onClick={() => setRemoving(false)} data-cancel>{t('Cancelar', 'Cancel')}</button>
          <button className="panel-btn warn" onClick={remove}>{t('Sí, quitarlo', 'Yes, remove it')}</button>
        </div>
      </div>
    ) : null}
    {asking ? (
      <div ref={noticeRef} className="st-tip" role="dialog" aria-label={t('Antes de descargar', 'Before downloading')}>
        {t(`Mejor precisión en BAXY: es Qwen3.5-4B ajustado por el autor de BAXY, que lo publica aparte como extra no oficial. Descarga de ${gb(value.bytes)} desde Hugging Face (${value.repo}). Licencia ${value.license}: es una obra derivada de Qwen3.5-4B, de Alibaba Cloud. Se comprueba con SHA-256 antes de usarlo. Necesitas ${gb(value.needBytes)} libres. El ajuste se entrenó con conversaciones sintéticas con recibos de trazas reales; no se usó texto privado de ninguna persona. Es opcional: si no lo instalas, BAXY usa Qwen3.5-4B de serie. Puedes volver al modelo de serie cuando quieras.`,
          `Better accuracy in BAXY: it’s Qwen3.5-4B tuned by BAXY’s author, who publishes it separately as an unofficial extra. A ${gb(value.bytes)} download from Hugging Face (${value.repo}). ${value.license} license: it’s a derivative work of Qwen3.5-4B, by Alibaba Cloud. It’s checked with SHA-256 before it’s used. You need ${gb(value.needBytes)} free. The fine-tune was trained on synthetic conversations whose tool receipts are taken from real traces; no private user text was used. It’s optional: unless you install it, BAXY uses the stock Qwen3.5-4B. You can go back to the stock model whenever you want.`)}
        <div style={{ display: 'flex', gap: 8, marginTop: 10 }}>
          <button className="panel-btn" onClick={install}>{t('Descargar', 'Download')}</button>
          <button className="panel-btn ghost" onClick={() => setAsking(false)} data-cancel>{t('Cancelar', 'Cancel')}</button>
        </div>
      </div>
    ) : null}
    {refused ? <div className="st-tip" role="alert">{refused}</div> : null}
  </>);
}

/* How far a model's download went, in whole percent, or null when nothing downloads (OpenModels: pullDone of pullTotal). */
function pullPercent(open: OpenState | undefined): number | null {
  return open?.pulling && open.pullTotal > 0 ? Math.min(100, Math.floor((open.pullDone / open.pullTotal) * 100)) : null;
}

/* Settings › Modelo (owner, 2026-11-08; design boards 13 to 16, approved): where BAXY thinks is one choice — the stock model,
   the tuned one, a local one (Ollama, from Hugging Face) or one by API — never two at once (the App keeps it so:
   MainWindowViewModel.KeepOneModel). Below, the model in use with what it takes and whether it sees, every model on this PC
   with its weight and an uninstall that asks first, then what the choice needs, and BAXY's memory, folded. */
type Where = 'serie' | 'ajustado' | 'local' | 'api';

/* Ollama's installed models (GET /settings/external-model/models while the provider is local): vision from /api/show, and
   their weight on disk when the host gives it. */
// VIVO1 F4: «profile», the tool profile with the most tools whose prompt fits this model's own context, when the chosen one does not.
// MOD1 V-07: «vramBytes», the video memory it takes at «vramContext», the least context BAXY would connect it with.
interface Installed {
  id: string; label: string; fits: boolean; why?: string | null; vision?: boolean; bytes?: number; profile?: string | null;
  vramBytes?: number | null; vramContext?: number | null;
}

// The translator's refusals that may pass by themselves (external_model.PASSING): a turn failed, the model was not refused.
const PASSING = ['limite', 'saturado', 'caido', 'lento', 'red'];

/* Chosen, but its start failed (the host said why and BAXY went back to its own model): not «connecting» (seen in the real
   App on the PC, 2026-11-09, «Conectando…» for good after the translator refused a model for RAM). The reason comes as a
   problem of the translator or as the model's error (the owner's capture: «No se conectó: … necesita unos 21,4 GB»). */
function failedToConnect(external: ExternalModel | null): boolean {
  return !!external?.enabled && !external.active && !external.switching && !!(external.problem || external.lastError);
}

function whereNow(external: ExternalModel | null, tuned: TunedModel | null): Where {
  if (external?.enabled && !failedToConnect(external)) return external.provider === 'local' ? 'local' : 'api';
  return tuned?.use ? 'ajustado' : 'serie';
}

function ModelTab({ alias, stockName, ownIsStock, metrics, external, onExternal, tuned, onTuned, localContext, onLocalContext }: {
  alias: string | null; stockName: string; ownIsStock: boolean | null; metrics: Metrics | null; external: ExternalModel | null; onExternal: (v: ExternalModel) => void;
  tuned: TunedModel | null; onTuned: (v: TunedModel) => void; localContext: LocalContextState | null; onLocalContext: (v: LocalContextState) => void;
}) {
  const t = useT();
  const gb = (bytes: number | undefined) => typeof bytes === 'number' && bytes > 0 ? size(bytes, t.locale) : '—';
  // Turned on but refused (it did not connect, with its error): BAXY runs its own model, and that is what the tab says runs
  // (the owner saw «Conectando…» above «No se conectó… BAXY sigue con su modelo», 2026-11-09).
  const notConnected = failedToConnect(external);
  const active = notConnected ? (tuned?.use ? 'ajustado' : 'serie') : whereNow(external, tuned);
  // What the person is looking at: the model in use until they pick another place; picking applies at once when it can.
  const [picked, setPicked] = useState<Where | null>(null);
  // The section shown is the one chosen, even when its start failed: its reason and choices are there (no_cabe_vram).
  const where = picked ?? (external?.enabled ? (external.provider === 'local' ? 'local' : 'api') : active);
  const [asking, setAsking] = useState<{ name: string; bytes?: number; tuned: boolean } | null>(null);
  const uninstallRef = useInnerDialog<HTMLDivElement>(() => setAsking(null));
  const [refused, setRefused] = useState<string | null>(null);
  const local = external?.provider === 'local';
  const [askOllama, setAskOllama] = useState(false);
  const ollamaUp = !!external?.open?.ollamaRunning;
  const listFor = external && (local || ollamaUp || askOllama) ? `${external.model}|${external.active}|${external.open?.pulling ?? ''}|${askOllama}` : null;
  const [installed, setInstalled] = useState<{ for: string; models: Installed[] } | null>(null);
  // VIVO1: uninstalling a model not in use leaves listFor as it was: the list is asked again all the same
  const [removals, setRemovals] = useState(0);
  useEffect(() => {
    if (listFor === null) return undefined;
    let current = true;
    void getJson<{ models?: Installed[] }>('/settings/external-model/models?provider=local').then((l) => { if (current) setInstalled({ for: listFor, models: l?.models ?? [] }); });
    return () => { current = false; };
  }, [listFor, removals]);
  const ollama = listFor !== null && installed?.for === listFor ? installed.models : [];
  // REV_VISTA V-02: the App keeps one model (KeepOneModel: the one just chosen stays, the other goes off in the same request)
  // and each request answers only its own state, so after one is saved the other is read again: kept as it was, the tab said
  // two models in use and «Usar» on the one the App had turned off sent nothing.
  const rereadExternal = useCallback(async () => {
    const e = await getJson<ExternalModel>('/settings/external-model');
    if (e?.providers) onExternal(e);
  }, [onExternal]);
  const rereadTuned = useCallback(async () => {
    const v = await getJson<TunedModel>('/settings/tuned-model');
    if (v?.available) onTuned(v);
  }, [onTuned]);
  // What the host refuses is said with its cause (REV_VISTA V-01: a refused «Usar» said nothing and looked taken).
  const putExternal = async (body: Record<string, unknown>, say: (refusal: string) => void = setRefused) => {
    const { value: v, code } = await sendTold<ExternalModel>('PUT', '/settings/external-model', body);
    if (v?.providers) { onExternal(v); await rereadTuned(); }
    else say(t.w(EXTERNAL_REFUSED[code ?? ''] ?? NOT_SAVED));
    return !!v?.providers;
  };
  // The ways out of «no cabe», beside the model in use: their refusal is said there, not in the list below.
  const [outRefused, setOutRefused] = useState<string | null>(null);
  const wayOut = (body: Record<string, unknown>) => {
    setRefused(null);
    setOutRefused(null);
    void putExternal(body, setOutRefused);
  };
  // A model of this PC is asked for as this PC's, in the same PUT (V-01): sent alone, its name went to the place chosen
  // before, and with an API chosen the conversation left for it (takeLocal, below).
  const putTuned = async (body: Record<string, unknown>) => {
    const v = await send<TunedModel>('PUT', '/settings/tuned-model', body);
    if (v?.available) { onTuned(v); await rereadExternal(); }
    return !!v?.available;
  };
  // VIS1: a row of Ollama's is a local model whatever is chosen above (the rows are listed whenever Ollama runs), and the
  // host keeps a model under the provider in force (ExternalModel.Apply): the provider goes with it, in the same request.
  // VIVO1 F4 / VIVO2 F15: a model short of the chosen profile goes with the profile that fits it, in that same request,
  // which the App takes whole or not at all (a profile sent first stayed changed when the model was refused).
  // What the host refuses is said with its cause (MOD1 V-01). VIS1: a request not answered may have been taken or not
  // (field-native-bridge.js answers 503 when the host takes too long): what the host has is read again, and a model it did
  // not take is said, with the tab back where the person had it (unless they picked another place while it waited). If
  // the reading gets no answer either, nothing is known, and that is what is said.
  const takeLocal = async (model: string, profile?: string) => {
    const before = picked;
    setRefused(null);
    setPicked('local');
    const { value: v, refused: said, code } = await sendTold<ExternalModel>('PUT', '/settings/external-model',
      { provider: 'local', model, enabled: true, ...(profile ? { profile } : {}) });
    if (v?.providers) { onExternal(v); await rereadTuned(); return; }
    if (said) {
      setPicked((p) => (p === 'local' ? before : p));
      setRefused(t.w(EXTERNAL_REFUSED[code ?? ''] ?? NOT_SAVED));
      return;
    }
    const now = await getJson<ExternalModel>('/settings/external-model');
    if (now?.providers) onExternal(now);
    if (now?.enabled && now.provider === 'local' && now.model === model) return;
    setPicked((p) => (p === 'local' ? before : p));
    setRefused(now?.providers ? t('No se pudo cambiar de modelo', 'The model couldn’t be changed')
      : t('BAXY no contestó: no se sabe si cambió de modelo.', 'BAXY didn’t answer: it’s unknown whether the model changed.'));
  };
  const pickWithProfile = (model: string, profile: string) => takeLocal(model, profile);
  const choose = async (w: Where) => {
    setPicked(w);
    setRefused(null);
    if (w === 'serie') {
      if (external?.enabled) await putExternal({ enabled: false });
      if (tuned?.use) await putTuned({ use: false });
    } else if (w === 'ajustado') {
      if (tuned?.installed && active !== 'ajustado') await putTuned({ use: true });
    } else if (w === 'local') {
      if (external && !local) await putExternal({ provider: 'local' });
    } else if (external && local) {
      await putExternal({ provider: external.providers.find((p) => p.id !== 'local' && p.hasKey)?.id ?? 'anthropic' });
    }
  };
  const uninstall = async () => {
    const what = asking;
    setAsking(null);
    if (!what) return;
    if (what.tuned) { await putTuned({ remove: true }); return; }
    setRefused(null);
    const { value: answer, refused: said, code } = await sendTold<ExternalModel>('POST', '/settings/external-model/remove', { name: what.name });
    if (answer?.providers) { onExternal(answer); setInstalled(null); setRemovals((n) => n + 1); return; }
    // REV_VISTA V-10: said with its cause («No se pudo desinstalar» for all but one). With no answer, or a model Ollama no
    // longer has, the list is asked again: it says what is there.
    if (!said || code === 'open_models_not_found') setRemovals((n) => n + 1);
    setRefused(!said ? t('No supe si se desinstaló: BAXY no respondió. Míralo en esta lista', 'I couldn’t tell whether it was uninstalled: BAXY didn’t answer. See it in this list')
      : NOT_REMOVED[code ?? ''] ? t.w(NOT_REMOVED[code!]) : t('No se desinstaló', 'It wasn’t uninstalled'));
  };
  const places: [Where, string, string][] = [
    ['serie', t('De serie', 'Stock'), stockName],
    ...(tuned ? [['ajustado', t('Ajustado', 'Tuned'), t('Extra no oficial', 'Unofficial extra')] as [Where, string, string]] : []),
    ...(external ? [['local', t('Local', 'Local'), t('Ollama · Hugging Face', 'Ollama · Hugging Face')] as [Where, string, string],
      ['api', 'API', t('Sale a internet', 'Goes online')] as [Where, string, string]] : []),
  ];
  // the model in use, said as the host says it
  // Chosen but not connected yet (Ollama loading it, the API answering): said as the model chosen, connecting — never as
  // the stock model, which only runs meanwhile (seen in the real App, 2026-11-09).
  const other = !!external?.active || (!!external?.enabled && !notConnected);
  const byApi = other && (external?.active ? !external.activeLocal : external?.provider !== 'local');
  const name = external?.active ? external.activeModel ?? '—' : external?.enabled && !notConnected ? external.model || '—' : tuned?.active ? t('BAXY ajustado', 'Tuned BAXY') : alias ?? '—';
  const origin = other ? (byApi ? t('Por API · sale a internet', 'By API · goes online') : t('Local · Ollama', 'Local · Ollama'))
    : tuned?.active ? t('Extra no oficial', 'Unofficial extra') : t('De serie · en este PC', 'Stock · on this PC');
  // VIVO1 F4: connected and every turn refused said «Conectado»; the last line of its log says the refusal until a turn answers.
  // A line the translator wrote with no kind (a turn cut on the way) is a failed turn too: said here, as every reason is.
  // REV_VISTA V-04: said in the view's language by its kind, about this place and this model
  const failing = { provider: external?.provider, model: external?.active ? external.activeModel : external?.model };
  const refusedWhy = external?.active ? translatorSaid(external.lastError, t, failing) : undefined;
  const refusedKind = refusedWhy ? /^ERROR\[(\w+)\]/.exec(external?.lastError ?? '')?.[1] : undefined;
  // REV_VISTA V-08: why the chosen model did not connect, once and here (it was said in the state, and again, twice, in its
  // section below). What did not fit the card says its figures and its ways out; a line an older start left in the
  // translator's log is not that start's reason (ExternalModel.StartAsync refuses it before the translator runs).
  const short = notConnected && external?.problem === 'no_cabe_vram' ? external.vramShort ?? null : null;
  const notConnectedWhy = !notConnected || short ? undefined
    : (external?.problem === 'no_cabe_vram' ? undefined : translatorSaid(external?.lastError, t, failing))
      ?? (external?.problem ? (EXTERNAL_PROBLEM[external.problem] ? t.w(EXTERNAL_PROBLEM[external.problem]) : external.problem) : undefined);
  // VIVO2 F15: the model was asked with a tool profile, which the App took back when it did not connect. Its ways out of
  // «no cabe» ask for it again with that profile, and say so.
  const lent = external?.profileBack?.model === external?.model && external?.profileBack && PROFILE_NAME[external.profileBack.profile] ? external.profileBack.profile : null;
  const withLent = lent ? { profile: lent } : {};
  const sayLent = lent ? t(`, con el perfil ${t.w(PROFILE_NAME[lent])}`, `, with the ${t.w(PROFILE_NAME[lent])} profile`) : '';
  const tok = (n: number) => num(n, t.locale);
  // VIVO2 F15: the profile put on for a model that did not connect is the person's old one again, and it is said.
  const back = external?.profileBack && !external.switching ? external.profileBack : null;
  const backName = back ? (PROFILE_NAME[back.profile] ? t.w(PROFILE_NAME[back.profile]) : back.profile) : '';
  const backSaid = !back ? null
    : back.back && PROFILE_NAME[back.back]
      ? t(`Volví al perfil de herramientas ${t.w(PROFILE_NAME[back.back])}, el que tenías: ${backName} era sólo para usar ${back.model}, que no se conectó.`,
        `I went back to the ${t.w(PROFILE_NAME[back.back])} tool profile, the one you had: ${backName} was only for using ${back.model}, which didn’t connect.`)
      : t(`Volví al perfil de herramientas que tenías: ${backName} era sólo para usar ${back.model}, que no se conectó.`,
        `I went back to the tool profile you had: ${backName} was only for using ${back.model}, which didn’t connect.`);
  const status = external?.switching || tuned?.switching ? t('Cambiando…', 'Switching…')
    : refusedWhy ? (!refusedKind || PASSING.includes(refusedKind) ? t('Falló el último turno', 'The last turn failed') : t('Rechaza los turnos', 'Refuses the turns'))
      : external?.active ? (byApi ? t('Conectado a la API', 'Connected to the API') : t('Conectado', 'Connected'))
        : notConnected ? t(`No se conectó ${external?.model ?? ''}`, `${external?.model ?? 'It'} didn’t connect`)
          : external?.enabled ? t('Conectando…', 'Connecting…') : null;
  // The development launcher may give the mind another file as BAXY's own (scripts/run_renew.cmd): said, never named stock.
  const notStock = !other && !tuned?.active && ownIsStock === false;
  const pct = pullPercent(external?.open);
  const pulling = external?.open?.pulling ?? null;
  const sees = other ? external?.sees ?? null : null;
  const chosenOllama = external?.active ? external.activeModel : external?.model;
  // A model of Ollama's in use is measured too: the rail's reading counts the Ollama BAXY opened (FieldTelemetrySampler).
  const vram = other && byApi ? t('En la nube', 'In the cloud') : other && !external?.active ? '—' : gbOf(metrics?.model_vram_gb, t.locale);
  // MOD1 V-07 / VIVO2 F11: each model on this PC says what it takes on disk, named so (the one figure it had was unlabelled, and
  // the stock model's was «—»), and on the card: the one that runs, what the card holds of it now, as the box above; another,
  // the App's estimate from its own file with the context it is for. What the host did not say is not said.
  const disk = (bytes: number | null | undefined) => typeof bytes === 'number' && bytes > 0
    ? <>{size(bytes, t.locale)}<small>{t('en disco', 'on disk')}</small></> : '—';
  const measured = typeof metrics?.model_vram_gb === 'number' && Number.isFinite(metrics.model_vram_gb) ? gbOf(metrics.model_vram_gb, t.locale) : null;
  const onCard = (runs: boolean, bytes: number | null | undefined, context: number | null | undefined, least: boolean) => {
    if (runs && measured) return <span className="mem">{t(`${measured} de VRAM ahora`, `${measured} of VRAM now`)}</span>;
    if (typeof bytes !== 'number' || !(bytes > 0) || !context) return null;
    const cells = num(context, t.locale);
    return (
      <span className="mem">{least
        ? t(`desde unos ${size(bytes, t.locale)} de VRAM, con ${cells} tokens de contexto`, `from about ${size(bytes, t.locale)} of VRAM, with ${cells} tokens of context`)
        : t(`unos ${size(bytes, t.locale)} de VRAM con ${cells} tokens de contexto`, `about ${size(bytes, t.locale)} of VRAM with ${cells} tokens of context`)}</span>
    );
  };
  return (<>
    <div className="bx-pick" role="radiogroup" aria-label={t('Dónde piensa BAXY', 'Where BAXY thinks')} onKeyDown={radioKeys(false)}>
      {places.map(([id, label, sub], i) => (
        <button key={id} className={'bx-pick-o' + (where === id ? ' on' : '') + (active === id ? ' live' : '')} role="radio" aria-checked={where === id}
          tabIndex={rovingIndex(i, places.findIndex(([x]) => x === where))} onClick={() => void choose(id)}>
          <span className="t"><span className="dot" />{label}</span>
          <span className="s">{active === id ? t('En uso · ', 'In use · ') : ''}{sub}</span>
        </button>
      ))}
    </div>
    <div className="bx-inuse" aria-label={t('Modelo en uso', 'Model in use')}>
      <div className="nm"><span className="name">{name}</span><span className="bx-tag on">{origin}</span>
        {sees === true ? <span className="bx-tag">{t('Con visión', 'Sees')}</span> : sees === false ? <span className="bx-tag busy">{t('Sin visión', 'No vision')}</span> : null}</div>
      <div className="facts">
        <span className="bx-fact"><em>{t('Memoria de vídeo', 'Video memory')}</em>{vram}</span>
        {external?.active && !byApi && (external.activeContext ?? external.context) ? <span className="bx-fact"><em>{t('Contexto', 'Context')}</em>{num((external.activeContext ?? external.context)!, t.locale)} tokens</span> : null}
        {status ? <span className="bx-fact"><em>{t('Estado', 'State')}</em><span className={'st' + (notConnected ? ' bad' : '')}>{status}</span></span> : null}
      </div>
      {notStock ? <div className="note">{t(`Este perfil usa ${alias ?? 'otro archivo'} como modelo propio: no es el modelo de serie (${stockName}).`, `This profile uses ${alias ?? 'another file'} as its own model: it isn’t the stock model (${stockName}).`)}</div> : null}
      {refusedWhy ? <div className="note" role="status">{refusedWhy}</div> : null}
      {notConnectedWhy ? <div className="note" role="alert">{notConnectedWhy}</div> : null}
      {short ? (
        <div className="note" role="alert">
          {t(`Con ${tok(short.context)} tokens de contexto necesita unos ${size(short.needBytes, t.locale)} de VRAM y tu tarjeta tiene ${size(short.freeBytes, t.locale)} libres: no lo cargué.`,
            `With ${tok(short.context)} tokens of context it needs about ${size(short.needBytes, t.locale)} of VRAM and your card has ${size(short.freeBytes, t.locale)} free: I didn’t load it.`)}
          <div style={{ display: 'flex', gap: 8, marginTop: 8, flexWrap: 'wrap' }}>
            {short.fittingContext ? <button className="panel-btn" onClick={() => wayOut({ context: short.fittingContext, ...withLent })}>{t(`Usar ${tok(short.fittingContext)} tokens, que caben`, `Use ${tok(short.fittingContext)} tokens, which fit`) + sayLent}</button> : null}
            {short.partialPossible ? <button className="panel-btn ghost" onClick={() => wayOut({ partialRam: true, ...withLent })}>{t('Cargarlo en parte en la RAM (mucho más lento)', 'Load it partly in RAM (much slower)') + sayLent}</button> : null}
          </div>
          {outRefused ? <div style={{ marginTop: 8 }}>{outRefused}</div> : null}
        </div>
      ) : null}
      {backSaid ? <div className="note" role="status">{backSaid}</div> : null}
      {sees === false ? <div className="note">{t('Este modelo no ve: BAXY no podrá ver la pantalla ni imágenes. Lee el texto de la pantalla igual.', 'This model doesn’t see: BAXY won’t be able to see the screen or images. It reads the screen’s text all the same.')}</div> : null}
    </div>
    {pulling && pct !== null && where !== 'local' ? (
      <DownloadBar what={pulling.replace(/^hf\.co\//, '')} done={external!.open!.pullDone} total={external!.open!.pullTotal}
        bytesPerSecond={external!.open!.pullBytesPerSecond} secondsLeft={external!.open!.pullSecondsLeft}
        onStop={() => void send<ExternalModel>('POST', '/settings/external-model/cancel').then((v) => { if (v?.providers) onExternal(v); })} />
    ) : null}
    {tuned?.downloading && !tuned.installed && where !== 'ajustado' ? <TunedDownloadBar value={tuned} onStop={() => void putTuned({ cancel: true })} /> : null}
    <Fold id="instalados" open title={t('Modelos en este PC', 'Models on this PC')} summary={String(1 + (tuned?.installed ? 1 : 0) + ollama.length)}>
      <div className="bx-installed">
        <div className="bx-irow"><span className="n">{stockName}<span className="bx-tag">{t('De serie', 'Stock')}</span>
          {onCard(!other && !tuned?.active, localContext?.stock?.vramBytes, localContext?.stock?.vramContext, false)}</span><span className="w">{disk(localContext?.stock?.bytes)}</span>
          <span className="a">{active === 'serie' ? <span className="live">{t('En uso', 'In use')}</span> : <button className="panel-btn ghost" onClick={() => void choose('serie')}>{t('Usar', 'Use')}</button>}
            <button className="panel-btn ghost" disabled title={t('Viene con BAXY: lo necesita para funcionar', 'It comes with BAXY: it needs it to work')}>{t('Desinstalar', 'Uninstall')}</button></span></div>
        {tuned?.installed ? (
          <div className="bx-irow"><span className="n">{t('BAXY ajustado', 'Tuned BAXY')}<span className="bx-tag busy">{t('Extra no oficial', 'Unofficial extra')}</span>
            {onCard(!other && !!tuned.active, localContext?.tuned?.vramBytes, localContext?.tuned?.vramContext, false)}</span><span className="w">{disk(localContext?.tuned?.bytes ?? tuned.bytes)}</span>
            <span className="a">{active === 'ajustado' ? <span className="live">{t('En uso', 'In use')}</span> : <button className="panel-btn ghost" onClick={() => void choose('ajustado')}>{t('Usar', 'Use')}</button>}
              <button className="panel-btn ghost" disabled={!!tuned.switching} onClick={() => setAsking({ name: t('BAXY ajustado', 'Tuned BAXY'), bytes: tuned.bytes, tuned: true })}>{t('Desinstalar', 'Uninstall')}</button></span></div>
        ) : null}
        {ollama.map((m) => {
          // «En uso» is the one chosen, as for the stock and tuned rows and the box above (connecting, it is already the one in
          // use); one still running while BAXY switches away from it is not, but it cannot be uninstalled until it stops.
          const inUse = active === 'local' && chosenOllama === m.id;
          const runs = !!external?.active && external.activeModel === m.id;
          return (
            <div key={m.id} className="bx-irow"><span className="n">{m.id}<span className="bx-tag">{t('Local · Ollama', 'Local · Ollama')}</span>
              {m.vision === false ? <span className="bx-tag" title={t('BAXY no podrá ver la pantalla ni imágenes con él', 'BAXY won’t see the screen or images with it')}>{t('Sin visión', 'No vision')}</span> : m.vision ? <span className="bx-tag">{t('Con visión', 'Sees')}</span> : null}
              {!m.fits && !inUse ? <span className="why">{m.profile ? t('necesita un perfil más pequeño', 'it needs a smaller profile') : m.why}</span> : null}
              {onCard(runs && !byApi, m.vramBytes, m.vramContext, true)}</span>
              <span className="w">{disk(m.bytes)}</span>
              <span className="a">{inUse ? <span className="live">{t('En uso', 'In use')}</span> : <button className="panel-btn ghost" disabled={!m.fits} title={m.fits ? undefined : m.why ?? undefined} onClick={() => void takeLocal(m.id)}>{t('Usar', 'Use')}</button>}
                {!m.fits && !inUse && m.profile && PROFILE_NAME[m.profile] ? <button className="panel-btn ghost" title={m.why ?? undefined}
                  onClick={() => void pickWithProfile(m.id, m.profile!)}>{t('Usar con ', 'Use with ') + t.w(PROFILE_NAME[m.profile])}</button> : null}
                <button className="panel-btn ghost" disabled={inUse || runs} title={inUse || runs ? t('Está en uso: elige otro antes', 'It’s in use: choose another first') : undefined} onClick={() => setAsking({ name: m.id, bytes: m.bytes, tuned: false })}>{t('Desinstalar', 'Uninstall')}</button></span></div>
          );
        })}
        {external && listFor === null ? (
          <div className="bx-irow note"><span className="n" style={{ color: 'var(--t-second)' }}>{t('Ollama está cerrado: sus modelos se ven al abrirlo', 'Ollama is closed: its models show once it’s open')}</span><span className="w" />
            <span className="a"><button className="panel-btn ghost" onClick={() => setAskOllama(true)}>{t('Ver los modelos de Ollama', 'Show Ollama’s models')}</button></span></div>
        ) : null}
        {asking ? (
          <div ref={uninstallRef} className="bxs-ask" role="dialog" aria-label={t('Desinstalar ', 'Uninstall ') + asking.name}>
            <span><b>{t(`¿Desinstalar ${asking.name}?`, `Uninstall ${asking.name}?`)}</b> {asking.tuned ? (asking.bytes ? t(`Se borra de este PC y libera ${gb(asking.bytes)}.`, `It’s deleted from this PC and frees ${gb(asking.bytes)}.`) : t('Se borra de este PC.', 'It’s deleted from this PC.')) : t('Se borra de Ollama en este PC, también para otros programas que lo usen', 'It’s deleted from Ollama on this PC, also for other programs that use it') + (asking.bytes ? t(`, y libera hasta ${gb(asking.bytes)}: menos si otro modelo comparte sus archivos.`, `, and frees up to ${gb(asking.bytes)}: less if another model shares its files.`) : '.')} {t('Para volver a usarlo habrá que bajarlo otra vez.', 'To use it again it must be downloaded again.')}</span>
            <span className="btns"><button className="panel-btn ghost" onClick={() => setAsking(null)} data-cancel>{t('Cancelar', 'Cancel')}</button><button className="panel-btn warn" onClick={() => void uninstall()}>{t('Sí, desinstalar', 'Yes, uninstall')}</button></span>
          </div>
        ) : null}
        {refused ? <div className="st-tip" role="alert">{refused}</div> : null}
      </div>
    </Fold>
    {where === 'ajustado' && tuned ? <TunedModelSection value={tuned} onChange={onTuned} onSaved={() => void rereadExternal()} /> : null}
    {/* The context BAXY's own model runs with (LocalContext, vram-contexto): stock and tuned alike, folded under them (INT17). */}
    {(where === 'serie' || where === 'ajustado') && localContext ? (
      <Fold id="contexto-baxy" open title={t('Contexto', 'Context')}
        summary={localContext.chosen ? `${num(localContext.chosen, t.locale)} tokens` : t('Automático', 'Automatic')}>
        <LocalContextRow value={localContext} onChange={onLocalContext} tuned={!!tuned} ownRuns={!other} />
      </Fold>
    ) : null}
    {(where === 'local' || where === 'api') && external ? <ExternalModelSection value={external} onChange={onExternal} onSaved={() => void rereadTuned()} mode={where} /> : null}
    <MemoryBreakdown model={external?.active ? null : alias} />
    <div className="st-tip">{t('Si un dato no se puede leer, se muestra «—», nunca 0.', 'A reading that can’t be taken shows “—”, never 0.')}</div>
  </>);
}

/* Settings → Behavior (owner's order of 2026-11-08): the person's own texts for BAXY's personality, replies and
   preferences (PersonBehavior in the App, behavior.py in the mind). They are words in its instructions: what it can do and
   what it asks before doing it stay the same. Saving one relaunches the mind on it, which reads its instructions once. */
type BehaviorField = 'personality' | 'replies' | 'preferences';
interface Behavior {
  /** BAXY's name and identity: fixed, nobody edits it (owner's limit of 2026-11-08); null until the mind said it */
  identity: string | null;
  factory: Record<BehaviorField, string> | null;
  texts: Record<BehaviorField, string | null>;
  maxChars: number;
  switching: boolean;
}

const BEHAVIOR_FIELDS: [BehaviorField, Words, Words][] = [
  ['personality', { es: 'Personalidad y tono', en: 'Personality and tone' }, { es: 'Cómo suena BAXY: su carácter y su tono', en: 'How BAXY sounds: its character and tone' }],
  ['replies', { es: 'Cómo responde', en: 'How it replies' }, { es: 'Largo, idioma y trato de sus respuestas', en: 'Length, language and manner of its replies' }],
  ['preferences', { es: 'Tus preferencias', en: 'Your preferences' }, { es: 'Lo que quieres que tenga siempre en cuenta', en: 'What you want it to always keep in mind' }],
];

const BEHAVIOR_REFUSED: Record<string, Words> = {
  behavior_too_long: { es: 'Es demasiado largo', en: 'It’s too long' },
  behavior_not_saved: { es: 'Windows no me dejó guardarlo', en: 'Windows didn’t let me save it' },
};

const sameText = (a: string, b: string) => a.trim() === b.trim();

function BehaviorText({ field, label, hint, value, onSend }: { field: BehaviorField; label: string; hint: string; value: Behavior; onSend: (body: Record<string, unknown>) => void }) {
  const t = useT();
  const factory = value.factory?.[field] ?? '';
  const own = value.texts[field];
  const shown = own ?? factory;
  // What is shown changes only by a new state from the host, which mounts this box again (its key): the draft starts there,
  // or where the person left it unsaved (REV_VISTA V-05: another tab, Escape or a click outside took it).
  const [draft, setDraft] = useDraft('behavior.' + field, shown, sameText);
  const id = 'bxs-behavior-' + field;
  const changed = draft.trim() !== shown.trim();
  const long = draft.trim().length > value.maxChars;
  // The factory's own words, or nothing, go back as «no text of mine».
  const save = () => onSend({ [field]: draft.trim() === factory.trim() ? null : draft });
  return (
    <div className="bxs-text">
      <label className="bxs-l" htmlFor={id}><span>{label}{own === null ? null : <em className="ro">{t('tuyo', 'yours')}</em>}</span><span className="h">{hint}</span></label>
      <textarea id={id} className="st-input" value={draft} rows={field === 'preferences' ? 3 : 4} disabled={value.switching || !value.factory}
        aria-describedby={id + '-n'} aria-invalid={long}
        placeholder={!value.factory ? t('BAXY está arrancando…', 'BAXY is starting…')
          : field === 'preferences' ? t('Por ejemplo: llámame por mi nombre, Ana; cuando hables de dinero usa pesos chilenos', 'For example: call me by my name, Ana; when you talk about money use euros')
            : field === 'personality' ? t('Por ejemplo: con humor seco y muy paciente cuando algo falla', 'For example: with dry humor and very patient when something fails') : ''}
        onChange={(e) => setDraft(e.target.value)} />
      <div className="foot">
        <span id={id + '-n'} className={'n' + (long ? ' hot' : '')}>{draft.trim().length} / {value.maxChars}{long ? t(' · demasiado largo', ' · too long') : ''}</span>
        {own !== null ? <button className="panel-btn ghost" disabled={value.switching} onClick={() => { forgetDraft('behavior.' + field); onSend({ [field]: null }); }}>{t('Restaurar', 'Restore')}</button> : null}
        <button className="panel-btn" disabled={!changed || long || value.switching} onClick={save}>{t('Guardar', 'Save')}</button>
      </div>
      {factory ? (
        <details>
          <summary>{t('Ver el texto de fábrica', 'See the factory text')}</summary>
          <p>{factory}</p>
        </details>
      ) : null}
    </div>
  );
}

function BehaviorSection({ value, onChange }: { value: Behavior; onChange: (v: Behavior) => void }) {
  const t = useT();
  const [refused, setRefused] = useState<string | null>(null);
  const send = async (body: Record<string, unknown>) => {
    let answer: (Behavior & { error?: string }) | null = null;
    try {
      const r = await fetch('/settings/behavior', { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
      answer = await r.json() as Behavior & { error?: string };
    } catch { /* said below */ }
    if (!answer?.texts) {
      setRefused(t.w(BEHAVIOR_REFUSED[answer?.error ?? ''] ?? { es: 'No se pudo guardar', en: 'It couldn’t be saved' }));
      return;
    }
    setRefused(null);
    for (const field of Object.keys(body)) forgetDraft('behavior.' + field);
    onChange(answer);
  };
  const anyOwn = BEHAVIOR_FIELDS.some(([field]) => value.texts[field] !== null);
  return (<>
    <div className="st-tip" role="note">
      {t('Aquí cambias cómo habla BAXY: su personalidad, cómo te responde y lo que quieres que tenga en cuenta. ', 'Here you change how BAXY talks: its personality, how it replies and what you want it to keep in mind. ')}
      <b className="bone">{t('No cambia lo que puede hacer ni lo que te pregunta antes de hacerlo.', 'It doesn’t change what it can do or what it asks you before doing it.')}</b>
      {t(' BAXY está medido con los textos de fábrica: con los tuyos puede acertar menos, y siempre puedes restaurarlos. Al guardar, BAXY vuelve a leer sus instrucciones una vez: tarda unos segundos, más en una tarjeta lenta. Sus instrucciones están en español; puedes escribir en español o en inglés.', ' BAXY is measured with the factory texts: with yours it may get things right less often, and you can always restore them. When you save, BAXY reads its instructions again once: it takes a few seconds, longer on a slow card. Its instructions are in Spanish; you can write in Spanish or English.')}
    </div>
    {value.switching ? <div className="st-tip" role="status">{t('Aplicando tus cambios…', 'Applying your changes…')}</div> : null}
    <div className="bxs-text">
      <div className="bxs-l"><span>{t('Nombre e identidad', 'Name and identity')}<em className="ro">{t('fijo', 'fixed')}</em></span><span className="h">{t('Su nombre es BAXY y esta parte no se puede editar: abre las instrucciones y, si cambias algún texto, una regla fija del nombre las cierra; aun así, un texto tuyo puede hacer que a veces diga otro nombre', 'Its name is BAXY and this part can’t be edited: it opens the instructions and, if you change any text, a fixed rule on the name closes them; even so, a text of yours can make it give another name at times')}</span></div>
      <p className="bxs-fixedtext">{value.identity ?? t('BAXY está arrancando…', 'BAXY is starting…')}</p>
    </div>
    {BEHAVIOR_FIELDS.map(([field, label, hint]) => <BehaviorText key={field + ':' + (value.texts[field] ?? value.factory?.[field] ?? '')} field={field} label={t.w(label)} hint={t.w(hint)} value={value} onSend={(body) => void send(body)} />)}
    {refused ? <div className="st-tip" role="alert">{refused}</div> : null}
    {anyOwn ? <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: 12 }}><button className="panel-btn ghost" disabled={value.switching} onClick={() => void send({ reset: true })}>{t('Restaurar todo de fábrica', 'Restore all factory texts')}</button></div> : null}
  </>);
}

interface Props {
  onClose: () => void;
  theme: 'dark' | 'light';
  onTheme: (t: 'dark' | 'light') => void;
  /** the interface's language: this view's own presentation, like the theme */
  lang: LangChoice;
  onLang: (l: LangChoice) => void;
  bypass: boolean;
  onBypass: (v: boolean) => void;
  mic: MicMode;
  micAvailable: boolean;
  /** V132: why «Siempre» cannot answer to «BAXY» (no wake word), or null */
  noWake?: string | null;
  onMic: (m: MicMode) => void;
  a11y: A11y;
  onA11y: (a: A11y) => void;
  general: GeneralSettings | null;
  onGeneral: (patch: Partial<GeneralSettings>) => void;
  metrics: Metrics | null;
  netLog: NetEntry[];
  /** REV_VISTA V-03: some of this conversation went to an API (the host marks its turns), also in an earlier run */
  apiPast?: boolean;
  /** how long the engine's confirmation waits (the host's), null while unknown */
  confirmSeconds: number | null;
  onMemory: () => void;
  /** the section it opens on */
  initialTab?: Tab;
  proposals: ProposalSettings | null;
  proposalSeconds: number | null;
  onProposals: (p: Partial<ProposalSettings>) => void;
  look: Look;
  onLook: (l: Look) => void;
}

// licenses/PRIVACIDAD.md says the same twice: its title, then «## Español» and «## English». The view's language is shown.
function policyIn(text: string, english: boolean): string {
  const at = text.search(/^## English\s*$/m);
  if (at < 0) return text;
  return english ? text.slice(0, text.indexOf('\n') + 1) + '\n' + text.slice(at) : text.slice(0, at);
}

export function SettingsPanel({ onClose, theme, onTheme, lang, onLang, bypass, onBypass, mic, micAvailable, noWake = null, onMic, a11y, onA11y, general, onGeneral, metrics, netLog, apiPast = false, confirmSeconds, onMemory, initialTab = 'general', proposals, proposalSeconds, onProposals, look, onLook }: Props) {
  const t = useT();
  const [tab, setTab] = useState<Tab>(initialTab);
  const [find, setFind] = useState('');
  // REV_VISTA V-05: the footer said «Los cambios se guardan al momento» over texts that keep only with «Guardar»; it says what
  // is saved how, and which tabs hold something written and not saved yet (drafts.ts keeps it until then).
  const drafts = useDraftKeys();
  const unsaved = TABS.filter(([id]) => drafts.some((k) => draftTab(k) === id)).map(([, name]) => t.w(name));
  // V5 D4: Sin frenos is a conscious choice, asked once more in its own row before it is sent
  const [askBypass, setAskBypass] = useState(false);
  const bypassRef = useInnerDialog<HTMLDivElement>(() => setAskBypass(false));
  const [legalProblem, setLegalProblem] = useState<string | null>(null);
  const legalSaid = (code: string | null) => setLegalProblem(code === 'legal_not_found'
    ? t('No encontré los textos legales en la carpeta de BAXY: están en la carpeta «licenses» del paquete que bajaste', 'I didn’t find the legal texts in BAXY’s folder: they’re in the «licenses» folder of the package you downloaded')
    : t('Windows no abrió el texto: está en la carpeta «licenses» de BAXY', 'Windows didn’t open the text: it’s in BAXY’s «licenses» folder'));
  const openLicenses = async () => {
    setLegalProblem(null);
    const { value, code } = await sendTold('POST', '/settings/legal/open', { doc: 'licenses' });
    if (!value) legalSaid(code);
  };
  // VIS3 (VIVO6 fila 4): the policy is a .md, and a Windows with no program for .md showed «Open with» instead of it. Its text
  // is shown here, drawn by the answers' own renderer (markdown.tsx), which needs nothing installed.
  const [policy, setPolicy] = useState<string | null>(null);
  const togglePolicy = async () => {
    setLegalProblem(null);
    if (policy !== null) { setPolicy(null); return; }
    const told = await getJson<{ text?: string }>('/settings/legal/privacy');
    if (typeof told?.text === 'string') setPolicy(told.text);
    else legalSaid('legal_not_found');
  };
  const needle = find.trim().toLowerCase();
  const shownTabs = TABS.filter(([, l, k]) => !needle || (t.w(l) + ' ' + t.w(k)).toLowerCase().includes(needle));
  const ref = useDialogFocus<HTMLDivElement>();
  const [voice, setVoice] = useState<{ tts?: { name?: string; downloaded?: boolean }; wake?: { downloaded?: boolean } } | null>(null);
  const [model, setModel] = useState<{ modelAlias?: string; stockName?: string; ownIsStock?: boolean | null } | null>(null);
  const [external, setExternal] = useState<ExternalModel | null>(null);
  const [tuned, setTuned] = useState<TunedModel | null>(null);
  const [behavior, setBehavior] = useState<Behavior | null>(null);
  const [localContext, setLocalContext] = useState<LocalContextState | null>(null);
  useEffect(() => {
    void getJson<typeof voice>('/voice/inventory').then(setVoice);
    void getJson<{ modelAlias?: string }>('/settings').then(setModel);
    void getJson<ExternalModel>('/settings/external-model').then((e) => setExternal(e?.providers ? e : null));
    void getJson<TunedModel>('/settings/tuned-model').then((v) => setTuned(v?.available ? v : null));
    void getJson<Behavior>('/settings/behavior').then((b) => setBehavior(b?.texts ? b : null));
    void getJson<LocalContextState>('/settings/local-context').then((c) => setLocalContext(c?.options ? c : null));
  }, []);
  // While the mind is relaunched on a new context (or still starting, with its graphics card not known yet), read every second.
  const localContextBusy = !!localContext && (localContext.switching || localContext.automatic === null);
  useEffect(() => {
    if (!localContextBusy) return undefined;
    const every = setInterval(() => { void getJson<LocalContextState>('/settings/local-context').then((c) => { if (c?.options) setLocalContext(c); }); }, 1000);
    return () => clearInterval(every);
  }, [localContextBusy]);
  // While the mind is relaunched on the person's texts (or still starting, with no factory texts known yet), read every second.
  const behaviorBusy = !!behavior && (behavior.switching || behavior.factory === null);
  useEffect(() => {
    if (!behaviorBusy) return undefined;
    const every = setInterval(() => { void getJson<Behavior>('/settings/behavior').then((b) => { if (b?.texts) setBehavior(b); }); }, 1000);
    return () => clearInterval(every);
  }, [behaviorBusy]);
  // While a model downloads (the tuned one, Ollama or one of its models) or the mind switches, both models' states are read
  // every second, and once more when it ends, with the model shown: the App turns one off when the other is chosen, also by
  // itself when «Instalar y usar» ends (REV_VISTA V-02), and a download's bar is shown outside its own section too.
  const modelsBusy = !!tuned?.downloading || !!tuned?.switching || !!external?.switching || !!external?.open?.pulling || !!external?.open?.ollamaInstalling;
  useEffect(() => {
    if (!modelsBusy) return undefined;
    const read = () => {
      void getJson<TunedModel>('/settings/tuned-model').then((v) => { if (v?.available) setTuned(v); });
      void getJson<ExternalModel>('/settings/external-model').then((e) => { if (e?.providers) setExternal(e); });
    };
    const every = setInterval(read, 1000);
    // …and the files of BAXY's own models, which an install or a change of model moves (MOD1 V-07).
    return () => {
      clearInterval(every); read(); void getJson<{ modelAlias?: string }>('/settings').then(setModel);
      void getJson<LocalContextState>('/settings/local-context').then((c) => { if (c?.options) setLocalContext(c); });
    };
  }, [modelsBusy]);
  // VIS1: BAXY thinks with one model (the host's KeepOneModel: turning one on turns the other off, in the same request),
  // and each request answers with the state of the one it asked for. Holding both as on, the other's state is an old one.
  const bothOn = !!external?.enabled && !!tuned?.use;
  useEffect(() => {
    if (!bothOn) return;
    void getJson<ExternalModel>('/settings/external-model').then((e) => { if (e?.providers) setExternal(e); });
    void getJson<TunedModel>('/settings/tuned-model').then((v) => { if (v?.available) setTuned(v); });
  }, [bothOn]);
  const byApi = external?.active && !external.activeLocal ? external.activeModel : null;
  const g = general;
  const lock = g === null;
  const tts = voice?.tts?.name ? 'Supertonic · ' + voice.tts.name + (voice.tts.downloaded ? '' : t(' · no está en disco', ' · not on disk')) : '—';
  return (
    <div className="panel-shroud" onClick={onClose}>
      <div ref={ref} tabIndex={-1} style={{ outline: 'none' }} className="panel settings-panel bxs" onClick={(e) => e.stopPropagation()} role="dialog" aria-modal="true" aria-label={t('Ajustes', 'Settings')}>
        <div className="panel-head">
          {/* BAXY's identity on all of Settings (owner, 2026-11-08; design boards 13 to 24): its face and its name */}
          <span className="bxs-head">
            <svg className="bxs-face" width="24" height="24" viewBox="0 0 26 26" fill="none" aria-hidden="true"><rect x="3" y="4" width="20" height="17" rx="7" stroke="var(--p-blue-hi)" strokeWidth="1.4" /><circle cx="9.5" cy="12" r="2.4" fill="var(--bx-hot)" /><circle cx="16.5" cy="12" r="2.4" fill="var(--bx-hot)" /><path d="M10 16.6q3 2 6 0" stroke="var(--p-blue-hi)" strokeWidth="1.3" strokeLinecap="round" /><circle cx="13" cy="2.2" r="1.4" stroke="var(--bx-hot)" strokeWidth="1" /></svg>
            <span className="bxs-brand">BAXY<small>{t('Ajustes', 'Settings')}</small></span>
          </span>
          <button className="bx-ib plain" onClick={onClose} title={t('Cerrar', 'Close')} aria-label={t('Cerrar', 'Close')}><Icon name="x" size={14} /></button>
        </div>
        <div className="settings-main">
        <div className="settings-tabs">
          <input className="settings-find" type="search" value={find} onChange={(e) => setFind(e.target.value)} placeholder={t('Buscar un ajuste', 'Search settings')} aria-label={t('Buscar un ajuste', 'Search settings')} />
          {/* REV_VISTA V-12: the sections are tabs (APG tabs, vertical, automatic activation; utils/radioKeys.ts tabKeys) */}
          <div className="settings-tablist" role="tablist" aria-orientation="vertical" aria-label={t('Secciones de ajustes', 'Settings sections')} onKeyDown={tabKeys}>
            {shownTabs.map(([id, l], i) => <button key={id} id={'bxs-tab-' + id} role="tab" aria-selected={tab === id} aria-controls="bxs-tabpanel"
              tabIndex={rovingIndex(i, shownTabs.findIndex(([x]) => x === tab))} className={'settings-tab' + (tab === id ? ' on' : '')} onClick={() => setTab(id)}>{t.w(l)}</button>)}
          </div>
          {shownTabs.length ? null : <span className="settings-none" role="status">{t('Ningún ajuste con esas palabras', 'No setting with those words')}</span>}
        </div>
        <div className="panel-body settings-body" role="tabpanel" id="bxs-tabpanel" aria-labelledby={'bxs-tab-' + tab}>
          {/* APP1 (REV_APP ASY-b): a switch the host could not write is said, not left to come back by itself */}
          {g?.unsaved || proposals?.unsaved ? <div className="bx-mem-empty" role="status">{t('No pude guardar este cambio en el disco. Vale mientras BAXY siga abierta y lo intento de nuevo con cada cambio; si cierras BAXY antes, vuelve lo de antes.', 'I couldn’t save this change to disk. It holds while BAXY stays open and I try again with each change; if you close BAXY first, the old setting comes back.')}</div> : null}
          {tab === 'personalizacion' ? (<>
            <Fold id="pers-textos" open title={t('Textos', 'Text')} summary={`${look.reply.toUpperCase()} · ${look.you.toUpperCase()}`}>
            <Row label={t('Tamaño de las respuestas de BAXY', 'Size of BAXY’s replies')}>
              <Seg label={t('Tamaño de las respuestas de BAXY', 'Size of BAXY’s replies')} value={look.reply} onChange={(v) => onLook({ ...look, reply: v })}
                options={[['m', t('Normal', 'Normal')], ['l', t('Grande', 'Large')], ['xl', t('Muy grande', 'Extra large')]]} />
            </Row>
            <Row label={t('Tamaño de tus mensajes', 'Size of your messages')}>
              <Seg label={t('Tamaño de tus mensajes', 'Size of your messages')} value={look.you} onChange={(v) => onLook({ ...look, you: v })}
                options={[['s', t('Pequeño', 'Small')], ['m', t('Normal', 'Normal')]]} />
            </Row>
            </Fold>
            <Fold id="pers-chat" title={t('Conversación', 'Conversation')} summary={look.chat === 'n' ? t('Estrecha', 'Narrow') : look.chat === 'm' ? t('Media', 'Medium') : t('Ancha', 'Wide')}>
            <Row label={t('Ancho de la conversación', 'Conversation width')} hint={t('Más ancha deja menos sitio a la cara', 'Wider leaves less room for the face')}>
              <Seg label={t('Ancho de la conversación', 'Conversation width')} value={look.chat} onChange={(v) => onLook({ ...look, chat: v })}
                options={[['n', t('Estrecha', 'Narrow')], ['m', t('Media', 'Medium')], ['w', t('Ancha', 'Wide')]]} />
            </Row>
            <Row label={t('Abrir siempre «Cómo lo comprobé»', 'Always open “How I checked it”')} hint={t('Si no, se abre solo mientras trabaja o si algo falla', 'Otherwise it opens by itself while it works or if something fails')}>
              <Toggle on={look.steps} label={t('Abrir siempre «Cómo lo comprobé»', 'Always open “How I checked it”')} onChange={(v) => onLook({ ...look, steps: v })} />
            </Row>
            </Fold>
            <Fold id="pers-cara" open title={t('Cara y borde', 'Face and border')} summary={look.ring === 'on' ? t('Borde animado', 'Running border') : look.ring === 'still' ? t('Borde quieto', 'Still border') : t('Sin borde', 'No border')}>
            <Row label={t('Subtítulos bajo la cara', 'Captions under the face')} hint={t('Lo que BAXY dice, también escrito bajo su cara', 'What BAXY says, also written under its face')}>
              <Toggle on={look.captions} label={t('Subtítulos bajo la cara', 'Captions under the face')} onChange={(v) => onLook({ ...look, captions: v })} />
            </Row>
            <Row label={t('Medidores del sistema en la barra', 'System readings in the sidebar')} hint={t('Procesador, gráfica, temperatura y memoria del modelo', 'Processor, graphics card, temperature and the model’s memory')}>
              <Toggle on={look.gauges} label={t('Medidores del sistema en la barra', 'System readings in the sidebar')} onChange={(v) => onLook({ ...look, gauges: v })} />
            </Row>
            <Row label={t('Borde de color', 'Coloured border')} hint={t('La luz que recorre el borde de la ventana y cambia con lo que hace BAXY', 'The light that runs round the window’s border and changes with what BAXY does')}>
              <Seg label={t('Borde de color', 'Coloured border')} value={look.ring} onChange={(v) => onLook({ ...look, ring: v })}
                options={[['on', t('Animado', 'Running')], ['still', t('Quieto', 'Still')], ['off', t('Apagado', 'Off')]]} />
            </Row>
            <Row label={t('Velocidad del borde', 'Border speed')} hint={look.ring === 'on' ? undefined : t('Sólo con el borde animado', 'Only with the running border')}>
              <Seg label={t('Velocidad del borde', 'Border speed')} locked={look.ring !== 'on'} value={look.ringSpeed} onChange={(v) => onLook({ ...look, ringSpeed: v })}
                options={[['slow', t('Lenta', 'Slow')], ['normal', t('Normal', 'Normal')], ['fast', t('Rápida', 'Fast')]]} />
            </Row>
            </Fold>
            <div className="st-tip">{t('Lo de arriba sólo cambia cómo se ve BAXY en este PC, no lo que hace. El tema y el idioma están en General.', 'The settings above only change how BAXY looks on this PC, not what it does. Theme and language are in General.')}
              {' '}<button className="bx-lnk" onClick={() => onLook(LOOK_DEFAULT)}>{t('Volver a lo de siempre', 'Back to the defaults')}</button></div>
            <Fold id="pers-overlay" title={t('Overlay mientras trabaja', 'Overlay while it works')}><OverlaySection /></Fold>
          </>) : null}
          {tab === 'general' ? (<>
            <Fold id="gen-idioma" open title={t('Idioma', 'Language')} summary={lang === 'auto' ? t('Automático', 'Automatic') : lang === 'es' ? 'Español' : 'English'}>
            <Pick label={t('Idioma de la interfaz', 'Interface language')} value={lang} onChange={onLang} options={[
              { v: 'auto', title: t('Automático', 'Automatic'), sub: t('El de tu Windows', 'Your Windows’ one') },
              { v: 'es', title: 'Español', sub: 'Siempre en español' },
              { v: 'en', title: 'English', sub: 'Always in English' }]} />
            <div className="st-tip">{t('Las respuestas de BAXY siguen el idioma en que le hablas.', 'BAXY replies in the language you use with it.')}</div>
            </Fold>
            <Fold id="gen-apariencia" title={t('Apariencia', 'Appearance')} summary={theme === 'dark' ? t('Oscuro', 'Dark') : t('Claro', 'Light')}>
              <Row label={t('Tema', 'Theme')}><Seg value={theme} onChange={onTheme} options={[['dark', t('Oscuro', 'Dark')], ['light', t('Claro', 'Light')]]} /></Row>
            </Fold>
            <Fold id="gen-arranque" open title={t('Arranque y bandeja', 'Startup and tray')} summary={[g?.autostart ? t('Con Windows', 'With Windows') : null, g?.closeToTray ? t('cerrar: bandeja', 'close: tray') : t('cerrar: salir', 'close: quit')].filter(Boolean).join(' · ')}>
            <Row label={t('Arrancar con Windows', 'Start with Windows')} hint={g?.autostartBlocked === 'steam_copy' || g?.autostartBlocked === 'itch_copy'
              // LEG1 §5: a store's copy was called a development copy (FieldProductChannel.AutostartBlocked)
              ? (g.autostartBlocked === 'steam_copy' ? t('La copia de Steam no arranca con Windows: ábrela desde Steam', 'The Steam copy doesn’t start with Windows: open it from Steam')
                : t('La copia de itch.io no arranca con Windows: ábrela desde la app de itch.io o desde su carpeta', 'The itch.io copy doesn’t start with Windows: open it from the itch app or from its folder'))
              : g?.autostartBlocked === 'not_this_copy' ? t('Esta copia de desarrollo no arranca con Windows: se abre con run_renew.cmd', 'This development copy doesn’t start with Windows: open it with run_renew.cmd')
              : g?.autostart === null ? t('No se pudo leer el inicio de Windows', 'Couldn’t read Windows startup') : t('Se queda en la bandeja del sistema', 'Stays in the system tray')}>
              <Toggle on={!!g?.autostart} label={t('Arrancar con Windows', 'Start with Windows')} locked={lock || g?.autostart === null} onChange={(v) => onGeneral({ autostart: v })} />
            </Row>
            <Row label={t('Al cerrar la ventana', 'When the window closes')} hint={g?.closeToTray ? t('Sigue escuchando desde la bandeja', 'Keeps listening from the tray') : t('BAXY se cierra del todo', 'BAXY quits completely')}>
              <Toggle on={!!g?.closeToTray} label={t('Al cerrar la ventana, seguir en la bandeja', 'When the window closes, stay in the tray')} locked={lock} onChange={(v) => onGeneral({ closeToTray: v })} />
            </Row>
            <Row label={t('Al minimizar', 'When minimized')} hint={g?.minimizeToTray ? t('Se esconde en la bandeja, fuera de la barra de tareas', 'It hides in the tray, out of the taskbar') : t('Queda en la barra de tareas', 'It stays in the taskbar')}>
              <Toggle on={!!g?.minimizeToTray} label={t('Al minimizar, ir a la bandeja', 'When minimized, go to the tray')} locked={lock} onChange={(v) => onGeneral({ minimizeToTray: v })} />
            </Row>
            </Fold>
            <Fold id="gen-version" open title={t('Versión', 'Version')}>
              <UpdateSection installed={g?.version ?? undefined} notice={g?.updateNotice !== false} locked={lock} onNotice={(v) => onGeneral({ updateNotice: v })} />
            </Fold>
          </>) : null}
          {tab === 'herramientas' ? <ToolsSection /> : null}
          {tab === 'comportamiento' ? (<>
            <Fold id="comp-textos" open title={t('Personalidad y respuestas', 'Personality and replies')} summary={behavior ? (Object.values(behavior.texts).some((v) => v !== null) ? t('Con tus textos', 'With your texts') : t('De fábrica', 'Factory')) : undefined}>
              {behavior ? <BehaviorSection value={behavior} onChange={setBehavior} /> : <div className="st-tip">{t('No se pudo leer este ajuste', 'This setting couldn’t be read')}</div>}
            </Fold>
            <Fold id="comp-propuestas" open title={t('Propuestas', 'Proposals')}>
              <ProposalsSection value={proposals} proposalSeconds={proposalSeconds} onChange={onProposals} />
            </Fold>
          </>) : null}
          {tab === 'confirmacion' ? (<>
            <Fold id="conf-antes" open title={t('Antes de actuar', 'Before acting')} summary={bypass ? t('Sin frenos', 'No brakes') : 'Normal'}>
            <Pick label={t('Antes de actuar', 'Before acting')} value={bypass || askBypass ? 'never' : 'risk'}
              onChange={(v) => { if (v === 'never') { if (!bypass) setAskBypass(true); } else { setAskBypass(false); onBypass(false); } }} options={[
                { v: 'risk', title: t('Normal', 'Normal'), sub: t('Te pregunta antes de lo destructivo o peligroso. Lo demás lo hace y lo comprueba.', 'It asks before anything destructive or dangerous. It does the rest and checks it.'), tag: t('Recomendado', 'Recommended'), tone: 'on' },
                { v: 'never', title: t('Sin frenos', 'No brakes'), sub: t('No pregunta. Mientras siga encendido se ve arriba, en su etiqueta.', 'It doesn’t ask. While it’s on, its label shows at the top.'), tag: t('Con cuidado', 'With care'), tone: 'busy' }]} />
            {askBypass && !bypass ? (
              <div ref={bypassRef} className="bxs-ask" role="alertdialog" aria-label={t('¿Activar sin frenos?', 'Turn on no brakes?')}>
                <b>{t('¿Activar sin frenos?', 'Turn on no brakes?')}</b>
                <span>{t('Lo que le pidas, BAXY lo hará sin preguntarte, aunque sea borrar, cerrar sin guardar o enviar. Arriba verás «Sin frenos» mientras siga encendido.', 'What you ask for, BAXY will do without asking you, even deleting, closing without saving or sending. You’ll see “No brakes” at the top while it’s on.')}</span>
                <span className="btns">
                  <button className="panel-btn ghost" onClick={() => setAskBypass(false)} data-cancel>{t('Cancelar', 'Cancel')}</button>
                  <button className="panel-btn warn" onClick={() => { setAskBypass(false); onBypass(true); }}>{t('Sí, activar sin frenos', 'Yes, turn on no brakes')}</button>
                </span>
              </div>
            ) : null}
            {t.lang === 'en' ? (
              <div className="st-tip">In <b className="bone">Normal</b>, BAXY asks only before something destructive or dangerous: deleting or emptying the Recycle Bin, losing unsaved work, sending or posting something, joining a call, installing or uninstalling programs, buying or paying, force-closing a program, and a command that changes something. With <b className="bone">no brakes</b>, it goes ahead without asking and the conversation says so. The card shows up in the conversation, never over your window, and waits {spoken(confirmSeconds, t)} for your answer; if you don’t answer, nothing is done.</div>
            ) : (
              <div className="st-tip">En <b className="bone">Normal</b>, BAXY pregunta sólo antes de lo destructivo o peligroso: borrar o vaciar la papelera, perder lo que no guardaste, enviar o publicar algo, entrar a una llamada, instalar o desinstalar programas, comprar o pagar, forzar el cierre de un programa y un comando que cambia algo. <b className="bone">Sin frenos</b>, lo hace sin preguntar y la conversación lo dice. La tarjeta aparece en la conversación, nunca encima de tu ventana, y espera tu respuesta {spoken(confirmSeconds, t)}; si no contestas, no se hace nada.</div>
            )}
            </Fold>
          </>) : null}
          {tab === 'voz' ? (<>
            <div className="st-tip">{t('La entrada por voz está en pruebas. Todo lo que BAXY hace se puede pedir también por escrito.', 'Voice input is in testing. Everything BAXY does can also be asked in writing.')}</div>
            <Fold id="voz-mic" open title={t('Micrófono', 'Microphone')} summary={mic === 'always' ? t('Escucha «BAXY»', 'Listens for “BAXY”') : mic === 'ptt' ? t('Al pulsar', 'Push to talk') : t('Apagado', 'Off')}>
            <Pick label={t('Micrófono', 'Microphone')} value={mic} onChange={(m) => (m === 'off' || (micAvailable && !(m === 'always' && noWake))) && onMic(m)} options={[
              { v: 'off', title: t('Apagado', 'Off'), sub: t('No escucha nada', 'It listens to nothing') },
              { v: 'ptt', title: t('Al pulsar', 'Push to talk'), sub: t('Escucha mientras mantienes el micrófono', 'It listens while you hold the microphone') },
              { v: 'always', title: t('Siempre', 'Always'), sub: t('Atento a «BAXY», en este PC', 'Listening for “BAXY”, on this PC') }]} />
            {!micAvailable || noWake ? <div className="st-tip" role="note">{!micAvailable ? t('No hay micrófono disponible', 'No microphone available') : noWake}</div> : null}
            <Row label={t('Sonido al despertar', 'Sound on wake')}><Toggle on={!!g?.wakeSound} label={t('Sonido al despertar', 'Sound on wake')} locked={lock || mic === 'off'} onChange={(v) => onGeneral({ wakeSound: v })} /></Row>
            <Row label={t('Ignorar lo que suena en el PC', 'Ignore what the PC is playing')} hint={t('Música y videos no entran en lo que oye ni la despiertan', 'Music and videos don’t count as speech or wake it')}><Toggle on={g?.echoCancel !== false} label={t('Ignorar lo que suena en el PC', 'Ignore what the PC is playing')} locked={lock || mic === 'off'} onChange={(v) => onGeneral({ echoCancel: v })} /></Row>
            </Fold>
            <Fold id="voz-su" open title={t('Su voz', 'Its voice')} summary={g?.voiceMuted ? t('Silenciada', 'Muted') : t('Activa', 'On')}>
            <Row label={t('Decir «Un momento»', 'Say “One moment”')} hint={t('Si una respuesta tarda más de 2,5 s, lo avisa en voz alta', 'If a reply takes longer than 2.5 s, it says so out loud')}><Toggle on={g?.waitNotice !== false} label={t('Decir «Un momento»', 'Say “One moment”')} locked={lock || !!g?.voiceMuted} onChange={(v) => onGeneral({ waitNotice: v })} /></Row>
            <Row label={t('Silenciar su voz', 'Mute BAXY’s voice')} hint={t('Seguirá respondiendo por escrito', 'It still replies in text')}><Toggle on={!!g?.voiceMuted} label={t('Silenciar su voz', 'Mute BAXY’s voice')} locked={lock} onChange={(v) => onGeneral({ voiceMuted: v })} /></Row>
            </Fold>
            <Fold id="voz-palabra" title={t('Palabra de activación y voz', 'Wake word and voice')} summary="BAXY">
            <Row label={t('Palabra de activación', 'Wake word')} ro hint={voice?.wake?.downloaded === false ? t('El modelo de activación no está en disco', 'The wake word model isn’t on disk') : undefined}><span className="bxs-fixed">BAXY</span></Row>
            <Row label={t('Voz de BAXY', 'BAXY’s voice')} ro><span className="bxs-fixed">{tts}</span></Row>
            </Fold>
          </>) : null}
          {tab === 'accesibilidad' ? (<>
            <Fold id="acc-modo" open title={t('Modo', 'Mode')} summary={a11y.on ? t('Accesible', 'Accessible') : 'Normal'}>
            <Pick label={t('Modo accesible', 'Accessible mode')} value={a11y.on ? 'on' : 'off'} onChange={(v) => onA11y({ ...a11y, on: v === 'on' })} options={[
              { v: 'off', title: 'Normal', sub: t('Como siempre', 'As always') },
              { v: 'on', title: t('Accesible', 'Accessible'), sub: t('Texto más grande, más contraste y botones más amplios', 'Larger text, more contrast and bigger buttons') }]} />
            <Row label={t('Tamaño del texto', 'Text size')} hint={a11y.on ? undefined : t('Sólo en el modo accesible', 'Only in accessible mode')}><Seg label={t('Tamaño del texto', 'Text size')} locked={!a11y.on} value={a11y.size} onChange={(v) => onA11y({ ...a11y, size: v })} options={[['m', t('Normal', 'Normal')], ['l', t('Grande', 'Large')], ['xl', t('Muy grande', 'Extra large')]]} /></Row>
            <Row label={t('Alto contraste', 'High contrast')}><Toggle on={a11y.contrast} label={t('Alto contraste', 'High contrast')} onChange={(v) => onA11y({ ...a11y, contrast: v })} /></Row>
            </Fold>
            <div className="st-tip">{t('Todo lo que hace BAXY se puede pedir por escrito y oír en voz alta; la entrada por voz está en pruebas. El modo cambia cómo se ve, no lo que puede hacer. Los perfiles «No vidente» y «Movilidad» están en desarrollo y aún no se pueden elegir.', 'Everything BAXY does can be asked for in writing and heard out loud; voice input is in testing. The mode changes how it looks, not what it can do. The “Blind or low vision” and “Mobility” profiles are in development and can’t be chosen yet.')}</div>
          </>) : null}
          {tab === 'extras' ? (<>
            <div className="st-tip">{t('No están probados como el resto de BAXY: pueden fallar o gastar más. Si algo va raro, apágalo aquí.', 'They aren’t tested like the rest of BAXY: they can fail or use more. If something goes wrong, turn it off here.')}</div>
            <Fold id="extras-ajustado" open title={t('Modelo ajustado a BAXY', 'Model tuned for BAXY')} summary={tuned ? (tuned.use ? t('En uso', 'In use') : tuned.installed ? t('Instalado', 'Installed') : t('Sin instalar', 'Not installed')) : undefined}>
            <Row label={t('Modelo ajustado a BAXY', 'Model tuned for BAXY')} hint={tuned ? t('Lo publica su autor aparte y no forma parte del producto oficial. Se instala y se elige en Modelo', 'Its author publishes it separately and it isn’t part of the official product. It’s installed and chosen in Model') : t('No está disponible en esta copia', 'Not available in this copy')}>
              {tuned ? <button className="panel-btn ghost" onClick={() => setTab('modelo')}>{t('Ir a Modelo', 'Go to Model')}</button> : null}
            </Row>
            </Fold>
          </>) : null}
          {tab === 'privacidad' ? (<>
            <Fold id="priv-donde" open title={t('Dónde piensa', 'Where it thinks')} summary={byApi ? t('Por API', 'By API') : t('En este PC', 'On this PC')}>
            {byApi
              ? <Row label={t('El modelo corre en este PC', 'The model runs on this PC')} ro hint={t('Ahora no: usas ', 'Not now: you use ') + byApi + t(' por API, y lo que le pases sale de este PC', ' by API, and what you give it leaves this PC')}><Toggle on={false} locked label={t('El modelo corre en este PC', 'The model runs on this PC')} /></Row>
              : <Row label={t('El modelo corre en este PC', 'The model runs on this PC')} ro hint={t('Lo que dices, tus archivos, tu pantalla y tus recuerdos no salen de tu computador, salvo en los casos que dice la política de privacidad', 'What you say, your files, your screen and your memories do not leave your computer, except in the cases the privacy policy lists')}><Toggle on locked label={t('El modelo corre en este PC', 'The model runs on this PC')} /></Row>}
            </Fold>
            <Fold id="priv-salidas" open title={t('Salidas a internet', 'Going online')} summary={[g?.web ? t('búsqueda', 'search') : null, g?.weather ? t('clima', 'weather') : null].filter(Boolean).join(' · ') || t('ninguna', 'none')}>
            {/* APP2 (REV11 A-1): each hint says what licenses/PRIVACIDAD.md says goes out under its switch (test_license_texts) */}
            <Row label={t('Búsqueda web', 'Web search')} hint={t('Lo que pides buscar, leer o bajar sale desde tu IP a DuckDuckGo, Wikipedia, Photon, Frankfurter, YouTube, la tienda de Steam o la página que pides; para «cerca de mí», antes tu IP a ipwho.is. Nunca tus archivos ni la conversación', 'What you ask to search for, read or download goes out from your IP to DuckDuckGo, Wikipedia, Photon, Frankfurter, YouTube, the Steam store or the page you ask for; for “near me”, your IP to ipwho.is first. Never your files or the conversation')}><Toggle on={!!g?.web} label={t('Búsqueda web', 'Web search')} locked={lock} onChange={(v) => onGeneral({ web: v })} /></Row>
            <Row label={t('Clima', 'Weather')} hint={t('Salen a MET Norway las coordenadas del lugar y tu IP; para «aquí», antes tu IP a ipwho.is. El nombre del lugar se busca en este PC y no sale', 'MET Norway gets the place’s coordinates and your IP; for “here”, your IP goes to ipwho.is first. The place’s name is looked up on this PC and doesn’t go out')}><Toggle on={!!g?.weather} label={t('Clima', 'Weather')} locked={lock} onChange={(v) => onGeneral({ weather: v })} /></Row>
            <Row label={t('Mirar la pantalla', 'Look at the screen')} hint={t('Lo que necesita ver: una ventana o la pantalla entera, con todos tus monitores, y el paso dice cuál. Sale de este PC sólo si usas un modelo por API', 'What it needs to see: one window or the whole screen, with all your monitors, and the step says which. It leaves this PC only if you use a model by API')}><Toggle on={!!g?.screen} label={t('Mirar la pantalla', 'Look at the screen')} locked={lock} onChange={(v) => onGeneral({ screen: v })} /></Row>
            </Fold>
            {/* REV_LEGAL LEG-15: the texts that go in BAXY's folder, opened from here (FieldProductChannel.OpenLegal) */}
            <Fold id="priv-legal" title={t('Privacidad y licencias', 'Privacy and licenses')} summary={t('Textos de la carpeta de BAXY', 'Texts in BAXY’s folder')}>
              <Row label={t('Política de privacidad', 'Privacy policy')} hint={t('Qué guarda BAXY, qué sale de este PC y cómo borrarlo', 'What BAXY keeps, what leaves this PC and how to delete it')}>
                <button className="panel-btn ghost" aria-expanded={policy !== null} onClick={() => void togglePolicy()}>{policy !== null ? t('Cerrar la política de privacidad', 'Close the privacy policy') : t('Abrir la política de privacidad', 'Open the privacy policy')}</button></Row>
              {policy !== null ? <div className="bx-legal" role="region" tabIndex={0} aria-label={t('Política de privacidad', 'Privacy policy')}><Marked text={policyIn(policy, t.lang === 'en')} /></div> : null}
              <Row label={t('Licencias', 'Licenses')} hint={t('La de BAXY y las de cada pieza de terceros que lleva', 'BAXY’s and those of every third-party piece it carries')}>
                <button className="panel-btn ghost" onClick={() => void openLicenses()}>{t('Abrir las licencias', 'Open the licenses')}</button></Row>
              {legalProblem ? <div className="st-tip" role="alert">{legalProblem}</div> : null}
            </Fold>
            <Fold id="priv-memoria" title={t('Memoria', 'Memory')} summary={t('Sólo en este PC', 'Only on this PC')}>
              <Row label={t('Memoria', 'Memory')}><button className="panel-btn ghost" onClick={onMemory}>{t('Ver y editar', 'View and edit')}</button></Row>
            </Fold>
            <Fold id="priv-sesion" open title={t('Salidas a internet de esta sesión', 'What went online this session')} summary={String(netLog.length)}>
            {byApi
              ? <div className="bxs-log"><Globe s={10} /><span>{t('La conversación sale hacia la API en cada turno.', 'The conversation goes out to the API every turn.')}</span></div>
              // REV_VISTA V-03: this box is this conversation's (its internet log); apiThisRun is BAXY's run, which may be another
              // conversation's, and a conversation opened again after a restart went out in a run that is over
              : apiPast ? <div className="bxs-log"><Globe s={10} /><span>{t('En esta conversación, lo que le pasaste mientras usabas un modelo por API salió de este PC.', 'In this conversation, what you gave BAXY while you used a model by API left this PC.')}</span></div>
              : external?.apiThisRun ? <div className="bxs-log"><Globe s={10} /><span>{t('Desde que se abrió BAXY se conectó un modelo por API: lo que le pasaste mientras estaba activo salió de este PC.', 'Since BAXY opened, a model by API was connected: what you gave it while it was on left this PC.')}</span></div> : null}
            {netLog.map((n, i) => <div key={i} className="bxs-log"><Globe s={10} /><span>{n.what}</span><span className="ts">{n.ts}</span></div>)}
            {netLog.length || byApi || apiPast || external?.apiThisRun ? null : <div className="bxs-log empty">{t('Ninguna. Todo se ha quedado en este PC.', 'None. Everything has stayed on this PC.')}</div>}
            </Fold>
          </>) : null}
          {tab === 'modelo' ? <ModelTab alias={model?.modelAlias ?? null} metrics={metrics} external={external} onExternal={setExternal} tuned={tuned} onTuned={setTuned} localContext={localContext} onLocalContext={setLocalContext} stockName={model?.stockName ?? 'Qwen3.5-4B'} ownIsStock={model?.ownIsStock ?? null} /> : null}
        </div>
        </div>
        <div className="settings-footer"><span className="bxs-foot" role="status">{unsaved.length
          ? t('Sin guardar: ', 'Not saved: ') + unsaved.join(' · ') + t('. Lo escrito se conserva aquí mientras BAXY siga abierto', '. What you wrote is kept here while BAXY stays open')
          : t('Interruptores y opciones se guardan al momento; lo que escribes, con «Guardar» o al salir de su campo', 'Switches and choices are saved right away; what you type, with “Save” or on leaving its box')}</span><button className="panel-btn" onClick={onClose}>{t('Listo', 'Done')}</button></div>
      </div>
    </div>
  );
}
