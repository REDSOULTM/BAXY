import { MOUTHS, MOUTH_BOX } from './avatarClips';
import { MouthBlend } from './mouthBlend';

/* The lip-sync mouths, cut from the speaking clips by the view's own video decoder (a frame decoded elsewhere has other
   colours: the clips declare no colour space, and ffmpeg's guess left a darker box around the mouth), in MOUTHS'
   order; mouthBlend.ts composes them into the live frame. */

const once = (v: HTMLVideoElement, ev: string, ms: number) => new Promise<boolean>((resolve) => {
  const t = window.setTimeout(() => { v.removeEventListener(ev, on); resolve(false); }, ms);
  const on = () => { window.clearTimeout(t); resolve(true); };
  v.addEventListener(ev, on, { once: true });
});

// A cut is a real mouth only when the frame was decoded: every pixel opaque and the mouth's LEDs lit. With the GPU
// busy (the vision model loading, 2026-10-21) a frame drawn right after «seeked» could still be empty, and an empty
// mouth opened a dark box where the mouth should be.
function isMouth(c: CanvasRenderingContext2D): boolean {
  const d = c.getImageData(0, 0, MOUTH_BOX.w, MOUTH_BOX.h).data;
  let opaque = 0, lit = 0;
  for (let i = 0; i < d.length; i += 4) { if (d[i + 3] > 250) opaque++; if (d[i] > 150) lit++; }
  const n = d.length / 4;
  return opaque > n * 0.98 && lit >= 60;
}

/** Resolves with the mouths ready to compose, or null when a clip could not be read or a mouth never decoded (the
    clip's own mouth stays: the view never opens the hole without a mouth to put in it). */
export async function cutMouths(isDead: () => boolean): Promise<MouthBlend | null> {
  const { x, y, w, h, fps } = MOUTH_BOX, all = MOUTHS.flat();
  const cuts: Uint8ClampedArray[] = new Array(all.length);
  const clips = [...new Set(all.map(([name]) => name))];
  const cut = document.createElement('canvas'); cut.width = w; cut.height = h;
  const cg = cut.getContext('2d', { willReadFrequently: true })!;
  for (const name of clips) {
    const v = document.createElement('video');
    v.muted = true; v.preload = 'auto'; v.src = 'clips/' + name + '.mp4';
    try {
      if (v.readyState < 2 && !(await once(v, 'loadeddata', 10_000))) return null;
      for (let k = 0; k < all.length; k++) {
        if (all[k][0] !== name) continue;
        if (isDead()) return null;
        let ok = false;
        for (let attempt = 0; attempt < 12 && !ok; attempt++) {
          if (isDead()) return null;
          if (attempt % 4 === 0) {
            v.currentTime = (all[k][1] + 0.5) / fps + (attempt ? 0.0001 * attempt : 0);
            if (!(await once(v, 'seeked', 4000))) continue;
          }
          await new Promise((r) => requestAnimationFrame(r));
          await new Promise((r) => window.setTimeout(r, attempt ? 60 : 0));
          cg.clearRect(0, 0, w, h);
          cg.drawImage(v, x, y, w, h, 0, 0, w, h);
          ok = isMouth(cg);
        }
        if (!ok) return null;
        cuts[k] = new Uint8ClampedArray(cg.getImageData(0, 0, w, h).data);
      }
    } finally {
      v.removeAttribute('src'); v.load();
    }
  }
  return new MouthBlend(cuts);
}
