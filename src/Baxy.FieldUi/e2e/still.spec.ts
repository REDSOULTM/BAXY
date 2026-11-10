import { chromium, expect, test, type Browser, type Page } from '@playwright/test';
import { join } from 'node:path';
import { ROOT, serveView } from './headless';
import { openView, stopHost, type Host } from './host';
import { stillIn } from '../src/still';

/* VUL1: while the model reads what it prepares («Arrancando») the window keeps still: the avatar's clip does not play
   and the sky is not painted again, so the graphics card is the model's. They move again once it is ready. */

test('sólo se queda quieta mientras el modelo se prepara', () => {
  expect(stillIn('booting')).toBe(true);
  for (const s of ['standby', 'idle', 'listening', 'thinking', 'speaking', 'error', 'confirm'] as const) expect(stillIn(s), s).toBe(false);
});

// ---- the avatar's clip, on its own (e2e/harness/avatar.html) ----
// in Edge, headless, as the stand-in host's view (host.ts): the clips are H.264, which Playwright's own headless shell
// does not decode (there a clip never has a frame)
let browser: Browser;
let view: Awaited<ReturnType<typeof serveView>>;
test.beforeAll(async () => {
  view = await serveView();
  browser = process.env.BAXY_TEST_BROWSER ? await chromium.launch({ executablePath: process.env.BAXY_TEST_BROWSER }) : await chromium.launch({ channel: 'msedge' });
});
test.afterAll(async () => { await browser?.close(); await view?.close(); await stopHost(); });

async function avatar(): Promise<Page> {
  const page = await browser.newPage();
  await page.route('**/clips/*.mp4', (r) => r.fulfill({ path: join(ROOT, 'public', 'clips', r.request().url().split('/').pop()!), contentType: 'video/mp4' }));
  await page.goto(view.base + '/e2e/harness/avatar.html');
  await page.waitForFunction(() => { const v = document.querySelector<HTMLVideoElement>('.bx-avid video.on'); return !!v && v.readyState >= 2; });
  return page;
}
const clip = (page: Page) => page.evaluate(() => {
  const v = document.querySelector<HTMLVideoElement>('.bx-avid video.on')!;
  return { g: v.dataset.g, paused: v.paused, t: v.currentTime, frame: v.readyState >= 2 };
});
/** how far the clip on screen plays in ``ms`` */
async function played(page: Page, ms: number): Promise<number> {
  const a = await clip(page);
  await page.waitForTimeout(ms);
  return (await clip(page)).t - a.t;
}

test('arrancando, el clip del avatar no se reproduce: queda en su fotograma, y sigue al estar listo', async () => {
  test.setTimeout(60_000);
  const page = await avatar();
  expect(await played(page, 1000), 'en reposo el clip corre').toBeGreaterThan(0.5);
  await page.evaluate(() => window.bxSet('booting'));
  await page.waitForTimeout(300);
  const held = await clip(page);
  expect(held).toMatchObject({ g: 'reposo', paused: true, frame: true });
  expect(await played(page, 1500), 'arrancando el clip no avanza').toBe(0);
  await page.evaluate(() => window.bxSet('idle'));
  await page.waitForTimeout(300);
  expect((await clip(page)).paused).toBe(false);
  expect(await played(page, 1000), 'listo, el clip vuelve a correr').toBeGreaterThan(0.5);
  await page.close();
});

test('un avatar que nace arrancando muestra su fotograma sin reproducir nada, y corre al estar listo', async () => {
  test.setTimeout(60_000);
  const page = await browser.newPage();
  await page.route('**/clips/*.mp4', (r) => r.fulfill({ path: join(ROOT, 'public', 'clips', r.request().url().split('/').pop()!), contentType: 'video/mp4' }));
  // the state the harness mounts with: booting, as BAXY's window opens
  await page.goto(view.base + '/e2e/harness/avatar.html?first=booting');
  await page.waitForFunction(() => { const v = document.querySelector<HTMLVideoElement>('.bx-avid video.on'); return !!v && v.readyState >= 2; });
  expect(await clip(page)).toMatchObject({ g: 'reposo', paused: true, t: 0, frame: true });
  // the player says it has a frame (it looks every 0.3 s): the parent need not draw the whole face meanwhile
  await expect.poll(() => page.evaluate(() => window.bxReady)).toBe(true);
  expect(await played(page, 1500)).toBe(0);
  // no clip plays meanwhile, neither the ones kept warm
  expect(await page.evaluate(() => [...document.querySelectorAll('video')].filter((v) => !v.paused).length)).toBe(0);
  await page.evaluate(() => window.bxSet('idle'));
  expect(await played(page, 1200)).toBeGreaterThan(0.5);
  await page.close();
});

test('un estado que no se queda quieto cambia de clip y lo reproduce como siempre', async () => {
  test.setTimeout(60_000);
  const page = await avatar();
  for (const [s, g] of [['thinking', 'pensando'], ['speaking', 'hablando'], ['listening', 'escuchando']] as const) {
    await page.evaluate((st) => window.bxSet(st), s);
    await page.waitForFunction((want) => document.querySelector<HTMLVideoElement>('.bx-avid video.on')?.dataset.g === want, g, { timeout: 5000 });
    expect(await played(page, 1000), s).toBeGreaterThan(0.5);
  }
  await page.close();
});

test('medición: con bx-still=thinking guardado en la vista, «Pensando» también se queda quieta', async () => {
  // not the product's behaviour: the switch a measurement on a card flips before deciding it (still.ts)
  test.setTimeout(60_000);
  const page = await browser.newPage();
  await page.route('**/clips/*.mp4', (r) => r.fulfill({ path: join(ROOT, 'public', 'clips', r.request().url().split('/').pop()!), contentType: 'video/mp4' }));
  await page.addInitScript(() => { try { localStorage.setItem('bx-still', 'thinking'); } catch { /* none */ } });
  await page.goto(view.base + '/e2e/harness/avatar.html');
  await page.waitForFunction(() => { const v = document.querySelector<HTMLVideoElement>('.bx-avid video.on'); return !!v && v.readyState >= 2; });
  expect(await played(page, 1000), 'en reposo corre').toBeGreaterThan(0.5);
  await page.evaluate(() => window.bxSet('thinking'));
  await page.waitForFunction(() => { const v = document.querySelector<HTMLVideoElement>('.bx-avid video.on'); return v?.dataset.g === 'pensando' && v.readyState >= 2; }, undefined, { timeout: 5000 });
  // the thinking clip comes in on its first frame, the master frame, and does not play
  expect(await clip(page)).toMatchObject({ g: 'pensando', paused: true, t: 0, frame: true });
  expect(await played(page, 1500)).toBe(0);
  await page.evaluate(() => window.bxSet('speaking'));
  await page.waitForFunction(() => document.querySelector<HTMLVideoElement>('.bx-avid video.on')?.dataset.g === 'hablando', undefined, { timeout: 5000 });
  expect(await played(page, 1000), 'al hablar corre').toBeGreaterThan(0.5);
  await page.close();
});

// ---- the sky, in the whole view against the stand-in host ----
let h: Host;
test.afterEach(async () => { await h?.close(); });

/** how many times the sky's canvas is painted in ``ms`` (each paint clears it first) */
async function skyPaints(page: Page, ms: number): Promise<number> {
  const count = () => page.evaluate(() => (window as unknown as { bxSky: number }).bxSky);
  const a = await count();
  await page.waitForTimeout(ms);
  return (await count()) - a;
}

test('arrancando, el cielo se pinta una vez y no más; listo, vuelve a moverse', async () => {
  h = await openView();
  await h.page.evaluate(() => {
    const w = window as unknown as { bxSky: number };
    w.bxSky = 0;
    const clear = CanvasRenderingContext2D.prototype.clearRect;
    CanvasRenderingContext2D.prototype.clearRect = function (...a) { if (this.canvas.classList.contains('bx-cosmos')) w.bxSky++; return clear.apply(this, a); };
  });
  expect(await skyPaints(h.page, 1000), 'listo: unas 30 veces por segundo').toBeGreaterThan(10);
  h.emit({ type: 'agent', built: true, ready: false, powered: true });
  h.emit({ type: 'boot', stt: true, wake: true, tts: true, model: false, startedAt: Date.now(), readyAt: null });
  await expect(h.page.locator('.bx-statel')).toContainText('Arrancando');
  await h.page.waitForTimeout(400);
  expect(await skyPaints(h.page, 1500), 'arrancando: quieto').toBe(0);
  // a change of what it shows is painted, once: the window's size
  await h.page.setViewportSize({ width: 1200, height: 800 });
  await h.page.waitForTimeout(400);
  expect(await skyPaints(h.page, 1000)).toBe(0);
  expect(await h.page.evaluate(() => { const c = document.querySelector<HTMLCanvasElement>('.bx-cosmos')!; const d = c.getContext('2d')!.getImageData(0, 0, c.width, c.height).data; let n = 0; for (let i = 3; i < d.length; i += 4) if (d[i]) n++; return n; }),
    'el cielo quieto está pintado, no vacío').toBeGreaterThan(100);
  h.emit({ type: 'boot', stt: true, wake: true, tts: true, model: true, startedAt: 1, readyAt: 2 });
  h.emit({ type: 'agent', built: true, ready: true, powered: true });
  await expect(h.page.locator('.bx-statel')).toContainText('Listo');
  expect(await skyPaints(h.page, 1000), 'listo otra vez').toBeGreaterThan(10);
});
