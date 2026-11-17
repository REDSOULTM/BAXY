import { useEffect, useState } from 'react';
import type { BaxyState } from './types';

/* VUL1 (2026-11-09): while the model on this PC reads what it prepares («Arrancando»), the window does not spend the
   graphics card on playing a clip or on redrawing the sky: it shows them still, and they move again once the model is
   ready. The window and the model share one card. Measured on an RX 7600 (INFORME_AMD3.md §1): during the first start
   BAXY's own WebView2 took 49-99 % of the GPU, and with the page hidden the server read the same prompt 2.4 times
   faster (44 → 110 tokens/s). The states that keep still are named here and nowhere else.
   UIX1 (2026-11-15): on a 4-core laptop with a GTX 1650 (INFORME_C1650Y.md §3) the model's output layer runs on the
   CPU, and BAXY's own WebView2 took 1.4 cores while the model wrote: 6.5-7 tokens/s with the window shown, 15.7 with it
   minimized. While the model thinks, speed comes before the animation: the avatar holds its frame, the sky is painted
   once, the frame's ring stops, the state's pulsing marks stand still and the face draws 8 times a second; they move
   again when it answers. Measured in the view (INFORME_UIX1.md): thinking 90 → 8 frames a second.
   At rest the look is kept. The «max» build (`VITE_BX_AHORRO=max`, for the owner to choose after measuring it) also
   keeps still at rest while the window does not have the focus (the person is in another window), until it gets it
   back: 51 → 7 frames a second.
   UIX2 (2026-11-16): «max» is the default. Measured on the same laptop (INFORME_C1650Y.md §17), the window at rest took
   2.3-2.5 of its 4 cores with or without the focus, and 0.5 once still; the person in another window does not see the
   avatar move. Nothing jumps when the focus comes back: the clip goes on from the frame it held, the sky from the frame
   it showed (Cosmos.tsx) and the ring eases back to its speed. `VITE_BX_AHORRO=reposo` builds the 1.5.5 behaviour, to
   measure against it.
   UIX2, calm rest: at rest with the focus the window took the same 2.3-2.5 cores, all day, with nobody looking at it.
   Once nobody has moved the pointer over the window, pressed a key or scrolled for CALM_S seconds, the window goes calm:
   the sky, the face and the ring keep still as above, and the avatar plays its clip to the end, where every clip
   rests on the same master frame (avatarClips.ts), waits there BREATH_S seconds and plays the next one: it still
   breathes, at a fraction of the cost. Any touch, or any state other than rest, wakes it at once. */
export type Saving = 'reposo' | 'max';
export const SAVING: Saving = import.meta.env?.VITE_BX_AHORRO === 'reposo' ? 'reposo' : 'max';

/** whether the avatar's clip and the sky keep still in ``state`` (``focused``: the window has the focus) */
export function stillIn(state: BaxyState, saving: Saving = SAVING, focused = true): boolean {
  if (state === 'booting' || state === 'thinking') return true;
  return saving === 'max' && !focused && (state === 'idle' || state === 'standby');
}

/** UIX2: seconds at rest with nobody touching the window before it goes calm, and seconds the avatar rests on its
    master frame between two clips while calm; `VITE_BX_CALMA_S` / `VITE_BX_RESPIRO_S` at build time only to measure
    other values */
export const CALM_S = Number(import.meta.env?.VITE_BX_CALMA_S) || 20;
export const BREATH_S = Number(import.meta.env?.VITE_BX_RESPIRO_S) || 12;

/** whether the window is calm now: at rest (``state`` idle or standby) and untouched for CALM_S seconds */
export function useCalm(state: BaxyState): boolean {
  const [calm, setCalm] = useState(false);
  const rest = state === 'idle' || state === 'standby';
  useEffect(() => {
    if (!rest) return;
    let id = 0;
    const arm = () => { window.clearTimeout(id); id = window.setTimeout(() => setCalm(true), CALM_S * 1000); };
    const wake = () => { setCalm(false); arm(); };
    const touches = ['pointermove', 'pointerdown', 'keydown', 'wheel', 'focus'] as const;
    for (const e of touches) window.addEventListener(e, wake, { passive: true });
    arm();
    return () => { window.clearTimeout(id); for (const e of touches) window.removeEventListener(e, wake); setCalm(false); };
  }, [rest]);
  return rest && calm;
}

/** whether the window has the focus now (it re-renders only when that changes) */
export function useFocused(): boolean {
  const [on, setOn] = useState(() => typeof document === 'undefined' || document.hasFocus());
  useEffect(() => {
    const got = () => setOn(true), lost = () => setOn(false);
    window.addEventListener('focus', got); window.addEventListener('blur', lost);
    return () => { window.removeEventListener('focus', got); window.removeEventListener('blur', lost); };
  }, []);
  return on;
}
