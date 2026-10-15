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
  /** what the line is: the model's answer, its question, or its question about a call waiting for a «sí». */
  route?: string;
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

export interface MetricSnapshot {
  cpu: number;
  mem: number;
  /** memory used in gb (display value for the mem row), separate from the %
   *  that drives the bar. zero when it can't be read. */
  mem_used_gb?: number;
  /** null when no GPU adapter reports a usage counter. */
  gpu: number | null;
  dsk: number;
  /** time since Windows started, "HH:MM:SS". */
  uptime?: string;
}

/* WS event union — matches the contract in the task brief */
export type ServerEvent =
  | { type: 'state'; value: ConvState }
  | { type: 'activity'; entry: ActivityEntry }
  | {
      type: 'surfaces';
      sessions: number;
      memory: number;
      memory_revision?: number;
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
      /** a risky call waits for the person's Sí or No */
      pendingConfirmation?: boolean;
    }
  /** wipe the activity log everywhere — fired by POST /log/clear. */
  | { type: 'log_clear' };
