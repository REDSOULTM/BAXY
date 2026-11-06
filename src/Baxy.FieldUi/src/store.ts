import { useEffect, useReducer } from 'react';
import { lipPush } from './lip';
import type {
  AgentStatus, BootPieces, ChatItem, Fam, HostState, NetEntry, ServerEvent, Step, StepStatus, Surfaces, VoiceStatus,
} from './types';

/** the path the face's network walks this turn: the families of the calls in the order the model made them. */
export interface Journey {
  turn: string;
  path: string[];
  /** the family of a call that failed (a red ✕). */
  fail: Fam | null;
  /** the family of a call that may have run, unconfirmed (the doubtful «?»); a failure of the same family shows instead. */
  maybe: Fam | null;
}

/** a call's end on this turn's walk: «fail» marks its family with the ✕, «maybe» with the doubtful «?», others nothing. */
export function journeyAtEnd(journey: Journey | null, status: StepStatus, fam: Fam): Journey | null {
  if (!journey) return journey;
  if (status === 'fail') return { ...journey, fail: fam };
  if (status === 'maybe') return { ...journey, maybe: fam };
  return journey;
}

export type Mood = 'happy' | 'sad' | 'curious' | null;

export interface BaxyStore {
  connected: boolean;
  hostState: HostState;
  /** the host's state without the voice (what follows when the voice stops sounding) */
  hostQuiet: HostState;
  agent: AgentStatus;
  items: ChatItem[];
  session: { id: string; label: string } | null;
  surfaces: Surfaces | null;
  boot: BootPieces | null;
  voice: VoiceStatus;
  /** what the ear transcribed so far while listening. */
  live: string;
  /** the call running now, for the caption under the face. */
  running: string | null;
  journey: Journey | null;
  /** what left the PC last (shown for a while on the rail and above the captions). */
  net: { what: string; at: number } | null;
  netLog: NetEntry[];
  activity: 'free' | 'game' | 'call' | 'video' | 'away';
  /** BAXY's last words (the captions), with a key that changes with every new reply. */
  sub: { text: string; key: string } | null;
  mood: Mood;
  /** when the ear last failed on what it heard (voice_error), for the state «Falló la escucha». */
  voiceErrorAt: number | null;
  /** when something heard was dropped because a turn ran (voice_dropped_busy), for a notice instead of silence. */
  voiceDroppedAt: number | null;
}

export const INITIAL: BaxyStore = {
  connected: false,
  hostState: 'idle',
  hostQuiet: 'idle',
  agent: { built: false, ready: false },
  items: [],
  session: null,
  surfaces: null,
  boot: null,
  voice: { available: false, mode: 'off', speaking: false },
  live: '',
  running: null,
  journey: null,
  net: null,
  netLog: [],
  activity: 'free',
  sub: null,
  mood: null,
  voiceErrorAt: null,
  voiceDroppedAt: null,
};

const MAX_ITEMS = 150;

/** the mood a reply leaves on the face, from what its calls really did. */
function moodOf(steps: Step[]): Mood {
  if (steps.some((s) => s.status === 'fail')) return 'sad';
  // sent without reading its effect is not known done: it reads as a doubt, like one that may have run
  if (steps.some((s) => s.status === 'maybe' || s.status === 'sent')) return 'curious';
  if (steps.some((s) => s.status === 'ok' || s.status === 'same' || s.status === 'read')) return 'happy';
  return null;
}

function netOf(items: ChatItem[]): NetEntry[] {
  return items.flatMap((it) => (it.who === 'baxy' ? it.steps.filter((st) => st.net).map((st) => ({ what: st.net!, ts: it.ts })) : []));
}

function upsert(items: ChatItem[], item: ChatItem): ChatItem[] {
  const i = items.findIndex((x) => x.id === item.id);
  if (i < 0) return [...items, item].slice(-MAX_ITEMS);
  const next = items.slice();
  next[i] = item;
  return next;
}

export function reduce(s: BaxyStore, ev: ServerEvent | { type: '_connected'; value: boolean }): BaxyStore {
  switch (ev.type) {
    case '_connected':
      return { ...s, connected: ev.value };
    case 'state':
      // listening starts a new request: the last reply's captions leave (owner, 2026-10-20: they came back and
      // re-animated over what BAXY said next)
      return { ...s, hostState: ev.value, hostQuiet: ev.quiet ?? (ev.value === 'speaking' ? 'idle' : ev.value), live: ev.value === 'listening' ? s.live : '', running: ev.value === 'thinking' ? s.running : null,
        sub: ev.value === 'listening' ? null : s.sub };
    case 'agent':
      return { ...s, agent: { built: ev.built, ready: ev.ready, failure: ev.failure ?? null, pendingConfirmation: !!ev.pendingConfirmation, waitingForMind: !!ev.waitingForMind, failureCause: ev.failureCause ?? null, failureMemory: ev.failureMemory ?? null, failureRead: ev.failureRead ?? null, powered: ev.powered !== false } };
    case 'transcript':
      // a session opened or started: its internet log is its own calls' (Ajustes → Privacidad says «de esta sesión»)
      return { ...s, items: ev.items.slice(-MAX_ITEMS), sub: null, mood: null, journey: null, netLog: netOf(ev.items) };
    case 'item': {
      const before = s.items.find((x) => x.id === ev.item.id);
      const items = upsert(s.items, ev.item);
      const it = ev.item;
      // a reply's words arrived (new, or the steps' holder got its text): captions, mood and the walk's end.
      if (it.who === 'baxy' && it.text && !(before && before.who === 'baxy' && before.text === it.text)) {
        // the walk ends at «verificar»; it only grows: what the face already walked is never reordered or cut (a turn
        // that went back to a family after asking, a confirmed call, walks on from where it was)
        const at = s.journey?.path;
        const journey = s.journey && at && at[at.length - 1] !== 'verificar' ? { ...s.journey, path: [...at, 'verificar'] } : s.journey;
        return { ...s, items, sub: { text: it.text, key: it.id + ':' + it.text.length }, mood: moodOf(it.steps), journey, running: null };
      }
      // a new request (typed or heard): the last reply's captions leave with it
      if (it.who === 'you' && !before) return { ...s, items, sub: null, mood: null };
      return { ...s, items };
    }
    case 'step': {
      if (ev.phase === 'start') {
        const same = s.journey && s.journey.turn === ev.turn;
        const path = same ? s.journey!.path : ['mente'];
        const next = path[path.length - 1] === ev.fam ? path : [...path, ev.fam];
        return { ...s, running: ev.label + '…', journey: { turn: ev.turn, path: next, fail: same ? s.journey!.fail : null, maybe: same ? s.journey!.maybe : null } };
      }
      return { ...s, journey: journeyAtEnd(s.journey, ev.status, ev.fam), running: null };
    }
    case 'net':
      return { ...s, net: { what: ev.what, at: Date.now() }, netLog: [...s.netLog, { what: ev.what, ts: ev.ts }].slice(-200) };
    case 'voice': {
      const failed = ev.last_error === 'voice_error' && s.voice.last_error !== 'voice_error';
      return {
        ...s,
        voice: { available: ev.available, mode: ev.mode, speaking: ev.speaking, last_error: ev.last_error ?? null, waiting_memory: ev.waiting_memory ?? null },
        voiceErrorAt: failed ? Date.now() : s.voiceErrorAt,
        voiceDroppedAt: ev.last_error === 'voice_dropped_busy' && s.voice.last_error !== 'voice_dropped_busy'
          ? Date.now() : s.voiceDroppedAt,
      };
    }
    case 'voice_partial':
      return { ...s, live: ev.text };
    case 'lip':
      return s; // taken by the socket into lip.ts (the reducer stays pure: StrictMode runs it twice)
    case 'voice_wake':
      return { ...s, live: '' };
    case 'boot':
      return { ...s, boot: { stt: ev.stt, wake: ev.wake, tts: ev.tts, model: ev.model, startedAt: ev.startedAt, readyAt: ev.readyAt, failed: ev.failed ?? null, lastFailure: ev.lastFailure ?? null, failureMemory: ev.failureMemory ?? null, failureRead: ev.failureRead ?? null, reading: ev.reading ?? null, onProcessor: !!ev.onProcessor } };
    case 'surfaces':
      return { ...s, surfaces: { sessions: ev.sessions, memory: ev.memory, memory_revision: ev.memory_revision, tools: ev.tools, triggers: ev.triggers } };
    case 'session':
      return { ...s, session: { id: ev.id, label: ev.label } };
    case 'context':
      return { ...s, activity: ev.activity };
    default:
      return s;
  }
}

/** subscribes to the host's event socket (`/events`, the native bridge's WebSocket) and mirrors its events into one
 *  state object; reconnects with backoff when the socket drops (the host replays the current state on connect). */
export function useBaxy(): BaxyStore {
  const [state, dispatch] = useReducer(reduce, INITIAL);

  useEffect(() => {
    let cancelled = false;
    let retry = 0;
    let timer: number | null = null;
    let ws: WebSocket | null = null;
    const schedule = () => {
      if (cancelled) return;
      retry = Math.min(retry + 1, 6);
      timer = window.setTimeout(connect, Math.min(8000, 500 * 2 ** (retry - 1)));
    };
    const connect = () => {
      timer = null;
      if (cancelled) return;
      const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      try {
        ws = new WebSocket(`${proto}//${window.location.host}/events`);
      } catch {
        schedule();
        return;
      }
      ws.onopen = () => {
        if (cancelled) { ws?.close(); return; }
        retry = 0;
        dispatch({ type: '_connected', value: true });
      };
      ws.onmessage = (e) => {
        if (cancelled) return;
        try {
          const ev = JSON.parse(e.data as string) as ServerEvent;
          // the voice's timeline for the mouth is read every frame by the avatar: it never re-renders the view
          if (ev.type === 'lip') lipPush(ev); else dispatch(ev);
        } catch { /* a malformed event changes nothing */ }
      };
      ws.onclose = () => {
        if (cancelled) return;
        dispatch({ type: '_connected', value: false });
        schedule();
      };
    };
    connect();
    return () => {
      cancelled = true;
      if (timer !== null) window.clearTimeout(timer);
      if (ws && ws.readyState !== WebSocket.CLOSED) ws.close();
    };
  }, []);

  return state;
}
