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

const gb = (mb: number, t: T) => (mb / 1024).toLocaleString(t.locale, { maximumFractionDigits: 1, minimumFractionDigits: 1 }) + ' GB';

/** uso-116: the figures of a lack of memory (llm_server.startup_failure): the buffer that did not fit, the PC's RAM free. */
export type FailureMemory = { need_mb: number; free_mb?: number | null };

/** what the person can read of a start's cause, or null when the host gave none it can name. */
export function causeText(cause: string | null | undefined, t: T, memory?: FailureMemory | null): string | null {
  if (!cause) return null;
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

/** what the person can do about it: free memory, or bring the model's file back. */
export function causeAdvice(cause: string | null | undefined, t: T): string | null {
  if (cause && MODEL_FILE[cause]) return t('Reinstala BAXY para recuperarlo: tus datos no se borran.', 'Reinstall BAXY to get it back: your data is not deleted.');
  return causeText(cause, t) ? t('Cierra programas que no estés usando para liberar memoria.', 'Close programs you are not using to free up memory.') : null;
}
