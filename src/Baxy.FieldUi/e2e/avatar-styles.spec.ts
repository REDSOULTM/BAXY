import { expect, test, type Browser } from '@playwright/test';
import { readFileSync } from 'node:fs';
import { headless } from './headless';

/* The avatar's styles (v4.css) in a headless page, with no app. */

let browser: Browser;
test.beforeAll(async () => { browser = await headless(); });
test.afterAll(async () => { await browser.close(); });

const CSS = readFileSync(new URL('../src/styles/v4.css', import.meta.url), 'utf8').replace(/url\("\/bg\/[^"]*"\)/g, 'none');

test('con «reducir movimiento» el avatar no tiembla en un error ni funde un clip en otro', async () => {
  const page = await browser.newPage();
  // a cut with a fade («fade») on an error clip: the playing clip («on») and the one going out
  await page.setContent('<style>' + CSS + '</style><div class="bx-avid fade s-error"><video class="on"></video><video></video></div>');
  const motion = () => page.evaluate(() => [...document.querySelectorAll('video')].map((v) => {
    const cs = getComputedStyle(v);
    return { anim: cs.animationName, trans: cs.transitionDuration.split(',').map((d) => parseFloat(d)).reduce((a, b) => Math.max(a, b), 0) };
  }));
  const normal = await motion();
  expect(normal[0].anim, 'sin la preferencia, el temblor del diseño sigue').toBe('bxAvShake');
  await page.emulateMedia({ reducedMotion: 'reduce' });
  const reduced = await motion();
  expect(reduced.map((m) => m.anim), 'sin temblor').toEqual(['none', 'none']);
  expect(reduced.map((m) => m.trans), 'sin fundido ni transición').toEqual([0, 0]);
  await page.close();
});
