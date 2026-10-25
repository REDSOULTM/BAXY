import { expect, test, type Browser } from '@playwright/test';
import { headless, serveView } from './headless';

/* The drawn face and the starfield on their own (e2e/harness/face.html, served by Vite) in a headless page, with no
   app. */

let browser: Browser;
let view: Awaited<ReturnType<typeof serveView>>;
test.setTimeout(60_000);
test.beforeAll(async () => { view = await serveView(); browser = await headless(); });
test.afterAll(async () => { await browser?.close(); await view?.close(); });

test('al pasar la ventana a una pantalla de otra escala, la cara y el cielo se redibujan a la nueva densidad', async () => {
  // a window dragged to a 150 % screen keeps its size in CSS pixels (no resize): only the density changes
  const page = await browser.newPage({ viewport: { width: 800, height: 600 }, deviceScaleFactor: 1 });
  const errors: string[] = [];
  page.on('pageerror', (e) => errors.push(String(e)));
  await page.goto(view.base + '/e2e/harness/face.html');
  const density = () => page.evaluate(() => ['canvas.bx-face', 'canvas.bx-cosmos'].map((q) => {
    const c = document.querySelector<HTMLCanvasElement>(q)!;
    return Math.round((c.width / c.clientWidth) * 100) / 100;
  }));
  await page.waitForFunction(() => document.querySelector<HTMLCanvasElement>('canvas.bx-face')!.width === 600);
  expect(await density(), 'a 100 %').toEqual([1, 1]);
  const cdp = await page.context().newCDPSession(page);
  await cdp.send('Emulation.setDeviceMetricsOverride', { width: 800, height: 600, deviceScaleFactor: 1.5, mobile: false });
  await page.waitForTimeout(600);
  expect(await page.evaluate(() => devicePixelRatio)).toBe(1.5);
  expect(await density(), 'a 150 % (la densidad del lienzo llega hasta 1,25)').toEqual([1.25, 1.25]);
  await cdp.send('Emulation.setDeviceMetricsOverride', { width: 800, height: 600, deviceScaleFactor: 1, mobile: false });
  await page.waitForTimeout(600);
  expect(await density(), 'de vuelta a 100 %').toEqual([1, 1]);
  expect(errors).toEqual([]);
  await page.close();
});

// counts the face's drawing calls that got a coordinate that is not a number (a NaN draws nothing: the shape is gone)
const SPY = () => {
  const w = window as unknown as { bxBad: number };
  w.bxBad = 0;
  const P = CanvasRenderingContext2D.prototype as unknown as Record<string, (...a: number[]) => void>;
  for (const k of ['moveTo', 'lineTo', 'arc', 'ellipse', 'translate', 'rotate', 'scale']) {
    const f = P[k];
    P[k] = function (this: CanvasRenderingContext2D, ...a: number[]) {
      if (this.canvas.classList.contains('bx-face') && a.some((x) => typeof x === 'number' && !Number.isFinite(x))) w.bxBad++;
      return f.apply(this, a);
    };
  }
};

test('un movimiento del puntero con la cara a 0×0 no la deja sin ojos ni boca para siempre', async () => {
  // the pointer's place over the canvas is (x − left) / width: with the canvas measuring 0 × 0 that is 0 / 0
  const page = await browser.newPage({ viewport: { width: 800, height: 600 } });
  await page.addInitScript(SPY);
  await page.goto(view.base + '/e2e/harness/face.html');
  await page.evaluate(() => window.bxFace({ state: 'listening', expr: 'listen' }));
  await page.waitForTimeout(800);
  await page.evaluate(() => {
    // a canvas out of the layout for a moment (collapsed, not displayed) measures 0 × 0 at the page's origin
    const c = document.querySelector<HTMLCanvasElement>('canvas.bx-face')!;
    c.style.display = 'none';
    window.dispatchEvent(new PointerEvent('pointermove', { clientX: 0, clientY: 0 }));
    c.style.display = '';
  });
  await page.waitForTimeout(400);
  await page.evaluate(() => { (window as unknown as { bxBad: number }).bxBad = 0; });
  await page.mouse.move(300, 250);
  await page.waitForTimeout(800);
  expect(await page.evaluate(() => (window as unknown as { bxBad: number }).bxBad), 'trazos con coordenadas que no son números').toBe(0);
  await page.close();
});
