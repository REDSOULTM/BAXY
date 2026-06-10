/* SettingsPanel — 12 tabs, persisted to ~/.gemma4/gui.json via PUT /settings.
   markup follows prototype/components/settings-panel.jsx 1:1: the chrome is
   the shared Panel (.panel-shroud > .panel.settings-panel) with .settings-tabs
   header, .settings-body section, .settings-footer; primitives reuse the
   prototype's .sf / .st-input / .sf-check / .toggle / .st-tip classes. */

import {
  useEffect, useRef, useState, useCallback, type PropsWithChildren,
  type ChangeEvent,
} from 'react';
import { Icon } from './Icon';
import { Toggle } from './Toggle';
import { Slider } from './Slider';
import { Select, type SelectOption } from './Select';
import { toastError, pushToast } from '../hooks/useToast';

const SETTINGS_TABS = [
  { id: 'connection', label: 'connection' },
  { id: 'agent',      label: 'agent' },
  { id: 'sampling',   label: 'sampling' },
  { id: 'behaviour',  label: 'behaviour' },
  { id: 'transcript', label: 'transcript' },
  { id: 'voice',      label: 'voice' },
  { id: 'profiles',   label: 'profiles' },
  { id: 'optim',      label: 'optim' },
  { id: 'toggles',    label: 'toggles' },
  { id: 'paths',      label: 'paths' },
  { id: 'prompt',     label: 'prompt' },
  { id: 'about',      label: 'about' },
] as const;
type TabId = typeof SETTINGS_TABS[number]['id'];

export interface SettingsConfig {
  // connection
  llamaUrl: string; modelAlias: string; ggufPath: string;
  ctxSize: number; maxTokens: number;
  // agent
  agentMode: string; persona: string; maxTurns: number; safetyFilter: boolean;
  // sampling
  temperature: number; topP: number; topK: number; minP: number;
  repeatPenalty: number; seed: number;
  allowCoT: boolean; parallelTools: boolean;
  // behaviour
  summarizationCooldown: number; factCooldown: number;
  phraseTriggerTimeout: number; llmTimeout: number; maxExpRecords: number;
  // transcript
  sttProvider: string; sttModel: string; sttLanguage: string;
  ttsProvider: string; ttsVoice: string; ttsRate: number;
  wakeWord: string; wakeWordEnabled: boolean;
  // voice
  voiceEnabled: boolean; wakeBeep: boolean; wakeHudBlink: boolean; wakeTts: boolean;
  sttParakeetOnly: boolean;    // GEMMA4_STT_NO_FALLBACK (solo Parakeet, sin Whisper)
  inputDevice: string; followUpWindow: number; followUpClosePhrases: string; muteTts: boolean;
  // profiles
  autoSwitch: boolean; autoSwitchGame: boolean; autoSwitchGpu: boolean; autoSwitchRam: boolean;
  autoSwitchTo: string; autoSwitchBack: string; gameProcesses: string;
  vramDetected: number; recommendedProfile: string;
  // toggles
  factExtraction: boolean; crossEncoderRerank: boolean; parallelToolExec: boolean;
  autoLoadCtx: boolean; persistentSessions: boolean; toolTimeline: boolean;
  summarization: boolean; tracing: boolean;
  visionAlways: boolean;       // GEMMA4_VISION_ALWAYS (mmproj residente, default ON)
  // optim (roadmap Gemma 4 — palancas avanzadas)
  disablePrewarm: boolean;     // GEMMA4_DISABLE_PREWARM
  telemetry: boolean;          // GEMMA4_TELEMETRY
  kvType: string;              // GEMMA4_LLAMA_KV_TYPE ("" | "f16" | "q8_0" | "q4_0")
  specDraftModel: string;      // GEMMA4_SPEC_DRAFT_MODEL (path)
  llamaApiKey: string;         // GEMMA4_LLAMA_API_KEY
  voiceLang: string;           // GEMMA4_VOICE_LANG ("" = auto | es/en/pt/fr/de/it)
  confirmationPolicy: string;  // GEMMA4_CONFIRMATION_POLICY ("" = confirm_risky | never | all | always)
  // paths
  memoryJson: string; stateJson: string; traceJsonl: string;
  sessionsDir: string; timelineDir: string;
}

const DEFAULTS: SettingsConfig = {
  llamaUrl: 'http://127.0.0.1:8080', modelAlias: '', ggufPath: '',
  ctxSize: 16384, maxTokens: 1280,
  agentMode: 'auto', persona: 'default', maxTurns: 8, safetyFilter: true,
  temperature: 1.0, topP: 0.95, topK: 64, minP: 0.0,
  repeatPenalty: 1.0, seed: -1, allowCoT: true, parallelTools: true,
  summarizationCooldown: 6, factCooldown: 5,
  phraseTriggerTimeout: 30, llmTimeout: 180, maxExpRecords: 5000,
  sttProvider: 'sherpa-onnx (local)', sttModel: 'parakeet-tdt-0.6b-v3-int8', sttLanguage: 'auto',
  ttsProvider: 'piper (local)', ttsVoice: 'es_MX-claude-high', ttsRate: 1.0,
  wakeWord: 'baxy', wakeWordEnabled: true,
  voiceEnabled: true, wakeBeep: true, wakeHudBlink: true, wakeTts: false,
  sttParakeetOnly: true,
  inputDevice: 'system default',
  followUpWindow: 5, followUpClosePhrases: 'gracias\nlisto\nya está\ncancelar', muteTts: false,
  autoSwitch: false, autoSwitchGame: true, autoSwitchGpu: false, autoSwitchRam: false,
  autoSwitchTo: 'vram4', autoSwitchBack: 'vram6',
  gameProcesses: 'steam.exe\nRobloxPlayer.exe\njavaw.exe',
  vramDetected: 16380, recommendedProfile: 'vram16',
  factExtraction: false, crossEncoderRerank: true, parallelToolExec: false,
  autoLoadCtx: false, persistentSessions: true, toolTimeline: true,
  summarization: true, tracing: true,
  visionAlways: true,
  disablePrewarm: false, telemetry: false, kvType: '',
  specDraftModel: '', llamaApiKey: '', voiceLang: '', confirmationPolicy: '',
  memoryJson: '~/gemma4/data/memory.json', stateJson: '~/gemma4/data/state.json',
  traceJsonl: '~/gemma4/data/traces.jsonl', sessionsDir: '~/.gemma4/sessions',
  timelineDir: '~/.gemma4/timeline',
};

/* ---------- form primitives — class names match prototype 1:1 ---------- */

function Field({ label, hint, wide, children }: PropsWithChildren<{ label: string; hint?: string; wide?: boolean }>) {
  return (
    <div className={`sf${wide ? ' wide' : ''}`}>
      <label className="sf-label">{label}</label>
      <div className="sf-ctl">{children}</div>
      {hint && <div className="sf-hint">{hint}</div>}
    </div>
  );
}

interface STInputProps {
  value: string | number;
  onChange: (v: string) => void;
  placeholder?: string;
  mono?: boolean;
}
function STInput({ value, onChange, placeholder, mono = true }: STInputProps) {
  return (
    <input
      type="text"
      className={`st-input${mono ? ' mono' : ''}`}
      value={value}
      placeholder={placeholder}
      onChange={(e: ChangeEvent<HTMLInputElement>) => onChange(e.target.value)}
      spellCheck={false}
    />
  );
}

function STNumber({
  value, onChange, min, max, step,
}: { value: number; onChange: (v: number) => void; min?: number; max?: number; step?: number }) {
  return (
    <input
      type="number"
      className="st-input mono num"
      value={Number.isFinite(value) ? value : ''}
      min={min} max={max} step={step}
      onChange={(e: ChangeEvent<HTMLInputElement>) => {
        const n = parseFloat(e.target.value);
        if (!Number.isNaN(n)) onChange(n);
      }}
    />
  );
}

function STText({
  value, onChange, rows = 4, mono = true,
}: { value: string; onChange: (v: string) => void; rows?: number; mono?: boolean }) {
  return (
    <textarea
      className={`st-textarea${mono ? ' mono' : ''}`}
      value={value}
      rows={rows}
      onChange={(e: ChangeEvent<HTMLTextAreaElement>) => onChange(e.target.value)}
      spellCheck={false}
    />
  );
}

function STCheck({
  value, onChange, label, hint,
}: { value: boolean; onChange: (v: boolean) => void; label: string; hint?: string }) {
  return (
    <div
      className="sf-check"
      onClick={() => onChange(!value)}
      role="checkbox"
      aria-checked={value}
      tabIndex={0}
      onKeyDown={(e) => {
        if (e.key === ' ' || e.key === 'Enter') {
          e.preventDefault();
          onChange(!value);
        }
      }}
    >
      <span className={`check-box${value ? ' on' : ''}`} aria-pressed={value}>
        {value ? <Icon name="check" size={9} /> : null}
      </span>
      <div className="check-body">
        <span className="check-label">{label}</span>
        {hint && <span className="check-hint">{hint}</span>}
      </div>
    </div>
  );
}

function STBrowse({
  value, onChange, placeholder,
}: { value: string; onChange: (v: string) => void; placeholder?: string }) {
  // Browsers can't expose an absolute path for security reasons — the picker
  // only gives us the filename. We surface that limitation in the tooltip so
  // users don't think the button is broken. The text input is the source of
  // truth; the button is a convenience for getting the filename portion.
  const inputRef = useRef<HTMLInputElement | null>(null);
  return (
    <div className="st-browse">
      <STInput value={value} onChange={onChange} placeholder={placeholder} />
      <button
        type="button"
        className="st-browse-btn"
        title="browser cannot read absolute paths — paste the full path manually after picking"
        aria-label="browse (filename only)"
        onClick={() => inputRef.current?.click()}
      >
        <Icon name="folder" size={12} />
      </button>
      <input
        ref={inputRef}
        type="file"
        hidden
        onChange={(e) => {
          const f = e.target.files?.[0];
          if (f) onChange(f.name);
          e.target.value = '';
        }}
      />
    </div>
  );
}

function STTip({ children, warn }: PropsWithChildren<{ warn?: boolean }>) {
  return <div className={`st-tip${warn ? ' warn' : ''}`}>{children}</div>;
}

function STSection({ title, children }: PropsWithChildren<{ title?: string }>) {
  return (
    <div className="st-section">
      {title && <div className="st-section-head">{title}</div>}
      {children}
    </div>
  );
}

/* ---------- option catalogs fetched from the backend ---------- */

interface AgentMode { name: string; description: string; }
interface AgentPersona { name: string; description: string; tone?: string; preferred_tools?: string[]; }
interface STTOption { name: string; size_label?: string; downloaded?: boolean | null; }
interface TTSOption { name: string; downloaded?: boolean; }
interface VoiceInventory {
  stt_default?: string;
  stt: STTOption[];
  tts: TTSOption[];
  wake?: { name?: string | null; downloaded: boolean };
  languages: string[];
}

function useAgentOptions() {
  const [modes, setModes] = useState<AgentMode[]>([]);
  const [personas, setPersonas] = useState<AgentPersona[]>([]);
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const [a, b] = await Promise.all([fetch('/agent/modes'), fetch('/agent/personas')]);
        if (cancelled) return;
        if (a.ok) {
          const data = (await a.json()) as { items?: AgentMode[] };
          setModes(data.items ?? []);
        }
        if (b.ok) {
          const data = (await b.json()) as { items?: AgentPersona[] };
          setPersonas(data.items ?? []);
        }
      } catch { /* server may be down; selects fall back to a single option */ }
    })();
    return () => { cancelled = true; };
  }, []);
  return { modes, personas };
}

function useVoiceInventory() {
  const [inv, setInv] = useState<VoiceInventory | null>(null);
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const r = await fetch('/voice/inventory');
        if (cancelled || !r.ok) return;
        setInv((await r.json()) as VoiceInventory);
      } catch { /* ignore */ }
    })();
    return () => { cancelled = true; };
  }, []);
  return inv;
}

/* ---------- tab content ---------- */

type Setter = <K extends keyof SettingsConfig>(key: K) => (val: SettingsConfig[K]) => void;

function ConnectionTab({ c, set }: { c: SettingsConfig; set: Setter }) {
  return (
    <STSection>
      <Field label="llama-server url">
        <STInput value={c.llamaUrl} onChange={set('llamaUrl')} placeholder="http://127.0.0.1:8080" />
      </Field>
      <Field label="model alias">
        <STInput value={c.modelAlias} onChange={set('modelAlias')} placeholder="optional alias — e.g. gemma-3-e4b-it.Q6_K" />
      </Field>
      <Field label="gguf path">
        <STBrowse value={c.ggufPath} onChange={set('ggufPath')} placeholder=".gguf path — passed to launcher / used by agent.config" />
      </Field>
      <Field label="context size (tokens)">
        <STNumber value={c.ctxSize} onChange={set('ctxSize')} min={1024} max={131072} step={1024} />
      </Field>
      <Field label="max tokens per reply">
        <STNumber value={c.maxTokens} onChange={set('maxTokens')} min={64} max={8192} step={32} />
      </Field>
      <STTip>
        the agent talks to a llama-server you start separately. changes here require <b className="bone">restart agent</b> to take effect.
      </STTip>
    </STSection>
  );
}

function AgentTab({ c, set }: { c: SettingsConfig; set: Setter }) {
  const { modes, personas } = useAgentOptions();

  // catalog → SelectOption[]. always keep the user's persisted value as an
  // option even if the backend hasn't returned the catalog yet (or returned
  // a smaller set than what's stored), so the field never appears empty.
  const modeOptions: SelectOption[] = (() => {
    const opts: SelectOption[] = modes.map((m) => ({
      value: m.name,
      label: m.name,
      hint: m.description,
    }));
    if (c.agentMode && !opts.some((o) => o.value === c.agentMode)) {
      opts.unshift({ value: c.agentMode, label: c.agentMode, hint: 'custom' });
    }
    return opts;
  })();
  const personaOptions: SelectOption[] = (() => {
    const opts: SelectOption[] = personas.map((p) => ({
      value: p.name,
      label: p.name,
      hint: p.description,
    }));
    if (c.persona && !opts.some((o) => o.value === c.persona)) {
      opts.unshift({ value: c.persona, label: c.persona, hint: 'custom' });
    }
    return opts;
  })();

  const selectedPersona = personas.find((p) => p.name === c.persona);

  return (
    <STSection>
      <Field label="agent mode" hint="auto infers from the user's message">
        <Select
          value={c.agentMode}
          onChange={(v) => set('agentMode')(v)}
          options={modeOptions}
          ariaLabel="agent mode"
        />
      </Field>
      <Field label="persona" hint={selectedPersona?.preferred_tools?.length
        ? `prefers: ${selectedPersona.preferred_tools.slice(0, 4).join(', ')}` : undefined}>
        <Select
          value={c.persona}
          onChange={(v) => set('persona')(v)}
          options={personaOptions}
          ariaLabel="persona"
        />
      </Field>
      <Field label="max turns per request">
        <STNumber value={c.maxTurns} onChange={set('maxTurns')} min={1} max={64} step={1} />
      </Field>
      <Field label=" ">
        <STCheck value={c.safetyFilter} onChange={set('safetyFilter')} label="safety filter on" />
      </Field>
      <Field label="confirmaciones" hint="cuándo Baxy te pide confirmar antes de actuar">
        <Select
          value={c.confirmationPolicy || 'confirm_risky'}
          onChange={(v) => set('confirmationPolicy')(v === 'confirm_risky' ? '' : v)}
          options={[
            { value: 'confirm_risky', label: 'normal (confirma lo riesgoso)', hint: 'default' },
            { value: 'never', label: 'permisivo (solo confirma lo destructivo)', hint: 'cerrar apps, settings → sin confirmar' },
            { value: 'all', label: 'TODO permisivo (nada confirma)', hint: '⚠ ejecuta hasta borrar/apagar sin preguntar' },
            { value: 'always', label: 'estricto (confirma todo)', hint: 'auditoría' },
          ]}
          ariaLabel="confirmation policy"
        />
      </Field>
      <STTip warn>
        safety <b className="carmine">off</b> means destructive tools run <b className="carmine">without</b> confirmation.
        recommended on for unattended sessions; off only if you trust every prompt you give and you watch every turn.
        {c.confirmationPolicy === 'all' && (
          <> <b className="carmine">modo TODO permisivo activo</b>: Baxy ejecuta cualquier acción (incl. borrar archivos, apagar, desinstalar) sin pedirte confirmación.</>
        )}
      </STTip>
    </STSection>
  );
}

/* slider row helper for sampling tab — slider on the left, mono value on the right */
function SliderRow({
  label, value, onChange, min, max, step, fmt,
}: {
  label: string;
  value: number;
  onChange: (v: number) => void;
  min: number;
  max: number;
  step: number;
  fmt?: (v: number) => string;
}) {
  const display = fmt ? fmt(value) : value.toString();
  return (
    <div className="slider-row">
      <div className="slider-meta">
        <span className="k">{label}</span>
        <span className="v">{display}</span>
      </div>
      <Slider value={value} onChange={onChange} min={min} max={max} step={step} ariaLabel={label} />
    </div>
  );
}

function SamplingTab({ c, set }: { c: SettingsConfig; set: Setter }) {
  return (
    <STSection>
      <STTip>
        sampling parameters passed to llama-server. lower temperature is more deterministic;
        top_p + top_k narrow the candidate pool; min_p prunes low-probability tokens.
      </STTip>
      <SliderRow label="temperature"     value={c.temperature}    onChange={set('temperature')}    min={0}    max={2}    step={0.01} fmt={(v) => v.toFixed(2)} />
      <SliderRow label="top_p"           value={c.topP}           onChange={set('topP')}           min={0}    max={1}    step={0.01} fmt={(v) => v.toFixed(2)} />
      <SliderRow label="top_k"           value={c.topK}           onChange={set('topK')}           min={1}    max={1000} step={1} />
      <SliderRow label="min_p"           value={c.minP}           onChange={set('minP')}           min={0}    max={1}    step={0.01} fmt={(v) => v.toFixed(2)} />
      <SliderRow label="repeat penalty"  value={c.repeatPenalty}  onChange={set('repeatPenalty')}  min={0.8}  max={2}    step={0.01} fmt={(v) => v.toFixed(2)} />
      <Field label="seed">
        <STInput
          value={c.seed}
          onChange={(s) => {
            const n = parseInt(s, 10);
            set('seed')(Number.isNaN(n) ? -1 : n);
          }}
          placeholder="-1 (random)"
        />
      </Field>
      <Field label=" "><STCheck value={c.allowCoT} onChange={set('allowCoT')} label="allow gemma to expose chain-of-thought" hint="slower" /></Field>
      <Field label=" "><STCheck value={c.parallelTools} onChange={set('parallelTools')} label="let model emit multiple tool_calls per turn" /></Field>
    </STSection>
  );
}

function BehaviourTab({ c, set }: { c: SettingsConfig; set: Setter }) {
  return (
    <STSection>
      <STTip>higher-level behaviour knobs. strict honesty + auto-replan are always on.</STTip>
      <Field label="summarization cooldown (turns)"><STNumber value={c.summarizationCooldown} onChange={set('summarizationCooldown')} min={0} max={50} step={1} /></Field>
      <Field label="fact extraction cooldown"><STNumber value={c.factCooldown} onChange={set('factCooldown')} min={0} max={50} step={1} /></Field>
      <Field label="phrase-trigger step timeout (s)"><STNumber value={c.phraseTriggerTimeout} onChange={set('phraseTriggerTimeout')} min={1} max={600} step={1} /></Field>
      <Field label="llm request timeout (s)"><STNumber value={c.llmTimeout} onChange={set('llmTimeout')} min={10} max={1800} step={1} /></Field>
      <Field label="max experience records"><STNumber value={c.maxExpRecords} onChange={set('maxExpRecords')} min={0} max={100000} step={100} /></Field>
    </STSection>
  );
}

/** state of a model file: downloaded, not yet, or status unknown.
 *  shows up as a coloured suffix in the Select options. */
function downloadedHint(d: boolean | null | undefined): string | undefined {
  if (d === true) return 'descargado';
  if (d === false) return 'no descargado';
  return undefined;  // null/undefined → don't decorate
}

function TranscriptTab({ c, set }: { c: SettingsConfig; set: Setter }) {
  const inv = useVoiceInventory();

  // STT provider is fixed for this build: Parakeet-TDT-v3 through sherpa-onnx.
  // Whisper-small remains a backend fallback in voice.pipeline if Parakeet fails
  // to load, but it is no longer the advertised default.
  // we still surface it as a dropdown so future providers slot in trivially.
  const sttProviderOptions: SelectOption[] = [
    { value: 'sherpa-onnx (local)', label: 'sherpa-onnx (local)', hint: 'Parakeet-TDT-v3 default' },
  ];
  if (c.sttProvider && !sttProviderOptions.some((o) => o.value === c.sttProvider)) {
    sttProviderOptions.unshift({ value: c.sttProvider, label: c.sttProvider, hint: 'custom' });
  }

  const sttModelOptions: SelectOption[] = (inv?.stt ?? []).map((m) => ({
    value: m.name,
    label: m.name,
    hint: [m.size_label, downloadedHint(m.downloaded)].filter(Boolean).join(' · '),
  }));
  if (sttModelOptions.length === 0) {
    sttModelOptions.push({ value: c.sttModel, label: c.sttModel || 'auto' });
  } else if (c.sttModel && !sttModelOptions.some((o) => o.value === c.sttModel)) {
    sttModelOptions.unshift({ value: c.sttModel, label: c.sttModel, hint: 'custom' });
  }

  const langOptions: SelectOption[] = (inv?.languages ?? ['auto']).map((l) => ({
    value: l, label: l,
  }));
  if (c.sttLanguage && !langOptions.some((o) => o.value === c.sttLanguage)) {
    langOptions.unshift({ value: c.sttLanguage, label: c.sttLanguage });
  }

  const ttsProviderOptions: SelectOption[] = [
    { value: 'piper (local)', label: 'piper (local)' },
  ];
  if (c.ttsProvider && !ttsProviderOptions.some((o) => o.value === c.ttsProvider)) {
    ttsProviderOptions.unshift({ value: c.ttsProvider, label: c.ttsProvider, hint: 'custom' });
  }

  const ttsVoiceOptions: SelectOption[] = (inv?.tts ?? []).map((v) => ({
    value: v.name,
    label: v.name,
    hint: downloadedHint(v.downloaded),
  }));
  if (ttsVoiceOptions.length === 0) {
    ttsVoiceOptions.push({ value: c.ttsVoice, label: c.ttsVoice || '(none)' });
  } else if (c.ttsVoice && !ttsVoiceOptions.some((o) => o.value === c.ttsVoice)) {
    ttsVoiceOptions.unshift({ value: c.ttsVoice, label: c.ttsVoice, hint: 'custom' });
  }

  // wake-word model status — single option from voice/wake.py
  const wakeHint = inv?.wake?.name
    ? `${inv.wake.name} · ${inv.wake.downloaded ? 'descargado' : 'no descargado'}`
    : undefined;

  return (
    <STSection>
      <STTip>
        stt/tts settings. all providers below are local. items marked
        <span className="bone"> descargado </span>are already on disk; the rest
        will fetch on first use.
      </STTip>
      <Field label="stt provider">
        <Select value={c.sttProvider} onChange={set('sttProvider')} options={sttProviderOptions} ariaLabel="stt provider" />
      </Field>
      <Field label="stt model">
        <Select value={c.sttModel} onChange={set('sttModel')} options={sttModelOptions} ariaLabel="stt model" />
      </Field>
      <Field label="stt language">
        <Select value={c.sttLanguage} onChange={set('sttLanguage')} options={langOptions} ariaLabel="stt language" />
      </Field>
      <Field label="tts provider">
        <Select value={c.ttsProvider} onChange={set('ttsProvider')} options={ttsProviderOptions} ariaLabel="tts provider" />
      </Field>
      <Field label="tts voice">
        <Select value={c.ttsVoice} onChange={set('ttsVoice')} options={ttsVoiceOptions} ariaLabel="tts voice" />
      </Field>
      <SliderRow label="tts speech rate" value={c.ttsRate} onChange={set('ttsRate')} min={0.5} max={2} step={0.05} fmt={(v) => v.toFixed(2)} />
      <Field
        label="wake words"
        hint={wakeHint ?? "LiveKit baxy is the active local wake model"}
      >
        <span className="muted mono">baxy</span>
      </Field>
      <Field label=" "><STCheck value={c.wakeWordEnabled} onChange={set('wakeWordEnabled')} label="wake word enabled" hint="passive listening" /></Field>
    </STSection>
  );
}

function VoiceTab({ c, set }: { c: SettingsConfig; set: Setter }) {
  return (
    <STSection>
      <STTip>local voice — LiveKit wake + Parakeet STT + Piper TTS. all cpu.</STTip>
      <Field label="idioma" hint="fija el idioma de TODO (transcripción + respuesta). 'automático' = detecta por turno.">
        <Select
          value={c.voiceLang || 'auto'}
          onChange={(v) => set('voiceLang')(v === 'auto' ? '' : v)}
          options={[
            { value: 'auto', label: 'automático (detecta)' },
            { value: 'es', label: 'Español' },
            { value: 'en', label: 'English' },
            { value: 'pt', label: 'Português' },
            { value: 'fr', label: 'Français' },
            { value: 'de', label: 'Deutsch' },
            { value: 'it', label: 'Italiano' },
          ]}
          ariaLabel="idioma"
        />
      </Field>
      <Field label=" "><STCheck value={c.voiceEnabled} onChange={set('voiceEnabled')} label="enable voice" hint="master switch" /></Field>
      <Field label=" "><STCheck value={c.sttParakeetOnly} onChange={set('sttParakeetOnly')} label="solo Parakeet (sin Whisper)" hint="apaga el fallback a Whisper; si Parakeet no carga, la voz falla limpio" /></Field>
      <Field label="wake words" hint="custom LiveKit model; transcript cleanup also strips short wake variants">
        <span className="muted mono">baxy</span>
      </Field>
      <Field label="wake feedback">
        <div className="check-row">
          <STCheck value={c.wakeBeep}     onChange={set('wakeBeep')}     label="beep" />
          <STCheck value={c.wakeHudBlink} onChange={set('wakeHudBlink')} label="hud blink" />
          <STCheck value={c.wakeTts}      onChange={set('wakeTts')}      label="tts 'sí'" />
        </div>
      </Field>
      <Field label="input device"><STInput value={c.inputDevice} onChange={set('inputDevice')} /></Field>
      <Field label="follow-up window (s)"><STNumber value={c.followUpWindow} onChange={set('followUpWindow')} min={1} max={60} step={1} /></Field>
      <Field label="follow-up close phrases" hint="one per line">
        <STText value={c.followUpClosePhrases} onChange={set('followUpClosePhrases')} rows={5} />
      </Field>
      <Field label=" "><STCheck value={c.muteTts} onChange={set('muteTts')} label="mute tts" hint="wake + stt keep working" /></Field>
    </STSection>
  );
}

function ProfilesTab({ c, set, profile, onProfile }: { c: SettingsConfig; set: Setter; profile: string; onProfile: (p: string) => void }) {
  // populate vram + recommended profile from the server on mount so the
  // numbers reflect the actual machine even before the user clicks re-detect.
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const r = await fetch('/hardware');
        if (cancelled || !r.ok) return;
        const data = (await r.json()) as { gpu_vram_gb?: number };
        const vramMb = Math.round((data.gpu_vram_gb ?? 0) * 1024);
        if (vramMb > 0) {
          set('vramDetected')(vramMb);
          // 2026-05-26: el producto tiene UN solo perfil (vram4 = E2B-Q4, todo
          // en ≤4 GB). Ya no hay escalera por VRAM: la recomendación es siempre
          // vram4 sin importar cuánta VRAM haya.
          set('recommendedProfile')('vram4');
        }
      } catch { /* ignore */ }
    })();
    return () => { cancelled = true; };
    // intentionally not depending on `set` — it's stable from useCallback in the parent.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // 2026-05-26: colapsado a un solo perfil operante (vram4) + standby (server off).
  const PROFILES = ['vram4', 'standby'] as const;
  const ROWS = [
    { row: 'ctx', values: ['16 384', 'off'] },
    { row: 'server', values: ['on', 'off'] },
    { row: 'voice', values: ['on', 'off'] },
    { row: 'vision', values: ['on', 'off'] },
    { row: 'vram cap', values: ['4 gb', '0 gb'] },
  ];
  return (
    <STSection>
      <div className="st-sub-head">hardware detection</div>
      <div className="kv" style={{ marginBottom: 12 }}>
        <div className="kv-row"><span className="k">vram detected</span><span className="v">{c.vramDetected.toLocaleString()} mb</span></div>
        <div className="kv-row"><span className="k">recommended profile</span><span className="v">{c.recommendedProfile}</span></div>
      </div>
      <button
        type="button"
        className="st-redetect"
        onClick={() => {
          // /hardware/redetect drops the server cache + re-runs detection;
          // the response carries the fresh cpu/mem/gpu specs which we feed
          // back into the config so the user sees the updated VRAM cap.
          fetch('/hardware/redetect', { method: 'POST' })
            .then((r) => r.ok ? r.json() : null)
            .then((data) => {
              if (!data) return;
              const vramMb = Math.round((data.gpu_vram_gb ?? 0) * 1024);
              if (vramMb > 0) set('vramDetected')(vramMb);
            })
            .catch(() => { /* ignore — activity log shows the failure if any */ });
        }}
      >
        <Icon name="restart" size={11} /> re-detect
      </button>

      {/* 2026-05-26: el auto-switch entre perfiles se quitó (un solo perfil:
          no hay a dónde cambiar). El único toggle real es vram4 <-> standby. */}
      <div className="st-sub-head" style={{ marginTop: 18 }}>active profile</div>
      <div className="profile-chips" style={{ marginBottom: 12 }}>
        {PROFILES.map((p) => (
          <button
            type="button"
            key={p}
            className={`chip${profile === p ? ' on' : ''}`}
            onClick={() => onProfile(p)}
          >{p}</button>
        ))}
      </div>

      <div className="st-sub-head">profile capabilities</div>
      <table className="st-table">
        <thead>
          <tr>
            <th></th>
            {PROFILES.map((p) => <th key={p}>{p}</th>)}
          </tr>
        </thead>
        <tbody>
          {ROWS.map((r) => (
            <tr key={r.row}>
              <td className="row-label">{r.row}</td>
              {r.values.map((v, i) => <td key={`${r.row}-${PROFILES[i]}`}>{v}</td>)}
            </tr>
          ))}
        </tbody>
      </table>
    </STSection>
  );
}

/* ---- OPTIM: palancas low-level del roadmap Gemma 4 ----
   GEMMA4_DISABLE_PREWARM, GEMMA4_TELEMETRY, GEMMA4_LLAMA_KV_TYPE,
   GEMMA4_SPEC_DRAFT_MODEL, GEMMA4_LLAMA_API_KEY. Cambios requieren restart
   del agente para aplicarse en el llama-server. */
const KV_TYPE_OPTIONS: SelectOption[] = [
  { value: '', label: '(default · f16)' },
  { value: 'f16', label: 'f16 · sin quantizacion' },
  { value: 'q8_0', label: 'q8_0 · ~50% menos VRAM' },
  { value: 'q4_0', label: 'q4_0 · ~75% menos VRAM (calidad ↓)' },
];

function OptimTab({ c, set }: { c: SettingsConfig; set: Setter }) {
  return (
    <STSection>
      <STTip>
        palancas low-level del runtime de llama.cpp y del prewarm. solo cambialas
        si seguis una guia de optimizacion concreta o tenes una razon concreta.
        cambios mal aplicados pueden degradar throughput o causar OOM.{' '}
        <b className="bone">restart agent</b> aplica los cambios.
      </STTip>

      <div className="toggle-list">
        <div className="toggle-list-row">
          <div>
            <div className="toggle-label">
              disable kv cache prewarm at boot
              <span className="needs-restart">needs restart</span>
            </div>
            <div className="toggle-sub">
              opt-out del prewarm. el primer turn paga ttft del prefill (60-90s).
              util solo si el prewarm causa problemas.
            </div>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <span className="env mono">GEMMA4_DISABLE_PREWARM</span>
            <Toggle
              value={c.disablePrewarm}
              onChange={(v) => set('disablePrewarm')(v as boolean)}
              ariaLabel="disable prewarm"
            />
          </div>
        </div>

        <div className="toggle-list-row">
          <div>
            <div className="toggle-label">
              enable local telemetry (sqlite)
              <span className="needs-restart">needs restart</span>
            </div>
            <div className="toggle-sub">
              opt-in. escribe turns/voice/incidents en ~/.gemma4/telemetry.sqlite.
              solo local, sin red.
            </div>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <span className="env mono">GEMMA4_TELEMETRY</span>
            <Toggle
              value={c.telemetry}
              onChange={(v) => set('telemetry')(v as boolean)}
              ariaLabel="telemetry"
            />
          </div>
        </div>
      </div>

      <div className="st-sub-head" style={{ marginTop: 16 }}>llama-server</div>
      <Field
        label="kv cache type"
        hint="quantizacion del kv cache. util en perfiles vram4/vram6 con context grandes."
      >
        <Select
          value={c.kvType}
          options={KV_TYPE_OPTIONS}
          onChange={(v) => set('kvType')(v)}
          ariaLabel="kv cache type"
        />
      </Field>

      <Field
        label="speculative draft model"
        hint="path al modelo draft (q4_k_m de 1-2b) para speculative decoding. solo activo si el perfil tambien lo permite. vacio = off."
      >
        <input
          type="text"
          className="st-input"
          value={c.specDraftModel}
          onChange={(e: ChangeEvent<HTMLInputElement>) => set('specDraftModel')(e.target.value)}
          placeholder="(empty = disabled)"
        />
      </Field>

      <Field
        label="llama-server api key"
        hint="si seteado, llama-server requiere authorization: bearer <key> en cada request. hardening sprint 12."
      >
        <input
          type="password"
          className="st-input"
          value={c.llamaApiKey}
          onChange={(e: ChangeEvent<HTMLInputElement>) => set('llamaApiKey')(e.target.value)}
          placeholder="(empty = no auth)"
          autoComplete="new-password"
        />
      </Field>

      <STTip>
        env vars equivalentes:{' '}
        <span className="env mono">GEMMA4_LLAMA_KV_TYPE</span>{' · '}
        <span className="env mono">GEMMA4_SPEC_DRAFT_MODEL</span>{' · '}
        <span className="env mono">GEMMA4_LLAMA_API_KEY</span>.
      </STTip>
    </STSection>
  );
}

interface ToggleSpec { key: keyof SettingsConfig; label: string; env: string; sub?: string; }
const TOGGLES: ToggleSpec[] = [
  { key: 'factExtraction',     label: 'fact extraction (post-turn)',              env: 'GEMMA4_AGENT_FACT_EXTRACTION' },
  { key: 'crossEncoderRerank', label: 'cross-encoder rerank in knowledge.search', env: 'GEMMA4_KNOWLEDGE_RERANK' },
  { key: 'parallelToolExec',   label: 'parallel tool execution',                  env: 'GEMMA4_AGENT_PARALLEL_TOOLS' },
  { key: 'autoLoadCtx',        label: 'auto-load project context',                env: 'GEMMA4_AGENT_PROJECT_CONTEXT' },
  { key: 'persistentSessions', label: 'persistent chat sessions',                 env: 'GEMMA4_AGENT_SESSIONS' },
  { key: 'toolTimeline',       label: 'tool timeline jsonl export',               env: 'GEMMA4_AGENT_TIMELINE' },
  { key: 'summarization',      label: 'llm-summarization compaction',             env: 'GEMMA4_AGENT_SUMMARIZATION' },
  { key: 'tracing',            label: 'tracing to jsonl (trace.jsonl)',           env: 'GEMMA4_AGENT_TRACING' },
  { key: 'visionAlways',       label: 'modo visión siempre activo',               env: 'GEMMA4_VISION_ALWAYS',
    sub: 'mantiene el modelo de visión (mmproj) cargado todo el tiempo, así una imagen no paga ~2-5s de carga. medido: no ralentiza el texto. apagalo solo si tu llama.cpp es viejo.' },
];

function TogglesTab({ c, set }: { c: SettingsConfig; set: Setter }) {
  return (
    <STSection>
      <STTip>
        feature toggles. each one is mirrored into the env var shown on the
        right. <b className="bone">apply</b> writes them but the running agent
        won't honour them until you also click <b className="bone">restart
        agent</b> (button appears in the footer after apply if you changed
        anything here).
      </STTip>
      <div className="toggle-list">
        {TOGGLES.map((t) => (
          <div key={t.key} className="toggle-list-row">
            <div>
              <div className="toggle-label">
                {t.label}
                <span className="needs-restart">needs restart</span>
              </div>
              {t.sub && <div className="toggle-sub">{t.sub}</div>}
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
              <span className="env mono">{t.env}</span>
              <Toggle
                value={c[t.key] as boolean}
                onChange={(v) => set(t.key)(v as never)}
                ariaLabel={t.label}
              />
            </div>
          </div>
        ))}
      </div>
    </STSection>
  );
}

function PathsTab({ c, set }: { c: SettingsConfig; set: Setter }) {
  return (
    <STSection>
      <Field label="memory.json"><STBrowse value={c.memoryJson}  onChange={set('memoryJson')}  /></Field>
      <Field label="state.json"><STBrowse  value={c.stateJson}   onChange={set('stateJson')}   /></Field>
      <Field label="trace.jsonl"><STBrowse value={c.traceJsonl}  onChange={set('traceJsonl')}  /></Field>
      <Field label="sessions dir"><STBrowse value={c.sessionsDir} onChange={set('sessionsDir')} /></Field>
      <Field label="timeline dir"><STBrowse value={c.timelineDir} onChange={set('timelineDir')} /></Field>
    </STSection>
  );
}

function PromptTab() {
  const [prompt, setPrompt] = useState<string>('');
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const r = await fetch('/agent/system_prompt');
        if (cancelled) return;
        if (!r.ok) { setErr(`server error ${r.status}`); return; }
        const data = (await r.json()) as { prompt?: string; error?: string };
        if (data.error) setErr(data.error);
        setPrompt(data.prompt ?? '');
      } catch (e) {
        if (!cancelled) setErr(String(e));
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, []);

  return (
    <STSection>
      <div className="st-sub-head">system prompt <span className="muted">· read-only · live from agent.py</span></div>
      <pre className="st-prompt" style={{ maxHeight: 320, overflow: 'auto' }}>
        {loading ? 'loading…' : err ? `error · ${err}` : prompt || '(empty)'}
      </pre>
      <STTip>
        override by editing <span className="mono">gemma4_agent/agent.py</span>{' '}
        <span className="mono">SYSTEM_PROMPT</span>. persona and project_context hints are
        appended automatically at runtime.
      </STTip>
    </STSection>
  );
}

function AboutTab() {
  return (
    <STSection>
      <div className="st-about-title">gemma 4 · field</div>
      <div className="st-about-sub">local ai agent · gemma4 build · runs entirely offline</div>
      <div className="hair" style={{ margin: '16px 0' }} />
      <div className="kv">
        <div className="kv-row"><span className="k">python</span><span className="v">3.10.11</span></div>
        <div className="kv-row"><span className="k">settings file</span><span className="v">~/.gemma4/gui.json</span></div>
        <div className="kv-row"><span className="k">agent module</span><span className="v">gemma4_agent/</span></div>
        <div className="kv-row"><span className="k">build</span><span className="v">gemma4 · 2026.05</span></div>
        <div className="kv-row"><span className="k">runtime</span><span className="v">llama.cpp · cuda 12</span></div>
      </div>
      <STTip>all inference is local. no telemetry. no external network calls.</STTip>
    </STSection>
  );
}

/* ---------- panel shell ---------- */

interface Props {
  onClose: () => void;
  profile: string;
  onProfile: (p: string) => void;
}

const TOGGLE_KEYS: (keyof SettingsConfig)[] = TOGGLES.map((t) => t.key);

export function SettingsPanel({ onClose, profile, onProfile }: Props) {
  const [tab, setTab] = useState<TabId>('connection');
  const [config, setConfig] = useState<SettingsConfig>(DEFAULTS);
  const [savedConfig, setSavedConfig] = useState<SettingsConfig>(DEFAULTS);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  /** After a successful apply, if the user changed any restart-required
   *  field we offer a "restart agent" button. Reset on close/cancel. */
  const [restartOffered, setRestartOffered] = useState(false);
  const [restartPending, setRestartPending] = useState(false);

  useEffect(() => {
    let cancelled = false;
    const run = async () => {
      try {
        const r = await fetch('/settings');
        if (cancelled) return;
        if (r.ok) {
          const data = (await r.json()) as Partial<SettingsConfig>;
          if (data && typeof data === 'object' && Object.keys(data).length > 0) {
            const merged = { ...DEFAULTS, ...data };
            setConfig(merged);
            setSavedConfig(merged);
          } else {
            setSavedConfig(DEFAULTS);
          }
        }
      } catch { /* defaults are fine */ }
      finally {
        if (!cancelled) setLoading(false);
      }
    };
    run();
    return () => { cancelled = true; };
  }, []);

  const set = useCallback(
    <K extends keyof SettingsConfig>(key: K) => (val: SettingsConfig[K]) =>
      setConfig((prev) => ({ ...prev, [key]: val })),
    [],
  );

  const apply = useCallback(async () => {
    setSaving(true);
    try {
      const r = await fetch('/settings', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(config),
      });
      if (!r.ok) {
        toastError(`settings save failed · ${r.status}`);
        return;
      }
      const toggleChanged = TOGGLE_KEYS.some((k) => config[k] !== savedConfig[k]);
      setSavedConfig(config);
      if (toggleChanged) {
        // keep the panel open so the user can hit "restart agent" right
        // here without leaving the settings flow.
        setRestartOffered(true);
      } else {
        onClose();
      }
    } catch {
      toastError('settings save failed · backend unreachable');
    } finally { setSaving(false); }
  }, [config, savedConfig, onClose]);

  const restartAgent = useCallback(async () => {
    setRestartPending(true);
    try {
      const r = await fetch('/agent/restart', { method: 'POST' });
      if (!r.ok) {
        toastError(`agent restart failed · ${r.status}`);
        return;
      }
      pushToast({ kind: 'success', msg: 'agent restart triggered' });
      setRestartOffered(false);
      onClose();
    } catch {
      toastError('agent restart failed · backend unreachable');
    } finally { setRestartPending(false); }
  }, [onClose]);

  const reset = useCallback(() => setConfig(DEFAULTS), []);

  return (
    <div className="panel-shroud" onClick={onClose} role="presentation">
      <div
        className="panel settings-panel"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-label="settings"
      >
        <div className="panel-head">
          <div className="panel-head-left">
            <span className="panel-title">configuration</span>
            <span className="muted">·</span>
            <span className="panel-subtitle">all subsystems</span>
          </div>
          <button className="ibtn" onClick={onClose} data-tip="close" aria-label="close">
            <Icon name="x" />
          </button>
        </div>

        <div className="settings-tabs" role="tablist">
          {SETTINGS_TABS.map((t) => (
            <button
              key={t.id}
              role="tab"
              aria-selected={tab === t.id}
              className={`settings-tab${tab === t.id ? ' on' : ''}`}
              onClick={() => setTab(t.id)}
            >
              {t.label}
            </button>
          ))}
        </div>

        <div className="settings-body">
          {loading ? (
            <div className="muted" style={{ padding: 24 }}>loading settings…</div>
          ) : (
            <>
              {tab === 'connection' && <ConnectionTab c={config} set={set} />}
              {tab === 'agent'      && <AgentTab      c={config} set={set} />}
              {tab === 'sampling'   && <SamplingTab   c={config} set={set} />}
              {tab === 'behaviour'  && <BehaviourTab  c={config} set={set} />}
              {tab === 'transcript' && <TranscriptTab c={config} set={set} />}
              {tab === 'voice'      && <VoiceTab      c={config} set={set} />}
              {tab === 'profiles'   && <ProfilesTab   c={config} set={set} profile={profile} onProfile={onProfile} />}
              {tab === 'optim'      && <OptimTab      c={config} set={set} />}
              {tab === 'toggles'    && <TogglesTab    c={config} set={set} />}
              {tab === 'paths'      && <PathsTab      c={config} set={set} />}
              {tab === 'prompt'     && <PromptTab />}
              {tab === 'about'      && <AboutTab />}
            </>
          )}
        </div>

        <div className="settings-footer">
          <div className="footer-left">
            <button type="button" className="panel-btn ghost" onClick={reset}>
              <Icon name="restart" size={11} />
              <span>reset to defaults</span>
            </button>
          </div>
          <div className="footer-right">
            {restartOffered && (
              <button
                type="button"
                className="panel-btn"
                onClick={restartAgent}
                disabled={restartPending}
                style={{ borderColor: 'var(--carmine)', color: 'var(--carmine)' }}
                title="toggle changes only take effect after restarting the agent"
              >
                <Icon name="restart" size={11} />
                <span>{restartPending ? 'restarting…' : 'restart agent now'}</span>
              </button>
            )}
            <button type="button" className="panel-btn ghost" onClick={onClose}>
              {restartOffered ? 'later' : 'cancel'}
            </button>
            <button type="button" className="panel-btn" onClick={apply} disabled={saving}>
              {saving ? 'applying…' : 'apply'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
