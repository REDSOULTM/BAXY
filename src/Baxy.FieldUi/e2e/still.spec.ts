import { chromium, expect, test, type Browser, type Page } from '@playwright/test';
import { join } from 'node:path';
import { ROOT, serveView } from './headless';
import { openView, stopHost, type Host } from './host';
import { BREATH_S, CALM_S, SAVING, stillIn } from '../src/still';

/* VUL1: while the model reads what it prepares («Arrancando») the window keeps still: the avatar's clip does not play
   and the sky is not painted again, so the graphics card is the model's. They move again once it is ready. */

test('sólo se queda quieta mientras el modelo se prepara o piensa', () => {
  // UIX1: while the model writes, the window leaves the CPU to it
  for (const f of [true, false]) {
    expect(stillIn('booting', 'reposo', f)).toBe(true);
    expect(stillIn('thinking', 'reposo', f)).toBe(true);
    for (const s of ['standby', 'idle', 'listening', 'speaking', 'error', 'confirm'] as const) expect(stillIn(s, 'reposo', f), s).toBe(false);
  }
});

test('la compilación «max» también se queda quieta en reposo sin el foco', () => {
  // UIX1: at rest, while the person is in another window
  for (const f of [true, false]) {
    expect(stillIn('booting', 'max', f)).toBe(true);
    expect(stillIn('thinking', 'max', f)).toBe(true);
    for (const s of ['listening', 'speaking', 'error', 'confirm'] as const) expect(stillIn(s, 'max', f), s).toBe(false);
  }
  for (const s of ['idle', 'standby'] as const) {
    expect(stillIn(s, 'max', true), s + ' con foco').toBe(false);
    expect(stillIn(s, 'max', false), s + ' sin foco').toBe(true);
  }
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
  for (const [s, g] of [['speaking', 'hablando'], ['listening', 'escuchando']] as const) {
    await page.evaluate((st) => window.bxSet(st), s);
    await page.waitForFunction((want) => document.querySelector<HTMLVideoElement>('.bx-avid video.on')?.dataset.g === want, g, { timeout: 5000 });
    expect(await played(page, 1000), s).toBeGreaterThan(0.5);
  }
  await page.close();
});

test('pensando, el clip del avatar se queda en su fotograma y vuelve a correr al hablar', async () => {
  // UIX1: the window leaves the CPU to the model while it writes (still.ts)
  test.setTimeout(60_000);
  const page = await avatar();
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

test('pensando, ni el aro ni las marcas de estado se mueven; listo, vuelven a moverse', async () => {
  // UIX1: the CSS marks alone repainted the window about 60 times a second while the model wrote, the ring 30
  test.setTimeout(60_000);
  h = await openView();
  const ring = () => h.page.evaluate(() => document.querySelector<HTMLElement>('.bd-spin')!.style.transform);
  const running = () => h.page.evaluate(() => document.getAnimations().filter((a) => a.playState === 'running').length);
  const turns = async () => { const a = await ring(); await h.page.waitForTimeout(500); return (await ring()) !== a; };
  expect(await turns(), 'en reposo el aro gira').toBe(true);
  h.emit({ type: 'state', value: 'thinking' });
  h.emit({ type: 'step', phase: 'start', turn: 't1', fam: 'web', label: 'Buscando' });
  await h.page.waitForSelector('.bx-step');
  await h.page.waitForTimeout(2500); // the ring slows down to a stop
  expect(await turns(), 'pensando el aro está quieto').toBe(false);
  expect(await running(), 'pensando ninguna animación corre').toBe(0);
  h.emit({ type: 'state', value: 'idle' });
  await h.page.waitForTimeout(1000);
  expect(await turns(), 'listo, el aro gira otra vez').toBe(true);
});

test('por defecto, en reposo sin el foco el cielo y la cara se quedan en el cuadro que mostraban; con el foco siguen', async () => {
  // UIX2: on the 4-core laptop the window at rest took 2.3-2.5 cores with or without the focus, 0.5 once still
  expect(stillIn('idle', SAVING, false), 'la compilación de siempre').toBe(true);
  expect(stillIn('idle', SAVING, true)).toBe(false);
  test.setTimeout(60_000);
  h = await openView();
  await h.page.evaluate(() => {
    const w = window as unknown as { bxSky: number; bxFace: number };
    w.bxSky = 0; w.bxFace = 0;
    const clear = CanvasRenderingContext2D.prototype.clearRect;
    CanvasRenderingContext2D.prototype.clearRect = function (...a) {
      if (this.canvas.classList.contains('bx-cosmos')) w.bxSky++;
      if (this.canvas.classList.contains('bx-face')) w.bxFace++;
      return clear.apply(this, a);
    };
  });
  const faces = async (ms: number) => { const f = () => h.page.evaluate(() => (window as unknown as { bxFace: number }).bxFace); const a = await f(); await h.page.waitForTimeout(ms); return (await f()) - a; };
  await h.page.waitForTimeout(2500); // comets on their way
  expect(await skyPaints(h.page, 1000), 'con el foco el cielo se mueve').toBeGreaterThan(10);
  const sky = () => { const c = document.querySelector<HTMLCanvasElement>('.bx-cosmos')!; const d = c.getContext('2d')!.getImageData(0, 0, c.width, c.height).data, o: number[] = []; for (let i = 0; i < d.length; i += 4 * 7) o.push(d[i], d[i + 1], d[i + 2], d[i + 3]); return o; };
  // the frame on screen the instant the focus goes, and the one the still sky keeps
  const before = await h.page.evaluate((f) => { const d = (0, eval)(f)(); window.dispatchEvent(new Event('blur')); return d; }, '(' + sky.toString() + ')');
  await h.page.waitForTimeout(400);
  expect(await skyPaints(h.page, 1500), 'sin el foco el cielo no se pinta').toBe(0);
  expect(await faces(1500), 'sin el foco la cara no se pinta').toBe(0);
  const held = await h.page.evaluate((f) => (0, eval)(f)(), '(' + sky.toString() + ')');
  let off = 0;
  for (let i = 0; i < held.length; i++) off += Math.abs(held[i] - before[i]);
  // at most the one frame the sky may still paint before the window learns it lost the focus (≈ 0.004); repainted in
  // its still look (stars at a set brightness, no comets) it is ≈ 0.018
  expect(off / held.length, 'el cielo quieto es el cuadro que se veía (sin salto)').toBeLessThan(0.009);
  await h.page.evaluate(() => window.dispatchEvent(new Event('focus')));
  await h.page.waitForTimeout(300);
  expect(await skyPaints(h.page, 1000), 'con el foco otra vez se mueve').toBeGreaterThan(10);
  expect(await faces(1500), 'y la cara').toBeGreaterThan(5);
});

test('quieta, la ventana no pide un cuadro tras otro para no pintar nada; al moverse, sí', async () => {
  // UIX2: the view's drawing loops asking for every frame to draw nothing were most of what a still window cost
  test.setTimeout(60_000);
  h = await openView();
  await h.page.evaluate(() => {
    const w = window as unknown as { bxRaf: number };
    w.bxRaf = 0;
    const raf = window.requestAnimationFrame.bind(window);
    window.requestAnimationFrame = (cb) => { w.bxRaf++; return raf(cb); };
  });
  const asks = async (ms: number) => { const f = () => h.page.evaluate(() => (window as unknown as { bxRaf: number }).bxRaf); const a = await f(); await h.page.waitForTimeout(ms); return ((await f()) - a) / (ms / 1000); };
  // the loops already running were started before the count: they show up once they nap and look again
  h.emit({ type: 'state', value: 'thinking' });
  await h.page.waitForTimeout(3000); // the ring slows down to a stop
  expect(await asks(2000), 'pensando: la cara 8 veces por segundo, lo demás duerme').toBeLessThan(30);
  h.emit({ type: 'state', value: 'idle' });
  await h.page.evaluate(() => window.dispatchEvent(new Event('blur')));
  await h.page.waitForTimeout(3000);
  expect(await asks(2000), 'en reposo sin el foco, todo duerme').toBeLessThan(20);
  await h.page.evaluate(() => window.dispatchEvent(new Event('focus')));
  await h.page.waitForTimeout(500);
  expect(await asks(1000), 'con el foco, cada cuadro').toBeGreaterThan(40);
});

test('el avatar en vídeo no pide cuadros para la boca mientras no habla', async () => {
  // UIX2: the mouth's loop composes only over a speaking clip with the voice on (frameLoop.ts)
  test.setTimeout(60_000);
  const page = await avatar();
  await page.evaluate(() => {
    const w = window as unknown as { bxRaf: number };
    w.bxRaf = 0;
    const raf = window.requestAnimationFrame.bind(window);
    window.requestAnimationFrame = (cb) => { w.bxRaf++; return raf(cb); };
  });
  await page.waitForTimeout(4000); // the mouths are cut from the speaking clips once, after the start (mouths.ts)
  const a = await page.evaluate(() => (window as unknown as { bxRaf: number }).bxRaf);
  await page.waitForTimeout(2000);
  const n = (await page.evaluate(() => (window as unknown as { bxRaf: number }).bxRaf)) - a;
  expect(n / 2, 'en reposo, unas 10 miradas por segundo').toBeLessThan(20);
  await page.close();
});

test('en reposo y en calma, el clip llega a su fotograma maestro, descansa allí y luego sigue con otro', async () => {
  // UIX2: calm (still.ts useCalm): the avatar breathes at a fraction of the cost
  test.setTimeout(90_000);
  const page = await avatar();
  await page.evaluate(() => window.bxSet('idle', undefined, true));
  // the clip on screen plays on to its end (every clip is about 5 s) and rests there, on its last frame
  await page.waitForFunction(() => document.querySelector<HTMLVideoElement>('.bx-avid video.on')?.ended === true, undefined, { timeout: 8000 });
  const end = await clip(page);
  expect(end.frame).toBe(true);
  expect(await played(page, 2000), 'en calma descansa en su fotograma').toBe(0);
  expect(await page.evaluate(() => [...document.querySelectorAll('video')].filter((v) => !v.paused).length), 'ningún clip corre').toBe(0);
  // after its rest (BREATH_S) the next clip plays
  await page.waitForFunction(() => { const v = document.querySelector<HTMLVideoElement>('.bx-avid video.on'); return !!v && !v.paused && !v.ended; }, undefined, { timeout: (BREATH_S + 4) * 1000 });
  expect(await played(page, 1000), 'y respira otra vez').toBeGreaterThan(0.5);
  // out of calm, a clip resting on its end goes on at once
  await page.waitForFunction(() => document.querySelector<HTMLVideoElement>('.bx-avid video.on')?.ended === true, undefined, { timeout: 8000 });
  await page.evaluate(() => window.bxSet('idle', undefined, false));
  await page.waitForTimeout(400);
  expect(await played(page, 1000), 'sin calma sigue enseguida').toBeGreaterThan(0.5);
  await page.close();
});

test('en reposo, sin que nadie toque la ventana unos segundos, el cielo, la cara y el aro se quedan quietos; al tocarla, vuelven', async () => {
  // UIX2: at rest with the focus the window took 2.3-2.5 of a laptop's 4 cores all day
  test.setTimeout(30_000 + CALM_S * 1000);
  h = await openView();
  await h.page.evaluate(() => {
    const w = window as unknown as { bxSky: number; bxFace: number };
    w.bxSky = 0; w.bxFace = 0;
    const clear = CanvasRenderingContext2D.prototype.clearRect;
    CanvasRenderingContext2D.prototype.clearRect = function (...a) {
      if (this.canvas.classList.contains('bx-cosmos')) w.bxSky++;
      if (this.canvas.classList.contains('bx-face')) w.bxFace++;
      return clear.apply(this, a);
    };
  });
  const faces = async (ms: number) => { const f = () => h.page.evaluate(() => (window as unknown as { bxFace: number }).bxFace); const a = await f(); await h.page.waitForTimeout(ms); return (await f()) - a; };
  const ring = () => h.page.evaluate(() => document.querySelector<HTMLElement>('.bd-spin')!.style.transform);
  const turns = async () => { const a = await ring(); await h.page.waitForTimeout(500); return (await ring()) !== a; };
  expect(await skyPaints(h.page, 1000), 'recién tocada, el cielo se mueve').toBeGreaterThan(10);
  await h.page.waitForTimeout(CALM_S * 1000 + 2500); // calm, and the ring slows down to a stop
  expect(await skyPaints(h.page, 1500), 'en calma el cielo no se pinta').toBe(0);
  expect(await faces(1500), 'ni la cara').toBe(0);
  expect(await turns(), 'ni gira el aro').toBe(false);
  await h.page.mouse.move(600, 400);
  await h.page.mouse.move(640, 420);
  await h.page.waitForTimeout(300);
  expect(await skyPaints(h.page, 1000), 'al mover el puntero el cielo vuelve').toBeGreaterThan(10);
  expect(await faces(1000), 'y la cara').toBeGreaterThan(5);
  // and a turn wakes it too: thinking is still in its own way, and the rest after it starts its count again
  h.emit({ type: 'state', value: 'thinking' });
  await h.page.waitForTimeout(300);
  h.emit({ type: 'state', value: 'idle' });
  await h.page.waitForTimeout(300);
  expect(await skyPaints(h.page, 1000), 'tras un turno, despierta').toBeGreaterThan(10);
});
