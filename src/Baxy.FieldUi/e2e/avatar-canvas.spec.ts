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

// records the face's transform (where the head is, its tilt, its squash) and the confetti it throws
const MOTION = () => {
  const w = window as unknown as { bxT: [string, number, string][]; bxConf: number };
  w.bxT = []; w.bxConf = 0;
  const P = CanvasRenderingContext2D.prototype as unknown as Record<string, (...a: number[]) => void>;
  for (const k of ['translate', 'rotate', 'scale']) {
    const f = P[k];
    P[k] = function (this: CanvasRenderingContext2D, ...a: number[]) {
      if (this.canvas.classList.contains('bx-face')) w.bxT.push([k, performance.now(), a.map((x) => x.toFixed(3)).join(',')]);
      return f.apply(this, a);
    };
  }
  const d = Object.getOwnPropertyDescriptor(CanvasRenderingContext2D.prototype, 'strokeStyle')!;
  Object.defineProperty(CanvasRenderingContext2D.prototype, 'strokeStyle', {
    configurable: true, get: d.get,
    set(this: CanvasRenderingContext2D, v: string) { if (this.canvas.classList.contains('bx-face') && ['#FFB3BC', '#F5D69C', '#9DB4F5', '#FF7A9A', '#EEF2FF'].includes(v)) w.bxConf++; d.set!.call(this, v); },
  });
};

test('con «reducir movimiento» la cara no flota, no salta ni tira confeti, y el cielo queda quieto', async () => {
  const page = await browser.newPage({ viewport: { width: 800, height: 600 }, reducedMotion: 'reduce' });
  await page.addInitScript(MOTION);
  await page.goto(view.base + '/e2e/harness/face.html');
  await page.waitForTimeout(1500);
  const t0 = await page.evaluate(() => performance.now());
  await page.waitForTimeout(3000); // the idle behaviours (a hop, a shake, a look) start from the third second
  await page.evaluate(() => window.bxFace({ expr: 'happy' })); // a happy face throws confetti and hops
  await page.waitForTimeout(1500);
  const r = await page.evaluate((from) => {
    const w = window as unknown as { bxT: [string, number, string][]; bxConf: number };
    const of = (k: string) => [...new Set(w.bxT.filter(([n, t]) => n === k && t >= from).map(([, , a]) => a))];
    return { translate: of('translate'), rotate: of('rotate'), scale: of('scale'), conf: w.bxConf };
  }, t0);
  expect(r.translate.length, 'la cabeza no flota ni salta: ' + r.translate.slice(0, 4).join(' · ')).toBe(1);
  expect(r.scale, 'no se aplasta ni rebota').toEqual(['1.000,1.000']);
  expect(r.rotate.length, 'la inclinación sólo cambia con la expresión: ' + r.rotate.slice(0, 4).join(' · ')).toBeLessThanOrEqual(2);
  expect(r.conf, 'sin confeti').toBe(0);
  const sky = () => page.evaluate(() => {
    const c = document.querySelector<HTMLCanvasElement>('canvas.bx-cosmos')!, d = c.getContext('2d')!.getImageData(0, 0, c.width, c.height).data;
    let h = 0;
    for (let i = 0; i < d.length; i++) h = (h * 31 + d[i]) | 0;
    return h;
  });
  const a = await sky();
  await page.waitForTimeout(1200);
  expect(await sky(), 'el cielo no gira, no titila ni cruza cometas').toBe(a);
  await page.close();
});

test('con «reducir movimiento» la cara sigue diciendo qué hace BAXY', async () => {
  // the state shows still: listening keeps its rings, speaking moves the mouth with the voice
  const page = await browser.newPage({ viewport: { width: 800, height: 600 }, reducedMotion: 'reduce' });
  await page.goto(view.base + '/e2e/harness/face.html');
  await page.waitForTimeout(1200);
  const mouth = () => page.evaluate(() => {
    const c = document.querySelector<HTMLCanvasElement>('canvas.bx-face')!, g = c.getContext('2d')!;
    const d = g.getImageData(Math.round(c.width * 0.35), Math.round(c.height * 0.45), Math.round(c.width * 0.3), Math.round(c.height * 0.25)).data;
    let h = 0;
    for (let i = 0; i < d.length; i += 4) h = (h * 31 + d[i] + d[i + 1] + d[i + 2]) | 0;
    return h;
  });
  await page.evaluate(() => window.bxFace({ state: 'speaking', talking: true }));
  const seen = new Set<number>();
  for (let i = 0; i < 8; i++) { seen.add(await mouth()); await page.waitForTimeout(120); }
  expect(seen.size, 'al hablar la boca se mueve').toBeGreaterThan(2);
  await page.close();
});
