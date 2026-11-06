import { expect, test, type Page } from '@playwright/test';
import { existsSync, unlinkSync, writeFileSync } from 'node:fs';
import { homedir } from 'node:os';
import { join } from 'node:path';
import { attach, ready, size, spanish, unsize, type App } from './app';

/* «Avatar · clips de Higgsfield + red viva» of Baxy pruebas.html (design v5) against the real app: the video avatar
   under the live network, its idle rotation, the clip following the state through real turns, the Sí / No card, sleep
   and wake, and the ?avatar=live fallback. The requests are harmless ones: the date and time, a question that goes to
   the internet, a file that does not exist, and a test file of its own sent to the recycle bin (No first, then Sí). */

let app: App;
let page: Page;
let restoreLang: () => Promise<void>;
test.setTimeout(240_000);
test.beforeAll(async () => {
  app = await attach();
  page = app.page;
  await ready(page);
  restoreLang = await spanish(page);
  await page.waitForFunction(async () => (await (await fetch('/agent/status')).json()).ready === true, undefined, { timeout: 180_000, polling: 1000 });
  await size(app, 1280, 720);
  await page.waitForTimeout(2500);
});
test.afterAll(async () => { await unsize(app); await restoreLang?.(); await app.browser.close(); });

// the clip groups each status label may show (the bridges «despertar» / «dormirse» are always allowed)
const EXP: Record<string, string[]> = {
  Pensando: ['pensando'], Hablando: ['hablando'], Escuchando: ['escuchando'], 'En espera': ['reposo', 'contento'],
  'Esperando tu ok': ['reposo', 'contento'], 'En reposo': ['dormido', 'dormirse'], 'Falló la escucha': ['error'],
};
interface Sample { t: number; lab: string; g: string | null; src: string | null; rs: number; n: number; seen: boolean }
const now = (): Promise<Omit<Sample, 't'>> => page.evaluate(() => {
  const v = document.querySelector<HTMLVideoElement>('.bx-avid video.on');
  const lab = (document.querySelector('.bx-statel')?.textContent ?? '').trim();
  // BAXY is on screen: either the face is drawn whole, or the video layer and its clip are really showing a frame
  const av = document.querySelector('.bx-avid'), face = document.querySelector('canvas.bx-face');
  const whole = !!face && (face as HTMLElement).dataset.overlay !== '1' && getComputedStyle(face).opacity !== '0';
  // during the 0.35 s crossfade the clip coming in and the one going out add up
  const shown = [...document.querySelectorAll<HTMLVideoElement>('.bx-avid video')].filter((x) => x.readyState >= 2).reduce((a, x) => a + +getComputedStyle(x).opacity, 0);
  const video = !!av && !!v && +getComputedStyle(av).opacity > 0.5 && shown > 0.5 && getComputedStyle(av).display !== 'none';
  return { seen: whole || video, lab, g: v ? v.dataset.g ?? null : null, src: v ? v.src.split('/').pop() ?? null : null, rs: v ? v.readyState : -1, n: document.querySelectorAll('.bx-avid video.on').length };
});
async function trace(ms: number, every = 150): Promise<Sample[]> {
  const out: Sample[] = [], t0 = Date.now();
  while (Date.now() - t0 < ms) { out.push({ t: Date.now() - t0, ...(await now()) }); await page.waitForTimeout(every); }
  // never blank: at most one sample (the frame between the video losing its frame and the face drawing itself whole)
  const blank = out.filter((s, i) => !s.seen && i > 0 && !out[i - 1].seen);
  expect.soft(blank.length, 'BAXY se ve siempre (vídeo con fotograma o cara dibujada) · en blanco en ' + blank.slice(0, 4).map((s) => Math.round(s.t) + ' ms ' + s.lab + ' ' + s.g).join(', ')).toBe(0);
  return out;
}
// samples whose label has held for 700 ms and whose clip is not one the label allows
function mismatch(tr: Sample[]) {
  let bad = 0, n = 0, since = 0, last = '';
  const ex: string[] = [];
  for (const s of tr) {
    const lab = Object.keys(EXP).find((k) => s.lab.startsWith(k));
    if (s.lab !== last) { last = s.lab; since = s.t; }
    if (!lab || s.t - since < 700) continue;
    n++;
    if (!EXP[lab].includes(s.g ?? '') && s.g !== 'despertar' && s.g !== 'dormirse') { bad++; if (ex.length < 4) ex.push(lab + '→' + s.g); }
  }
  return { bad, n, ex };
}
async function say(text: string) {
  const input = page.locator('.bx-line > input');
  await input.fill(text);
  await input.press('Enter');
}
const idle = (timeout = 90_000) => page.waitForFunction(() => /^En espera|^Esperando tu ok/.test((document.querySelector('.bx-statel')?.textContent ?? '').trim()), undefined, { timeout });

test('avatar: vídeo bajo la red viva, sin imagen en la cabecera ni controles', async () => {
  expect(await page.locator('.left-header img, .left-header .mark').count(), 'sin imagen en la cabecera del panel izquierdo').toBe(0);
  const av = page.locator('.bx-avid');
  expect(await av.count(), 'hay avatar en vídeo').toBe(1);
  expect(await av.evaluate((e) => getComputedStyle(e).backgroundImage), 'sin imagen fija detrás del vídeo').toBe('none');
  const vids = await page.evaluate(() => [...document.querySelectorAll<HTMLVideoElement>('.bx-avid video')].map((v) => v.disablePictureInPicture && !v.controls && v.muted));
  expect(vids.length, 'hay clips cargados').toBeGreaterThan(0);
  expect(vids.every(Boolean), 'vídeos sin controles ni imagen en miniatura, sin sonido').toBe(true);
  const geo = await page.evaluate(() => {
    const g = document.querySelector<HTMLElement>('.bx-graph')!, s = g.style.getPropertyValue('--av-s');
    const ui = parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--ui')) || 1;
    return { s, w: document.querySelector('.bx-avid')!.getBoundingClientRect().width / ui };
  });
  expect(geo.s, 'la red viva publica su geometría para alinear el vídeo').not.toBe('');
  expect(Math.abs(geo.w - parseFloat(geo.s) * 2.844), 'el vídeo mide lo que pide la geometría').toBeLessThan(3);
  expect(await page.locator('.bx-graph canvas.bx-face').count(), 'una sola capa viva encima del vídeo').toBe(1);
});

test('avatar: en espera rota entre variantes, sin repetir, siempre un clip con fotogramas', async () => {
  await idle();
  const tr = await trace(12_000, 250);
  const srcs = tr.map((s) => s.src).filter((x, i, A) => x && x !== A[i - 1]);
  expect(Math.max(...tr.map((s) => s.n)), 'siempre hay exactamente un clip visible').toBe(1);
  expect(Math.min(...tr.map((s) => s.n)), 'nunca queda sin clip').toBe(1);
  expect(srcs.length, 'en espera rota entre variantes: ' + srcs.join(' → ')).toBeGreaterThanOrEqual(2);
  expect(srcs.every((x, i) => i === 0 || x !== srcs[i - 1]), 'no repite la misma variante seguida').toBe(true);
  expect(tr[tr.length - 1].rs, 'el clip actual tiene fotogramas decodificados').toBeGreaterThanOrEqual(2);
});

for (const [name, text, ms] of [
  ['Varios pasos', 'qué hora es y qué día es hoy', 16_000],
  ['Falla a mitad', 'abre el archivo zz-no-existe-baxy.txt del escritorio', 16_000],
  ['Sale a internet', 'qué tiempo hace mañana', 16_000],
] as const) {
  test(`avatar: ${name}: el clip sigue al estado`, async () => {
    await idle();
    await say(text);
    const tr = await trace(ms);
    const m = mismatch(tr), seen = [...new Set(tr.map((s) => s.g))].join(', ');
    expect(m.n, 'hubo estados que comparar · grupos: ' + seen).toBeGreaterThan(0);
    expect(m.bad / m.n, `${m.bad}/${m.n} fuera · ${m.ex.join(' ') || 'ok'} · grupos: ${seen}`).toBeLessThan(0.12);
  });
}

test('avatar: tarjeta Sí / No: en reposo mientras espera, y tras responder sigue al estado', async () => {
  test.setTimeout(480_000);
  // a test file of this suite on the Desktop: «No» keeps it, «Sí» sends it to the recycle bin (recoverable_delete is
  // the risk the kernel asks about in Normal mode)
  const file = join(homedir(), 'Desktop', 'baxy-prueba-avatar.txt');
  writeFileSync(file, 'Archivo de prueba de BAXY (avatar.spec.ts). Se puede borrar.\n');
  // the card only exists in Normal mode: Bypass (the person's choice, kept by the host) is put back afterwards
  const policy = () => page.evaluate(async () => (await (await fetch('/confirmation')).json()).confirmationPolicy as string);
  const setPolicy = (v: string) => page.evaluate(async (x) => {
    await fetch('/confirmation', { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ confirmationPolicy: x }) });
  }, v);
  const was = await policy();
  if (was !== 'normal') await setPolicy('normal');
  await expect.poll(policy, { message: 'modo Normal para la prueba' }).toBe('normal');
  try {
    for (const [label, yes] of [['rechazada', false], ['aceptada', true]] as const) {
      await idle();
      await say('borra el archivo baxy-prueba-avatar.txt del escritorio');
      let card = false;
      for (let t0 = Date.now(); Date.now() - t0 < 45_000 && !card;) { card = (await page.locator('.bx-card.s-pending .bx-btn').count()) > 0; if (!card) await page.waitForTimeout(250); }
      expect.soft(card, `confirmación ${label}: aparece la tarjeta Sí / No`).toBe(true);
      if (!card) continue;
      await page.waitForTimeout(900);
      const a = await now();
      expect.soft(['reposo', 'contento'], `confirmación ${label}: mientras espera tu ok, BAXY queda en reposo (${a.lab} · ${a.g})`).toContain(a.g);
      await page.locator('.bx-card.s-pending .bx-btn' + (yes ? '.yes' : ':not(.yes)')).first().click();
      const m = mismatch(await trace(9000));
      expect.soft(m.n === 0 || m.bad / m.n < 0.12, `confirmación ${label}: tras responder, el clip sigue al estado (${m.bad}/${m.n} · ${m.ex.join(' ') || 'ok'})`).toBe(true);
      if (!yes) expect.soft(existsSync(file), 'tras «No» el archivo sigue ahí').toBe(true);
      // the turn ends before the file is touched again (2026-10-21: the confirmed move to the recycle bin took 101 s and
      // BAXY said it could not confirm it; the avatar stayed «pensando» all along, as the state said)
      await idle(180_000);
    }
  } finally {
    if (existsSync(file)) unlinkSync(file);
    if (was !== 'normal') await setPolicy(was);
  }
});

test('avatar: al apagar se duerme con transición y al encender se despierta', async () => {
  await idle();
  await page.click('.power-row');
  const gs = (await trace(11_000, 200)).map((s) => s.g).filter((x, i, A) => x !== A[i - 1]);
  expect.soft(gs.includes('dormirse') || gs[0] === 'dormido', 'al apagar: se duerme con transición · ' + gs.join(' → ')).toBe(true);
  expect.soft(gs[gs.length - 1], 'queda dormido').toBe('dormido');
  await page.click('.power-row');
  const gw = (await trace(9000, 200)).map((s) => s.g).filter((x, i, A) => x !== A[i - 1]);
  expect.soft(gw.includes('despertar'), 'al encender: se despierta con transición · ' + gw.join(' → ')).toBe(true);
  expect(['reposo', 'contento', 'escuchando'], 'vuelve a reposo · ' + gw.join(' → ')).toContain(gw[gw.length - 1]);
  expect(app.errors, 'sin errores de consola').toEqual([]);
});

test('avatar: ?avatar=live muestra la cara dibujada', async () => {
  const home = page.url().split('?')[0];
  const errors = app.errors.length;
  try {
    await page.goto(home + '?avatar=live');
    await ready(page);
    await page.waitForTimeout(3000);
    expect(await page.locator('.bx-avid').count(), '?avatar=live: sin vídeo').toBe(0);
    expect(await page.locator('canvas.bx-face').count(), '?avatar=live: la cara dibujada').toBe(1);
    expect(app.errors.slice(errors), '?avatar=live sin errores').toEqual([]);
  } finally {
    await page.goto(home);
    await ready(page);
  }
});
