/* UIX2 (2026-11-16): a drawing loop asks the browser for a frame only while it has something to draw. A loop with
   nothing to draw (the window keeps still, still.ts; the ring has stopped; no voice to put on the avatar's mouth) naps:
   it looks again after the milliseconds its tick returned, with a timer, or at once when it is woken because what it
   shows changed. Asking for every frame to draw nothing still runs the page's frame, its scripts and the compositor's
   request for it 60 times a second: with the window still, the view's four loops doing that were most of what it cost
   (INFORME_UIX2.md: 0.20 → 0.04 cores on an Intel GPU, 0.48 → 0.20 with Edge composing in software). */

/** runs ``tick`` on animation frames; a tick that returns a number of milliseconds naps that long before the next */
export function frameLoop(tick: (now: number) => number | void): { wake: () => void; stop: () => void } {
  let raf = 0, nap = 0, dead = false;
  const ask = () => { nap = 0; if (!dead) raf = requestAnimationFrame(run); };
  const run = (now: number) => {
    raf = 0;
    const rest = tick(now);
    if (dead || raf || nap) return; // the tick woke the loop itself
    if (typeof rest === 'number') nap = window.setTimeout(ask, Math.max(0, rest));
    else raf = requestAnimationFrame(run);
  };
  raf = requestAnimationFrame(run);
  return {
    wake: () => { if (nap) { window.clearTimeout(nap); ask(); } },
    stop: () => { dead = true; cancelAnimationFrame(raf); window.clearTimeout(nap); },
  };
}
