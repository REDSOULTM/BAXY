/* shared types — match server WS payload contract and HTTP endpoints. */

export type ConvState = 'standby' | 'idle' | 'listening' | 'thinking' | 'speaking' | 'error';

/** who wrote the line: the person, BAXY (what the model wrote), or the view itself. */
export type SourceTag = 'YOU' | 'BAXY' | 'SYSTEM';

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
  context_size: number;
}

/** Each reading is null when the PC did not give it; the view shows «—», never a 0 as if measured. */
export interface MetricSnapshot {
  cpu: number | null;
  mem: number | null;
  /** memory used in gb (display value for the mem row), separate from the %
   *  that drives the bar. */
  mem_used_gb?: number | null;
  /** null when no GPU adapter reports a usage counter. */
  gpu: number | null;
  dsk: number | null;
  /** time since Windows started, "HH:MM:SS". */
  uptime?: string | null;
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
      /** the shell's gate: the chat input is disabled until a turn is accepted. */
      type: 'agent';
      built: boolean;
      ready: boolean;
      /** the observed failure's code (the engine's or the last turn's), null when there is none */
      failure?: string | null;
      /** a risky call waits for the person's Sí or No */
      pendingConfirmation?: boolean;
    }
  /** wipe the activity log everywhere — fired by POST /log/clear. */
  | { type: 'log_clear' };
