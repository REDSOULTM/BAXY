/* The view's contract with Baxy.App (FieldProductChannel, channel baxy.field.v1). Every value here comes from the
   host; a reading the host could not take travels as null and the view shows «—», never a 0. */

/** what the host says BAXY is doing (FieldProductChannel.CurrentConversationState). */
export type HostState = 'idle' | 'listening' | 'thinking' | 'speaking' | 'error';

/** what the view shows: the host's state plus the shell's own (booting, resting, a card waiting for the person). */
export type BaxyState = 'booting' | 'standby' | HostState | 'confirm';

/** the tool families the face's network lights (FieldStepProjection.Family). */
export type Fam = 'apps' | 'ventanas' | 'archivos' | 'web' | 'musica' | 'memoria' | 'alarmas';

/** a call the model made (FieldStepProjection): «ok» completed and its effect was read back, «same» found the asked
 *  state already there, «sent» was delivered without reading its effect, «read» is a read whose output is the result,
 *  «fail» failed, «skip» did not run, «maybe» may have run or completed without a verification. */
export type StepStatus = 'run' | 'ok' | 'same' | 'sent' | 'read' | 'fail' | 'skip' | 'maybe';

export interface Step {
  id: string;
  label: string;
  fam: Fam;
  status: StepStatus;
  /** how it was verified and what the provider observed (required with ok, same, sent and read). */
  obs?: string;
  /** why it failed, did not run or may have run (required with fail, skip and maybe). */
  reason?: string;
  /** what left the PC, when the call went out to the internet. */
  net?: string;
}

export type CardStatus = 'pending' | 'yes' | 'no' | 'expired' | 'dropped';

/** a risky call waiting for the person's Sí or No (the kernel's challenge) or a heartbeat's proposal. */
export interface Confirmation {
  id: string;
  kind: 'confirm' | 'proposal';
  risk?: string | null;
  title: string;
  target: string;
  context?: string | null;
  /** when the kernel's token expires, ms since the epoch. */
  expires: number;
  /** the kernel asks again for a call whose earlier attempt may already have happened. */
  effectStarted?: boolean;
  status: CardStatus;
  via?: string | null;
}

export type ChatItem =
  | { who: 'you'; id: string; text: string; ts: string }
  | { who: 'baxy'; id: string; text: string; ts: string; steps: Step[]; net?: string | null; silent?: string | null }
  | { who: 'sys'; id: string; text: string; ts: string }
  | ({ who: 'card'; ts: string } & Confirmation);

export interface AgentStatus {
  built: boolean;
  ready: boolean;
  failure?: string | null;
  pendingConfirmation?: boolean;
  /** active or at rest (the rail's power row and the tray menu change it) */
  powered?: boolean;
}

export type MicMode = 'off' | 'always' | 'ptt';

export interface VoiceStatus {
  available: boolean;
  /** off, wake (answers to «BAXY») or direct (one phrase). */
  mode: 'off' | 'wake' | 'direct';
  speaking: boolean;
  last_error?: string | null;
}

/** each piece is null while the host has not read it, false when it is not there. */
export interface BootPieces {
  stt: boolean | null;
  wake: boolean | null;
  tts: boolean | null;
  model: boolean;
  /** when the host started loading the model, ms since the epoch. */
  startedAt: number;
  /** when the model was ready, ms since the epoch; null while it loads. */
  readyAt: number | null;
  failed?: string | null;
}

export interface Metrics {
  cpu: number | null;
  gpu: number | null;
  /** °C of the graphics card (the PC's hottest reading BAXY can take without administrator rights). */
  temp: number | null;
  /** the model's own memory: llama-server and the mind. */
  model_vram_gb: number | null;
  model_ram_gb: number | null;
}

export interface Surfaces {
  sessions: number;
  memory: number | null;
  memory_revision?: number;
  tools: number;
  triggers: number | null;
}

export interface NetEntry { what: string; ts: string }

export type QuietSpan = '30m' | '1h' | 'tomorrow';

export interface ProposalSettings {
  /** proposals are silenced until this moment (ms since the epoch), null when they are on. */
  quietUntil: number | null;
  quiet: QuietSpan | null;
  ctx: { game: boolean; call: boolean; video: boolean };
}

export interface GeneralSettings {
  autostart: boolean | null;
  /** why the switch is locked: this copy may not own the sign-in start, or the Run key could not be read */
  autostartBlocked?: 'not_this_copy' | 'unreadable' | null;
  closeToTray: boolean;
  voiceMuted: boolean;
  wakeSound: boolean;
  waitNotice: boolean;
  web: boolean;
  weather: boolean;
  screen: boolean;
}

/** the host keeps the conversation (FieldTranscript): it sends an item whenever one is added or changes, and the whole
 *  list when the view connects or a session is opened. */
export type ServerEvent =
  | { type: 'state'; value: HostState; quiet?: HostState }
  | { type: 'agent'; built: boolean; ready: boolean; failure?: string | null; pendingConfirmation?: boolean; powered?: boolean }
  | { type: 'item'; item: ChatItem }
  | { type: 'transcript'; items: ChatItem[] }
  | ({ type: 'step'; phase: 'start' | 'end'; turn: string } & Step)
  | ({ type: 'voice' } & VoiceStatus)
  | { type: 'voice_partial'; text: string }
  | { type: 'lip'; t0?: number | null; step?: number | null; env?: number[] | null; stop?: number | null }
  | { type: 'voice_wake' }
  | ({ type: 'boot' } & BootPieces)
  | ({ type: 'net' } & NetEntry)
  | ({ type: 'surfaces' } & Surfaces)
  | { type: 'session'; id: string; label: string }
  | { type: 'context'; activity: 'free' | 'game' | 'call' | 'video' | 'away' };
