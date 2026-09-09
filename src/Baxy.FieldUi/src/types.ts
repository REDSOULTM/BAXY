/* shared types — match server WS payload contract and HTTP endpoints. */

export type ConvState = 'standby' | 'idle' | 'listening' | 'thinking' | 'speaking' | 'error';

export type SourceTag =
  | 'TOOL'
  | 'YOU'
  | 'GEMMA'
  | 'MEMORY'
  | 'TRIGGER'
  | 'BOOT'
  | 'THOUGHT'
  | 'SYSTEM'
  | 'CONTEXT';

export interface ActivityEntry {
  id: string;
  src: SourceTag;
  msg: string;
  ts: string; // 'HH:MM:SS'
}

export interface ModelInfo {
  family: string;
  params: string;
  runtime: 'local' | 'remote' | 'mock';
  quant: string;
  size_bytes: number;
  name_full: string;
  context_size: number;
  mmproj: boolean;
}

/* GET /model returns 503 with this body while the server is still booting */
export interface ModelLoadingResponse {
  status: 'loading';
}

export type MetricKey = 'cpu' | 'mem' | 'gpu' | 'net' | 'dsk' | 'tmp';

export interface MetricSnapshot {
  cpu: number;
  mem: number;
  /** memory used in gb (display value for the mem row), separate from the %
   *  that drives the bar. zero when psutil can't read it. */
  mem_used_gb?: number;
  gpu: number;
  net: number;
  dsk: number;
  tmp: number;
  /** uptime "HH:MM:SS" since the launcher process started. */
  uptime?: string;
  /* per-metric flag: true if the agent doesn't actually produce this yet
     and the value is a deterministic placeholder. UI renders these dim. */
  placeholder?: Partial<Record<MetricKey, boolean>>;
}

/** /hardware specs — detected once at server start and cached. */
export interface HardwareInfo {
  cpu: string;            // "ryzen 7 7700x · 16c" or "unknown · 16c"
  cpu_cores: number;
  mem: string;            // "32 gb"
  mem_total_gb: number;
  gpu: string;            // "rtx 4090 · 24 gb"
  gpu_vram_gb: number;
}

/* WS event union — matches the contract in the task brief */
export type ServerEvent =
  | { type: 'state'; value: ConvState }
  | { type: 'activity'; entry: ActivityEntry }
  | { type: 'metric'; key: MetricKey; value: number; label?: string; placeholder?: boolean }
  | { type: 'ctx'; used: number; budget: number }
  | { type: 'tokens'; delta: number }
  | {
      type: 'field';
      entropy: number;
      temperature: number;
      tokens_per_s: number;
      draw_w: number;
    }
  | {
      type: 'surfaces';
      sessions: number;
      memory: number;
      triggers: number;
      tools: number;
    }
  | { type: 'session'; id: string; label: string }
  | { type: 'model'; info: ModelInfo }
  | {
      /** agent boot lifecycle. lets the UI disable the chat input until the
       *  agent is built AND llama-server responds to /health. */
      type: 'agent';
      built: boolean;
      healthy: boolean;
      ready: boolean;
    }
  | {
      /** granular boot-time progress. Emitted while the LLM and voice stack
       *  are coming up so the UI can show what's actually loading instead of
       *  a single opaque "loading…". `progress` is 0..100 when known; null
       *  otherwise. `error` non-null means the stage failed and the chat
       *  input should surface a retry button.
       *
       *  Campos opcionales (label/progress/error) porque algunos publicadores
       *  (prewarm.py) emiten un shape mas simple: {stage, elapsed_s, ok,
       *  system_prompt_chars}. El reducer normaliza ambos. */
      type: 'boot_stage';
      stage: string;
      label?: string | null;
      progress?: number | null;
      error?: string | null;
      // one-shot stages (e.g. profile_swap) report a lifecycle phase; when
      // 'completed' the UI clears the boot overlay instead of pinning the
      // stage name as the placeholder.
      phase?: 'starting' | 'completed' | string;
      profile?: string;
      result?: string;
      // shape extendido del prewarm
      elapsed_s?: number;
      ok?: boolean;
      system_prompt_chars?: number;
      msg?: string;
    }
  | {
      /** El contador de imagenes cruzo el umbral del mmproj leak
       *  (issue ggml-org/llama.cpp#21690). La UI debe mostrar un banner
       *  amber con accion "recycle llama-server" hasta que el server sea
       *  reciclado (POST /agent/recycle_server).
       *
       *  El BUS publica con `kind: 'vision_threshold_reached'`; useEventStream
       *  copia kind a type antes del reducer, asi el discriminante funciona
       *  con la misma forma que el resto del union. */
      type: 'vision_threshold_reached';
      image_count: number;
      threshold: number;
      issue: string;
    }
  /** wipe the activity log everywhere — fired by POST /log/clear. */
  | { type: 'log_clear' }
  /** A voice capture was dropped (silence below the RMS floor, or a Whisper
   *  silence hallucination). The user who tried to speak gets a brief "no te
   *  entendí" cue instead of the HUD silently dropping back to idle. */
  | { type: 'voice_no_speech' };
