import { useCallback, useEffect, useRef, useState } from 'react';
import { SubstratePanel } from './components/SubstratePanel';
import { ActivityPanel } from './components/ActivityPanel';
import { FieldCenter } from './components/FieldCenter';
import { TitleBar } from './components/TitleBar';
import { SettingsPanel } from './components/SettingsPanel';
import { SessionsPanel } from './components/SessionsPanel';
import { MemoryPanel } from './components/MemoryPanel';
import { TriggersPanel } from './components/TriggersPanel';
import { ToolsPanel } from './components/ToolsPanel';
import { ToastHost } from './components/ToastHost';
import { useClock } from './hooks/useClock';
import { useEventStream } from './hooks/useEventStream';
import type { SurfacesCount } from './hooks/useEventStream';
import { toastError } from './hooks/useToast';
import type { ConvState } from './types';
// the prototype's styles.css is loaded literal — this is the single source of
// truth for all cosmetic rules. additions live at the bottom of that file.
import './styles/prototype.css';

type OpenPanel = 'settings' | 'sessions' | 'memory' | 'triggers' | 'tools' | null;
type SurfaceId = 'sessions' | 'memory' | 'triggers' | 'tools';

/** Mic has three modes. `listening` = always-on wake word; `ptt` = push-to-talk
 *  (mic loop is up, but capture only fires on right-click trigger); `off` =
 *  voice loop fully stopped. Click-left cycles listening↔off; click-right
 *  toggles ptt against the previous on-mode. */
export type MicMode = 'listening' | 'ptt' | 'off';

const STATE_CYCLE: ConvState[] = ['idle', 'listening', 'thinking', 'speaking', 'standby'];
// 2026-05-26: un solo perfil operante (vram4) + standby; el hotkey alterna entre esos dos.
const PROFILE_CYCLE = ['vram4', 'standby'];
const ONLY_ACCESS_MODE = 'normal';

export default function App() {
  const { clock } = useClock();
  const stream = useEventStream();

  const [openPanel, setOpenPanel] = useState<OpenPanel>(null);
  // mic mode reflects the voice loop on the backend. defaults to 'listening'
  // (always-on wake word) since server.py auto-enables voice on boot. mode
  // is persisted to localStorage so it survives reloads.
  const [micMode, setMicMode] = useState<MicMode>(() => {
    const stored = localStorage.getItem('field.mic_mode');
    if (stored === 'listening' || stored === 'ptt' || stored === 'off') return stored;
    return 'listening';
  });
  useEffect(() => { localStorage.setItem('field.mic_mode', micMode); }, [micMode]);

  // poll /voice/status once after mount + every 4s while the page is open,
  // so a backend-driven voice state change (load failed, mic device went
  // away, etc.) shows up in the UI. backend only knows on/off — we keep our
  // own ptt/listening distinction client-side; if backend reports running
  // false while we think we're on, flip to 'off' so the icon stays honest.
  // Guards the status-sync from fighting the mount auto-start: until the
  // auto-start has had its chance (and while a start is in flight), we must NOT
  // flip the UI to 'off' just because the backend loop hasn't finished booting.
  const voiceBootSettled = useRef(false);
  useEffect(() => {
    let cancelled = false;
    const sync = async () => {
      try {
        const r = await fetch('/voice/status');
        if (cancelled || !r.ok) return;
        const data = (await r.json()) as { running?: boolean };
        if (typeof data.running !== 'boolean') return;
        setMicMode((prev) => {
          if (data.running && prev === 'off') return 'listening';
          // Only DROP to 'off' once the auto-start boot has settled — otherwise
          // the first poll (backend still loading models) would wrongly mute the
          // UI and cancel the auto-start. After boot, a genuine backend stop
          // (device lost, load failed) still flips us off as before.
          if (!data.running && prev !== 'off' && voiceBootSettled.current) return 'off';
          return prev;
        });
      } catch { /* ignore */ }
    };
    sync();
    const id = window.setInterval(sync, 4000);
    return () => { cancelled = true; window.clearInterval(id); };
  }, []);
  // Start from the last-used chip, defaulting to vram4 (a safe modest profile)
  // — NOT the old 'bal' alias, which matches no vramN chip and left nothing
  // highlighted. The real source of truth is the backend; we sync it on mount
  // below so the highlighted chip always reflects what's actually loaded.
  const [profile, setProfile] = useState<string>(() => {
    return localStorage.getItem('field.profile') ?? 'vram4';
  });
  // True until we've reconciled `profile` with GET /profile. Prevents the
  // push-effect below from PUTting (and restarting llama-server) on first
  // mount before we even know the real active profile.
  const profileSynced = useRef(false);
  // Modo de accesibilidad (normal | no_vidente | movilidad). Mismo ciclo que
  // profile: arranca del último, se reconcilia con GET /accessibility en mount,
  // y se PUT-ea al cambiar. NO reinicia el server (es capa de comportamiento).
  const [accessMode, setAccessMode] = useState<string>(() => {
    const stored = localStorage.getItem('field.accessMode');
    return stored === ONLY_ACCESS_MODE ? stored : ONLY_ACCESS_MODE;
  });
  const accessSynced = useRef(false);
  // value last adopted FROM the backend (the persisted "last config"). The
  // push-effect skips PUTting when accessMode equals this, so reconciling the
  // backend value never fires a redundant PUT (which emitted a spurious
  // "accessibility · X" activity entry on every boot).
  const accessReconciled = useRef<string | null>(null);
  const [activeSurface, setActiveSurface] = useState<SurfaceId>(() => {
    const stored = localStorage.getItem('field.surface');
    if (stored === 'sessions' || stored === 'memory' || stored === 'triggers' || stored === 'tools') {
      return stored;
    }
    return 'memory';
  });

  // persist surface so the chip selection survives reloads
  useEffect(() => {
    localStorage.setItem('field.surface', activeSurface);
  }, [activeSurface]);

  // poll /surfaces every 5s for counts. The poll wins after its first verified
  // response because the initial WS snapshot is not updated by panel mutations.
  // Lifted here
  // from ActivityPanel so BOTH columns share the same live counts — the redesign
  // splits the four surfaces: triggers/tools on the left, sessions/memory on the
  // right.
  const [polledSurfaces, setPolledSurfaces] = useState<SurfacesCount | null>(null);
  useEffect(() => {
    let cancelled = false;
    const fetchSurfaces = async () => {
      try {
        const r = await fetch('/surfaces');
        if (cancelled || !r.ok) return;
        setPolledSurfaces((await r.json()) as SurfacesCount);
      } catch { /* ignore */ }
    };
    fetchSurfaces();
    const id = window.setInterval(fetchSurfaces, 5000);
    return () => { cancelled = true; window.clearInterval(id); };
  }, []);
  const liveSurfaces = polledSurfaces ?? stream.surfaces;

  // vision_threshold warning: el banner aparece cuando llega el evento
  // del WS; visionDismissedAt guarda el image_count que el usuario ya
  // cerro para que un mismo aviso no reaparezca cada render — solo si
  // el counter cruza un nuevo umbral en el futuro reaparece.
  const [visionDismissedAt, setVisionDismissedAt] = useState<number | null>(null);
  const effectiveVisionThreshold = (stream.visionThreshold
    && (visionDismissedAt === null
      || stream.visionThreshold.imageCount > visionDismissedAt))
    ? stream.visionThreshold
    : null;
  const onRecycleServer = useCallback(async () => {
    try {
      const r = await fetch('/agent/recycle_server', { method: 'POST' });
      if (!r.ok) throw new Error(`status ${r.status}`);
      // recycle reseteo el counter en el backend; ocultamos el banner local.
      setVisionDismissedAt(stream.visionThreshold?.imageCount ?? null);
    } catch (e) {
      toastError(`recycle failed · ${String(e).replace(/^Error: /, '')}`);
    }
  }, [stream.visionThreshold]);
  const onDismissVisionWarning = useCallback(() => {
    setVisionDismissedAt(stream.visionThreshold?.imageCount ?? null);
  }, [stream.visionThreshold]);

  // On mount: read the REAL active profile from the backend and reflect it in
  // the chip. This is the source of truth (the launcher booted some profile),
  // so the highlighted chip matches what's actually loaded — without this the
  // chip showed a stale localStorage value (or the old 'bal' alias) and
  // nothing was highlighted. We mark profileSynced AFTER setting it so the
  // push-effect below doesn't immediately PUT it back (which would restart
  // llama-server for no reason).
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const r = await fetch('/profile');
        if (!cancelled && r.ok) {
          const data = await r.json();
          if (data?.active) setProfile(String(data.active));
        }
      } catch { /* keep the localStorage default; sync flag still set below */ }
      finally { profileSynced.current = true; }
    })();
    return () => { cancelled = true; };
  }, []);

  // Push profile changes to the backend so set_active_profile +
  // apply_profile_to_env + the llama-server restart happen. We SKIP the very
  // first run (before the mount-sync above resolves) so we don't fire a PUT —
  // and a model reload — for a profile the backend already has. After that,
  // every user click PUTs once. Surface a toast on rejection (chip stays
  // selected for transparency).
  useEffect(() => {
    if (!profileSynced.current) return;  // don't PUT until reconciled
    localStorage.setItem('field.profile', profile);
    fetch('/profile', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name: profile }),
    })
      .then((r) => { if (!r.ok) toastError(`profile change rejected · ${r.status}`); })
      .catch(() => toastError('profile change failed · backend unreachable'));
  }, [profile]);

  // Accessibility mode: the backend's persisted active_accessibility_mode.txt is
  // the source of truth for "what the user left last time". Reconcile from it on
  // mount and remember that value so the push-effect below does NOT PUT it back
  // (which would emit a spurious activity entry and could clobber it on boot).
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const r = await fetch('/accessibility');
        if (!cancelled && r.ok) {
          const data = await r.json();
          if (data?.active) {
            const rawActive = String(data.active);
            const active = ONLY_ACCESS_MODE;
            accessReconciled.current = active;
            localStorage.setItem('field.accessMode', active);
            setAccessMode(active);
            if (rawActive !== active) {
              fetch('/accessibility', {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ mode: active }),
              }).catch(() => { /* backend may be offline during static previews */ });
            }
          }
        }
      } catch { /* keep localStorage default */ }
      finally { accessSynced.current = true; }
    })();
    return () => { cancelled = true; };
  }, []);

  useEffect(() => {
    if (!accessSynced.current) return;  // don't PUT until reconciled
    // Skip the PUT when this value is exactly what we just read from the backend
    // — it's already persisted there; re-PUTting it only spams the activity log.
    if (accessMode === accessReconciled.current) return;
    accessReconciled.current = null;  // subsequent equal values are user-driven
    localStorage.setItem('field.accessMode', accessMode);
    fetch('/accessibility', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ mode: accessMode }),
    })
      .then((r) => { if (!r.ok) toastError(`accessibility change rejected · ${r.status}`); })
      .catch(() => toastError('accessibility change failed · backend unreachable'));
  }, [accessMode]);

  // debug override + auto-cycler when WS is down
  const [debugState, setDebugState] = useState<ConvState | null>(null);
  const debugOn =
    typeof window !== 'undefined'
    && new URLSearchParams(window.location.search).has('debug');

  useEffect(() => {
    if (!debugOn || stream.connected) return;
    let i = 0;
    const id = window.setInterval(() => {
      i = (i + 1) % STATE_CYCLE.length;
      setDebugState(STATE_CYCLE[i]);
    }, 3500);
    return () => window.clearInterval(id);
  }, [debugOn, stream.connected]);

  // when the WS is live, debug override is ignored so real events win.
  // The mic being OFF does NOT deactivate the app: text mode is a fully alive
  // mode. We keep the real conversational state (idle stays idle, alive) so the
  // field, neurons and border keep breathing while the user types. Only an
  // actual backend disconnect drops us to a degraded look (see `online` below);
  // muting the mic just mutes the mic.
  const effectiveState: ConvState =
    stream.connected ? stream.convState : (debugState ?? stream.convState);

  // global keyboard shortcuts. mirror the legacy QShortcut bindings so users
  // of the PyQt6 GUI find the same muscle memory here. shortcuts that hit
  // network endpoints (clear/new/redetect) are fired via plain fetch — no
  // race with React state.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      // ignore shortcuts when typing in an input/textarea, except Escape
      const tgt = e.target as HTMLElement | null;
      const tag = tgt?.tagName;
      const inField = tag === 'INPUT' || tag === 'TEXTAREA';

      if (e.key === 'Escape') {
        setOpenPanel(null);
        return;
      }
      if (inField) return;

      // F11 → toggle fullscreen
      if (e.key === 'F11') {
        e.preventDefault();
        if (document.fullscreenElement) {
          document.exitFullscreen().catch(() => { /* ignore */ });
        } else {
          document.documentElement.requestFullscreen().catch(() => { /* ignore */ });
        }
        return;
      }
      // "/" → focus chat input
      if (e.key === '/' && !e.ctrlKey && !e.metaKey) {
        e.preventDefault();
        const input = document.querySelector<HTMLInputElement>('.chat .line input');
        input?.focus();
        return;
      }

      // ctrl + ... shortcuts
      if (!e.ctrlKey && !e.metaKey) return;
      const k = e.key.toLowerCase();
      if (k === 'l') {
        e.preventDefault();
        fetch('/log/clear', { method: 'POST' }).catch(() => { /* ignore */ });
      } else if (k === 'n' && !e.shiftKey) {
        e.preventDefault();
        fetch('/sessions/new', { method: 'POST' }).catch(() => { /* ignore */ });
      } else if (k === ',') {
        e.preventDefault();
        setOpenPanel('settings');
      } else if (k === 's' && e.shiftKey) {
        e.preventDefault();
        setOpenPanel('sessions');
      } else if (k === 't' && !e.shiftKey) {
        e.preventDefault();
        setOpenPanel('triggers');
      } else if (k === 'm' && !e.shiftKey) {
        e.preventDefault();
        setOpenPanel('memory');
      } else if (k === 'e' && !e.shiftKey) {
        e.preventDefault();
        setOpenPanel('tools');
      } else if (k === 'g' && e.shiftKey) {
        e.preventDefault();
        // cycle high -> low VRAM using the canonical names accepted by
        // profiles.py and shown by the chips.
        const idx = PROFILE_CYCLE.indexOf(profile);
        const next = PROFILE_CYCLE[(idx + 1) % PROFILE_CYCLE.length] ?? 'vram4';
        setProfile(next);
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [profile]);

  const closePanel = useCallback(() => setOpenPanel(null), []);

  const postActivity = useCallback(async (src: string, msg: string) => {
    try {
      await fetch('/activity', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ src, msg }),
      });
    } catch {
      /* server down — silently drop; this is UI flavor, not state */
    }
  }, []);

  // top-bar "+ new" → POST /sessions/new clears the agent + history and the
  // backend pushes its own SYSTEM activity entry, so we don't need to add one
  // here. postActivity stays as a fallback if the endpoint isn't reachable.
  const onNewSession = useCallback(async () => {
    try {
      const r = await fetch('/sessions/new', { method: 'POST' });
      if (!r.ok) throw new Error(`status ${r.status}`);
    } catch {
      postActivity('SYSTEM', 'new session · backend unreachable; UI-only reset');
    }
  }, [postActivity]);

  const onHelp = useCallback(() => {
    postActivity(
      'SYSTEM',
      'shortcuts: enter sends · / focus · ⌘k history · shift+enter newline · esc closes modal',
    );
  }, [postActivity]);

  // Mic has three modes — see MicMode docstring. Left click cycles
  // listening↔off (the common case: just want to mute the mic). Right click
  // toggles ptt mode: if you're in listening it enters ptt and immediately
  // arms a capture; if already in ptt it goes back to listening. Right click
  // while in off turns voice on into ptt (so the user can opt-in to manual
  // capture without going through always-listen first).
  //
  // Backend only knows on/off through /voice/start and /voice/stop. We map:
  //   listening → /voice/start  (mic loop up, wake-word armed)
  //   ptt       → /voice/start  (mic loop up; capture only via /voice/trigger)
  //   off       → /voice/stop
  // /voice/trigger fires the wake event manually so the next phrase is
  // captured without saying 'gemma'.
  // True while /voice/start is loading the models (VAD + wake + STT +
  // Piper, ~1-3s blocking on the backend). Drives the mic button's
  // "loading" animation so the icon stays lit + pulsing instead of
  // flickering red→black while the request is in flight.
  const [micLoading, setMicLoading] = useState(false);
  const setMicModeAsync = useCallback(async (next: MicMode, opts?: { triggerAfter?: boolean }) => {
    const prev = micMode;
    // Optimistic: light the icon immediately so the click feels responsive.
    setMicMode(next);
    if (next === 'off') {
      try {
        const r = await fetch('/voice/stop', { method: 'POST' });
        if (!r.ok) throw new Error(`stop ${r.status}`);
      } catch (e) {
        setMicMode(prev);
        toastError(`mic off failed · ${String(e).replace(/^Error: /, '')}`);
      }
      return;
    }
    // listening / ptt need the loop running. The backend blocks while it
    // loads models, so show the loading state and DON'T revert just
    // because it took a few seconds — only revert on an explicit failure.
    setMicLoading(true);
    try {
      const r = await fetch('/voice/start', { method: 'POST' });
      if (!r.ok) throw new Error(`start ${r.status}`);
      const data = (await r.json()) as { ok?: boolean; running?: boolean; last_error?: string | null };
      if (data.ok === false || data.running === false) {
        throw new Error(data.last_error || 'voice failed to start');
      }
      if (opts?.triggerAfter) {
        await fetch('/voice/trigger', { method: 'POST' });
      }
    } catch (e) {
      setMicMode(prev);
      toastError(`mic ${next} failed · ${String(e).replace(/^Error: /, '')}`);
    } finally {
      setMicLoading(false);
    }
  }, [micMode]);

  // AUTO-START voice on mount, but RESPECT the user's choice. The persisted
  // micMode ('listening'/'ptt'/'off') is the source of truth: if it's not
  // 'off' we boot the backend voice loop automatically (so the mic is armed AND
  // Gemma's TTS plays without the user having to click the mic first). If the
  // user previously turned the mic OFF, we honor that and stay silent — we do
  // NOT auto-start. One-shot: runs once after mount.
  const didAutoStartVoice = useRef(false);
  useEffect(() => {
    if (didAutoStartVoice.current) return;
    didAutoStartVoice.current = true;
    if (micMode !== 'off') {
      // bring the backend loop up to match the persisted on-state. Don't
      // arm a capture (no triggerAfter) — just enable wake-word + TTS.
      const id = window.setTimeout(() => {
        setMicModeAsync(micMode).finally(() => { voiceBootSettled.current = true; });
      }, 0);
      return () => window.clearTimeout(id);
    } else {
      // user chose 'off' — nothing to start; let the sync act normally.
      voiceBootSettled.current = true;
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const onMicLeftClick = useCallback(() => {
    // listening → off. off → listening. ptt → off (so left click is always
    // "mute me"; to leave ptt the user right-clicks again).
    setMicModeAsync(micMode === 'off' ? 'listening' : 'off');
  }, [micMode, setMicModeAsync]);

  const onMicRightClick = useCallback(() => {
    // toggle ptt vs the previous on-mode. when leaving 'off' via right click
    // we go straight to ptt and arm a capture; that's the whole point of the
    // gesture (user wants to speak NOW without the wake word).
    if (micMode === 'ptt') {
      setMicModeAsync('listening');
    } else {
      setMicModeAsync('ptt', { triggerAfter: true });
    }
  }, [micMode, setMicModeAsync]);

  // clicking a surface card BOTH marks it active (visual carmesí border) AND
  // opens the matching modal — sessions opens SessionsPanel, memory/triggers/
  // tools open the generic InfoPanel with the right endpoint.
  const onSurface = useCallback((id: SurfaceId) => {
    setActiveSurface(id);
    setOpenPanel(id);
  }, []);

  // ---- aliveness vs. mic. These used to be the same thing (mic off → whole app
  // to standby), which made muting the mic look like powering the assistant down.
  // They are now independent:
  //   * `online`  — is the assistant alive? It is, as long as the backend is
  //                 reachable. This drives the traveling border. Text mode works
  //                 whenever the agent is ready, mic or no mic.
  //   * `voiceOn` — is the mic loop up? Drives the left-rail voice toggle only.
  // So with the mic off the app stays online (border travels, neurons breathe,
  // chat works); only the voice toggle reads "off". ----
  const online = stream.connected;
  const voiceOn = micMode !== 'off';
  const poweredRef = useRef(online);
  useEffect(() => { poweredRef.current = online; }, [online]);

  // Drive the traveling border light. Ramps speed UP when powered and decelerates
  // smoothly to a stop on standby (prototype app.jsx border loop, verbatim params).
  useEffect(() => {
    const frame = document.querySelector<HTMLElement>('.app-frame');
    if (!frame) return;
    let raf = 0;
    let last = performance.now();
    let nextPaint = last;
    let angle = 0;
    let speed = 1; // 0..1 fraction of full speed
    const FULL = 360 / 3.4; // deg/s at full speed
    const loop = (now: number) => {
      // Skip the repaint while the window is hidden (minimised) — no point
      // animating a border nobody sees, and it spares the CPU while gaming.
      if (typeof document !== 'undefined' && document.hidden) {
        last = now;
        raf = requestAnimationFrame(loop);
        return;
      }
      // A continuously rasterised conic gradient made an idle WebView consume
      // a material fraction of one CPU core. Ten paints per second preserve
      // the slow ambient travel without paying for 60 identical UI updates.
      if (now < nextPaint) {
        raf = requestAnimationFrame(loop);
        return;
      }
      const dt = Math.min(0.15, (now - last) / 1000);
      last = now;
      nextPaint = now + 100;
      const target = poweredRef.current ? 1 : 0;
      speed += (target - speed) * Math.min(1, dt * 2.6);
      if (target === 0 && speed < 0.012) speed = 0;
      angle = (angle + speed * FULL * dt) % 360;
      frame.style.setProperty('--bd-angle', angle.toFixed(2) + 'deg');
      raf = requestAnimationFrame(loop);
    };
    raf = requestAnimationFrame(loop);
    return () => cancelAnimationFrame(raf);
  }, []);

  // Recolor the border, the chrome accent (--carmine) and the metric bars
  // (--bar-color) per state — the prototype's SET table, verbatim. Chrome stays
  // carmesí at rest (idle/standby) and only takes the contrast color during an
  // active conversation state (listening/thinking/speaking), then returns to red.
  useEffect(() => {
    const frame = document.querySelector<HTMLElement>('.app-frame');
    if (!frame) return;
    const SET: Record<string, { base: string; mid: string; hi: string; peak: string; glow: string; bar: string }> = {
      standby:   { base: '#2a2f3a', mid: '#5B6580', hi: '#8B95A8', peak: '#D8DCE6', glow: 'rgba(139,149,168,0.75)', bar: '#5B6580' },
      idle:      { base: '#5a1a22', mid: '#B83A4A', hi: '#FF4D63', peak: '#FFE3E7', glow: 'rgba(255,77,99,0.9)',    bar: '#5B7FDB' },
      listening: { base: '#7A1E2B', mid: '#E55366', hi: '#FF6677', peak: '#FFFFFF', glow: 'rgba(255,102,119,0.95)', bar: '#6FA8B0' },
      thinking:  { base: '#1B2A5E', mid: '#2E4BA0', hi: '#5B7FDB', peak: '#C8D6F5', glow: 'rgba(91,127,219,0.9)',   bar: '#C9A66B' },
      speaking:  { base: '#6B5A2F', mid: '#C9A66B', hi: '#E8C98E', peak: '#F8EED2', glow: 'rgba(232,201,142,0.9)',  bar: '#7B95D9' },
    };
    const c = SET[effectiveState] || SET.idle;
    frame.style.setProperty('--bd-base', c.base);
    frame.style.setProperty('--bd-mid', c.mid);
    frame.style.setProperty('--bd-hi', c.hi);
    frame.style.setProperty('--bd-peak', c.peak);
    frame.style.setProperty('--bd-glow', c.glow);
    frame.style.setProperty('--bar-color', c.bar);
    const active = effectiveState === 'listening' || effectiveState === 'thinking' || effectiveState === 'speaking';
    frame.style.setProperty('--carmine', active ? c.bar : '#B83A4A');
  }, [effectiveState]);

  return (
    <div className="window-root">
      <TitleBar />
      <div className="app-frame">
      <div className="shell">
        {effectiveVisionThreshold && (
          <div className="vision-banner" role="alert" aria-live="polite">
            <span className="vision-banner-msg">
              vision leak ·{' '}
              <b>{effectiveVisionThreshold.imageCount}/{effectiveVisionThreshold.threshold}</b>{' '}
              imagenes procesadas · recyclar llama-server recomendado{' '}
              <span className="vision-banner-issue">({effectiveVisionThreshold.issue})</span>
            </span>
            <button type="button" className="vision-banner-btn" onClick={onRecycleServer}>
              recycle now
            </button>
            <button
              type="button"
              className="vision-banner-dismiss"
              onClick={onDismissVisionWarning}
              aria-label="dismiss warning"
            >
              ×
            </button>
          </div>
        )}
        <div className="cols">
          <div className="col left">
            <SubstratePanel
              convState={effectiveState}
              wsModel={stream.model}
              ctx={stream.ctx}
              accessMode={accessMode}
              onAccessMode={setAccessMode}
              online={online}
              voiceOn={voiceOn}
              onToggleVoice={onMicLeftClick}
              surfaces={liveSurfaces}
              activeSurface={activeSurface}
              onSurface={onSurface}
            />
          </div>
          <div className="col center">
            <FieldCenter
              convState={effectiveState}
              onDebugState={debugOn ? setDebugState : null}
              ctx={stream.ctx}
              micMode={micMode}
              micLoading={micLoading}
              onMicLeftClick={onMicLeftClick}
              onMicRightClick={onMicRightClick}
              agent={stream.agent}
              bootStage={stream.bootStage}
            />
          </div>
          <div className="col right">
            <ActivityPanel
              entries={stream.entries}
              session={stream.session}
              surfaces={liveSurfaces}
              activeSurface={activeSurface}
              onSurface={onSurface}
              clock={clock}
              settingsOpen={openPanel === 'settings'}
              onSettings={() => setOpenPanel(openPanel === 'settings' ? null : 'settings')}
              onNewSession={onNewSession}
              onHelp={onHelp}
            />
          </div>
        </div>

        {openPanel === 'settings' && (
          <SettingsPanel
            onClose={closePanel}
            profile={profile}
            onProfile={setProfile}
          />
        )}
        {openPanel === 'sessions' && <SessionsPanel onClose={closePanel} />}
        {openPanel === 'memory' && <MemoryPanel onClose={closePanel} />}
        {openPanel === 'triggers' && <TriggersPanel onClose={closePanel} />}
        {openPanel === 'tools' && <ToolsPanel onClose={closePanel} />}

        <ToastHost />
      </div>
      </div>
    </div>
  );
}
