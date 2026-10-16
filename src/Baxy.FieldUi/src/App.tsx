import { useCallback, useEffect, useRef, useState } from 'react';
import { SubstratePanel } from './components/SubstratePanel';
import { ActivityPanel } from './components/ActivityPanel';
import { FieldCenter } from './components/FieldCenter';
import { TitleBar } from './components/TitleBar';
import { SettingsPanel } from './components/SettingsPanel';
import { SessionsPanel } from './components/SessionsPanel';
import { MemoryPanel } from './components/MemoryPanel';
import { ToolsPanel } from './components/ToolsPanel';
import { ToastHost } from './components/ToastHost';
import { useClock } from './hooks/useClock';
import { useEventStream } from './hooks/useEventStream';
import type { SurfacesCount } from './hooks/useEventStream';
import { toastError } from './hooks/useToast';
import { startNewSession } from './hooks/newSession';
// the cosmetic rules: the prototype's stylesheet with this app's additions.
import './styles/prototype.css';

type OpenPanel = 'settings' | 'sessions' | 'memory' | 'tools' | null;
type SurfaceId = 'sessions' | 'memory' | 'tools';

/** The voice is on or off. `listening` = the voice loop is up and saying «Baxy»
 *  starts a request; a right click also starts one at once, without the wake
 *  word, and the voice goes back to waiting for «Baxy» after it. `off` = the
 *  voice loop is stopped. */
export type MicMode = 'listening' | 'off';

// The interface's two presentations. The profile's file on the host is the only
// source (GET/PUT /accessibility); the chat switches the same file.
export type AccessMode = 'normal' | 'accessible';
export type ConfirmationPolicy = 'normal' | 'bypass';

export default function App() {
  const { clock } = useClock();
  const stream = useEventStream();

  const [openPanel, setOpenPanel] = useState<OpenPanel>(null);
  // mic mode reflects the voice loop on the host. defaults to 'listening' (the
  // wake word armed), which the mount auto-start below brings up. mode is
  // persisted to localStorage so it survives reloads; an earlier 'ptt' ran the
  // same wake-word loop, so it reads as 'listening'.
  const [micMode, setMicMode] = useState<MicMode>(() => {
    const stored = localStorage.getItem('field.mic_mode');
    return stored === 'off' ? 'off' : 'listening';
  });
  useEffect(() => { localStorage.setItem('field.mic_mode', micMode); }, [micMode]);

  // poll /voice/status once after mount + every 4s while the page is open,
  // so a backend-driven voice state change (load failed, mic device went
  // away, etc.) shows up in the UI. if the backend reports running false
  // while we think we're on, flip to 'off' so the icon stays honest.
  // Guards the status-sync from fighting the mount auto-start: until the
  // auto-start has had its chance (and while a start is in flight), we must NOT
  // flip the UI to 'off' just because the backend loop hasn't finished booting.
  const voiceBootSettled = useRef(false);
  // the voice's last trouble the host observed (voice_unavailable, voice_error, voice_dropped_busy), shown on the mic.
  const [voiceError, setVoiceError] = useState<string | null>(null);
  useEffect(() => {
    let cancelled = false;
    const sync = async () => {
      try {
        const r = await fetch('/voice/status');
        if (cancelled || !r.ok) return;
        const data = (await r.json()) as { running?: boolean; last_error?: string | null };
        setVoiceError(data.last_error ?? null);
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

  // Modo de la interfaz (normal | accessible) and the confirmation policy
  // (normal | bypass): both live in the profile on the host and are read from
  // it on mount and every few seconds, so a change made by chat shows here too.
  // The view only PUTs what the person chose in it.
  const [accessMode, setAccessModeState] = useState<AccessMode>('normal');
  const [confirmation, setConfirmationState] = useState<ConfirmationPolicy>('normal');
  const [activeSurface, setActiveSurface] = useState<SurfaceId>(() => {
    const stored = localStorage.getItem('field.surface');
    if (stored === 'sessions' || stored === 'memory' || stored === 'tools') {
      return stored;
    }
    return 'memory';
  });

  // persist surface so the chip selection survives reloads
  useEffect(() => {
    localStorage.setItem('field.surface', activeSurface);
  }, [activeSurface]);

  // poll /surfaces every 5s for counts (WS event wins when present). Lifted here
  // from ActivityPanel so BOTH columns share the same live counts — the redesign
  // splits the surfaces: tools on the left, sessions/memory on the right.
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
  const liveSurfaces = stream.surfaces ?? polledSurfaces;

  // Read both settings from the profile now and every 4s (the chat may change
  // the accessible mode, and bypass stays on until it is switched off).
  useEffect(() => {
    let cancelled = false;
    const sync = async () => {
      try {
        const [a, s] = await Promise.all([fetch('/accessibility'), fetch('/confirmation')]);
        if (cancelled) return;
        if (a.ok) {
          const data = (await a.json()) as { active?: string };
          setAccessModeState(data.active === 'accessible' ? 'accessible' : 'normal');
        }
        if (s.ok) {
          const data = (await s.json()) as { confirmationPolicy?: string };
          setConfirmationState(data.confirmationPolicy === 'bypass' ? 'bypass' : 'normal');
        }
      } catch { /* backend offline: keep what is shown */ }
    };
    sync();
    const id = window.setInterval(sync, 4000);
    return () => { cancelled = true; window.clearInterval(id); };
  }, []);

  // The presentation hangs from the document root: the stylesheet's accessible
  // rules (contrast, focus, no motion) and the paint loops read it.
  useEffect(() => {
    document.documentElement.dataset.access = accessMode;
  }, [accessMode]);

  const setAccessMode = useCallback(async (mode: AccessMode) => {
    try {
      const r = await fetch('/accessibility', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ mode }),
      });
      if (!r.ok) throw new Error(`status ${r.status}`);
      const data = (await r.json()) as { active?: string };
      setAccessModeState(data.active === 'accessible' ? 'accessible' : 'normal');
    } catch (e) {
      toastError(`modo accesible sin cambiar · ${String(e).replace(/^Error: /, '')}`);
    }
  }, []);

  const setConfirmation = useCallback(async (policy: ConfirmationPolicy) => {
    try {
      const r = await fetch('/confirmation', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ confirmationPolicy: policy }),
      });
      if (!r.ok) throw new Error(`status ${r.status}`);
      const data = (await r.json()) as { confirmationPolicy?: string };
      setConfirmationState(data.confirmationPolicy === 'bypass' ? 'bypass' : 'normal');
    } catch (e) {
      toastError(`confirmaciones sin cambiar · ${String(e).replace(/^Error: /, '')}`);
    }
  }, []);

  // The mic being OFF does NOT deactivate the app: text mode is a fully alive
  // mode. We keep the real conversational state (idle stays idle, alive) so the
  // field, neurons and border keep breathing while the user types. Only an
  // actual backend disconnect drops us to a degraded look (see `online` below);
  // muting the mic just mutes the mic.
  const convState = stream.convState;

  // global keyboard shortcuts (onHelp below lists them). shortcuts that hit
  // host routes (clear/new) are fired via plain fetch — no race with React
  // state.
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
        void startNewSession();
      } else if (k === ',') {
        e.preventDefault();
        setOpenPanel('settings');
      } else if (k === 's' && e.shiftKey) {
        e.preventDefault();
        setOpenPanel('sessions');
      } else if (k === 'm' && !e.shiftKey) {
        e.preventDefault();
        setOpenPanel('memory');
      } else if (k === 'e' && !e.shiftKey) {
        e.preventDefault();
        setOpenPanel('tools');
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, []);

  const closePanel = useCallback(() => setOpenPanel(null), []);

  // A line of the view itself (the host shows it as SYSTEM).
  const postActivity = useCallback(async (msg: string) => {
    try {
      await fetch('/activity', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ msg }),
      });
    } catch {
      /* server down — silently drop; this is UI flavor, not state */
    }
  }, []);

  // top-bar "+ new" → POST /sessions/new; the host clears the log itself (log_clear) and a refusal shows its code.
  const onNewSession = useCallback(() => { void startNewSession(); }, []);

  // the shortcuts this view handles (the keydown handler above), as a SYSTEM line.
  const onHelp = useCallback(() => {
    postActivity(
      'shortcuts: enter sends · / focus · ctrl+l clears the log · ctrl+n new session · ctrl+, settings'
        + ' · ctrl+shift+s sessions · ctrl+m memory · ctrl+e tools · f11 fullscreen · esc closes panel',
    );
  }, [postActivity]);

  // See MicMode. Left click cycles listening↔off (mute the mic). Right click
  // starts a request now: it turns the voice on if it was off, then captures
  // the next phrase without the wake word.
  //   listening   → /voice/start   (mic loop up, wake word armed)
  //   off         → /voice/stop
  //   right click → /voice/trigger (one phrase without saying «Baxy»; the voice
  //                                 then waits for «Baxy» again)
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
    // listening needs the loop running. The backend blocks while it
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
  // micMode ('listening'/'off') is the source of truth: if it's not 'off' we
  // boot the backend voice loop automatically (so the mic is armed AND BAXY's
  // spoken replies play without the user having to click the mic first). If the
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
    // listening → off. off → listening.
    setMicModeAsync(micMode === 'off' ? 'listening' : 'off');
  }, [micMode, setMicModeAsync]);

  // the person wants to speak NOW without the wake word.
  const onMicRightClick = useCallback(() => {
    setMicModeAsync('listening', { triggerAfter: true });
  }, [setMicModeAsync]);

  // clicking a surface card BOTH marks it active (visual carmesí border) AND
  // opens the matching modal — SessionsPanel, MemoryPanel or ToolsPanel.
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
  const visualStateRef = useRef(convState);
  useEffect(() => { visualStateRef.current = convState; }, [convState]);

  // Drive the traveling border without forcing a style/layout update at display
  // refresh rate while BAXY is resting. Active conversation remains at 30 Hz.
  useEffect(() => {
    const frame = document.querySelector<HTMLElement>('.app-frame');
    if (!frame) return;
    let timer = 0;
    let last = performance.now();
    let angle = 0;
    let speed = 1; // 0..1 fraction of full speed
    const FULL = 360 / 3.4; // deg/s at full speed
    const schedule = () => {
      const state = visualStateRef.current;
      const active = state === 'listening' || state === 'thinking' || state === 'speaking';
      const still = document.hidden || document.documentElement.dataset.access === 'accessible';
      const interval = still ? 1000 : 1000 / (active ? 30 : 4);
      timer = window.setTimeout(() => loop(performance.now()), interval);
    };
    const loop = (now: number) => {
      // Hidden, or the accessible presentation (no motion): the border stays still.
      if (document.hidden || document.documentElement.dataset.access === 'accessible') {
        last = now;
        schedule();
        return;
      }
      const state = visualStateRef.current;
      const active = state === 'listening' || state === 'thinking' || state === 'speaking';
      // Four paints per second keep the slow idle border visibly alive without
      // making WebView the dominant process while nobody is interacting.
      const dt = Math.min(active ? 0.05 : 0.25, (now - last) / 1000);
      last = now;
      const target = poweredRef.current ? 1 : 0;
      speed += (target - speed) * Math.min(1, dt * 2.6);
      if (target === 0 && speed < 0.012) speed = 0;
      angle = (angle + speed * FULL * dt) % 360;
      frame.style.setProperty('--bd-angle', angle.toFixed(2) + 'deg');
      schedule();
    };
    const onVisibilityChange = () => {
      window.clearTimeout(timer);
      last = performance.now();
      schedule();
    };
    document.addEventListener('visibilitychange', onVisibilityChange);
    schedule();
    return () => {
      document.removeEventListener('visibilitychange', onVisibilityChange);
      window.clearTimeout(timer);
    };
  }, []);

  // Recolor the border, the chrome accent (--carmine) and the metric bars
  // (--bar-color) per state — the prototype's SET table, verbatim. Chrome stays
  // carmesí at rest (idle) and only takes the contrast color during an
  // active conversation state (listening/thinking/speaking), then returns to red.
  useEffect(() => {
    const frame = document.querySelector<HTMLElement>('.app-frame');
    if (!frame) return;
    const SET: Record<string, { base: string; mid: string; hi: string; peak: string; glow: string; bar: string }> = {
      error:     { base: '#7A1E2B', mid: '#B83A4A', hi: '#E55366', peak: '#FFE9EC', glow: 'rgba(229,83,102,0.9)', bar: '#E55366' },
      idle:      { base: '#5a1a22', mid: '#B83A4A', hi: '#FF4D63', peak: '#FFE3E7', glow: 'rgba(255,77,99,0.9)',    bar: '#5B7FDB' },
      listening: { base: '#7A1E2B', mid: '#E55366', hi: '#FF6677', peak: '#FFFFFF', glow: 'rgba(255,102,119,0.95)', bar: '#6FA8B0' },
      thinking:  { base: '#1B2A5E', mid: '#2E4BA0', hi: '#5B7FDB', peak: '#C8D6F5', glow: 'rgba(91,127,219,0.9)',   bar: '#C9A66B' },
      speaking:  { base: '#6B5A2F', mid: '#C9A66B', hi: '#E8C98E', peak: '#F8EED2', glow: 'rgba(232,201,142,0.9)',  bar: '#7B95D9' },
    };
    const c = SET[convState] || SET.idle;
    frame.style.setProperty('--bd-base', c.base);
    frame.style.setProperty('--bd-mid', c.mid);
    frame.style.setProperty('--bd-hi', c.hi);
    frame.style.setProperty('--bd-peak', c.peak);
    frame.style.setProperty('--bd-glow', c.glow);
    frame.style.setProperty('--bar-color', c.bar);
    const active = convState === 'listening' || convState === 'thinking' || convState === 'speaking';
    frame.style.setProperty('--carmine', active ? c.bar : '#B83A4A');
  }, [convState]);

  return (
    <div className="window-root">
      <TitleBar bypass={confirmation === 'bypass'} />
      <div className="app-frame">
      <div className="shell">
        <div className="cols">
          <div className="col left">
            <SubstratePanel
              convState={convState}
              wsModel={stream.model}
              accessMode={accessMode}
              onAccessMode={setAccessMode}
              confirmation={confirmation}
              onConfirmation={setConfirmation}
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
              convState={convState}
              micMode={micMode}
              micLoading={micLoading}
              voiceError={voiceError}
              onMicLeftClick={onMicLeftClick}
              onMicRightClick={onMicRightClick}
              agent={stream.agent}
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
              pendingConfirmation={!!stream.agent.pendingConfirmation}
            />
          </div>
        </div>

        {openPanel === 'settings' && <SettingsPanel onClose={closePanel} />}
        {openPanel === 'sessions' && <SessionsPanel onClose={closePanel} />}
        {openPanel === 'memory' && <MemoryPanel onClose={closePanel} revision={liveSurfaces?.memory_revision ?? 0} />}
        {openPanel === 'tools' && <ToolsPanel onClose={closePanel} />}

        <ToastHost />
      </div>
      </div>
    </div>
  );
}
