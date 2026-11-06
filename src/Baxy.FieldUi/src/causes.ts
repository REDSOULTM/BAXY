import type { T, Words } from './i18n';

/* Uso 95 (F9): why the model did not start, as the host says it (MainWindowViewModel.MindFailureCause, from the mind's
   llm_server.memory_failure), told as a state of the interface: never words of BAXY's (zero fixed visible replies). */
const MEMORY: Record<string, Words> = {
  ram_insuficiente: { es: 'falta memoria RAM libre en el equipo', en: 'this PC is short of free RAM' },
  vram_insuficiente: { es: 'falta memoria libre en la tarjeta gráfica', en: 'the graphics card is short of free memory' },
  memoria_insuficiente: { es: 'falta memoria libre en el equipo', en: 'this PC is short of free memory' },
};

/* Uso 112: the server's log says it could not open the model's file, or that what it read is no model
   (llm_server.model_file_failure). */
const MODEL_FILE: Record<string, Words> = {
  modelo_ausente: { es: 'no se encuentra el archivo del modelo', en: 'the model file can’t be found' },
  modelo_danado: { es: 'el archivo del modelo está dañado', en: 'the model file is damaged' },
  // uso-116: what the install lacks before anything starts (MindRuntimeDiscovery.RegistrationProblem).
  sin_instalar: { es: 'BAXY no encuentra su instalación', en: 'BAXY can’t find its installation' },
  componente_ausente: { es: 'falta o cambió un componente de BAXY', en: 'a BAXY component is missing or changed' },
};

/* N9 (L5): this machine reads the model too slowly for the mind's limit (llm_server.ReadTooSlow): what is said is what it
   measured, and what would change it. */
const READ_TOO_SLOW = 'lectura_lenta';
const READ_TOO_SLOW_TEXT: Words = { es: 'este equipo lee el modelo demasiado lento', en: 'this PC reads the model too slowly' };
/* The model stopped advancing or never came up in its time: this PC may be too slow, or its graphics card hung; the read
   tells no pace to say which (a first batch under ~17 tokens/s ends no batch in its 120 s). */
const NO_ADVANCE = 'tiempo';
const NO_ADVANCE_TEXT: Words = {
  es: 'dejó de avanzar antes de terminar: este equipo puede ir demasiado lento para él, o su tarjeta gráfica se colgó',
  en: 'it stopped advancing before it finished: this PC may be too slow for it, or its graphics card hung',
};
const NEEDS: Words = {
  es: 'BAXY necesita una tarjeta gráfica dedicada con 4 GB de memoria libres o un procesador más rápido.',
  en: 'BAXY needs a dedicated graphics card with 4 GB of free memory or a faster processor.',
};

const gb = (mb: number, t: T) => (mb / 1024).toLocaleString(t.locale, { maximumFractionDigits: 1, minimumFractionDigits: 1 }) + ' GB';

/** uso-116: the figures of a lack of memory (llm_server.startup_failure): the buffer that did not fit, the PC's RAM free. */
export type FailureMemory = { need_mb: number; free_mb?: number | null };

/** N9: the figures of a read too slow (llm_server.startup_failure): its pace, and what the whole prefix would take. */
export type FailureRead = { tokens_per_s: number; minutes: number };

/** what the person can read of a start's cause, or null when the host gave none it can name. */
export function causeText(cause: string | null | undefined, t: T, memory?: FailureMemory | null, read?: FailureRead | null): string | null {
  if (!cause) return null;
  if (cause === READ_TOO_SLOW) {
    if (!read) return t.w(READ_TOO_SLOW_TEXT);
    // past 90 min the figure is a curve drawn from the first batches: an order of size, not a promise
    return t.w(READ_TOO_SLOW_TEXT) + t(': prepararlo tardaría ', ': getting it ready would take ')
      + (read.minutes < 90 ? t('unos ', 'about ') + read.minutes + ' min' : t('más de ', 'more than ') + Math.floor(read.minutes / 60) + ' h');
  }
  if (cause === NO_ADVANCE) return t.w(NO_ADVANCE_TEXT);
  if (MEMORY[cause] && memory) {
    return t.w(MEMORY[cause]) + t(': no cupo un bloque de ', ': a block of ') + gb(memory.need_mb, t) + t('', ' did not fit')
      + (memory.free_mb != null ? t(' y hay ', ', with ') + gb(memory.free_mb, t) + t(' libres', ' free') : '');
  }
  const words = MEMORY[cause] ?? MODEL_FILE[cause];
  return words ? t.w(words) : null;
}

/** uso 95: why the microphone cannot be used yet, when it is the ear waiting for memory and not a missing microphone. */
export function micBlockedText(waiting: { need_mb: number; left_mb: number } | null | undefined, t: T, noRecognizer?: boolean): string {
  return waiting
    ? t('La voz espera memoria libre: necesita ', 'Voice is waiting for free memory: it needs ') + gb(waiting.need_mb, t)
      + t(' y hay ', ' and ') + gb(waiting.left_mb, t) + t(' · se reintenta sola', ' is free · it retries by itself')
    : noRecognizer ? t('Falta el reconocimiento de voz: reinstala BAXY', 'Speech recognition is missing: reinstall BAXY') : t('No hay micrófono', 'No microphone');
}

/** N9: a start that repeats nothing the person can act on says it once, without the count of failed starts. */
export const startedOnlyOnce = (cause: string | null | undefined) => cause === READ_TOO_SLOW;

/** N9: how far a slow start is, from the server's own count, and what is left at its pace when it is known. */
export type ModelReading = { done: number; total: number; seconds_left?: number | null };

export function readingText(reading: ModelReading, t: T): string {
  const percent = Math.floor((reading.done / Math.max(1, reading.total)) * 100);
  const left = reading.seconds_left;
  const remaining = left == null ? ''
    : left < 60 ? t(' · queda menos de 1 min', ' · less than 1 min left')
      : t(' · quedan unos ', ' · about ') + Math.ceil(left / 60) + t(' min', ' min left');
  return t('Preparando el modelo · ', 'Getting the model ready · ') + percent + ' %' + remaining;
}

/** N9: why a start or an answer takes this long on a PC with no graphics card the model's server can use. */
export const ON_PROCESSOR_TEXT: Words = {
  es: 'BAXY no está usando una tarjeta gráfica: el modelo corre en el procesador y va más lento. Si el equipo tiene una, instala o actualiza su controlador.',
  en: 'BAXY is not using a graphics card: the model runs on the processor and is slower. If this PC has one, install or update its driver.',
};

/** what the person can do about it: free memory, bring the model's file back, or a machine that can run the model. */
export function causeAdvice(cause: string | null | undefined, t: T): string | null {
  if (cause === READ_TOO_SLOW) return t.w(NEEDS) + t(' Si el equipo estaba ocupado, cierra lo que no uses y reintenta.', ' If the PC was busy, close what you are not using and try again.');
  if (cause === NO_ADVANCE) return t('Actualiza el controlador de la tarjeta gráfica y reintenta. ', 'Update the graphics card driver and try again. ') + t.w(NEEDS);
  if (cause && MODEL_FILE[cause]) return t('Reinstala BAXY para recuperarlo: tus datos no se borran.', 'Reinstall BAXY to get it back: your data is not deleted.');
  return causeText(cause, t) ? t('Cierra programas que no estés usando para liberar memoria.', 'Close programs you are not using to free up memory.') : null;
}
