import type { BaxyState } from './types';

/* VUL1 (2026-11-09): while the model on this PC reads what it prepares («Arrancando»), the window does not spend the
   graphics card on playing a clip or on redrawing the sky: it shows them still, and they move again once the model is
   ready. The window and the model share one card. Measured on an RX 7600 (INFORME_AMD3.md §1): during the first start
   BAXY's own WebView2 took 49-99 % of the GPU, and with the page hidden the server read the same prompt 2.4 times
   faster (44 → 110 tokens/s). The states that keep still are named here and nowhere else.
   «Pensando» is not one of them: what it would give the model is not measured, and what it costs is seen (the avatar
   stands on its master frame for the whole turn; the thinking clips never play). Measurement only: `bx-still=thinking`
   in the view's localStorage adds it (as `bx-avatar` picks the avatar, App.tsx), so that a turn can be timed on a card
   both ways with the same build before it is decided. */
const ALSO_THINKING = (() => { try { return localStorage.getItem('bx-still') === 'thinking'; } catch { return false; } })();

export const stillIn = (state: BaxyState): boolean => state === 'booting' || (ALSO_THINKING && state === 'thinking');
