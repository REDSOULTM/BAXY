import { useEffect, useState } from 'react';
import type { ServerEvent, ActivityEntry, ConvState, ModelInfo } from '../types';

export interface SurfacesCount {
  sessions: number;
  memory: number;
  // Encargo I2: the number of the store's last change by chat; an open memory panel reads its list again on it.
  memory_revision?: number;
  tools: number;
}

export interface SessionInfo {
  id: string;
  label: string;
}

export interface AgentStatus {
  built: boolean;
  ready: boolean;
  /** the observed failure's code (retry_without_close, core_disconnected, mind_unavailable, decision_unavailable,
   *  turn_failed), null when there is none */
  failure?: string | null;
  /** a risky call waits for the person's Sí or No (the buttons under BAXY's question) */
  pendingConfirmation?: boolean;
}

export interface EventStreamState {
  connected: boolean;
  convState: ConvState;
  entries: ActivityEntry[];
  model: ModelInfo | null;
  surfaces: SurfacesCount | null;
  session: SessionInfo | null;
  /** the shell's gate. while !ready, the chat input is disabled so nothing
   *  is queued into the void. */
  agent: AgentStatus;
}

const MAX_ENTRIES = 80;
const INITIAL: EventStreamState = {
  connected: false,
  convState: 'idle',
  entries: [],
  model: null,
  surfaces: null,
  session: null,
  agent: { built: false, ready: false },
};

/** subscribe to the shell's event socket at `/events` (the native bridge's WebSocket). mirrors its events into a
 *  single reducer-shaped state object. reconnects with backoff if the socket drops. */
export function useEventStream(): EventStreamState {
  const [state, setState] = useState<EventStreamState>(INITIAL);

  // Belt-and-suspenders poll of /agent/status: the same state the `agent`
  // event carries, read every 4s in case an event was missed.
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
            ready: !!data.ready,
            failure: data.failure ?? null,
            pendingConfirmation: !!data.pendingConfirmation,
          };
          if (
            next.built === prev.agent.built
            && next.ready === prev.agent.ready
            && next.failure === (prev.agent.failure ?? null)
            && next.pendingConfirmation === !!prev.agent.pendingConfirmation
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
        let parsed: ServerEvent;
        try {
          parsed = JSON.parse(ev.data);
        } catch {
          return;
        }
        setState((prev) => reduce(prev, parsed));
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
    case 'model':
      return { ...prev, model: ev.info };
    case 'surfaces':
      return {
        ...prev,
        surfaces: {
          sessions: ev.sessions,
          memory: ev.memory,
          memory_revision: ev.memory_revision,
          tools: ev.tools,
        },
      };
    case 'session':
      return { ...prev, session: { id: ev.id, label: ev.label } };
    case 'agent':
      return {
        ...prev,
        agent: {
          built: ev.built, ready: ev.ready, failure: ev.failure ?? null, pendingConfirmation: !!ev.pendingConfirmation,
        },
      };
    case 'log_clear':
      return { ...prev, entries: [] };
    default:
      return prev;
  }
}
