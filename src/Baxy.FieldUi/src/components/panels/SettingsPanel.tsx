import { useEffect, useState, type ReactNode } from 'react';
import { Icon, Globe } from '../Icon';
import { Seg, Toggle } from '../Panel';
import { getJson } from '../../api';
import { spoken } from '../../duration';
import { useDialogFocus } from '../../utils/dialogFocus';
import { useT, type LangChoice, type Words } from '../../i18n';
import type { GeneralSettings, Metrics, MicMode, NetEntry } from '../../types';

/* Settings (design settings.jsx BxSettings). The theme, text size and contrast are this view's own presentation; the
   rest is the host's (GET/PUT /settings/general, /confirmation, /accessibility) and changes what BAXY does. */

const TABS: [Tab, Words][] = [
  ['general', { es: 'General', en: 'General' }], ['confirmacion', { es: 'Confirmación', en: 'Confirmation' }], ['voz', { es: 'Voz', en: 'Voice' }],
  ['accesibilidad', { es: 'Accesibilidad', en: 'Accessibility' }], ['privacidad', { es: 'Privacidad', en: 'Privacy' }], ['modelo', { es: 'Modelo', en: 'Model' }],
];
type Tab = 'general' | 'confirmacion' | 'voz' | 'accesibilidad' | 'privacidad' | 'modelo';

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

function Bar({ label, v, max, unit }: { label: string; v: number | null | undefined; max: number; unit: string }) {
  const known = typeof v === 'number' && Number.isFinite(v);
  return (
    <div className="bx-res">
      <div className="h"><span className="k">{label}</span><span className="v">{known ? v.toFixed(1) : '—'}<span className="u"> / {max} {unit}</span></span></div>
      <div className={'b' + (known && v / max > 0.9 ? ' hot' : '')}><span style={{ width: known ? Math.min(100, (v / max) * 100) + '%' : '0%' }}></span></div>
    </div>
  );
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
  apiThisRun: boolean;
  switching: boolean;
  problem: string | null;
  lastError: string | null;
  spentUsd: number;
  ceilingUsd: number | null;
  ceilingHolds: boolean;
  context: number | null;
}

/* The context sizes for the chosen Ollama model and the memory of each (GET /settings/external-model/estimate). */
interface ContextEstimate {
  contextLength?: number;
  recommended?: number;
  options?: { context: number; bytes: number | null }[];
  vramTotalBytes?: number;
  vramFreeBytes?: number;
  commitFreeBytes?: number | null;
  error?: string;
}

/* What BAXY sends a model before any conversation (external_model in the mind). */
const PROMPT_TOKENS = 49000;
/* What the translator leaves free for everything else, and what a model takes of it per byte on the card (external_model). */
const MEMORY_RESERVE = 3 * 2 ** 30;
const COMMIT_PER_BYTE_ENGINE = 1.2;
const COMMIT_PER_BYTE_OLLAMA = 1.7;
const shortOfMemory = (estimate: ContextEstimate, option: { context: number; bytes: number | null }) =>
  !!option.bytes && !!estimate.commitFreeBytes && option.bytes * (estimate.contextLength && option.context > estimate.contextLength ? COMMIT_PER_BYTE_ENGINE : COMMIT_PER_BYTE_OLLAMA) + MEMORY_RESERVE > estimate.commitFreeBytes;

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
};

const EXTERNAL_REFUSED: Record<string, Words> = {
  external_model_no_key: { es: 'Primero guarda la clave', en: 'Save the key first' },
  external_model_no_model: { es: 'Primero elige el modelo', en: 'Choose the model first' },
  external_model_no_url: { es: 'Primero escribe la dirección de la API', en: 'Type the API address first' },
  external_model_invalid_url: { es: 'Escribe solo la dirección, con https://, sin clave ni parámetros', en: 'Type only the address, with https://, no key or parameters' },
  external_model_invalid_key: { es: 'Esa clave no sirve', en: 'That key doesn’t work' },
  external_model_invalid_ceiling: { es: 'El tope debe estar entre 0 y 1.000 USD', en: 'The cap must be between 0 and 1,000 USD' },
  external_model_invalid_context: { es: 'Ese contexto no sirve', en: 'That context doesn’t work' },
};

function ExternalModelSection({ value, onChange }: { value: ExternalModel; onChange: (v: ExternalModel) => void }) {
  const t = useT();
  const tokens = (n: number) => n.toLocaleString(t.locale);
  const gigabytes = (bytes: number) => (bytes / 2 ** 30).toLocaleString(t.locale, { minimumFractionDigits: 1, maximumFractionDigits: 1 }) + ' GB';
  const [key, setKey] = useState('');
  const [model, setModel] = useState(value.model);
  const [url, setUrl] = useState(value.url);
  const [ceiling, setCeiling] = useState(value.ceilingUsd === null ? '' : String(value.ceilingUsd));
  const [refused, setRefused] = useState<string | null>(null);
  useEffect(() => { setModel(value.model); setUrl(value.url); setKey(''); }, [value.provider, value.model, value.url]);
  useEffect(() => { setCeiling(value.ceilingUsd === null ? '' : String(value.ceilingUsd)); }, [value.ceilingUsd]);
  const [list, setList] = useState<ModelList | null>(null);
  const [asked, setAsked] = useState(0);
  // Asked when the provider, the key or the address changes, and when the panel opens: what this key can use is its own.
  useEffect(() => {
    let current = true;
    setList(null);
    void getJson<ModelList>('/settings/external-model/models').then((l) => { if (current) setList(l ?? { error: t('no se pudo preguntar la lista', 'the list couldn’t be asked for') }); });
    return () => { current = false; };
  }, [value.provider, value.hasKey, value.url, asked]);
  const [estimate, setEstimate] = useState<ContextEstimate | null>(null);
  // Asked for the model chosen: the first time, Ollama loads it for some seconds to measure it.
  useEffect(() => {
    setEstimate(null);
    if (value.provider !== 'local' || !value.model) return undefined;
    let current = true;
    void getJson<ContextEstimate>('/settings/external-model/estimate').then((e) => { if (current) setEstimate(e ?? { error: t('no se pudo calcular', 'it couldn’t be worked out') }); });
    return () => { current = false; };
    // And again on connecting: BAXY's own model is gone by then, and the memory it held with it.
  }, [value.provider, value.model, value.active]);
  const put = async (body: Record<string, unknown>) => {
    let answer: (ExternalModel & { error?: string }) | null = null;
    let ok = false;
    try {
      const r = await fetch('/settings/external-model', { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
      ok = r.ok;
      answer = await r.json() as ExternalModel & { error?: string };
    } catch { /* said below */ }
    if (!ok || !answer?.providers) {
      setRefused(t.w(EXTERNAL_REFUSED[answer?.error ?? ''] ?? { es: 'No se pudo guardar', en: 'It couldn’t be saved' }));
      return;
    }
    setRefused(null);
    if (body.key) setAsked((n) => n + 1);
    setKey('');
    onChange(answer);
  };
  // on, the switch takes what is written, so nothing typed a moment ago is left behind it; off, nothing written can refuse it
  const turn = (on: boolean) => void put(on ? { ...(key.trim() ? { key } : {}), model, url, enabled: true } : { enabled: false });
  const local = value.provider === 'local';
  const compatible = value.provider === 'compatible';
  const models = list?.models ?? [];
  const chosen = models.find((m) => m.id === value.model);
  const listNote = list === null ? (local ? t('Buscando tus modelos de Ollama…', 'Looking for your Ollama models…') : t('Buscando los modelos disponibles…', 'Looking for the available models…'))
    : list.ollama === 'missing' ? t('No encontré Ollama en este PC. Instálalo desde ollama.com y descarga un modelo: aparecerá aquí', 'I didn’t find Ollama on this PC. Install it from ollama.com and download a model: it will show up here')
      : list.needsKey ? t('Guarda tu clave y aquí aparecerán los modelos que puedes usar', 'Save your key and the models you can use will show up here')
        : list.needsUrl ? t('Escribe la dirección de la API y aquí aparecerán sus modelos', 'Type the API address and its models will show up here')
          : list.error ? t('No se pudo leer la lista: ', 'The list couldn’t be read: ') + list.error
            : !models.length ? (local ? t('Ollama no tiene modelos. Descarga uno y aparecerá aquí', 'Ollama has no models. Download one and it will show up here') : t('Esta clave no tiene modelos disponibles', 'This key has no models available'))
              : t('Al elegir uno, BAXY lo carga y se conecta', 'When you choose one, BAXY loads it and connects');
  const contextNow = value.context ?? estimate?.recommended ?? 0;
  const contextOption = estimate?.options?.find((o) => o.context === contextNow);
  const room = contextNow - PROMPT_TOKENS;
  const beyond = !!estimate?.contextLength && contextNow > estimate.contextLength;
  const contextNote = estimate === null ? t('Calculando cuánta VRAM usa: la primera vez, Ollama lo carga unos segundos', 'Working out how much VRAM it uses: the first time, Ollama loads it for a few seconds')
    : !estimate.options?.length ? (estimate.contextLength ? t(`Admite ${tokens(estimate.contextLength)} tokens y BAXY necesita más de ${tokens(PROMPT_TOKENS)}`, `It takes ${tokens(estimate.contextLength)} tokens and BAXY needs more than ${tokens(PROMPT_TOKENS)}`) : t('No se pudo calcular: ', 'It couldn’t be worked out: ') + (estimate.error ?? t('Ollama no respondió', 'Ollama didn’t answer')))
      : [
        t(`Deja unos ${tokens(room)} tokens para la conversación`, `It leaves about ${tokens(room)} tokens for the conversation`),
        estimate.vramTotalBytes ? t(`Tu tarjeta tiene ${gigabytes(estimate.vramTotalBytes)}`, `Your card has ${gigabytes(estimate.vramTotalBytes)}`) + (estimate.vramFreeBytes !== undefined ? t(` y hay ${gigabytes(estimate.vramFreeBytes)} libres`, ` and ${gigabytes(estimate.vramFreeBytes)} are free`) : '') : '',
        contextOption?.bytes && estimate.vramFreeBytes !== undefined && contextOption.bytes > estimate.vramFreeBytes
          ? (beyond ? t('No cabe: elige menos contexto', 'It doesn’t fit: choose less context') : t('No cabe entero: lo demás irá a la RAM y responderá más lento', 'It doesn’t all fit: the rest goes to RAM and it will answer more slowly')) : '',
        contextOption && estimate.commitFreeBytes && shortOfMemory(estimate, contextOption)
          ? t(`Este PC tiene ${gigabytes(estimate.commitFreeBytes)} de memoria libre: no se conectará con este contexto`, `This PC has ${gigabytes(estimate.commitFreeBytes)} of memory free: it won’t connect with this context`) : '',
        beyond ? t(`El modelo declara ${tokens(estimate.contextLength!)}: BAXY le amplía el límite y lo corre con su propio motor`, `The model declares ${tokens(estimate.contextLength!)}: BAXY raises the limit and runs it with its own engine`) : '',
        estimate.error ? t('No se pudo calcular la VRAM: ', 'The VRAM couldn’t be worked out: ') + estimate.error : '',
      ].filter(Boolean).join('. ');
  const capped = value.lastError?.startsWith('TOPE');
  const failed = capped ? undefined : value.lastError?.replace(/^ERROR[^:]*:\s*/, '');
  const now = value.switching ? t('Cambiando…', 'Switching…') : value.active ? value.activeModel + (value.activeLocal ? t(' en este PC', ' on this PC') : t(' por API', ' by API')) : t('El modelo de BAXY', 'BAXY’s model');
  const trouble = value.switching ? undefined
    : capped ? t('Llegaste al tope de gasto: súbelo o bórralo abajo, o apaga esta opción para volver al modelo de este PC', 'You reached the spending cap: raise or clear it below, or turn this option off to go back to this PC’s model')
    : failed ? (value.active ? failed : t('No se conectó: ', 'It didn’t connect: ') + failed + t('. BAXY sigue con su modelo', '. BAXY stays on its own model'))
      : value.problem && EXTERNAL_PROBLEM[value.problem] ? t.w(EXTERNAL_PROBLEM[value.problem]) : undefined;
  const connected = !value.switching && value.active && !failed;
  return (<>
    <div className="panel-sec-head" style={{ marginTop: 16 }}>{t('Otro modelo', 'Another model')}</div>
    <Row label={t('Usar otro modelo', 'Use another model')} hint={t('Se aplica al momento. Con esto activo, BAXY no carga su propio modelo', 'It applies at once. With this on, BAXY doesn’t load its own model')}>
      <Toggle on={value.enabled} label={t('Usar otro modelo', 'Use another model')} onChange={turn} />
    </Row>
    <Row label={t('Ahora usa', 'Now using')} ro hint={trouble || (connected ? (value.activeLocal ? t('Conectado', 'Connected') : t('Conectado a la API', 'Connected to the API')) : undefined)}><span className="bxs-fixed">{now}</span></Row>
    <Row label={t('Dónde está', 'Where it is')}><Seg value={value.provider} onChange={(v) => void put({ provider: v })} options={value.providers.map((p) => [p.id, p.id === 'compatible' ? t('Otra', 'Other') : p.label] as [string, string])} /></Row>
    {compatible ? (
      <Row label={t('Dirección de la API', 'API address')} hint={t('Debe hablar el formato de chat de OpenAI. Una dirección de este PC no necesita clave', 'It must speak OpenAI’s chat format. An address on this PC needs no key')}>
        <input className="st-input" value={url} maxLength={200} aria-label={t('Dirección de la API', 'API address')} placeholder="https://" onChange={(e) => setUrl(e.target.value)}
          onBlur={() => { if (url.trim() !== value.url) void put({ url }); }} />
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
        <select className="st-input" value={chosen ? value.model : ''} aria-label={t('Modelo', 'Model')} onChange={(e) => { if (e.target.value) void put({ model: e.target.value, enabled: true }); }}>
          <option value="">{t('Elige un modelo', 'Choose a model')}</option>
          {models.map((m) => <option key={m.id} value={m.id} disabled={!m.fits}>{m.label}{m.fits ? '' : ' · ' + m.why}</option>)}
        </select>
      ) : (
        !local && list?.error ? <input className="st-input" value={model} maxLength={200} aria-label={t('Modelo', 'Model')} placeholder={t('Nombre del modelo', 'Model name')} onChange={(e) => setModel(e.target.value)}
          onBlur={() => { if (model.trim() !== value.model) void put({ model }); }} /> : null
      )}
      <button className="panel-btn ghost" onClick={() => setAsked((n) => n + 1)}>{t('Actualizar', 'Refresh')}</button>
    </Row>
    {local && value.model ? (
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
    ) : null}
    {refused ? <div className="st-tip" role="alert">{refused}</div> : null}
    {local ? null : value.ceilingHolds
      ? <>
        <Row label={t('Gastado', 'Spent')} ro hint={t('Lo que costó con esta clave en este perfil, según los precios que BAXY conoce', 'What it cost with this key on this profile, by the prices BAXY knows')}><span className="bxs-fixed">{value.spentUsd.toFixed(2)} USD</span></Row>
        <Row label={t('Tope de gasto en USD', 'Spending cap in USD')} hint={t('Opcional. Vacío, no hay tope. Con un número, deja de llamar a la API al llegar a ese total', 'Optional. Empty means no cap. With a number, it stops calling the API on reaching that total')}>
          <input className="st-input" type="number" min={0} max={1000} step={1} value={ceiling} placeholder={t('Sin tope', 'No cap')} aria-label={t('Tope de gasto en USD', 'Spending cap in USD')} onChange={(e) => setCeiling(e.target.value)}
            onBlur={() => { const v = ceiling.trim() ? Number(ceiling) : null; if (v !== value.ceilingUsd) void put({ ceilingUsd: v }); }} />
        </Row>
      </>
      : <Row label={t('Gastado', 'Spent')} ro hint={t('BAXY no conoce los precios de este modelo: pon tu límite en la consola de esa empresa', 'BAXY doesn’t know this model’s prices: set your limit in that company’s console')}><span className="bxs-fixed">—</span></Row>}
    {local
      ? <div className="st-tip">{t('El modelo corre en Ollama y ', 'The model runs in Ollama and ')}<b className="bone">{t('la conversación no sale de este PC', 'the conversation doesn’t leave this PC')}</b>{t(', sin gasto por uso. BAXY abre Ollama si hace falta. Los modelos de Ollama que corren en su nube no se pueden elegir, porque saldrían de este PC. El modelo debe saber usar herramientas. BAXY le envía unos 49.000 tokens solo con sus herramientas, así que el contexto parte en 64.000. Con más contexto recuerda más conversación y usa más VRAM. Si no cabe en la memoria, BAXY lo dice y sigue con su modelo. BAXY está ajustada para su propio modelo, así que otro puede rendir distinto.', ', with no cost per use. BAXY opens Ollama if needed. Ollama models that run in its cloud can’t be chosen, because they’d leave this PC. The model must know how to use tools. BAXY sends it about 49,000 tokens with its tools alone, so the context starts at 64,000. With more context it remembers more of the conversation and uses more VRAM. If it doesn’t fit in memory, BAXY says so and stays on its own model. BAXY is tuned for its own model, so another one may perform differently.')}</div>
      : <div className="st-tip">{t('Con esto activo, lo que le pases a BAXY ', 'With this on, what you give BAXY ')}<b className="bone">{t('sale de este PC hacia esa empresa', 'leaves this PC for that company')}</b>{t(': lo que digas, lo que lea de tu pantalla, archivos y páginas, y las capturas de pantalla. Eso incluye también la conversación que ya tuviste con BAXY antes de activarlo. Lo paga tu cuenta de esa empresa, aparte de BAXY.', ': what you say, what it reads from your screen, files and pages, and screenshots. That also includes the conversation you already had with BAXY before turning it on. Your account with that company pays for it, separately from BAXY.')}</div>}
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
  onMic: (m: MicMode) => void;
  a11y: A11y;
  onA11y: (a: A11y) => void;
  general: GeneralSettings | null;
  onGeneral: (patch: Partial<GeneralSettings>) => void;
  metrics: Metrics | null;
  netLog: NetEntry[];
  /** how long the engine's confirmation waits (the host's), null while unknown */
  confirmSeconds: number | null;
  onMemory: () => void;
}

export function SettingsPanel({ onClose, theme, onTheme, lang, onLang, bypass, onBypass, mic, micAvailable, onMic, a11y, onA11y, general, onGeneral, metrics, netLog, confirmSeconds, onMemory }: Props) {
  const t = useT();
  const [tab, setTab] = useState<Tab>('general');
  const ref = useDialogFocus<HTMLDivElement>();
  const [voice, setVoice] = useState<{ tts?: { name?: string; downloaded?: boolean }; wake?: { downloaded?: boolean } } | null>(null);
  const [model, setModel] = useState<{ modelAlias?: string } | null>(null);
  const [external, setExternal] = useState<ExternalModel | null>(null);
  useEffect(() => {
    void getJson<typeof voice>('/voice/inventory').then(setVoice);
    void getJson<{ modelAlias?: string }>('/settings').then(setModel);
    void getJson<ExternalModel>('/settings/external-model').then((e) => setExternal(e?.providers ? e : null));
  }, []);
  const byApi = external?.active && !external.activeLocal ? external.activeModel : null;
  const otherLocal = external?.active && external.activeLocal ? external.activeModel : null;
  const switching = !!external?.switching;
  useEffect(() => {
    if (!switching) return undefined;
    const every = setInterval(() => { void getJson<ExternalModel>('/settings/external-model').then((e) => { if (e?.providers) setExternal(e); }); }, 1000);
    return () => clearInterval(every);
  }, [switching]);
  const g = general;
  const lock = g === null;
  const tts = voice?.tts?.name ? 'Supertonic · ' + voice.tts.name + (voice.tts.downloaded ? '' : t(' · no está en disco', ' · not on disk')) : '—';
  return (
    <div className="panel-shroud" onClick={onClose}>
      <div ref={ref} tabIndex={-1} style={{ outline: 'none' }} className="panel settings-panel bxs" onClick={(e) => e.stopPropagation()} role="dialog" aria-modal="true" aria-label={t('Ajustes', 'Settings')}>
        <div className="panel-head">
          <span className="panel-title">{t('Ajustes', 'Settings')}</span>
          <button className="bx-ib plain" onClick={onClose} title={t('Cerrar', 'Close')} aria-label={t('Cerrar', 'Close')}><Icon name="x" size={14} /></button>
        </div>
        <div className="settings-tabs" role="group" aria-label={t('Secciones de ajustes', 'Settings sections')}>
          {TABS.map(([id, l]) => <button key={id} className={'settings-tab' + (tab === id ? ' on' : '')} aria-pressed={tab === id} onClick={() => setTab(id)}>{t.w(l)}</button>)}
        </div>
        <div className="panel-body settings-body">
          {tab === 'general' ? (<>
            <Row label={t('Tema', 'Theme')}><Seg value={theme} onChange={onTheme} options={[['dark', t('Oscuro', 'Dark')], ['light', t('Claro', 'Light')]]} /></Row>
            <Row label={t('Idioma de la interfaz', 'Interface language')} hint={t('Las respuestas de BAXY siguen el idioma en que le hablas', 'BAXY replies in the language you use with it')}>
              <Seg value={lang} onChange={onLang} label={t('Idioma de la interfaz', 'Interface language')}
                options={[['auto', t('Automático (Windows)', 'Automatic (Windows)')], ['es', 'Español'], ['en', 'English']]} />
            </Row>
            <Row label={t('Arrancar con Windows', 'Start with Windows')} hint={g?.autostartBlocked === 'not_this_copy' ? t('Esta copia de desarrollo no arranca con Windows: se abre con run_renew.cmd', 'This development copy doesn’t start with Windows: open it with run_renew.cmd')
              : g?.autostart === null ? t('No se pudo leer el inicio de Windows', 'Couldn’t read Windows startup') : t('Se queda en la bandeja del sistema', 'Stays in the system tray')}>
              <Toggle on={!!g?.autostart} label={t('Arrancar con Windows', 'Start with Windows')} locked={lock || g?.autostart === null} onChange={(v) => onGeneral({ autostart: v })} />
            </Row>
            <Row label={t('Al cerrar la ventana', 'When the window closes')} hint={g?.closeToTray ? t('Sigue escuchando desde la bandeja', 'Keeps listening from the tray') : t('BAXY se cierra del todo', 'BAXY quits completely')}>
              <Toggle on={!!g?.closeToTray} label={t('Al cerrar la ventana, seguir en la bandeja', 'When the window closes, stay in the tray')} locked={lock} onChange={(v) => onGeneral({ closeToTray: v })} />
            </Row>
          </>) : null}
          {tab === 'confirmacion' ? (<>
            <Row label={t('Nivel de confirmación', 'Confirmation level')} hint={t('Lo mismo que el interruptor del panel: Normal o Bypass', 'Same as the rail’s switch: Normal or Bypass')}>
              <Seg value={bypass ? 'never' : 'risk'} onChange={(v) => onBypass(v === 'never')} options={[['risk', t('Lo arriesgado', 'Risky things')], ['never', t('Nada', 'Nothing')]]} />
            </Row>
            {t.lang === 'en' ? (
              <div className="st-tip">With <b className="bone">risky things</b>, BAXY asks only before something destructive or dangerous: deleting or emptying the Recycle Bin, losing unsaved work, sending or posting something, joining a call, installing or uninstalling programs, buying or paying, force-closing a program, and a command that changes something. With <b className="bone">nothing</b> (bypass), it goes ahead without asking and the conversation says so. The card shows up in the conversation, never over your window, and waits {spoken(confirmSeconds, t)} for your answer; if you don’t answer, nothing is done.</div>
            ) : (
              <div className="st-tip">Con <b className="bone">lo arriesgado</b>, BAXY pregunta sólo antes de lo destructivo o peligroso: borrar o vaciar la papelera, perder lo que no guardaste, enviar o publicar algo, entrar a una llamada, instalar o desinstalar programas, comprar o pagar, forzar el cierre de un programa y un comando que cambia algo. Con <b className="bone">nada</b> (bypass), lo hace sin preguntar y la conversación lo dice. La tarjeta aparece en la conversación, nunca encima de tu ventana, y espera tu respuesta {spoken(confirmSeconds, t)}; si no contestas, no se hace nada.</div>
            )}
          </>) : null}
          {tab === 'voz' ? (<>
            <Row label={t('Palabra de activación', 'Wake word')} ro hint={voice?.wake?.downloaded === false ? t('El modelo de activación no está en disco', 'The wake word model isn’t on disk') : t('En pruebas · próximamente disponible', 'In testing · coming soon')}><span className="bxs-fixed">BAXY</span></Row>
            <Row label={t('Voz de BAXY', 'BAXY’s voice')} ro><span className="bxs-fixed">{tts}</span></Row>
            <Row label={t('Micrófono', 'Microphone')} hint={micAvailable ? t('Entrada por voz: en pruebas · próximamente disponible', 'Voice input: in testing · coming soon') : t('No hay micrófono disponible', 'No microphone available')}>
              <Seg value={mic} onChange={(m) => (m === 'off' || micAvailable) && onMic(m)} options={[['always', t('Siempre', 'Always')], ['ptt', t('Al pulsar', 'Push to talk')], ['off', t('Apagado', 'Off')]]} />
            </Row>
            <Row label={t('Sonido al despertar', 'Sound on wake')}><Toggle on={!!g?.wakeSound} label={t('Sonido al despertar', 'Sound on wake')} locked={lock} onChange={(v) => onGeneral({ wakeSound: v })} /></Row>
            <Row label={t('Ignorar lo que suena en el PC', 'Ignore what the PC is playing')} hint={t('Música y videos no entran en lo que oye ni la despiertan', 'Music and videos don’t count as speech or wake it')}><Toggle on={g?.echoCancel !== false} label={t('Ignorar lo que suena en el PC', 'Ignore what the PC is playing')} locked={lock} onChange={(v) => onGeneral({ echoCancel: v })} /></Row>
            <Row label={t('Decir «Un momento»', 'Say “One moment”')} hint={t('Si una respuesta tarda más de 2,5 s, lo avisa en voz alta', 'If a reply takes longer than 2.5 s, it says so out loud')}><Toggle on={g?.waitNotice !== false} label={t('Decir «Un momento»', 'Say “One moment”')} locked={lock} onChange={(v) => onGeneral({ waitNotice: v })} /></Row>
            <Row label={t('Silenciar su voz', 'Mute BAXY’s voice')} hint={t('Seguirá respondiendo por escrito', 'It still replies in text')}><Toggle on={!!g?.voiceMuted} label={t('Silenciar su voz', 'Mute BAXY’s voice')} locked={lock} onChange={(v) => onGeneral({ voiceMuted: v })} /></Row>
          </>) : null}
          {tab === 'accesibilidad' ? (<>
            <Row label={t('Modo accesible', 'Accessible mode')} hint={t('Texto más grande, más contraste y botones más amplios', 'Larger text, more contrast and bigger buttons')}><Toggle on={a11y.on} label={t('Modo accesible', 'Accessible mode')} onChange={(v) => onA11y({ ...a11y, on: v })} /></Row>
            <Row label={t('Tamaño del texto', 'Text size')}><Seg value={a11y.size} onChange={(v) => onA11y({ ...a11y, size: v })} options={[['m', t('Normal', 'Normal')], ['l', t('Grande', 'Large')], ['xl', t('Muy grande', 'Extra large')]]} /></Row>
            <Row label={t('Alto contraste', 'High contrast')}><Toggle on={a11y.contrast} label={t('Alto contraste', 'High contrast')} onChange={(v) => onA11y({ ...a11y, contrast: v })} /></Row>
            <div className="st-tip">{t('Todo lo que hace BAXY se puede pedir y escuchar por voz. El modo cambia cómo se ve, no lo que puede hacer.', 'Everything BAXY does can be asked for and heard by voice. The mode changes how it looks, not what it can do.')}</div>
          </>) : null}
          {tab === 'privacidad' ? (<>
            {byApi
              ? <Row label={t('El modelo corre en este PC', 'The model runs on this PC')} ro hint={t('Ahora no: usas ', 'Not now: you use ') + byApi + t(' por API, y lo que le pases sale de este PC', ' by API, and what you give it leaves this PC')}><Toggle on={false} locked label={t('El modelo corre en este PC', 'The model runs on this PC')} /></Row>
              : <Row label={t('El modelo corre en este PC', 'The model runs on this PC')} ro hint={t('Nada de lo tuyo sale sin que lo pidas', 'Nothing of yours leaves unless you ask')}><Toggle on locked label={t('El modelo corre en este PC', 'The model runs on this PC')} /></Row>}
            <Row label={t('Búsqueda web', 'Web search')} hint={t('Sale la búsqueda, nunca tus archivos ni la conversación', 'Only the search goes out, never your files or the conversation')}><Toggle on={!!g?.web} label={t('Búsqueda web', 'Web search')} locked={lock} onChange={(v) => onGeneral({ web: v })} /></Row>
            <Row label={t('Clima', 'Weather')} hint={t('Sale solo el nombre de la ciudad', 'Only the city name goes out')}><Toggle on={!!g?.weather} label={t('Clima', 'Weather')} locked={lock} onChange={(v) => onGeneral({ weather: v })} /></Row>
            <Row label={t('Mirar la pantalla', 'Look at the screen')} hint={t('Solo la ventana que necesita, y lo dice en el paso', 'Only the window it needs, and the step says so')}><Toggle on={!!g?.screen} label={t('Mirar la pantalla', 'Look at the screen')} locked={lock} onChange={(v) => onGeneral({ screen: v })} /></Row>
            <Row label={t('Memoria', 'Memory')}><button className="panel-btn ghost" onClick={onMemory}>{t('Ver y editar', 'View and edit')}</button></Row>
            <div className="panel-sec-head" style={{ marginTop: 16 }}>{t('Salidas a internet de esta sesión', 'What went online this session')}</div>
            {byApi
              ? <div className="bxs-log"><Globe s={10} /><span>{t('La conversación sale hacia la API en cada turno.', 'The conversation goes out to the API every turn.')}</span></div>
              : external?.apiThisRun ? <div className="bxs-log"><Globe s={10} /><span>{t('Esta sesión usó un modelo por API: lo que le pasaste mientras estaba activo salió de este PC.', 'This session used a model by API: what you gave it while it was on left this PC.')}</span></div> : null}
            {netLog.map((n, i) => <div key={i} className="bxs-log"><Globe s={10} /><span>{n.what}</span><span className="ts">{n.ts}</span></div>)}
            {netLog.length || byApi || external?.apiThisRun ? null : <div className="bxs-log empty">{t('Ninguna. Todo se ha quedado en este PC.', 'None. Everything has stayed on this PC.')}</div>}
          </>) : null}
          {tab === 'modelo' ? (<>
            <Row label={t('Modelo', 'Model')} ro><span className="bxs-fixed">{byApi ? byApi + t(' por API', ' by API') : otherLocal ? otherLocal + t(' en este PC', ' on this PC') : model?.modelAlias ?? '—'}</span></Row>
            {/* The 4 GB and these readings are BAXY's own model: another model has neither. */}
            {byApi || otherLocal ? null : (<>
              <Row label={t('Límite de memoria', 'Memory limit')} ro hint={t('Lo máximo que puede ocupar el modelo', 'The most the model can take up')}><span className="bxs-fixed">4 GB</span></Row>
              <div style={{ display: 'grid', gap: 10, marginTop: 14 }}>
                <Bar label={t('Memoria de vídeo', 'Video memory')} v={metrics?.model_vram_gb} max={4} unit="GB" />
                <Bar label="RAM" v={metrics?.model_ram_gb} max={4} unit="GB" />
              </div>
              <div className="st-tip">{t('Si un dato no se puede leer, se muestra «—», nunca 0.', 'A reading that can’t be taken shows “—”, never 0.')}</div>
            </>)}
            {external ? <ExternalModelSection value={external} onChange={setExternal} /> : null}
          </>) : null}
        </div>
        <div className="settings-footer"><span className="bxs-foot">{t('Los cambios se guardan al momento', 'Changes are saved right away')}</span><button className="panel-btn" onClick={onClose}>{t('Listo', 'Done')}</button></div>
      </div>
    </div>
  );
}
