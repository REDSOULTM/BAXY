import { useEffect, useState } from 'react';
import type { ServerEvent, ActivityEntry, ConvState, ModelInfo } from '../types';
import { pushToast } from './useToast';

export interface FieldReadout {
  entropy: number;
  temperature: number;
  tokens_per_s: number;
  draw_w: number;
}

export interface CtxBudget {
  used: number;
  budget: number;
}

export interface SurfacesCount {
  sessions: number;
  memory: number;
  triggers: number;
  tools: number;
}

export interface SessionInfo {
  id: string;
  label: string;
}

export interface AgentStatus {
  built: boolean;
  healthy: boolean;
  ready: boolean;
}

/** Latest boot_stage event from the backend. Drives the placeholder text and
 *  the inline retry button on the chat input. Null until the first stage is
 *  emitted (very brief — the runner emits one within the first thread tick). */
export interface BootStage {
  stage: string;
  label: string;
  progress: number | null;
  error: string | null;
}

/** Estado del mitigador del mmproj leak (issue #21690). null = no se cruzo
 *  el umbral; cuando se cruza, la UI muestra un banner amber con el conteo
 *  + boton para llamar a POST /agent/recycle_server. */
export interface VisionThreshold {
  imageCount: number;
  threshold: number;
  issue: string;
}

export interface EventStreamState {
  connected: boolean;
  convState: ConvState;
  entries: ActivityEntry[];
  tokens: number;
  model: ModelInfo | null;
  field: FieldReadout | null;
  ctx: CtxBudget | null;
  surfaces: SurfacesCount | null;
  session: SessionInfo | null;
  /** boot lifecycle of the agent + llama-server. while !ready, the chat
   *  input is disabled so users don't queue prompts into the void. */
  agent: AgentStatus;
  /** what's currently loading. */
  bootStage: BootStage | null;
  /** mmproj leak warning (#21690); null mientras no se cruzo el umbral. */
  visionThreshold: VisionThreshold | null;
}

const MAX_ENTRIES = 80;
const INITIAL: EventStreamState = {
  connected: false,
  convState: 'idle',
  entries: [],
  tokens: 0,
  model: null,
  field: null,
  ctx: null,
  surfaces: null,
  session: null,
  agent: { built: false, healthy: false, ready: false },
  bootStage: null,
  visionThreshold: null,
};

/** subscribe to the FastAPI WS at `/events`. mirrors the server's BUS events
 *  into a single reducer-shaped state object. reconnects with backoff if the
 *  socket drops, so the UI survives a server restart. */
export function useEventStream(): EventStreamState {
  const [state, setState] = useState<EventStreamState>(INITIAL);

  // Belt-and-suspenders poll of /agent/status. The WS emits `agent` events
  // only when the runner publishes one — if llama-server dies out from under
  // us (crash, OOM, manual kill), the runner never knows and the WS goes
  // quiet while the input stays unlocked. The 4s poll catches that case so
  // the gate closes within seconds of the backend going unhealthy.
  useEffect(() => {
    let cancelled = false;
    const sync = async () => {
      try {
        const r = await fetch('/agent/status');
        if (cancelled || !r.ok) return;
        const data = (await r.json()) as AgentStatus;
        if (typeof data.built !== 'boolean') return;
        setState((prev) => {
          const next: AgentStatus = {
            built: !!data.built,
            healthy: !!data.healthy,
            ready: !!data.ready,
          };
          if (
            next.built === prev.agent.built
            && next.healthy === prev.agent.healthy
            && next.ready === prev.agent.ready
          ) return prev;
          return { ...prev, agent: next };
        });
      } catch { /* ignore */ }
    };
    sync();
    const id = window.setInterval(sync, 4000);
    return () => { cancelled = true; window.clearInterval(id); };
  }, []);

  useEffect(() => {
    // per-mount state — using local variables instead of refs so each mount
    // (including StrictMode's double-invoke in dev) has its own bookkeeping
    // and the previous mount's lingering timers can't reconnect the new one.
    let cancelled = false;
    let retryCount = 0;
    let pendingTimer: number | null = null;
    let currentWs: WebSocket | null = null;

    const schedule = () => {
      if (cancelled) return;
      retryCount = Math.min(retryCount + 1, 6);
      // exponential backoff capped at 8s: 0.5, 1, 2, 4, 8, 8, 8…
      const delayMs = Math.min(8000, 500 * 2 ** (retryCount - 1));
      pendingTimer = window.setTimeout(() => {
        pendingTimer = null;
        connect();
      }, delayMs);
    };

    const connect = () => {
      if (cancelled) return;
      // resolve the ws url from window.location so the same code works behind
      // any port-forward / reverse proxy without configuration.
      const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      const url = `${proto}//${window.location.host}/events`;
      let ws: WebSocket;
      try {
        ws = new WebSocket(url);
      } catch {
        // some browsers throw on invalid url synchronously
        schedule();
        return;
      }
      currentWs = ws;

      ws.onopen = () => {
        if (cancelled) { ws.close(); return; }
        retryCount = 0;
        setState((s) => ({ ...s, connected: true }));
      };

      ws.onmessage = (ev) => {
        if (cancelled) return;
        let parsed: ServerEvent | { type: 'heartbeat' } | { kind: string; [k: string]: unknown };
        try {
          parsed = JSON.parse(ev.data);
        } catch {
          return;
        }
        // Normalizacion: el BUS publica eventos con `kind` (prewarm.py,
        // multimodal.py) o con `type` (boot_progress.py, agent_runner.py).
        // Aceptamos ambos y el reducer matchea sobre el discriminante
        // resuelto.
        const rec = parsed as Record<string, unknown>;
        if (rec.type === 'heartbeat') return;
        if (!rec.type && typeof rec.kind === 'string') {
          rec.type = rec.kind;
        }
        setState((prev) => reduce(prev, rec as ServerEvent));
      };

      ws.onerror = () => {
        // onerror is followed by onclose; let the close handler retry.
      };

      ws.onclose = () => {
        if (cancelled) return;
        setState((s) => ({ ...s, connected: false }));
        schedule();
      };
    };

    connect();

    return () => {
      cancelled = true;
      if (pendingTimer !== null) {
        window.clearTimeout(pendingTimer);
        pendingTimer = null;
      }
      if (currentWs && currentWs.readyState !== WebSocket.CLOSED) {
        currentWs.close();
      }
    };
  }, []);

  return state;
}

function reduce(prev: EventStreamState, ev: ServerEvent): EventStreamState {
  switch (ev.type) {
    case 'state':
      return { ...prev, convState: ev.value };
    case 'activity': {
      // newest first; cap at MAX_ENTRIES to keep memory bounded
      const entries = [ev.entry, ...prev.entries].slice(0, MAX_ENTRIES);
      return { ...prev, entries };
    }
    case 'tokens':
      return { ...prev, tokens: prev.tokens + ev.delta };
    case 'model':
      return { ...prev, model: ev.info };
    case 'field':
      return {
        ...prev,
        field: {
          entropy: ev.entropy,
          temperature: ev.temperature,
          tokens_per_s: ev.tokens_per_s,
          draw_w: ev.draw_w,
        },
      };
    case 'ctx':
      return { ...prev, ctx: { used: ev.used, budget: ev.budget } };
    case 'surfaces':
      return {
        ...prev,
        surfaces: {
          sessions: ev.sessions,
          memory: ev.memory,
          triggers: ev.triggers,
          tools: ev.tools,
        },
      };
    case 'session':
      return { ...prev, session: { id: ev.id, label: ev.label } };
    case 'agent':
      return {
        ...prev,
        agent: { built: ev.built, healthy: ev.healthy, ready: ev.ready },
      };
    case 'boot_stage': {
      // A stage that reports phase:"completed" (e.g. the profile swap) is a
      // ONE-SHOT that finished — clear the boot overlay so the placeholder
      // returns to the normal chat prompt instead of getting stuck on the
      // stage name ("profile_swap") forever.
      if (ev.phase === 'completed' || ev.stage === 'ready') {
        return { ...prev, bootStage: null };
      }
      // El shape extendido (prewarm.py) trae elapsed_s/ok/system_prompt_chars
      // en lugar de label/progress. Construimos un label legible asi la UI
      // (FieldCenter placeholder + log) muestra info util sin caso especial.
      let label = ev.label ?? null;
      let progress = ev.progress ?? null;
      const error = ev.error ?? null;
      if (!label) {
        if (ev.stage === 'prewarm_start') {
          const chars = typeof ev.system_prompt_chars === 'number'
            ? ` (${ev.system_prompt_chars} chars)` : '';
          label = `prewarm · warming KV cache${chars}`;
        } else if (ev.stage === 'prewarm_done') {
          const dt = typeof ev.elapsed_s === 'number' ? ` in ${ev.elapsed_s.toFixed(1)}s` : '';
          if (ev.ok) {
            label = `prewarm · KV cache primed${dt}`;
            progress = 1;
          } else if (error) {
            label = `prewarm · failed${dt}`;
          } else {
            label = `prewarm · empty result${dt}`;
          }
        } else {
          label = ev.stage;
        }
      }
      return {
        ...prev,
        bootStage: { stage: ev.stage, label, progress, error },
      };
    }
    case 'vision_threshold_reached':
      return {
        ...prev,
        visionThreshold: {
          imageCount: ev.image_count,
          threshold: ev.threshold,
          issue: ev.issue,
        },
      };
    case 'voice_no_speech':
      // Capture dropped (silence / Whisper hallucination). Give the user who
      // tried to speak a brief cue instead of a silent drop to idle. Stable id
      // dedups rapid repeats. convState returns to idle via the state event the
      // pipeline emits right after, so we only surface the toast here.
      pushToast({ id: 'voice-no-speech', kind: 'info', msg: 'No te entendí — probá de nuevo', ttlMs: 2500 });
      return prev;
    case 'log_clear':
      // wipe activity entries; tokens stay (they reflect lifetime usage).
      return { ...prev, entries: [] };
    case 'metric':
      // metrics are also published over WS in future passes; for now the
      // SubstratePanel still polls /metrics, so we ignore this branch.
      return prev;
    default:
      return prev;
  }
}
