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

test('en alto contraste la boca compuesta lleva el mismo filtro que el fotograma en que se compone', async () => {
  // the lip-sync composes the mouth from the raw frame (drawImage ignores CSS filters): with another filter on the
  // video than on the canvas, the mouth's area shows as a patch of other contrast
  const page = await browser.newPage();
  await page.emulateMedia({ reducedMotion: 'reduce' }); // the filter's 1.4 s transition, off: the final values at once
  await page.setContent('<style>' + CSS + '</style><div class="bx-avid lip"><video class="on"></video><canvas class="bx-lip"></canvas></div>');
  const filters = () => page.evaluate(() => ['video', 'canvas'].map((q) => getComputedStyle(document.querySelector(q)!).filter));
  for (const hc of [false, true]) {
    await page.evaluate((on) => document.documentElement.classList.toggle('hc', on), hc);
    const [video, mouth] = await filters();
    expect(mouth, (hc ? 'alto contraste' : 'normal') + ': filtro del vídeo ' + video).toBe(video);
  }
  await page.close();
});

test('con «reducir movimiento» se paran las animaciones sin fin de la vista y lo que indican queda a la vista', async () => {
  const all = ['base', 'baxy', 'v4'].map((f) => readFileSync(new URL('../src/styles/' + f + '.css', import.meta.url), 'utf8')).join('\n').replace(/url\("\/bg\/[^"]*"\)/g, 'none');
  const page = await browser.newPage();
  await page.setContent('<style>' + all + '</style>' +
    '<span class="bx-statel live"><i></i>Pensando</span><div class="bx-c-think"><i></i><i></i><i></i></div><span class="bx-live">texto</span>' +
    '<div class="bx-step"><span class="txt">Abriendo…</span></div><button class="bx-mic on breath"></button><button class="bx-mic talking"></button>' +
    '<div class="bx-wait"><span class="ar">→</span></div><div class="bx-boot"><div class="bar"><i></i></div></div><span class="spin"></span>');
  const endless = () => page.evaluate(() => {
    const out: string[] = [];
    for (const el of document.body.querySelectorAll('*')) for (const ps of [null, '::before', '::after']) {
      const cs = getComputedStyle(el, ps);
      if (cs.animationName !== 'none' && cs.animationIterationCount === 'infinite') out.push(el.className + (ps ?? '') + ' ' + cs.animationName);
    }
    return out;
  });
  expect((await endless()).length, 'sin la preferencia siguen las del diseño').toBe(11);
  await page.emulateMedia({ reducedMotion: 'reduce' });
  expect(await endless(), 'con la preferencia ninguna sin fin').toEqual([]);
  // still there: the live dot, the thinking dots, the caret, the talking ring, the spinner's arc and the boot bar
  const shown = await page.evaluate(() => [
    getComputedStyle(document.querySelector('.bx-statel i')!).opacity, getComputedStyle(document.querySelector('.bx-c-think i')!).opacity,
    getComputedStyle(document.querySelector('.bx-live')!, '::after').opacity, getComputedStyle(document.querySelector('.bx-mic.talking')!, '::before').opacity,
    getComputedStyle(document.querySelector('.spin')!).borderTopColor !== getComputedStyle(document.querySelector('.spin')!).borderBottomColor ? '1' : '0',
    // the boot bar fills its track (its content box): in progress, not stuck at 30 %
    String(((i: Element, bar: Element) => i.getBoundingClientRect().width >= bar.clientWidth - parseFloat(getComputedStyle(bar).paddingLeft) - parseFloat(getComputedStyle(bar).paddingRight) - 0.5)(document.querySelector('.bx-boot .bar i')!, document.querySelector('.bx-boot .bar')!) ? 1 : 0),
  ].map(Number));
  expect(shown.every((o) => o > 0.3), 'lo que indican sigue visible: ' + shown.join(' ')).toBe(true);
  await page.close();
});
