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
