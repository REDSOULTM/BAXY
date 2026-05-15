/* deterministic linear-congruential rng — same constants as the prototype,
   so starfield and cluster positions match pixel-for-pixel across reloads.
   never use Math.random() in the render path. */

export function seededRng(seed: number): () => number {
  let s = seed >>> 0;
  return () => {
    s = (s * 1664525 + 1013904223) >>> 0;
    return s / 0xffffffff;
  };
}
