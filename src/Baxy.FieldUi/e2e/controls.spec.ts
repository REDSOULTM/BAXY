import { expect, test, type Page } from '@playwright/test';
import { attach, ready, type App } from './app';

/* Every control of the view does what it says (owner, 2026-10-17: «que todos los botones funcionen y que nada lleve a
   un punto muerto»). Each reversible control is pressed in the real app and the host is read back through its own
   routes to see that it really changed; then it is put back as it was. The controls that need BAXY to act (cards,
   reminders, forgetting) and the window and tray gestures were checked by hand the same day (RENEW_TRASPASO.md). */

type Json = Record<string, unknown> & { [k: string]: any }; // eslint-disable-line @typescript-eslint/no-explicit-any

let app: App;
let page: Page;
test.beforeAll(async () => {
  app = await attach();
  page = app.page;
  await ready(page);
  await page.waitForFunction(async () => (await (await fetch('/agent/status')).json()).ready === true, undefined, { timeout: 180_000, polling: 1000 });
});
test.afterAll(async () => { await app.browser.close(); });

const get = (path: string): Promise<Json> => page.evaluate(async (p) => { const r = await fetch(p); return r.ok ? r.json() : { status: r.status }; }, path);
async function until<T>(fn: () => Promise<T>, ms = 8000): Promise<T> {
  const end = Date.now() + ms;
  let v = await fn();
  while (!v && Date.now() < end) { await page.waitForTimeout(250); v = await fn(); }
  return v;
}
async function esc() { await page.keyboard.press('Escape'); await page.waitForTimeout(250); }
async function settings(tab: string) {
  await esc();
  await page.click('.bx-gear');
  await page.locator('.settings-tab', { hasText: tab }).click();
}
const toggle = (label: string) => page.locator(`button.toggle[aria-label="${label}"]`).first();
const state = () => page.locator('.bx-statel').innerText();

test('ajustes: cada interruptor guarda en el host y vuelve', async () => {
  for (const [tab, label, key] of [
    ['General', 'Al cerrar la ventana, seguir en la bandeja', 'closeToTray'], ['Voz', 'Sonido al despertar', 'wakeSound'],
    ['Voz', 'Decir «Un momento»', 'waitNotice'], ['Voz', 'Silenciar su voz', 'voiceMuted'], ['Privacidad', 'Búsqueda web', 'web'], ['Privacidad', 'Clima', 'weather'],
    ['Privacidad', 'Mirar la pantalla', 'screen'],
  ] as const) {
    await settings(tab);
    const was = (await get('/settings/general'))[key];
    await toggle(label).click();
    expect.soft(await until(async () => (await get('/settings/general'))[key] !== was), `${label} cambia`).toBe(true);
    await toggle(label).click();
    expect.soft(await until(async () => (await get('/settings/general'))[key] === was), `${label} vuelve`).toBe(true);
  }
  await esc();
});

test('ajustes: arrancar con Windows dice por qué no se puede, nunca un fallo de lectura falso', async () => {
  const g = await get('/settings/general');
  await settings('General');
  const hint = await page.locator('.settings-body').innerText();
  if (g.autostartBlocked === 'not_this_copy') expect(hint).toContain('Esta copia de desarrollo');
  if (g.autostart !== null) expect(await toggle('Arrancar con Windows').isDisabled()).toBe(false);
  await esc();
});

test('ajustes: tema, confirmación y modo accesible', async () => {
  await settings('General');
  await page.getByRole('button', { name: 'Claro', exact: true }).click();
  expect(await page.evaluate(() => document.documentElement.classList.contains('lt'))).toBe(true);
  await page.getByRole('button', { name: 'Oscuro', exact: true }).click();
  expect(await page.evaluate(() => document.documentElement.classList.contains('lt'))).toBe(false);

  await settings('Confirmación');
  const bypass = (await get('/confirmation')).confirmationPolicy === 'bypass';
  await page.getByRole('button', { name: bypass ? 'Lo arriesgado' : 'Nada', exact: true }).click();
  expect.soft(await until(async () => ((await get('/confirmation')).confirmationPolicy === 'bypass') !== bypass), 'confirmación cambia').toBe(true);
  await page.getByRole('button', { name: bypass ? 'Nada' : 'Lo arriesgado', exact: true }).click();
  expect.soft(await until(async () => ((await get('/confirmation')).confirmationPolicy === 'bypass') === bypass), 'confirmación vuelve').toBe(true);

  await settings('Accesibilidad');
  const accessible = (await get('/accessibility')).active === 'accessible';
  await toggle('Modo accesible').click();
  expect.soft(await until(async () => ((await get('/accessibility')).active === 'accessible') !== accessible), 'modo accesible cambia').toBe(true);
  await toggle('Alto contraste').click();
  expect.soft(await page.evaluate(() => document.documentElement.classList.contains('hc'))).toBe(true);
  await toggle('Alto contraste').click();
  await toggle('Modo accesible').click();
  expect.soft(await until(async () => ((await get('/accessibility')).active === 'accessible') === accessible), 'modo accesible vuelve').toBe(true);

  await settings('Privacidad');
  await page.getByRole('button', { name: 'Ver y editar' }).click();
  await expect(page.locator('.panel', { hasText: 'Memoria' })).toBeVisible();
  await esc();
});

test('micrófono: los tres modos, en el menú y en ajustes, y en reposo se aplica al activar', async () => {
  await esc();
  const shown = await page.locator('.bx-mic').getAttribute('title');
  const pick = async (label: string) => { await page.click('.bx-caret'); await page.locator('.bx-micmenu button', { hasText: label }).click(); };
  await pick('Siempre activo');
  expect.soft(await until(async () => (await get('/voice/status')).mode === 'wake', 20_000), 'menú: siempre activo').toBe(true);
  await pick('Apagado');
  expect.soft(await until(async () => (await get('/voice/status')).mode === 'off'), 'menú: apagado').toBe(true);
  await pick('Mantener para hablar');
  expect.soft(await page.locator('.bx-mic').getAttribute('title')).toBe('Mantén para hablar');
  await page.keyboard.down(' ');
  expect.soft(await until(async () => /Escuchando/.test(await state()), 5000), 'espacio: escucha').toBe(true);
  await page.keyboard.up(' ');
  expect.soft(await until(async () => !/Escuchando/.test(await state()), 15_000), 'espacio: deja de escuchar').toBe(true);

  await settings('Voz');
  await page.getByRole('button', { name: 'Siempre', exact: true }).click();
  expect.soft(await until(async () => (await get('/voice/status')).mode === 'wake', 20_000), 'ajustes: siempre').toBe(true);
  await page.getByRole('button', { name: 'Apagado', exact: true }).click();
  expect.soft(await until(async () => (await get('/voice/status')).mode === 'off'), 'ajustes: apagado').toBe(true);
  await esc();

  await page.click('.power-row');
  expect(await until(async () => (await get('/agent/status')).powered === false, 20_000)).toBe(true);
  await pick('Siempre activo');
  expect.soft((await get('/voice/status')).mode, 'en reposo no escucha').toBe('off');
  await page.click('.power-row');
  expect.soft(await until(async () => (await get('/voice/status')).mode === 'wake', 20_000), 'al activar se aplica').toBe(true);
  await pick(shown === 'Siempre activo' ? 'Siempre activo' : shown === 'Apagado' ? 'Apagado' : 'Mantener para hablar');
  await page.waitForTimeout(1500);
});

test('rail: perfiles, Normal/Bypass y reposo', async () => {
  await esc();
  // The owner's decision (2026-10-18): only the standard mode is ready; «No vidente» and «Movilidad» say «próximamente
  // disponible» and a click on them changes nothing.
  for (const i of [1, 2]) {
    const chip = page.locator('.bx-pchip').nth(i);
    await expect(chip).toHaveAttribute('aria-disabled', 'true');
    expect.soft(await chip.getAttribute('title')).toMatch(/próximamente disponible/);
    await chip.click({ force: true });
    await expect(page.locator('.bx2.p-normal')).toHaveCount(1);
  }
  await page.locator('.bx-pchip').nth(0).click();
  await expect(page.locator('.bx2.p-normal')).toHaveCount(1);
  const policy = (await get('/confirmation')).confirmationPolicy;
  await page.click('.bx-modebtn');
  expect.soft(await until(async () => (await get('/confirmation')).confirmationPolicy !== policy)).toBe(true);
  await page.click('.bx-modebtn');
  expect.soft(await until(async () => (await get('/confirmation')).confirmationPolicy === policy)).toBe(true);
  await page.click('.power-row');
  expect.soft(await until(async () => (await get('/agent/status')).powered === false && /reposo/i.test(await state()), 20_000), 'reposo').toBe(true);
  await page.click('.power-row');
  expect.soft(await until(async () => (await get('/agent/status')).powered !== false && !/reposo/i.test(await state()), 20_000), 'activo').toBe(true);
});

test('paneles: propuestas, catálogo, sesiones y memoria', async () => {
  await esc();
  await page.locator('.bx-mod', { hasText: 'Propuestas' }).click();
  const p = await get('/proposals');
  await page.locator('.panel button.toggle').first().click();
  expect.soft(await until(async () => (await get('/proposals')).ctx?.game !== p.ctx?.game), 'no interrumpir cambia').toBe(true);
  await page.locator('.panel button.toggle').first().click();
  expect.soft(await until(async () => (await get('/proposals')).ctx?.game === p.ctx?.game), 'no interrumpir vuelve').toBe(true);
  await page.locator('.panel button', { hasText: '30 min' }).click();
  expect.soft(await until(async () => (await get('/proposals')).quiet === '30m'), 'silenciar').toBe(true);
  await page.locator('.panel button', { hasText: '30 min' }).click();
  expect.soft(await until(async () => !(await get('/proposals')).quiet), 'volver a activas').toBe(true);
  await esc();

  await page.locator('.bx-mod', { hasText: 'Qué puedo hacer' }).click();
  await page.locator('.panel input').fill('volumen');
  await expect(page.locator('.panel')).toContainText(/volumen/i);
  await esc();

  await page.locator('.bx-mod', { hasText: 'Sesiones' }).click();
  const cur = (await get('/sessions')).sessions.find((x: Json) => x.current);
  await page.locator('.bx-mem-row.cur .bx-lnk', { hasText: 'Renombrar' }).click();
  await page.locator('.panel input.st-input').fill('Prueba de botones');
  await page.keyboard.press('Enter');
  expect.soft(await until(async () => (await get('/sessions')).sessions.find((x: Json) => x.id === cur.id)?.label === 'Prueba de botones'), 'renombrar').toBe(true);
  await page.locator('.bx-mem-row.cur .bx-lnk', { hasText: 'Renombrar' }).click();
  await page.locator('.panel input.st-input').fill(cur.label);
  await page.keyboard.press('Enter');
  expect.soft(await until(async () => (await get('/sessions')).sessions.find((x: Json) => x.id === cur.id)?.label === cur.label), 'renombrar de vuelta').toBe(true);
  await esc();

  await page.locator('.bx-mod', { hasText: 'Memoria' }).click();
  const m = await get('/memory');
  await page.locator('.panel button.toggle').first().click();
  expect.soft(await until(async () => (await get('/memory')).enabled === !m.enabled, 20_000), 'recordar cambia').toBe(true);
  await page.locator('.panel button.toggle').first().click();
  expect.soft(await until(async () => (await get('/memory')).enabled === m.enabled, 20_000), 'recordar vuelve').toBe(true);
  await esc();
});

test('conversación y ventana: ocultar, mostrar, maximizar, restaurar', async () => {
  await esc();
  await page.locator('button[title="Ocultar conversación"]').click();
  await expect(page.locator('.bx2.chat-off')).toHaveCount(1);
  await page.locator('button[title="Mostrar conversación"]').click();
  await expect(page.locator('.bx2.chat-off')).toHaveCount(0);
  await page.locator('button[title="Maximizar"]').click();
  await expect(page.locator('button[title="Restaurar"]')).toHaveCount(1);
  await page.locator('button[title="Restaurar"]').click();
  await expect(page.locator('button[title="Maximizar"]')).toHaveCount(1);
  expect(app.errors).toEqual([]);
});
