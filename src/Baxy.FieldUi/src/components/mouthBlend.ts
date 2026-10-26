import { MOUTH_BOX } from './avatarClips';

/* Seamless mouths (owner, 2026-10-21: «se ve un cuadro en la boca que no encaja con el fondo, es una superposición»).
   A mouth cut from another frame of the clip carries that frame's light: when the clip's rim glows or its visor
   brightens, a pasted patch shows as a box. So every frame the mouth is composed into the LIVE frame of the clip:
   - the area replaced is the shape of every mouth the clips draw, with their glow (never the blushes or the rim);
   - where neither the clip's mouth nor the new one is, the pixel is the live one, exactly;
   - under the mouths, the new mouth's frame is corrected by the live light around it (live − cut, low-passed where it
     is known, coarse to fine), so the glow of the rim or of the visor runs through it as in the clip.
   Everything works on the MOUTH_BOX crop (204 × 136 px of the 960 px frame), about 28 000 pixels per frame. */

const { w: W, h: H, x: X0, y: Y0 } = MOUTH_BOX;
const N = W * H;

// the detection zone: a superellipse around the mouth that stays off the blushes and the visor's rim
const DETECT = new Uint8Array(N);
for (let y = 0; y < H; y++) for (let x = 0; x < W; x++) {
  const u = Math.abs((x + X0 - 478) / 101), v = Math.abs((y + Y0 - 590) / 68);
  DETECT[y * W + x] = u ** 5 + v ** 5 <= 1 ? 1 : 0;
}

/** sum of `a` over the (2r+1)² window around each pixel, the window clipped at the edges, and how many pixels it had */
function windowSums(a: Float32Array, r: number, out: Float32Array, count?: Float32Array): void {
  const I = new Float64Array((W + 1) * (H + 1));
  for (let y = 0; y < H; y++) {
    let row = 0;
    for (let x = 0; x < W; x++) { row += a[y * W + x]; I[(y + 1) * (W + 1) + x + 1] = I[y * (W + 1) + x + 1] + row; }
  }
  for (let y = 0; y < H; y++) {
    const y0 = Math.max(0, y - r), y1 = Math.min(H, y + r + 1);
    for (let x = 0; x < W; x++) {
      const x0 = Math.max(0, x - r), x1 = Math.min(W, x + r + 1);
      out[y * W + x] = I[y1 * (W + 1) + x1] - I[y0 * (W + 1) + x1] - I[y1 * (W + 1) + x0] + I[y0 * (W + 1) + x0];
      if (count) count[y * W + x] = (y1 - y0) * (x1 - x0);
    }
  }
}

const tmp = new Float32Array(N), cnt = new Float32Array(N);
/** mean over the window (edges: the window's own pixels) */
function boxMean(a: Float32Array, r: number, out: Float32Array): void {
  windowSums(a, r, tmp, cnt);
  for (let i = 0; i < N; i++) out[i] = tmp[i] / cnt[i];
}
/** a gaussian of about sigma: three box means */
function soften(a: Float32Array, sigma: number, out: Float32Array): void {
  const r = Math.max(1, Math.round(Math.sqrt((12 * sigma * sigma) / 3 + 1) / 2));
  boxMean(a, r, out); boxMean(out, r, out); boxMean(out, r, out);
}
function dilate(m: Uint8Array, r: number): Uint8Array {
  const f = Float32Array.from(m), s = new Float32Array(N), o = new Uint8Array(N);
  windowSums(f, r, s);
  for (let i = 0; i < N; i++) o[i] = s[i] > 0 ? 1 : 0;
  return o;
}
function erode(m: Uint8Array, r: number): Uint8Array {
  const f = Float32Array.from(m), s = new Float32Array(N), c = new Float32Array(N), o = new Uint8Array(N);
  windowSums(f, r, s, c);
  for (let i = 0; i < N; i++) o[i] = s[i] >= c[i] ? 1 : 0;
  return o;
}
/** what the background cannot reach from the crop's edge is inside the mouth */
function fillHoles(m: Uint8Array): Uint8Array {
  const seen = new Uint8Array(N), stack: number[] = [];
  const push = (i: number) => { if (!m[i] && !seen[i]) { seen[i] = 1; stack.push(i); } };
  for (let x = 0; x < W; x++) { push(x); push((H - 1) * W + x); }
  for (let y = 0; y < H; y++) { push(y * W); push(y * W + W - 1); }
  while (stack.length) {
    const i = stack.pop()!, x = i % W;
    if (x > 0) push(i - 1); if (x < W - 1) push(i + 1); if (i >= W) push(i - W); if (i < N - W) push(i + W);
  }
  const o = new Uint8Array(N);
  for (let i = 0; i < N; i++) o[i] = m[i] || !seen[i] ? 1 : 0;
  return o;
}
/** the lit mouth (LEDs, teeth, tongue and what they enclose), grown by `grow` px for its glow */
function mouthMask(rgba: Uint8ClampedArray, grow: number): Uint8Array {
  const m = new Uint8Array(N);
  for (let i = 0; i < N; i++) {
    const r = rgba[i * 4], g = rgba[i * 4 + 1], b = rgba[i * 4 + 2];
    const lum = 0.3 * r + 0.59 * g + 0.11 * b;
    m[i] = DETECT[i] && (lum > 95 || (r - b > 30 && r > 90)) ? 1 : 0;
  }
  return dilate(fillHoles(erode(dilate(m, 3), 3)), grow);
}

export class MouthBlend {
  private readonly cuts: Uint8ClampedArray[];
  private readonly cutMasks: Uint8Array[];
  /** how much of each pixel is replaced (0 outside the mouths' area) */
  readonly zone = new Float32Array(N);
  private readonly inZone = new Uint8Array(N);
  private readonly D = [new Float32Array(N), new Float32Array(N), new Float32Array(N)];
  private readonly corr = [new Float32Array(N), new Float32Array(N), new Float32Array(N)];
  private readonly w = new Float32Array(N);
  private readonly ws = new Float32Array(N);
  // the composition's work arrays, kept between frames (each is written whole before it is read)
  private readonly num = new Float32Array(N);
  private readonly den = new Float32Array(N);
  private readonly area = new Float32Array(N);
  private readonly a = new Float32Array(N);
  private readonly dw = new Float32Array(N);
  private readonly out: ImageData;

  constructor(cuts: Uint8ClampedArray[]) {
    this.cuts = cuts;
    this.cutMasks = cuts.map((c) => mouthMask(c, 6));
    // every mouth the clips draw with its glow, no dents (rows and columns filled between their ends), above the rim
    const u = new Uint8Array(N);
    for (const c of cuts) { const m = mouthMask(c, 11); for (let i = 0; i < N; i++) u[i] |= m[i]; }
    for (let y = 0; y < H; y++) {
      let a = -1, b = -1;
      for (let x = 0; x < W; x++) if (u[y * W + x]) { if (a < 0) a = x; b = x; }
      for (let x = a; a >= 0 && x <= b; x++) u[y * W + x] = 1;
    }
    for (let x = 0; x < W; x++) {
      let a = -1, b = -1;
      for (let y = 0; y < H; y++) if (u[y * W + x]) { if (a < 0) a = y; b = y; }
      for (let y = a; a >= 0 && y <= b; y++) u[y * W + x] = 1;
    }
    for (let y = 0; y < H; y++) if (y + Y0 > 648) for (let x = 0; x < W; x++) u[y * W + x] = 0;
    this.inZone.set(u);
    const f = Float32Array.from(u);
    soften(f, 6, this.zone);
    for (let i = 0; i < N; i++) this.zone[i] = Math.max(0, Math.min(1, this.zone[i] * 1.6 - 0.3));
    this.out = new ImageData(W, H);
  }

  /** the video's hole: the complement of the zone over the whole 960 px frame, as a mask image */
  holeImage(): string {
    const c = document.createElement('canvas'); c.width = MOUTH_BOX.frame; c.height = MOUTH_BOX.frame;
    const g = c.getContext('2d')!;
    g.fillStyle = '#fff'; g.fillRect(0, 0, c.width, c.height);
    const img = g.getImageData(X0, Y0, W, H);
    for (let i = 0; i < N; i++) img.data[i * 4 + 3] = Math.round(255 * (1 - this.zone[i]));
    g.putImageData(img, X0, Y0);
    return c.toDataURL('image/png');
  }

  /** the frame's mouth area with mouth k in it; `live` is the clip's frame cropped to MOUTH_BOX */
  compose(live: Uint8ClampedArray, k: number): ImageData {
    const cut = this.cuts[k], cm = this.cutMasks[k], lm = mouthMask(live, 18);
    const { D, corr, w, ws, num, den, area, a, dw } = this;
    for (let i = 0; i < N; i++) {
      w[i] = this.inZone[i] && !lm[i] && !cm[i] ? 1 : 0;
      for (let c = 0; c < 3; c++) D[c][i] = live[i * 4 + c] - cut[i * 4 + c];
    }
    soften(w, 5, ws);
    // the light under the mouths, coarse to fine: each finer estimate takes over where it has enough support
    let first = true;
    for (const r of [60, 30, 14, 6]) {
      windowSums(w, r, den, area);
      if (!first) { for (let i = 0; i < N; i++) a[i] = Math.max(0, Math.min(1, (den[i] / area[i] - 0.15) / 0.5)); soften(a, r / 2, a); }
      for (let c = 0; c < 3; c++) {
        for (let i = 0; i < N; i++) dw[i] = D[c][i] * w[i];
        windowSums(dw, r, num);
        const o = corr[c];
        for (let i = 0; i < N; i++) {
          const est = num[i] / Math.max(den[i], 1e-3);
          o[i] = first ? est : est * a[i] + o[i] * (1 - a[i]);
        }
      }
      first = false;
    }
    const px = this.out.data;
    for (let i = 0; i < N; i++) {
      for (let c = 0; c < 3; c++) px[i * 4 + c] = cut[i * 4 + c] + D[c][i] * ws[i] + corr[c][i] * (1 - ws[i]);
      // as opaque as the clips are there (during a cut both are half transparent and the backdrop shows through)
      px[i * 4 + 3] = Math.round(this.zone[i] * live[i * 4 + 3]);
    }
    return this.out;
  }
}

/** Which mouth the lip-sync composes and when (AvatarVid), about 30 times a second: a new level of openness shows a
    different mouth of that level each time, and a mouth stays at least 50 ms (a 20 fps mouth). The first one after the
    clip's own mouth showed is composed at once: the hole opens in the video in that same frame, and an empty hole is
    a dark box where the mouth goes. */
export class LipMouth {
  /** the level of openness shown (-1 while the clip keeps its own mouth) */
  level = -1;
  private since = 0;
  private turn = 0;
  private composed = 0;
  private readonly levels: number[];
  private readonly first: number[];

  constructor(levels: number[]) {
    this.levels = levels;
    this.first = levels.map((_, i) => levels.slice(0, i).reduce((a, b) => a + b, 0));
  }

  /** the clip's own mouth shows again */
  off(): void { this.level = -1; }

  /** the mouth (its index in MOUTHS.flat()) to compose at `t` for level `k`, or -1 while the last one composed stays */
  at(k: number, t: number): number {
    const fresh = this.level < 0;
    if (!fresh && t - this.composed < 30) return -1;
    this.composed = t;
    if (k !== this.level && (fresh || t - this.since >= 50)) { this.level = k; this.since = t; this.turn++; }
    return this.first[this.level] + (this.turn % this.levels[this.level]);
  }
}
