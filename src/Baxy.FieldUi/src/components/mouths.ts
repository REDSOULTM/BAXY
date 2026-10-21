import { MOUTHS, MOUTH_BOX } from './avatarClips';

/* The lip-sync mouths, cut from the speaking clips by the view's own video decoder (a frame decoded elsewhere has other
   colours: the clips declare no colour space, and ffmpeg's guess left a darker box around the mouth). One row of
   mouths in MOUTHS' order, each with a soft edge that is the exact complement of the hole v4.css opens in the video. */

const once = (v: HTMLVideoElement, ev: string, ms: number) => new Promise<boolean>((resolve) => {
  const t = window.setTimeout(() => { v.removeEventListener(ev, on); resolve(false); }, ms);
  const on = () => { window.clearTimeout(t); resolve(true); };
  v.addEventListener(ev, on, { once: true });
});

// one soft edge per mouth, the whole row at once: destination-in clears whatever the mask does not cover, so a mask
// drawn mouth by mouth would erase the others
function feather(count: number): HTMLCanvasElement {
  const { w, h, featherX, featherY } = MOUTH_BOX;
  const ramp = (i: number, n: number, f: number) => Math.max(0, Math.min(1, Math.min(i + 0.5, n - i - 0.5) / f));
  const c = document.createElement('canvas'); c.width = w * count; c.height = h;
  const g = c.getContext('2d')!, img = g.createImageData(w * count, h);
  for (let y = 0; y < h; y++) for (let x = 0; x < w * count; x++) img.data[(y * w * count + x) * 4 + 3] = Math.round(255 * ramp(y, h, featherY) * ramp(x % w, w, featherX));
  g.putImageData(img, 0, 0);
  return c;
}

/** Resolves with the sheet, or null when a clip could not be read (the clip's own mouth stays). */
export async function cutMouths(isDead: () => boolean): Promise<HTMLCanvasElement | null> {
  const { x, y, w, h, fps } = MOUTH_BOX, all = MOUTHS.flat();
  const sheet = document.createElement('canvas'); sheet.width = w * all.length; sheet.height = h;
  const g = sheet.getContext('2d')!;
  const clips = [...new Set(all.map(([name]) => name))];
  for (const name of clips) {
    const v = document.createElement('video');
    v.muted = true; v.preload = 'auto'; v.src = 'clips/' + name + '.mp4';
    try {
      if (v.readyState < 2 && !(await once(v, 'loadeddata', 10_000))) return null;
      for (let k = 0; k < all.length; k++) {
        if (all[k][0] !== name) continue;
        if (isDead()) return null;
        v.currentTime = (all[k][1] + 0.5) / fps;
        if (!(await once(v, 'seeked', 4000))) return null;
        await new Promise((r) => requestAnimationFrame(r));
        g.drawImage(v, x, y, w, h, k * w, 0, w, h);
      }
    } finally {
      v.removeAttribute('src'); v.load();
    }
  }
  g.globalCompositeOperation = 'destination-in';
  g.drawImage(feather(all.length), 0, 0);
  g.globalCompositeOperation = 'source-over';
  return sheet;
}
