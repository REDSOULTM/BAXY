import { expect, test, type Browser } from '@playwright/test';
import { join } from 'node:path';
import { ROOT, headless, serveView } from './headless';

/* AvatarVid on its own (e2e/harness/avatar.html, served by Vite) in a headless page, with no app: the clips come
   from public/clips through the page's router. */

let browser: Browser;
let view: Awaited<ReturnType<typeof serveView>>;
let base = '';
test.setTimeout(60_000);
test.beforeAll(async () => { view = await serveView(); base = view.base; browser = await headless(); });
test.afterAll(async () => { await browser?.close(); await view?.close(); });

test('un clip que sale de la pantalla suelta su archivo (no queda un reproductor vivo fuera de la página)', async () => {
  const page = await browser.newPage();
  const errors: string[] = [];
  page.on('pageerror', (e) => errors.push(String(e)));
  await page.route('**/clips/*.mp4', (r) => r.fulfill({ path: join(ROOT, 'public', 'clips', r.request().url().split('/').pop()!), contentType: 'video/mp4' }));
  // every clip taken off the page, and whether it still had its file when it left
  await page.addInitScript(() => {
    const gone: { g: string; src: boolean }[] = [];
    (window as unknown as { bxGone: typeof gone }).bxGone = gone;
    new MutationObserver((ms) => ms.forEach((m) => m.removedNodes.forEach((n) => {
      if (n instanceof HTMLVideoElement) gone.push({ g: n.dataset.g ?? '', src: n.hasAttribute('src') });
    }))).observe(document, { childList: true, subtree: true });
  });
  await page.goto(base + '/e2e/harness/avatar.html');
  await page.waitForFunction(() => !!document.querySelector('.bx-avid video.on'));
  for (const s of ['listening', 'thinking', 'speaking', 'idle'] as const) {
    await page.evaluate((st) => window.bxSet(st), s);
    await page.waitForTimeout(3200);
  }
  const gone = await page.evaluate(() => (window as unknown as { bxGone: { g: string; src: boolean }[] }).bxGone);
  expect(gone.length, 'hubo clips que salieron').toBeGreaterThan(2);
  expect(gone.filter((v) => v.src).map((v) => v.g), 'clips fuera de la página con su archivo aún cargado').toEqual([]);
  expect(errors).toEqual([]);
  await page.close();
});

test('montado dos veces (StrictMode) queda un solo lienzo de boca sobre el vídeo', async () => {
  // the effect's cleanup takes off the page what the effect put there: the clips and the lip-sync's canvas
  const page = await browser.newPage();
  await page.route('**/clips/*.mp4', (r) => r.fulfill({ path: join(ROOT, 'public', 'clips', r.request().url().split('/').pop()!), contentType: 'video/mp4' }));
  await page.goto(base + '/e2e/harness/avatar.html?strict');
  await page.waitForFunction(() => !!document.querySelector('.bx-avid video.on'));
  expect(await page.locator('.bx-avid canvas.bx-lip').count()).toBe(1);
  await page.close();
});
