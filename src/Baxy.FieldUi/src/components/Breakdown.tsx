import { useState } from 'react';
import { sendTold } from '../api';
import { useT, type Words } from '../i18n';
import { backToAutomatic, causeAdvice, causeText, fittingProfile, ON_PROCESSOR_TEXT, PROFILE_NAME, startedOnlyOnce, type FailureCard, type FailureMemory, type FailureRead } from '../causes';

/* Uso 85: the engine stopped for good (MainWindowViewModel.ProfileUnreadable, EngineUnavailable) and the host no longer
   relaunches it on its own. What happened is said as a state of the interface (never words of BAXY's: zero fixed
   visible replies), with what the person can do. Their memory is never deleted: a new profile sets the old one aside. */

const TEXT: Record<string, { title: Words; body: Words; act?: Words; path?: string }> = {
  profile_unreadable: {
    title: { es: 'Tus datos guardados no se pueden abrir', en: 'Your saved data can’t be opened' },
    body: {
      es: 'Son de otra versión de BAXY o los protegió otra cuenta de Windows, y esta cuenta no puede leerlos. '
        + 'Puedes empezar con un perfil nuevo: el anterior no se borra, queda apartado en su carpeta con la fecha de hoy.',
      en: 'It’s from another version of BAXY, or another Windows account protected it, so this account can’t read it. '
        + 'You can start with a new profile: the old one isn’t deleted, it’s set aside in its folder with today’s date.',
    },
    act: { es: 'Empezar con un perfil nuevo', en: 'Start with a new profile' },
    path: '/profile/fresh',
  },
  engine_unavailable: {
    title: { es: 'BAXY no logra arrancar', en: 'BAXY can’t start' },
    body: { es: 'El arranque falló varias veces seguidas y ya no se reintenta solo.', en: 'Startup failed several times in a row and won’t retry on its own.' },
    act: { es: 'Reintentar', en: 'Try again' },
    path: '/engine/retry',
  },
  // uso-101: nothing here can be retried; it changes when the person installs a driver or a GPU and opens BAXY again
  no_supported_gpu: {
    title: { es: 'BAXY necesita una GPU compatible', en: 'BAXY needs a supported GPU' },
    body: {
      es: 'Windows no muestra en este PC una GPU NVIDIA, AMD o Intel con su controlador, y el modelo de BAXY no funciona sin una. '
        + 'Si la tienes, instala o actualiza su controlador y vuelve a abrir BAXY.',
      en: 'Windows doesn’t show an NVIDIA, AMD or Intel GPU with its driver on this PC, and BAXY’s model doesn’t run without one. '
        + 'If you have one, install or update its driver and open BAXY again.',
    },
  },
};

// a refusal by the host (FieldProductChannel): the only one that can happen with the breakdown still shown
const REFUSED: Record<string, Words> = {
  profile_unreadable: {
    es: 'No se pudo apartar la carpeta: puede que otra ventana la tenga abierta. Ciérrala y vuelve a intentarlo.',
    en: 'The folder couldn’t be set aside: another window may have it open. Close it and try again.',
  },
};

/* API1 (a friend of the owner's, a 4 GB card, 12-11-2026): BAXY's own model could not load, and the way out that needs none of
   it, another model (Settings → Model, «Usar otro modelo»), was not offered where he was stuck. Offered where the model is what
   failed (not for unreadable data), whenever the host offers another model. */
const OTHER_MODEL = new Set(['engine_unavailable', 'no_supported_gpu']);

export function Breakdown({ failure, cause = null, memory = null, read = null, card = null, onProcessor = false, onOtherModel = null }: { failure: string; cause?: string | null; memory?: FailureMemory | null; read?: FailureRead | null; card?: FailureCard | null; onProcessor?: boolean; onOtherModel?: (() => void) | null }) {
  const t = useT();
  const [busy, setBusy] = useState(false);
  const [refused, setRefused] = useState<string | null>(null);
  const text = TEXT[failure];
  if (!text) return null;

  const act = async (path: string) => {
    setBusy(true);
    setRefused(null);
    // on success the host's next agent state takes this away; a refusal is said here and changed nothing
    const told = await sendTold<{ ok?: boolean }>('POST', path);
    if (!told.value?.ok) {
      const why = REFUSED[failure];
      setRefused(told.refused ? (why ? t.w(why) : t('No se pudo: vuelve a intentarlo.', 'That didn’t work: try again.')) : t('BAXY no respondió: vuelve a intentarlo.', 'BAXY didn’t answer: try again.'));
    }
    setBusy(false);
  };
  /* VRAM4B (the leader's decision, 2026-11-12): a profile the person chose that the card's free video memory does not hold is
     never changed by BAXY: the card says it in seconds and offers the profile that fits, as their choice (PUT /settings/tools,
     what Settings → Tools does) and a new start with it. A start the host already began for that change refuses the retry:
     nothing to say then. */
  const fits = failure === 'engine_unavailable' ? fittingProfile(card) : null;
  const startIn = async (profile: string) => {
    setBusy(true);
    setRefused(null);
    const kept = await sendTold<{ profile?: string }>('PUT', '/settings/tools', { profile });
    if (kept.value?.profile !== profile) {
      setRefused(kept.refused ? t('No se pudo cambiar de perfil: vuelve a intentarlo.', 'The profile couldn’t be changed: try again.') : t('BAXY no respondió: vuelve a intentarlo.', 'BAXY didn’t answer: try again.'));
      setBusy(false);
      return;
    }
    const told = await sendTold<{ ok?: boolean }>('POST', '/engine/retry');
    if (!told.value?.ok && !told.refused) setRefused(t('BAXY no respondió: vuelve a intentarlo.', 'BAXY didn’t answer: try again.'));
    setBusy(false);
  };
  /* VRAM5B (REV19 V-1, V-9): a context given in Settings the card does not hold: «Automático» there (what Settings → Model
     → Context does) and a new start, as startIn does with a profile. */
  const automatic = failure === 'engine_unavailable' && backToAutomatic(card);
  const startAutomatic = async () => {
    setBusy(true);
    setRefused(null);
    const kept = await sendTold<{ chosen?: number | null }>('PUT', '/settings/local-context', { context: null });
    if (!kept.value || kept.value.chosen != null) {
      setRefused(kept.refused ? t('No se pudo volver a «Automático»: vuelve a intentarlo.', 'Couldn’t go back to “Automatic”: try again.') : t('BAXY no respondió: vuelve a intentarlo.', 'BAXY didn’t answer: try again.'));
      setBusy(false);
      return;
    }
    const told = await sendTold<{ ok?: boolean }>('POST', '/engine/retry');
    if (!told.value?.ok && !told.refused) setRefused(t('BAXY no respondió: vuelve a intentarlo.', 'BAXY didn’t answer: try again.'));
    setBusy(false);
  };
  const leave = async () => {
    const api = (window as unknown as { pywebview?: { api: Record<string, () => Promise<unknown>> } }).pywebview?.api;
    if (api?.win_exit) await api.win_exit();
  };

  return (
    <div className="bx-card bx-breakdown" role="alertdialog" aria-labelledby="bx-breakdown-ti" aria-describedby="bx-breakdown-tg">
      <div className="hd"><span className="tag">{t('Avería', 'Breakdown')}</span></div>
      <div className="ti" id="bx-breakdown-ti">{t.w(text.title)}</div>
      <div className="tg" id="bx-breakdown-tg">{failure === 'engine_unavailable' && startedOnlyOnce(cause, card) ? (onProcessor ? t.w(ON_PROCESSOR_TEXT) + ' ' : '') : t.w(text.body) + ' '}
        {failure === 'engine_unavailable' && causeText(cause, t) ? t('El modelo no pudo cargarse: ', 'The model could not load: ') + causeText(cause, t, memory, read, card) + '. ' + causeAdvice(cause, t, card, read) : ''}</div>
      {refused ? <div className="tg">{refused}</div> : null}
      <div className="ft">
        <span></span>
        <div className="btns">
          <button className="bx-btn" onClick={() => void leave()} disabled={busy}>{t('Salir', 'Quit')}</button>
          {onOtherModel && OTHER_MODEL.has(failure) ? <button className="bx-btn" onClick={onOtherModel} disabled={busy}>{t('Usar otro modelo', 'Use another model')}</button> : null}
          {fits ? <button className="bx-btn yes" onClick={() => void startIn(fits)} disabled={busy}>{t('Arrancar en ', 'Start in ') + t.w(PROFILE_NAME[fits])}</button> : null}
          {automatic ? <button className="bx-btn yes" onClick={() => void startAutomatic()} disabled={busy}>{t('Volver a «Automático»', 'Back to “Automatic”')}</button> : null}
          {text.act && text.path ? <button className={fits || automatic ? 'bx-btn' : 'bx-btn yes'} onClick={() => void act(text.path!)} disabled={busy}>{t.w(text.act)}</button> : null}
        </div>
      </div>
    </div>
  );
}
