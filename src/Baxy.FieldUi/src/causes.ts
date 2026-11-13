import type { T, Words } from './i18n';
import { num } from './numbers';

/* Uso 95 (F9): why the model did not start, as the host says it (MainWindowViewModel.MindFailureCause, from the mind's
   llm_server.memory_failure), told as a state of the interface: never words of BAXY's (zero fixed visible replies). */
const MEMORY: Record<string, Words> = {
  ram_insuficiente: { es: 'falta memoria RAM libre en el equipo', en: 'this PC is short of free RAM' },
  vram_insuficiente: { es: 'falta memoria libre en la tarjeta gráfica', en: 'the graphics card is short of free memory' },
  /* VRAM5B (REV19 V-2): an integrated GPU has no card of its own: what it lacks is the PC's RAM (llm_server.integrated_room) */
  vram_integrada: { es: 'falta memoria RAM libre para la gráfica integrada', en: 'there isn’t enough free RAM for the integrated graphics' },
  memoria_insuficiente: { es: 'falta memoria libre en el equipo', en: 'this PC is short of free memory' },
};

/* Uso 112: the server's log says it could not open the model's file, or that what it read is no model
   (llm_server.model_file_failure). */
const gb = (mb: number, t: T) => num(mb / 1024, t.locale, 1) + ' GB';

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
/* VRAM4: «con 4 GB de memoria libres» was false on a card of 4 GB in all, the one BAXY is made for: with Windows and a desktop
   open it never has them free. API1 said the same of that card («unos 4 GB libres… a su contexto»): since VRAM4 the context
   follows what is free at start (llm_server.fit_card), so that figure is no longer what the model takes there. */
const NEEDS: Words = {
  es: 'BAXY necesita una tarjeta gráfica dedicada con 4 GB de memoria o un procesador más rápido.',
  en: 'BAXY needs a dedicated graphics card with 4 GB of memory or a faster processor.',
};

/* The tool profiles by their names (ToolProfile's presets in the App). */
export const PROFILE_NAME: Record<string, Words> = {
  esencial: { es: 'Esencial', en: 'Essential' }, diario: { es: 'Diario', en: 'Everyday' },
  avanzado: { es: 'Avanzado', en: 'Advanced' }, completo: { es: 'Completo', en: 'Complete' },
};

/** VRAM4: the model's start found a card whose free video memory does not hold the profile's instructions and tools whole
    (LocalContext.CardShort in the App, from the mind's llm_server.fit_card): the profile, what was free, what it takes, and
    the ready-made profile that fits whole (null when none does). */
export type FailureCard = {
  profile: string; freeMb: number; needMb: number; context?: number; fittingProfile?: string | null;
  /** VRAM5 (AUD1 F4): the cells are the person's own (Settings → Model → Context), and the most the card holds whole. */
  given?: boolean; fitsContext?: number | null;
  /** VRAM5 (AUD1 F5): an integrated GPU: its memory is the PC's RAM, and freeMb what it leaves past Windows and BAXY. */
  integrated?: boolean;
};

export function cardShortText(card: FailureCard, t: T): string {
  const name = (profile: string) => (PROFILE_NAME[profile] ? t.w(PROFILE_NAME[profile]) : profile);
  const fits = card.fittingProfile && card.fittingProfile !== card.profile ? card.fittingProfile : null;
  // VRAM5 (AUD1 F5): no card of its own: the RAM it shares, with what Windows and the rest of BAXY take of it.
  const where = card.integrated
    ? t(`Tu gráfica es integrada y usa la memoria RAM del equipo: después de Windows y del resto de BAXY quedan ${gb(card.freeMb, t)} para el modelo y necesita unos ${gb(card.needMb, t)}.`,
      `Your graphics is integrated and uses this PC’s RAM: after Windows and the rest of BAXY, ${gb(card.freeMb, t)} is left for the model and it needs about ${gb(card.needMb, t)}.`)
    : null;
  // VRAM5 (AUD1 F4): cells given in Settings are never changed: what was free, what they take, and the way out.
  // VRAM5B (REV19 V-10): the setting is named, not who wrote it (BAXY's KeepFitting writes it too, on a profile asked by
  // voice). V-1, V-9: the way out is «Automático», which fits the cells to the card (backToAutomatic); a smaller context
  // of the list is no way out right after a failed start: with no prefix read, the list allows none below every profile's.
  if (card.given) {
    const cells = (n: number) => num(n, t.locale, 0);
    return (where ?? t(`El contexto de Ajustes → Modelo → Contexto (${cells(card.context ?? 0)}) no cabe entero en la memoria de vídeo de tu tarjeta gráfica: había ${gb(card.freeMb, t)} libres al arrancar y necesita unos ${gb(card.needMb, t)}.`,
      `The context in Settings → Model → Context (${cells(card.context ?? 0)}) doesn’t fit whole in your graphics card’s video memory: ${gb(card.freeMb, t)} was free at start and it needs about ${gb(card.needMb, t)}.`))
      + (card.fitsContext ? t(' Para que BAXY lo ajuste a la memoria que hay, vuelve a «Automático» en Ajustes → Modelo → Contexto.', ' For BAXY to fit it to the memory there is, go back to “Automatic” in Settings → Model → Context.')
        : where ? t(' Ningún contexto cabe en la RAM de este equipo: usa otro modelo (Ajustes → Modelo).', ' No context fits this PC’s RAM: use another model (Settings → Model).')
          : t(' Ningún contexto cabe ahora: cierra lo que esté usando la tarjeta gráfica o usa otro modelo.', ' No context fits now: close what is using the graphics card or use another model.'));
  }
  if (where) {
    return where + (fits ? t(` El perfil ${name(fits)} sí cabe entero: elígelo en Ajustes → Herramientas → Perfil.`, ` The ${name(fits)} profile does fit whole: choose it in Settings → Tools → Profile.`)
      : t(' No cabe ningún perfil: usa otro modelo (Ajustes → Modelo), o un equipo con más RAM o con una tarjeta gráfica dedicada.', ' No profile fits: use another model (Settings → Model), or a PC with more RAM or a dedicated graphics card.'));
  }
  return t(`El perfil ${name(card.profile)} no cabe entero en la memoria de vídeo de tu tarjeta gráfica: había ${gb(card.freeMb, t)} libres al arrancar y necesita unos ${gb(card.needMb, t)}.`,
    `The ${name(card.profile)} profile doesn’t fit whole in your graphics card’s video memory: ${gb(card.freeMb, t)} was free at start and it needs about ${gb(card.needMb, t)}.`)
    + (fits ? t(` El perfil ${name(fits)} sí cabe entero: elígelo en Ajustes → Herramientas → Perfil.`, ` The ${name(fits)} profile does fit whole: choose it in Settings → Tools → Profile.`)
      : t(' Cierra lo que esté usando la tarjeta gráfica y reintenta.', ' Close what is using the graphics card and try again.'));
}

/** VRAM5B (REV19 V-1, V-9): a context given in Settings that the card does not hold, when some fewer cells would: the
    breakdown offers «Automático» (PUT /settings/local-context with none, then a new start), the way out that starts. */
export const backToAutomatic = (card: FailureCard | null | undefined): boolean => !!card?.given && !!card.fitsContext;

/** VRAM5B (REV19 N9): whether Settings → Model → Context says what the last start found: a context given there while one is
    still chosen, or the automatic one while «Automático» is. Not the other way, nor another context chosen since (with the
    mind down there is no «Cambiando»): the hint would outlive the change. */
export const cardShortInSettings = (card: FailureCard | null | undefined, chosen: number | null): boolean =>
  !!card && (card.given ? chosen !== null && chosen === card.context : chosen === null);

/** VRAM4B: the ready-made profile the card holds whole, when it is another than the one that did not fit: the breakdown
    offers to start in it («Arrancar en Esencial»). */
export const fittingProfile = (card: FailureCard | null | undefined): string | null =>
  card?.fittingProfile && card.fittingProfile !== card.profile && PROFILE_NAME[card.fittingProfile] ? card.fittingProfile : null;

/** VRAM4B (the leader's decision, 2026-11-12): the person never chose a tool profile, the card's free video memory did not
    hold the factory's, and a start took by itself the one it holds (ToolProfile.FitCard in the App): what was free, what
    the factory's takes, the profile it took, and the ways to more tools. VRAM4C: kept for this PC as BAXY's choice (not
    the person's) until the person chooses another; the notice is said on that start only, Settings → Tools always.
    VRAM4D (REV18 R18-2): only on a card short in all; on one with room (something held its memory at that start) the
    profile is that start's alone («thisStart»), and the next start tries the factory's again. */
export type CardProfile = { profile: string; factory: string; freeMb: number; needMb: number; thisStart?: boolean };

export function cardProfileText(card: CardProfile, t: T): string {
  const name = (profile: string) => (PROFILE_NAME[profile] ? t.w(PROFILE_NAME[profile]) : profile);
  if (card.thisStart) {
    return t(`Tu tarjeta gráfica tenía ${gb(card.freeMb, t)} de memoria de vídeo libres al arrancar y el perfil ${name(card.factory)} necesita unos ${gb(card.needMb, t)}: sólo en este arranque, BAXY usa el perfil ${name(card.profile)}, que sí cabe. El próximo arranque vuelve a intentar el perfil ${name(card.factory)}: para tenerlo ya, cierra lo que esté usando la tarjeta gráfica (un juego, por ejemplo) y vuelve a abrir BAXY.`,
      `Your graphics card had ${gb(card.freeMb, t)} of video memory free at start and the ${name(card.factory)} profile needs about ${gb(card.needMb, t)}: for this start only, BAXY uses the ${name(card.profile)} profile, which fits. The next start tries the ${name(card.factory)} profile again: to have it now, close what is using the graphics card (a game, for example) and open BAXY again.`);
  }
  // R18-12: another model alone does not bring the tools back: the profile is still the one BAXY chose.
  return t(`Tu tarjeta gráfica tenía ${gb(card.freeMb, t)} de memoria de vídeo libres y el perfil ${name(card.factory)} necesita unos ${gb(card.needMb, t)}: BAXY eligió para este equipo el perfil ${name(card.profile)}, que sí cabe, y se queda en él. Para tener más herramientas, usa otro modelo (Ajustes → Modelo) o libera memoria de la tarjeta gráfica, y elige el perfil ${name(card.factory)} en Ajustes → Herramientas o pidiéndomelo.`,
    `Your graphics card had ${gb(card.freeMb, t)} of video memory free and the ${name(card.factory)} profile needs about ${gb(card.needMb, t)}: BAXY chose the ${name(card.profile)} profile for this PC, which fits, and stays in it. For more tools, use another model (Settings → Model) or free up the graphics card’s memory, and choose the ${name(card.factory)} profile in Settings → Tools or by asking me.`);
}

/** uso-116: the figures of a lack of memory (llm_server.startup_failure): the buffer that did not fit, the PC's RAM free. */
export type FailureMemory = { need_mb: number; free_mb?: number | null };

/** N9: the figures of a read too slow (llm_server.startup_failure): its pace, and what the whole prefix would take. */
export type FailureRead = {
  tokens_per_s: number; minutes: number;
  /** VRAM5 (AUD1 F9): the card had less free than the mind's margin when it gave up, and the PC's RAM Windows gave the
      server as video memory (llm_server._card_full); absent otherwise. */
  card_free_mb?: number | null; shared_mb?: number | null;
};

/** what the person can read of a start's cause, or null when the host gave none it can name. */
export function causeText(cause: string | null | undefined, t: T, memory?: FailureMemory | null, read?: FailureRead | null, card?: FailureCard | null): string | null {
  if (!cause) return null;
  if (cause === 'vram_insuficiente' && card?.integrated) return t.w(MEMORY.vram_integrada);
  if (cause === READ_TOO_SLOW) {
    if (!read) return t.w(READ_TOO_SLOW_TEXT);
    // VRAM5 (AUD1 F9): what Windows does in silence when the card is full, as measured when the read gave up
    if (read.card_free_mb != null) {
      // VRAM5B (REV19 V-4, N4): no figure: the shared memory counted holds what a server that fits shares too
      return t('la tarjeta gráfica se quedó sin memoria y Windows pasa parte del modelo a la RAM del equipo, mucho más lenta',
        'the graphics card ran out of memory and Windows moves part of the model to this PC’s RAM, which is much slower')
        + t(': prepararlo tardaría ', ': getting it ready would take ')
        + (read.minutes < 90 ? t('unos ', 'about ') + read.minutes + ' min' : t('más de ', 'more than ') + Math.floor(read.minutes / 60) + ' h');
    }
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

/* V132: why the ear has no wake word, as the host read it in the installation (MindRuntimeDiscovery.UnverifiedWake). */
const WAKE: Record<string, Words> = {
  wake_missing: { es: 'falta su detector · reinstala BAXY', en: 'its detector is missing · reinstall BAXY' },
  wake_changed: { es: 'su detector no es el que se instaló · reinstala BAXY', en: 'its detector is not the installed one · reinstall BAXY' },
};

/** V132: the ear started without its wake word: said while «Siempre activo» is the person's choice, never a silent ear. */
export function noWakeText(problem: string | null | undefined, t: T): string {
  return t('Sin palabra de activación «BAXY»: ', 'No “BAXY” wake word: ')
    + (problem && WAKE[problem] ? t.w(WAKE[problem]) : t('no está disponible', 'it isn’t available'))
    + t(' · escribe o usa «Mantener para hablar»', ' · type, or use “Push to talk”');
}

/* QWB2: why the mind started on the stock model although the person chose the tuned one (TunedModel.Verify in the App). */
export const TUNED_PROBLEM: Record<string, Words> = {
  ajustado_ausente: { es: 'No encontré el modelo ajustado: BAXY sigue con el modelo de serie. Instálalo otra vez para usarlo', en: 'I didn’t find the tuned model: BAXY stays on the stock model. Install it again to use it' },
  ajustado_danado: { es: 'El modelo ajustado está dañado y no lo voy a usar: BAXY sigue con el modelo de serie. Instálalo otra vez para usarlo', en: 'The tuned model is damaged and I won’t use it: BAXY stays on the stock model. Install it again to use it' },
};

/** N9: a start that repeats nothing the person can act on says it once, without the count of failed starts. VRAM4B: so
    does one on a card that does not hold the profile (the host tries it once, MainWindowViewModel.RetryMindOrGiveUp). */
export const startedOnlyOnce = (cause: string | null | undefined, card?: FailureCard | null) => cause === READ_TOO_SLOW || !!card;

/** N9: how far a slow start is, from the server's own count, and what is left at its pace when it is known. */
export type ModelReading = {
  done: number; total: number; seconds_left?: number | null;
  /** VUL1, the view's own (reading.ts): the least time left said so far of this read, and whether the count rose above it. */
  least?: number | null; slower?: boolean;
};

export function readingText(reading: ModelReading, t: T): string {
  const percent = Math.floor((reading.done / Math.max(1, reading.total)) * 100);
  const left = reading.seconds_left;
  const remaining = left == null ? (reading.slower ? t(' · tarda más de lo previsto', ' · taking longer than expected') : '')
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
export function causeAdvice(cause: string | null | undefined, t: T, card?: FailureCard | null, read?: FailureRead | null): string | null {
  // VRAM4: a start that was slow, stopped or ran out of memory on a card that does not hold the profile whole: that is the cause
  if (card && cause && (cause === READ_TOO_SLOW || cause === NO_ADVANCE || MEMORY[cause])) return cardShortText(card, t);
  // VRAM5 (AUD1 F9): the card was full: what frees it, not a faster PC
  if (cause === READ_TOO_SLOW && read?.card_free_mb != null) return t('Cierra lo que esté usando la tarjeta gráfica (un juego, por ejemplo) y reintenta, o usa otro modelo.', 'Close what is using the graphics card (a game, for example) and try again, or use another model.');
  if (cause === READ_TOO_SLOW) return t.w(NEEDS) + t(' Si el equipo estaba ocupado, cierra lo que no uses y reintenta.', ' If the PC was busy, close what you are not using and try again.');
  if (cause === NO_ADVANCE) return t('Actualiza el controlador de la tarjeta gráfica y reintenta. ', 'Update the graphics card driver and try again. ') + t.w(NEEDS);
  if (cause && MODEL_FILE[cause]) return t('Reinstala BAXY para recuperarlo: tus datos no se borran.', 'Reinstall BAXY to get it back: your data is not deleted.');
  return causeText(cause, t) ? t('Cierra programas que no estés usando para liberar memoria.', 'Close programs you are not using to free up memory.') : null;
}
