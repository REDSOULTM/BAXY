import { useCallback, useEffect, useMemo, useRef, useState, type CSSProperties } from 'react';
import { useBaxy } from './store';
import { getJson, send, sendTold } from './api';
import { Rail, type PanelId, type Profile } from './components/Rail';
import { Chat } from './components/Chat';
import { Boot, Caption } from './components/Caption';
import { Breakdown } from './components/Breakdown';
import { VoiceInput } from './components/VoiceInput';
import { Cosmos } from './components/Cosmos';
import { Face } from './components/face/Face';
import { AvatarVid } from './components/AvatarVid';
import { useLipActive } from './lip';
import { liveText } from './live';
import { Globe, Icon } from './components/Icon';
import { causeText, type FailureMemory, type FailureRead } from './causes';
import { MemoryPanel } from './components/panels/MemoryPanel';
import { CatalogPanel } from './components/panels/CatalogPanel';
import { SessionsPanel } from './components/panels/SessionsPanel';
import { TriggersPanel } from './components/panels/TriggersPanel';
import { ProposalsPanel } from './components/panels/ProposalsPanel';
import { SettingsPanel, type A11y } from './components/panels/SettingsPanel';
import type { BaxyState, GeneralSettings, Metrics, MicMode, ProposalSettings } from './types';
import { LangContext, systemLang, translator, type Lang, type LangChoice, type T, type Words } from './i18n';

/* BAXY v4/v5 (design_handoff_baxy): rail · face and neural network · conversation, over the cosmos, inside the frame's
   travelling ring. Everything shown comes from Baxy.App; this file only composes it and sends what the person does. */

/* design v5: BAXY is the Higgsfield video avatar with the live network drawn over it; ?avatar=live (or localStorage
   bx-avatar=live) shows the face drawn in code instead. The light theme always uses the drawn face (the hologram clips
   only read on dark), and so does any moment without a decoded frame. */
const AVATAR = (() => { try { return new URLSearchParams(location.search).get('avatar') || localStorage.getItem('bx-avatar') || 'video'; } catch { return 'video'; } })();

const MAX_REQUEST = 4096; /* MissionInput.MaximumCharacters */
const NARROW = 1100; /* below this layout width the chat floats over the face */
const RAIL = 192, CHATW = 330;

function stored<T extends string>(key: string, allowed: readonly T[], fallback: T): T {
  try {
    const v = localStorage.getItem(key);
    return v && (allowed as readonly string[]).includes(v) ? (v as T) : fallback;
  } catch {
    return fallback;
  }
}
function keep(key: string, value: string) {
  try { localStorage.setItem(key, value); } catch { /* presentation only */ }
}

// uso-116: «El modelo no está disponible» alone left a new user with nothing to do: it goes with why, when it is known.
function failureLabel(failure: string | null | undefined, cause: string | null | undefined, memory: FailureMemory | null | undefined, read: FailureRead | null | undefined, t: T): string {
  const words = FAILURE[failure ?? ''];
  const said = words ? t.w(words) : t('Algo falló', 'Something went wrong');
  const why = failure === 'mind_unavailable' ? causeText(cause, t, memory, read) : null;
  return why ? said + ': ' + why : said;
}

// the shell's failure codes (MainWindowViewModel.Failure, FieldProductChannel.AgentStatus) said as the state they are.
const FAILURE: Record<string, Words> = {
  mind_unavailable: { es: 'El modelo no está disponible', en: 'The model isn’t available' },
  decision_unavailable: { es: 'El modelo no respondió', en: 'The model didn’t answer' },
  decision_unavailable_after_call: { es: 'El modelo no respondió después de actuar', en: 'The model didn’t answer after acting' },
  core_disconnected: { es: 'El motor local se desconectó', en: 'The local engine disconnected' },
  retry_without_close: { es: 'El motor local no arrancó', en: 'The local engine didn’t start' },
  // Uso 85: nothing is relaunched any more; Breakdown says what happened and what the person can do
  profile_unreadable: { es: 'Tus datos guardados no se pueden abrir', en: 'Your saved data can’t be opened' },
  engine_unavailable: { es: 'BAXY no logra arrancar', en: 'BAXY can’t start' },
  no_supported_gpu: { es: 'BAXY necesita una GPU compatible', en: 'BAXY needs a supported GPU' },
  turn_failed: { es: 'El turno no pudo terminar', en: 'The turn couldn’t finish' },
  // a state of the interface, never words of BAXY's (zero fixed visible replies); the ear failed (the microphone sent
  // nothing or a block of it could not be heard), which is not BAXY not understanding what was said
  voice_error: { es: 'Falló la escucha', en: 'Listening failed' },
};

// Uso 85: the failures the host no longer relaunches from; Breakdown offers the person what can be done.
const BREAKDOWNS: readonly string[] = ['profile_unreadable', 'engine_unavailable', 'no_supported_gpu'];

// the frame's ring per state (design app.jsx SET).
const RING: Record<string, string[]> = {
  standby: ['#2a2f3a', '#5B6580', '#8B95A8', '#D8DCE6', 'rgba(139,149,168,0.75)', '#5B6580'],
  idle: ['#5a1a22', '#B83A4A', '#FF4D63', '#FFE3E7', 'rgba(255,77,99,0.9)', '#5B7FDB'],
  listening: ['#7A1E2B', '#E55366', '#FF6677', '#FFFFFF', 'rgba(255,102,119,0.95)', '#6FA8B0'],
  thinking: ['#1B2A5E', '#2E4BA0', '#5B7FDB', '#C8D6F5', 'rgba(91,127,219,0.9)', '#C9A66B'],
  speaking: ['#6B5A2F', '#C9A66B', '#E8C98E', '#F8EED2', 'rgba(232,201,142,0.9)', '#7B95D9'],
  error: ['#5a1a22', '#D9364C', '#FF4D63', '#FFD0D6', 'rgba(255,77,99,0.95)', '#FF6677'],
};

const LABEL: Record<BaxyState, Words> = {
  booting: { es: 'Arrancando', en: 'Starting' }, standby: { es: 'En reposo', en: 'Asleep' }, idle: { es: 'En espera', en: 'Idle' },
  listening: { es: 'Escuchando', en: 'Listening' }, thinking: { es: 'Pensando', en: 'Thinking' }, speaking: { es: 'Hablando', en: 'Speaking' },
  confirm: { es: 'Esperando tu ok', en: 'Waiting for your OK' }, error: FAILURE.voice_error,
};

export default function App() {
  const s = useBaxy();

  // ---- presentation (this view's own, kept in localStorage) ----
  const [theme, setTheme] = useState<'dark' | 'light'>(() => stored('baxy.theme', ['dark', 'light'] as const, 'dark'));
  // Only the standard mode is ready (owner, 2026-10-18): a mode kept from before is not brought back as if it were.
  const [profile, setProfile] = useState<Profile>(() => stored('baxy.profile', ['normal'] as const, 'normal'));
  const [a11y, setA11yState] = useState<A11y>(() => ({
    on: false, size: stored('baxy.a11y.size', ['m', 'l', 'xl'] as const, 'm'), contrast: stored('baxy.a11y.contrast', ['0', '1'] as const, '0') === '1',
  }));
  const [mic, setMicState] = useState<MicMode>(() => stored('baxy.mic', ['off', 'always', 'ptt'] as const, 'always'));

  // ---- the host's settings ----
  const [bypass, setBypassState] = useState(false);
  // how long a card waits for the person, as the host says: the engine's confirmation and a heartbeat's proposal
  const [cardLife, setCardLife] = useState<{ confirm: number; proposal: number } | null>(null);
  const [general, setGeneral] = useState<GeneralSettings | null>(null);
  // the model behind an API that answers now: «todo local» is not true while it does
  const [api, setApi] = useState<string | null>(null);
  const [apiCapped, setApiCapped] = useState(false);
  useEffect(() => {
    const read = () => void getJson<{ active?: boolean; activeLocal?: boolean; activeModel?: string | null; lastError?: string | null }>('/settings/external-model')
      .then((e) => { if (!e) return; setApi(e.active && !e.activeLocal ? e.activeModel ?? null : null); setApiCapped(!!e.active && !!e.lastError?.startsWith('TOPE')); });
    read();
    const every = setInterval(read, 3000);
    return () => clearInterval(every);
  }, []);
  // the interface's language is the host's setting (its step titles follow it too): the one it says is in use, and
  // until its first reading the one shown last time (a first-paint cache only), else Windows'
  const [firstLang] = useState<Lang>(() => stored('baxy.lang', ['es', 'en'] as const, systemLang()));
  const inUse = general?.languageInUse;
  const lang: Lang = inUse === 'es' || inUse === 'en' ? inUse : firstLang;
  const t = useMemo(() => translator(lang), [lang]);
  useEffect(() => {
    document.documentElement.lang = lang;
    keep('baxy.lang', lang);
  }, [lang]);
  const [proposals, setProposals] = useState<ProposalSettings | null>(null);
  // at rest or active is the host's: the rail and the tray menu change it
  const powered = s.agent.powered !== false;
  const [metrics, setMetrics] = useState<Metrics | null>(null);
  const [vidOk, setVidOk] = useState(false);

  // ---- layout ----
  const [panel, setPanel] = useState<PanelId | null>(null);
  const bx2 = useRef<HTMLDivElement>(null);
  const [fw, setFw] = useState(0);
  const narrow = fw > 0 && fw < NARROW;
  const [chatOpen, setChatOpen] = useState(true);
  const [notice, setNotice] = useState<{ b: string; t: string } | null>(null);
  const [maximized, setMaximized] = useState(false);
  // timed things are keyed by what started them: a timer marks that key done, so nothing is set during render or in an
  // effect's body (captions, mood, the internet banner and dot, the voice error, the unread dot, a card's auto-open).
  const [done, setDone] = useState<Record<string, string | number>>({});
  const finish = useCallback((k: string, v: string | number, ms: number) => window.setTimeout(() => setDone((d) => ({ ...d, [k]: v })), ms), []);

  useEffect(() => {
    const el = bx2.current;
    if (!el) return;
    let was = false;
    const ro = new ResizeObserver(() => {
      const w = el.clientWidth;
      // narrowing the window folds the chat once; widening leaves it as the person had it.
      const now = w > 0 && w < NARROW;
      if (now && !was) setChatOpen(false);
      was = now;
      setFw(w);
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  // ---- read the host's settings now, and the ones the chat can change every few seconds ----
  // a reading that started before a change of the person's was sent or answered may hold the value from before it: it
  // is dropped (the next one reads the change), so a switch never jumps back to what it was for a few seconds
  const edits = useRef(0);
  const edit = useCallback(async <T,>(write: () => Promise<T>): Promise<T> => {
    edits.current++;
    try { return await write(); } finally { edits.current++; }
  }, []);
  useEffect(() => {
    let cancelled = false;
    const sync = async () => {
      const at = edits.current;
      const [c, a, g, p] = await Promise.all([
        getJson<{ confirmationPolicy?: string; confirmSeconds?: number; proposalSeconds?: number }>('/confirmation'),
        getJson<{ active?: string }>('/accessibility'),
        getJson<GeneralSettings>('/settings/general'),
        getJson<ProposalSettings>('/proposals'),
      ]);
      if (cancelled || edits.current !== at) return;
      if (c) setBypassState(c.confirmationPolicy === 'bypass');
      if (c && typeof c.confirmSeconds === 'number' && typeof c.proposalSeconds === 'number') {
        const life = { confirm: c.confirmSeconds, proposal: c.proposalSeconds };
        setCardLife((x) => (x && x.confirm === life.confirm && x.proposal === life.proposal ? x : life));
      }
      if (a) setA11yState((x) => ({ ...x, on: a.active === 'accessible' }));
      if (g) setGeneral(g);
      if (p) setProposals(p);
    };
    void sync();
    const id = window.setInterval(sync, 4000);
    return () => { cancelled = true; window.clearInterval(id); };
  }, []);
  // the panels' counters: the memory's is read by the host when asked (it publishes it as an event), the triggers' by
  // reading BAXY's alarms once BAXY is up; the surfaces again every 15 s
  useEffect(() => {
    if (!s.agent.built) return;
    void getJson('/triggers');
    void getJson('/surfaces');
    const id = window.setInterval(() => { void getJson('/surfaces'); }, 15_000);
    return () => window.clearInterval(id);
  }, [s.agent.built]);
  // the PC's readings every 1.5 s while the view is visible
  useEffect(() => {
    let cancelled = false;
    const read = async () => {
      if (document.hidden) return;
      const m = await getJson<Metrics>('/metrics');
      if (!cancelled) setMetrics(m);
    };
    void read();
    const id = window.setInterval(read, 1500);
    return () => { cancelled = true; window.clearInterval(id); };
  }, []);

  // ---- the view's state: the host's, plus starting, resting and a card waiting ----
  const listedCard = useMemo(() => {
    for (let i = s.items.length - 1; i >= 0; i--) {
      const it = s.items[i];
      if (it.who === 'card' && it.status === 'pending') return it;
    }
    return null;
  }, [s.items]);
  // a card past its time waits for nobody, even before the host says so (the card itself shows it expired): BAXY is not
  // «Esperando tu ok» and Enter / Esc answer nothing
  useEffect(() => {
    if (!listedCard) return;
    const id = finish('cardGone', listedCard.id, Math.max(0, listedCard.expires - Date.now()));
    return () => window.clearTimeout(id);
  }, [listedCard, finish]);
  const pendingCard = listedCard && done.cardGone !== listedCard.id ? listedCard : null;
  const voiceError = s.voiceErrorAt !== null && done.voiceError !== s.voiceErrorAt ? t.w(FAILURE.voice_error) : null;
  const breakdown = BREAKDOWNS.includes(s.agent.failure ?? '') ? s.agent.failure! : null;
  const booting = !!s.boot && !s.boot.model && !s.boot.failed && !breakdown;
  // «Hablando» is while BAXY's voice sounds (lip.ts, from the mind's own timeline): the host's speaking state starts
  // when the first sentence is ready and lasts 0.55 s of grace plus the output's latency after the last one (it guards
  // the ear against BAXY's own voice). Without the timeline the host's state is shown as it is.
  const voiceSounds = useLipActive();
  const host: BaxyState = voiceSounds === null ? s.hostState
    : voiceSounds ? 'speaking' : s.hostState === 'speaking' ? s.hostQuiet : s.hostState;
  const state: BaxyState = booting ? 'booting'
    : !powered ? 'standby'
      : voiceError ? 'error'
        : host === 'idle' && pendingCard ? 'confirm'
          : host;
  const gState = state === 'confirm' ? 'idle' : state === 'booting' ? 'standby' : state;
  const label = state === 'error' ? (voiceError ? t.w(LABEL.error) : apiCapped ? t('Llegaste al tope de gasto de la API', 'You reached the API spending cap') : failureLabel(s.agent.failure, s.agent.failureCause, s.agent.failureMemory, s.agent.failureRead, t))
    // uso 95: written while the model starts, the message waits for it (the host answers it once it is up)
    : state === 'booting' && s.agent.waitingForMind ? t('Arrancando · tu mensaje espera', 'Starting · your message is waiting')
      : t.w(LABEL[state]);

  // how long the model took this time, kept as this view's note for the next start (never a promise)
  useEffect(() => {
    if (s.boot?.readyAt) keep('baxy.lastLoad', String(Math.round((s.boot.readyAt - s.boot.startedAt) / 1000)));
  }, [s.boot?.readyAt, s.boot?.startedAt]);

  // a voice error shows for a few seconds, then BAXY waits again
  useEffect(() => {
    if (s.voiceErrorAt === null) return;
    const id = finish('voiceError', s.voiceErrorAt, 2800);
    return () => window.clearTimeout(id);
  }, [s.voiceErrorAt, finish]);

  // FT/proveedores goal (review of the App): heard while a turn ran, a request starts nothing; the host said so as a
  // state the view never showed, and the person saw the wake and the captions and then nothing. A notice says it.
  useEffect(() => {
    if (s.voiceDroppedAt === null) return;
    const id = finish('voiceDropped', s.voiceDroppedAt, 2800);
    return () => window.clearTimeout(id);
  }, [s.voiceDroppedAt, finish]);
  const dropped = s.voiceDroppedAt !== null && done.voiceDropped !== s.voiceDroppedAt
    ? { b: t('Voz', 'Voice'), t: t('pedido de voz no tomado: BAXY seguía ocupado · repítelo cuando termine', 'voice request not taken: BAXY was still busy · say it again when it’s done') } : null;
  const shownNotice = notice ?? dropped;

  // ---- captions and mood follow each reply: they last as long as reading it takes, plus a pause ----
  useEffect(() => {
    if (!s.sub) return;
    const read = Math.max(2200, s.sub.text.split(' ').length * 290);
    const hide = finish('sub', s.sub.key, read + 4200), calm = finish('mood', s.sub.key, read + 2800);
    return () => { window.clearTimeout(hide); window.clearTimeout(calm); };
  }, [s.sub, finish]);
  const subGone = !s.sub || (done.sub === s.sub.key && state !== 'speaking');
  const mood = s.sub && done.mood !== s.sub.key ? s.mood : null;

  // ---- what left the PC: the banner for 4.2 s; the rail and the antenna for the rest of the turn and 20 s after ----
  const turnRunning = s.hostState === 'thinking';
  useEffect(() => {
    if (!s.net) return;
    const b = finish('banner', s.net.at, 4200);
    return () => window.clearTimeout(b);
  }, [s.net, finish]);
  useEffect(() => {
    if (!s.net || turnRunning) return;
    const n = finish('net', s.net.at, 20000);
    return () => window.clearTimeout(n);
  }, [s.net, turnRunning, finish]);
  const banner = s.net && done.banner !== s.net.at ? s.net.what : null;
  const netShown = s.net && (turnRunning || done.net !== s.net.at) ? s.net.what : null;

  useEffect(() => {
    if (!notice) return;
    const id = window.setTimeout(() => setNotice(null), 2600);
    return () => window.clearTimeout(id);
  }, [notice]);

  // ---- presentation classes on <html> ----
  useEffect(() => {
    const h = document.documentElement;
    h.classList.toggle('lt', theme === 'light');
    h.classList.toggle('a11y', a11y.on);
    h.classList.toggle('a11y-l', a11y.on && a11y.size === 'l');
    h.classList.toggle('a11y-xl', a11y.on && a11y.size === 'xl');
    h.classList.toggle('hc', a11y.contrast);
  }, [theme, a11y]);

  // ---- the frame's ring: turns with the state (1.5× and a second comet in bypass), stops at rest ----
  const R = useRef({ powered, bypass });
  useEffect(() => { R.current = { powered, bypass }; }, [powered, bypass]);
  useEffect(() => {
    const frame = document.querySelector<HTMLElement>('.app-frame');
    if (!frame) return;
    const spins = [...frame.querySelectorAll<HTMLElement>('.bd-spin')];
    // final 4, accesibilidad: with prefers-reduced-motion the ring stays still, as the sky and the face do (its colours
    // still tell the state)
    const calm = window.matchMedia?.('(prefers-reduced-motion: reduce)');
    let raf = 0, last = performance.now(), acc = 0, angle = 0, speed = 1;
    const loop = (now: number) => {
      raf = requestAnimationFrame(loop);
      acc += now - last; last = now;
      if (acc < 32 || document.hidden) return; // 30 fps is enough for a slow ring
      const dt = Math.min(0.05, acc / 1000); acc = 0;
      const tg = R.current.powered && !calm?.matches ? (R.current.bypass ? 1.5 : 1) : 0;
      speed += (tg - speed) * Math.min(1, dt * 2.6);
      if (tg === 0 && speed < 0.012) speed = 0;
      if (speed === 0) return;
      angle = (angle + speed * (360 / 3.4) * dt) % 360;
      const tr = 'rotate(' + angle.toFixed(2) + 'deg)';
      spins.forEach((el) => { el.style.transform = tr; });
    };
    raf = requestAnimationFrame(loop);
    return () => cancelAnimationFrame(raf);
  }, []);
  useEffect(() => {
    const frame = document.querySelector<HTMLElement>('.app-frame');
    if (!frame) return;
    const c = RING[gState] ?? RING.idle;
    ['base', 'mid', 'hi', 'peak', 'glow'].forEach((k, i) => frame.style.setProperty('--bd-' + k, c[i]));
    frame.style.setProperty('--bar-color', c[5]);
    frame.style.setProperty('--carmine', ['listening', 'thinking', 'speaking'].includes(gState) ? c[5] : '#B83A4A');
    frame.classList.toggle('bx-bypass', bypass);
    frame.classList.toggle('bx-standby', gState === 'standby');
  }, [gState, bypass]);

  // ---- actions ----
  const submit = useCallback(async (text: string) => {
    // the host refuses a longer request (MissionInput.MaximumCharacters, UTF-16 like a JS string's length): it is never
    // cut to fit, which would send a request other than the one written; it is not sent, and the view says why
    if (text.length > MAX_REQUEST) {
      setNotice({ b: 'BAXY', t: t('el pedido es demasiado largo · máximo ', 'the request is too long · at most ') + MAX_REQUEST + t(' caracteres, tiene ', ' characters, it has ') + text.length });
      return false;
    }
    // /turn answers when the turn ends: a request that got no answer may have been taken and is not given back to the
    // box (Enter would send it again); only one the host refused is
    const r = await sendTold('POST', '/turn', { text });
    if (r.value === null) setNotice({ b: 'BAXY', t: t('no pudo recibir el pedido ahora', 'couldn’t take the request right now') });
    return !r.refused;
  }, [t]);
  // the answer names the card it answers: a press or a key meant for one that ended never answers the next (the host
  // refuses it), and a refused answer is said, never lost in silence. A card is answered once: a second press or key
  // while the host has not yet said the card ended is not sent (the host would refuse it and the view would say the
  // answer it took was not taken); a refused answer can be given again.
  const answered = useRef(new Set<string>());
  const answer = useCallback(async (approve: boolean, card: string) => {
    if (answered.current.has(card)) return;
    answered.current.add(card);
    if (await send('POST', '/confirmation/answer', { approve, card }) === null) {
      answered.current.delete(card);
      setNotice({ b: t('Confirmación', 'Confirmation'), t: t('no se tomó tu respuesta: BAXY seguía ocupado o esa tarjeta ya no espera', 'your answer wasn’t taken: BAXY was still busy or that card is no longer waiting') });
    }
  }, [t]);
  const newSession = useCallback(async () => {
    if (await send('POST', '/sessions/new') === null) setNotice({ b: t('Sesión', 'Session'), t: t('espera a que BAXY termine', 'wait for BAXY to finish') });
    else setPanel(null);
  }, [t]);
  const setBypass = useCallback(async (on: boolean) => {
    const r = await edit(() => send<{ confirmationPolicy?: string }>('PUT', '/confirmation', { confirmationPolicy: on ? 'bypass' : 'normal' }));
    if (!r) { setNotice({ b: t('Confirmación', 'Confirmation'), t: t('no se pudo cambiar', 'couldn’t change it') }); return; }
    const now = r.confirmationPolicy === 'bypass';
    setBypassState(now);
    setNotice(now ? { b: 'Bypass', t: t('sin frenos hasta que lo apagues', 'no brakes until you turn it off') } : { b: 'Normal', t: t('BAXY pregunta antes de lo arriesgado', 'BAXY asks before risky things') });
  }, [edit, t]);
  const setA11y = useCallback(async (next: A11y) => {
    setA11yState(next);
    keep('baxy.a11y.size', next.size); keep('baxy.a11y.contrast', next.contrast ? '1' : '0');
    const r = await edit(() => send<{ active?: string }>('PUT', '/accessibility', { mode: next.on ? 'accessible' : 'normal' }));
    if (r) setA11yState((x) => ({ ...x, on: r.active === 'accessible' }));
  }, [edit]);
  const applyMic = useCallback(async (m: MicMode) => {
    const r = m === 'always' ? await send<{ running?: boolean }>('POST', '/voice/start') : await send('POST', '/voice/stop');
    return r !== null && (m !== 'always' || (r as { running?: boolean }).running !== false);
  }, []);
  // the person's microphone choice is applied once BAXY can take voice commands
  const micApplied = useRef(false);
  const mindUp = !!s.boot?.model;
  const setMic = useCallback(async (m: MicMode) => {
    const said = {
      off: t('micrófono apagado · solo texto', 'microphone off · text only'),
      always: t('siempre activo · di «BAXY» · en pruebas', 'always on · say “BAXY” · in testing'),
      ptt: t('mantén el botón o espacio para hablar · en pruebas', 'hold the button or space to talk · in testing'),
    }[m];
    // while BAXY starts or rests the host takes no voice command: the choice is kept and applied when it can be
    // (once built, below; on waking, togglePower), instead of being refused and lost
    if (!s.agent.built || !mindUp || !powered) {
      setMicState(m); keep('baxy.mic', m);
      if (!s.agent.built || !mindUp) micApplied.current = false;
      setNotice({ b: t('Voz', 'Voice'), t: said + (s.agent.built && mindUp ? t(' · al activar a BAXY', ' · when BAXY wakes up') : t(' · cuando termine de arrancar', ' · once it finishes starting')) });
      return;
    }
    // the first change after a start waits for the voice to load: the mode shows at once and is said when applied
    setMicState(m);
    setNotice({ b: t('Voz', 'Voice'), t: t('cambiando el micrófono…', 'changing the microphone…') });
    const ok = await applyMic(m);
    if (!ok) { setMicState(mic); setNotice({ b: t('Voz', 'Voice'), t: t('no se pudo cambiar el micrófono', 'couldn’t change the microphone') }); return; }
    setMicState(m); keep('baxy.mic', m);
    setNotice({ b: t('Voz', 'Voice'), t: said });
  }, [applyMic, s.agent.built, mindUp, powered, mic, t]);
  // FT/proveedores goal (review of the App): the core is built while the model still loads, and the voice belongs to
  // the mind: applied then, the saved mode found no mind and was never applied again. It waits for the mind, and a
  // mode that could not be applied is tried again when the mind comes back (a relaunch).
  useEffect(() => { if (!mindUp) micApplied.current = false; }, [mindUp]);
  useEffect(() => {
    if (micApplied.current || !s.agent.built || !mindUp) return;
    micApplied.current = true;
    void applyMic(mic).then((ok) => { if (!ok) micApplied.current = false; });
  }, [s.agent.built, mindUp, mic, applyMic]);
  const ptt = useRef(false);
  const pttStart = useCallback(() => {
    if (ptt.current || !['idle', 'speaking', 'standby'].includes(state)) return;
    ptt.current = true;
    void send('POST', '/voice/trigger');
  }, [state]);
  const pttEnd = useCallback(() => {
    if (!ptt.current) return;
    ptt.current = false;
    void send('POST', '/voice/release');
  }, []);
  const togglePower = useCallback(async () => {
    // resting first stops the ear, which waits for the voice to finish loading after a start: say so at once
    setNotice({ b: 'BAXY', t: powered ? t('poniendo a BAXY en reposo…', 'putting BAXY to sleep…') : t('activando a BAXY…', 'waking BAXY up…') });
    const r = await send<{ ok?: boolean; on?: boolean }>('POST', '/power', { on: !powered });
    if (!r || r.on === powered) { setNotice({ b: 'BAXY', t: powered ? t('no se pudo poner en reposo', 'couldn’t put it to sleep') : t('no se pudo activar', 'couldn’t wake it up') }); return; }
    setNotice(null);
  }, [powered, t]);
  // back from rest, by this button, the tray's «Activar» or a text written to BAXY at rest, the microphone mode the
  // person chose comes back (FT/proveedores goal, review of the App: only this button brought it back)
  const wasPowered = useRef(powered);
  useEffect(() => {
    const woke = powered && !wasPowered.current;
    wasPowered.current = powered;
    if (woke && s.agent.built && mindUp) void applyMic(mic);
  }, [powered, s.agent.built, mindUp, applyMic, mic]);
  const onGeneral = useCallback(async (p: Partial<GeneralSettings>) => {
    const r = await edit(() => send<GeneralSettings>('PUT', '/settings/general', p));
    if (r) setGeneral(r); else setNotice({ b: t('Ajustes', 'Settings'), t: t('no se pudo guardar', 'couldn’t save it') });
  }, [edit, t]);
  // the person's choice (also «auto») is the host's; the settings are read again for the language it resolved
  const onLang = useCallback(async (choice: LangChoice) => {
    const r = await edit(async () => (await send('PUT', '/settings/language', { lang: choice })) === null ? null : getJson<GeneralSettings>('/settings/general'));
    if (r) setGeneral(r); else setNotice({ b: t('Ajustes', 'Settings'), t: t('no se pudo guardar', 'couldn’t save it') });
  }, [edit, t]);
  const onProposals = useCallback(async (p: Partial<ProposalSettings>) => {
    const r = await edit(() => send<ProposalSettings>('PUT', '/proposals', p));
    if (r) setProposals(r); else setNotice({ b: t('Propuestas', 'Proposals'), t: t('no se pudo guardar', 'couldn’t save it') });
  }, [edit, t]);
  // the last reply or card: unread while the chat is folded and it is not the one the person saw last; a waiting card
  // opens the chat by itself until the person folds it again.
  const lastReply = useMemo(() => {
    for (let i = s.items.length - 1; i >= 0; i--) if (s.items[i].who === 'baxy' || s.items[i].who === 'card') return s.items[i].id;
    return '';
  }, [s.items]);
  const toggleChat = useCallback((v: boolean) => {
    setChatOpen(v);
    setDone((d) => ({ ...d, seen: lastReply, card: v ? '' : pendingCard?.id ?? '' }));
  }, [lastReply, pendingCard]);
  const collapse = useCallback(() => toggleChat(false), [toggleChat]);
  const onNewChat = useCallback(() => { void newSession(); }, [newSession]);
  const win = useCallback(async (command: 'minimize' | 'toggle_maximize' | 'close') => {
    const api = (window as unknown as { pywebview?: { api: Record<string, () => Promise<unknown>> } }).pywebview?.api;
    if (!api) return;
    if (command === 'minimize') await api.win_minimize();
    else if (command === 'close') await api.win_close();
    else setMaximized(!!(await api.win_toggle_maximize()));
  }, []);

  // ---- keys: Sí = Enter, No = Esc for a waiting card; Esc closes a panel; space held talks in push-to-talk ----
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const a = document.activeElement as HTMLInputElement | null;
      const typing = !!a && (a.tagName === 'INPUT' || a.tagName === 'TEXTAREA') && !!a.value.trim();
      // Enter on a focused button of a card presses that button: on the card's «No» it is a No, never the card's Sí.
      // Any other focused button (the gear a closed panel gave the focus back to) does not take the card's Enter.
      const control = e.key === 'Enter' && !!a?.closest?.('.bx-card') && !!a.closest('button, a[href], select, [role="button"], [role="switch"]');
      if (pendingCard && !panel && !typing && !control && (e.key === 'Enter' || e.key === 'Escape')) { e.preventDefault(); void answer(e.key === 'Enter', pendingCard.id); return; }
      if (e.key === 'Escape' && panel) setPanel(null);
      if (e.key === ' ' && mic === 'ptt' && !e.repeat && !panel && !(a && a.tagName === 'INPUT' && a.value)) { e.preventDefault(); pttStart(); }
    };
    const onUp = (e: KeyboardEvent) => { if (e.key === ' ' && ptt.current) { e.preventDefault(); pttEnd(); } };
    // the window losing the focus with the space held (Alt+Tab, a notification) sends its release elsewhere: the ear
    // is let go then, never left listening
    const onBlur = () => pttEnd();
    window.addEventListener('keydown', onKey);
    window.addEventListener('keyup', onUp);
    window.addEventListener('blur', onBlur);
    return () => { window.removeEventListener('keydown', onKey); window.removeEventListener('keyup', onUp); window.removeEventListener('blur', onBlur); };
  }, [pendingCard, panel, mic, answer, pttStart, pttEnd]);

  // ---- what the face shows ----
  const expr = state === 'error' ? 'sad'
    : mood && (state === 'idle' || state === 'speaking') ? mood
      : s.activity === 'game' ? 'sleep'
        : ({ standby: 'sleep', booting: 'sleep', idle: 'neutral', listening: 'listen', thinking: 'think', speaking: 'neutral', confirm: pendingCard?.risk ? 'serious' : 'curious' } as Record<string, string>)[state] ?? 'neutral';
  const waiting = pendingCard ? (pendingCard.notified ? t('Propuesta enviada como notificación de Windows', 'Proposal sent as a Windows notification') : t('Esperando tu ok en la conversación', 'Waiting for your OK in the conversation')) : null;

  // the conversation's own count: its requests and the calls of this session that went out to the internet
  const nReq = s.items.filter((x) => x.who === 'you').length;
  const nNet = s.items.reduce((n, x) => n + (x.who === 'baxy' ? x.steps.filter((st) => st.net).length : 0), 0);
  const meta = state === 'booting' ? t('Arrancando', 'Starting')
    : nReq === 0 ? t('Sin pedidos aún', 'No requests yet')
      : nReq + (nReq === 1 ? t(' pedido', ' request') : t(' pedidos', ' requests'))
        + (api ? t(' · modelo por API', ' · model by API')
          : nNet ? ' · ' + nNet + (nNet === 1 ? t(' salida a internet', ' internet call') : t(' salidas a internet', ' internet calls')) : t(' · todo local', ' · all local'));
  const title = s.session?.label || t('Conversación', 'Conversation');
  const counts = { sessions: s.surfaces?.sessions ?? null, memory: s.surfaces?.memory ?? null, triggers: s.surfaces?.triggers ?? null, catalog: s.surfaces?.tools ?? null };
  const chatShown = chatOpen || (!!pendingCard && done.card !== pendingCard.id);
  const chatVisible = chatShown && !narrow;
  const unread = !chatShown && !!lastReply && done.seen !== lastReply;
  const focusX = fw ? (RAIL + (fw - RAIL - (chatVisible ? CHATW : 0)) / 2) / fw : 0.5;
  const quiet = !!proposals?.quiet;
  // uso 95 (F9): the host holds a message written while the model starts and answers it once it is up
  const canSend = s.agent.built;
  // what the microphone is really doing (the tray menu can switch the ear on or off): the person's push-to-talk choice,
  // else the host's own mode; at rest the ear is off by itself, so the choice it will wake with is shown
  const shownMic: MicMode = mic === 'ptt' || !powered ? mic : s.voice.mode === 'wake' ? 'always' : s.agent.built && s.voice.mode === 'off' ? 'off' : mic;

  return (
    <LangContext.Provider value={t}>
    <div className="app-frame">
      <div className="bd-ring"><i className="bd-spin"></i></div>
      <div className="bd-glow"><i className="bd-spin"></i></div>
      <div className="shell">
        <div ref={bx2} className={'bx2 p-' + profile + (chatShown ? '' : ' chat-off') + (narrow ? ' narrow' : '')}
          style={{ '--rail': RAIL + 'px', '--chatw': chatVisible ? CHATW + 'px' : '0px', '--chatfull': CHATW + 'px' } as CSSProperties}>
          <Cosmos state={gState} light={theme === 'light'} focusX={focusX} />
          <Rail api={api} state={state} powered={powered} onPower={togglePower} bypass={bypass} onMode={() => void setBypass(!bypass)}
            metrics={metrics} net={netShown} profile={profile} onProfile={(p) => { setProfile(p); keep('baxy.profile', p); }}
            counts={counts} quiet={quiet} onPanel={setPanel} />
          <div className="bx-center">
            {/* Uso real 03-11: a click here opened the ear as if the space were held; the wake word, the held space and the
                microphone button are what open it */}
            <div className="bx-graph">
              {AVATAR !== 'live' && theme !== 'light' ? <AvatarVid state={state} expr={expr} onReady={setVidOk} /> : null}
              <Face overlay={AVATAR !== 'live' && vidOk && theme !== 'light'} state={gState} expr={expr} talking={state === 'speaking'} journey={s.journey} hold={state === 'confirm'} light={theme === 'light'} net={!!netShown} />
            </div>
            <div className="bx-ctop pywebview-drag-region" onDoubleClick={(e) => { if (e.target === e.currentTarget) void win('toggle_maximize'); }}>
              <span className={'bx-statel ' + state + (['listening', 'thinking', 'speaking', 'confirm', 'error'].includes(state) ? ' live' : '')}>
                <i></i>{label}
                {bypass ? <span className="bp"><Icon name="bolt" size={10} />bypass</span> : null}
                {s.activity === 'game' ? <span className="bx-ctxp">{t('Jugando · aviso por Windows', 'Gaming · notifications via Windows')}</span> : null}
              </span>
              <span className="bx-ctr">
                {!chatShown ? (
                  <button className="bx-ib" title={t('Mostrar conversación', 'Show conversation')} aria-label={t('Mostrar conversación', 'Show conversation') + (unread ? t(' · hay una respuesta sin leer', ' · there’s an unread reply') : '')} onClick={() => toggleChat(true)}>
                    <svg width="15" height="15" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.25" strokeLinejoin="round"><path d="M2.5 4Q2.5 2.8 3.7 2.8H12.3Q13.5 2.8 13.5 4V9.6Q13.5 10.8 12.3 10.8H7L4.2 13.2V10.8H3.7Q2.5 10.8 2.5 9.6Z"></path><path d="M5.3 6.8h.01M8 6.8h.01M10.7 6.8h.01" strokeWidth="1.8" strokeLinecap="round"></path></svg>
                    {unread ? <span className="dot"></span> : null}
                  </button>
                ) : null}
                <span className="bx-win">
                  <button className="bx-ib plain" title={t('Minimizar', 'Minimize')} aria-label={t('Minimizar', 'Minimize')} onClick={() => void win('minimize')}><Icon name="win-min" size={12} /></button>
                  <button className="bx-ib plain" title={maximized ? t('Restaurar', 'Restore') : t('Maximizar', 'Maximize')} aria-label={maximized ? t('Restaurar', 'Restore') : t('Maximizar', 'Maximize')} onClick={() => void win('toggle_maximize')}><Icon name={maximized ? 'win-restore' : 'win-max'} size={12} /></button>
                  <button className="bx-ib plain bx-close" title={t('Cerrar', 'Close')} aria-label={t('Cerrar BAXY', 'Close BAXY')} onClick={() => void win('close')}><Icon name="x" size={12} /></button>
                </span>
              </span>
            </div>
            {/* final 4, accesibilidad: the notices, the internet banner and a failure are drawn for a moment and were
                never read by a screen reader; this region, always there, says them (politely, never over the voice) */}
            <div className="sr-only" role="status" aria-live="polite">{liveText(banner, shownNotice, state === 'error' ? label : null, t)}</div>
            <div className="bx-cbot">
              {banner ? <div className="bx-netban" key={banner}><Globe s={11} /><b>{t('Salió a internet', 'Went online')}</b><span>· {banner}</span></div>
                : shownNotice ? <div className="bx-notice" key={shownNotice.t}><b>{shownNotice.b}</b> · {shownNotice.t}</div> : null}
              {breakdown ? <Breakdown failure={breakdown} cause={s.agent.failureCause ?? null} memory={s.agent.failureMemory ?? null} read={s.agent.failureRead ?? null} onProcessor={!!s.boot?.onProcessor} />
                : booting && s.boot ? <Boot boot={s.boot} />
                : <Caption state={state} sub={s.sub} subGone={subGone} live={s.live} step={s.running} waiting={waiting} />}
              <VoiceInput mic={shownMic} micAvailable={s.voice.available} micWaiting={s.voice.waiting_memory ?? null} noRecognizer={s.voice.no_recognizer === true} onMic={(m) => void setMic(m)} onPttStart={pttStart} onPttEnd={pttEnd}
                onSubmit={submit} state={state} canSend={canSend} />
            </div>
          </div>
          <div className="bx-right">
            <Chat items={s.items} title={title} meta={meta} busy={state === 'thinking'} onAnswer={answer} onCollapse={collapse} onNew={onNewChat} />
          </div>
        </div>
      </div>
      {panel === 'memory' ? <MemoryPanel onClose={() => setPanel(null)} revision={s.surfaces?.memory_revision ?? 0} /> : null}
      {panel === 'triggers' ? <TriggersPanel onClose={() => setPanel(null)} /> : null}
      {panel === 'catalog' ? <CatalogPanel onClose={() => setPanel(null)} /> : null}
      {panel === 'sessions' ? <SessionsPanel onClose={() => setPanel(null)} onNew={onNewChat} revision={s.session?.id + ':' + s.session?.label} /> : null}
      {panel === 'proposals' ? <ProposalsPanel value={proposals} proposalSeconds={cardLife?.proposal ?? null} onChange={(p) => void onProposals(p)} onClose={() => setPanel(null)} /> : null}
      {panel === 'settings' ? (
        <SettingsPanel onClose={() => setPanel(null)} theme={theme} onTheme={(t) => { setTheme(t); keep('baxy.theme', t); }}
          bypass={bypass} onBypass={(v) => void setBypass(v)} mic={shownMic} micAvailable={s.voice.available} onMic={(m) => void setMic(m)}
          a11y={a11y} onA11y={(a) => void setA11y(a)} general={general} onGeneral={(p) => void onGeneral(p)} metrics={metrics}
          netLog={s.netLog} confirmSeconds={cardLife?.confirm ?? null} onMemory={() => setPanel('memory')}
          lang={general?.language ?? 'auto'} onLang={(l) => void onLang(l)} />
      ) : null}
    </div>
    </LangContext.Provider>
  );
}
