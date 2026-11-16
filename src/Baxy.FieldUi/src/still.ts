import type { BaxyState } from './types';

/* VUL1 (2026-11-09): while the model on this PC reads what it prepares («Arrancando»), the window does not spend the
   graphics card on playing a clip or on redrawing the sky: it shows them still, and they move again once the model is
   ready. The window and the model share one card. Measured on an RX 7600 (INFORME_AMD3.md §1): during the first start
   BAXY's own WebView2 took 49-99 % of the GPU, and with the page hidden the server read the same prompt 2.4 times
   faster (44 → 110 tokens/s). The states that keep still are named here and nowhere else.
   UIX1 (2026-11-15): «Pensando» keeps still too. On a 4-core laptop with a GTX 1650 (INFORME_C1650Y.md §3) the model's
   output layer runs on the CPU, and BAXY's own WebView2 took 1.4 cores while the model wrote: 6.5-7 tokens/s with the
   window shown, 15.7 with it minimized. While it thinks the avatar holds its frame (the thinking clips do not play) and
   the sky is painted once; they move again when it answers. */
export const stillIn = (state: BaxyState): boolean => state === 'booting' || state === 'thinking';
