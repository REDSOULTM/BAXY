import { expect, test, type Browser } from '@playwright/test';
import { headless, serveView } from './headless';

/* The lip-sync's composition (mouthBlend.ts) in a headless page, with no app, on frames made up for the test. */

let browser: Browser;
let view: Awaited<ReturnType<typeof serveView>>;
test.setTimeout(60_000);
test.beforeAll(async () => { view = await serveView(); browser = await headless(); });
test.afterAll(async () => { await browser?.close(); await view?.close(); });

test('cada composición de la boca depende sólo de su fotograma y de su boca', async () => {
  const page = await browser.newPage();
  await page.goto(view.base + '/e2e/harness/avatar.html?none');
  const r = await page.evaluate(async () => {
    const { MouthBlend } = await import('/src/components/mouthBlend.ts' as string) as typeof import('../src/components/mouthBlend');
    const W = 204, H = 136;
    // a frame: a lit mouth (an ellipse of width `wd`) on a backdrop of light `bg`, opaque
    const frame = (wd: number, bg: number) => {
      const d = new Uint8ClampedArray(W * H * 4);
      for (let y = 0; y < H; y++) for (let x = 0; x < W; x++) {
        const i = (y * W + x) * 4, inM = ((x - 102) / wd) ** 2 + ((y - 68) / 18) ** 2 <= 1;
        d[i] = inM ? 240 : bg + (x % 7); d[i + 1] = inM ? 120 : bg; d[i + 2] = inM ? 140 : bg + (y % 5); d[i + 3] = 255;
      }
      return d;
    };
    const b = new MouthBlend([frame(30, 20), frame(45, 25), frame(60, 30)]);
    const hash = (img: ImageData) => { let h = 0; for (let i = 0; i < img.data.length; i++) h = (h * 31 + img.data[i]) | 0; return h; };
    const a1 = hash(b.compose(frame(40, 60), 0));
    b.compose(frame(55, 10), 2);
    const a2 = hash(b.compose(frame(40, 60), 0));
    return { a1, a2 };
  });
  expect(r.a2, 'la misma boca en el mismo fotograma da lo mismo').toBe(r.a1);
  // what the composition gave for this frame on 2026-10-25, before its work arrays were kept between frames
  expect(r.a1, 'el mismo resultado que antes').toBe(-991962205);
  await page.close();
});
