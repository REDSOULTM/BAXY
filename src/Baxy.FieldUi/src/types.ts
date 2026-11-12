/* The view's contract with Baxy.App (FieldProductChannel, channel baxy.field.v1). Every value here comes from the
   host; a reading the host could not take travels as null and the view shows «—», never a 0. */

import type { FailureMemory, FailureRead, ModelReading } from './causes';

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
  /** it changed one of BAXY's own settings (COR1): the steps are shown open, never only behind their fold. */
  pin?: boolean;
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
  /** the host also sent it as a Windows notification (the person was not to be spoken to). */
  notified?: boolean;
  status: CardStatus;
  via?: string | null;
}

// ended: kept «ringing» in a conversation saved while it rang, opened again when it no longer rings (FieldTranscript).
// windows, failed (APP1): the host took it and could not sound it; Windows' notification rings it, or nothing could.
export type RingStatus = 'ringing' | 'stopped' | 'snoozed' | 'timeout' | 'unanswered' | 'closed' | 'ended' | 'windows' | 'failed';

/** an alarm or a reminder the host rings now (ALR1): what BAXY says, and how it ended. `id` is the one schedule.alarms
 *  stop and snooze take. */
export interface Ring {
  id: string;
  kind: 'alarm' | 'reminder';
  title?: string | null;
  clock: string;
  words: string;
  status: RingStatus;
}

export type ChatItem = (
  // api: the host marks a turn made while the mind thought with a company's API (FieldTranscript); kept with the conversation
  | { who: 'you'; id: string; text: string; ts: string; api?: boolean }
  | { who: 'baxy'; id: string; text: string; ts: string; steps: Step[]; net?: string | null; silent?: string | null; api?: boolean }
  | { who: 'sys'; id: string; text: string; ts: string }
  | ({ who: 'card'; ts: string } & Confirmation)
  | { who: 'ring'; id: string; ts: string; ring: Ring })
  // V-03: turns by API dropped from the start of a long conversation leave this on the first item kept (FieldTranscript, store.ts)
  & { apiBefore?: boolean };

export interface AgentStatus {
  built: boolean;
  ready: boolean;
  failure?: string | null;
  pendingConfirmation?: boolean;
  /** uso 95: a message of the person's waits for the model to come up (it starts or is relaunched) */
  waitingForMind?: boolean;
  /** uso 95: why the model's last start failed while none is up (ram_insuficiente, vram_insuficiente, …) */
  failureCause?: string | null;
  // VIVO1 F4: why the server of another model refused the turn (model_refused), in the translator's words
  failureWhy?: string | null;
  /** REV_VISTA V-04: that refusal's kind (external_model ERROR[kind]), which the view says in its own language */
  failureKind?: string | null;
  /** N9: the figures of a read too slow, when the cause is one. */
  failureRead?: FailureRead | null;
  /** uso-116: the figures of that lack of memory, when known */
  failureMemory?: FailureMemory | null;
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
  /** uso 95: the ear waits for memory to load (not for a microphone): what it needs and found left, in MB */
  waiting_memory?: { need_mb: number; left_mb: number } | null;
  /** uso-116: there is a microphone and the voice settled, with no recogniser to hear it */
  no_recognizer?: boolean;
  /** V132: the voice settled without a wake word: «Siempre activo» cannot answer to «BAXY» */
  no_wake?: boolean;
  /** V132: why, when the installation names one: wake_missing (its folder gone or empty) or wake_changed (not the installed one) */
  wake_problem?: string | null;
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
  /** uso 95: why the start before this one failed (a relaunch is under way or waits its turn). */
  lastFailure?: string | null;
  failureMemory?: FailureMemory | null;
  failureRead?: FailureRead | null;
  /** N9: how far the model has read what it prepares; null when it is not reading (a kept start takes under a second). */
  reading?: ModelReading | null;
  /** N9: no graphics card the model's server can use: the processor computes. */
  onProcessor?: boolean;
  /** QWB2: why this start runs the stock model although the person chose the tuned one (missing or damaged), or null. */
  tunedProblem?: string | null;
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
  /** grows when a kept conversation's name changed after the list was read (the model named one that closed) */
  sessions_revision?: number;
  memory: number | null;
  memory_revision?: number;
  tools: number;
  triggers: number | null;
  /** RUT3: the routines that are on (RUTINAS.md §6); absent from an App that does not give it yet */
  routines?: number | null;
}

export interface NetEntry { what: string; ts: string }

export type QuietSpan = '30m' | '1h' | 'tomorrow';

export interface ProposalSettings {
  /** proposals are silenced until this moment (ms since the epoch), null when they are on. */
  quietUntil: number | null;
  quiet: QuietSpan | null;
  ctx: { game: boolean; call: boolean; video: boolean };
  /** a choice the host could not write to its file yet: it holds while BAXY runs and is written with the next change */
  unsaved?: boolean;
}

export interface GeneralSettings {
  /** a choice the host could not write to its file yet (Settings says so until one is written) */
  unsaved?: boolean;
  autostart: boolean | null;
  /** why the switch is locked: this copy may not own the sign-in start, or the Run key could not be read */
  // LEG1 §5: a copy from Steam or itch.io says its store (FieldProductChannel.AutostartBlocked)
  autostartBlocked?: 'not_this_copy' | 'steam_copy' | 'itch_copy' | 'unreadable' | null;
  closeToTray: boolean;
  /** minimizing hides the window in the tray (Settings › General) */
  minimizeToTray?: boolean;
  voiceMuted: boolean;
  wakeSound: boolean;
  waitNotice: boolean;
  /** «Ignorar lo que suena en el PC»: the mind takes what the PC plays out of the microphone (voice_echo.py) */
  echoCancel: boolean;
  web: boolean;
  weather: boolean;
  screen: boolean;
  /** «Avisar de versiones nuevas»: one check at each start where BAXY was published (Settings › General) */
  updateNotice?: boolean;
  /** the interface's language as the person chose it (Settings); «auto» follows Windows */
  language?: 'auto' | 'es' | 'en';
  /** the language in use, resolved by the host (from Windows when the choice is «auto») */
  languageInUse?: 'es' | 'en';
  /** VIS3: the version this App is, from its own stamp (UpdatePanel.Installed): no check is needed to know it */
  version?: string | null;
}

/** the host keeps the conversation (FieldTranscript): it sends an item whenever one is added or changes, and the whole
 *  list when the view connects or a session is opened. */
export type ServerEvent =
  | { type: 'state'; value: HostState; quiet?: HostState }
  | { type: 'agent'; built: boolean; ready: boolean; failure?: string | null; pendingConfirmation?: boolean; powered?: boolean; waitingForMind?: boolean; failureCause?: string | null; failureWhy?: string | null; failureKind?: string | null; failureMemory?: FailureMemory | null; failureRead?: FailureRead | null }
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
  | { type: 'context'; activity: 'free' | 'game' | 'call' | 'video' | 'away' }
  /** a newer BAXY where it was published (the host's baxy.update check); nothing updates without the person's «Actualizar» */
  | { type: 'update'; latest: string; installed: string };
