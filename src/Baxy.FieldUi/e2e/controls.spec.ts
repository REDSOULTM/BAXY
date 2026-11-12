import { expect, test, type Page } from '@playwright/test';
import { attach, ready, spanish, type App } from './app';

/* Every control of the view does what it says (owner, 2026-10-17: «que todos los botones funcionen y que nada lleve a
   un punto muerto»). Each reversible control is pressed in the real app and the host is read back through its own
   routes to see that it really changed; then it is put back as it was. The controls that need BAXY to act (cards,
   reminders, forgetting) and the window and tray gestures were checked by hand the same day (RENEW_TRASPASO.md). */

type Json = Record<string, unknown> & { [k: string]: any }; // eslint-disable-line @typescript-eslint/no-explicit-any

let app: App;
let page: Page;
let restoreLang: () => Promise<void>;
test.beforeAll(async () => {
  app = await attach();
  page = app.page;
  await ready(page);
  restoreLang = await spanish(page);
  await page.waitForFunction(async () => (await (await fetch('/agent/status')).json()).ready === true, undefined, { timeout: 180_000, polling: 1000 });
});
test.afterAll(async () => { await restoreLang?.(); await app.browser.close(); });

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
// Settings fold by sections (owner, 2026-11-09): a section is opened before what is in it, and left as it was found.
async function unfold(title: string) {
  const head = page.locator('.bx-fold-h', { hasText: title }).first();
  if (await head.getAttribute('aria-expanded') === 'false') await head.click();
}
// The microphone's mode as the tray and the composer's menu set it, and the mode this machine had before a test.
const micModes = { wake: 'Siempre activo', off: 'Apagado', ptt: 'Mantener para hablar' } as const;
async function pickMic(label: string) { await esc(); await page.click('.bx-caret'); await page.locator('.bx-micmenu button', { hasText: label }).click(); }
async function micShown(): Promise<string> { return (await page.locator('.bx-mic').getAttribute('title')) ?? ''; }
const state = () => page.locator('.bx-statel').innerText();

test('ajustes: cada interruptor guarda en el host y vuelve', async () => {
  // What applies depends on other choices (the wake sound and the playback echo need the microphone, «Un momento» needs
  // the voice on): the test sets them to a known state first, checks a row is locked when it does not apply, and puts
  // everything back as this machine had it, whatever that was.
  const micBefore = await micShown();
  const mutedBefore = (await get('/settings/general')).voiceMuted === true;
  await pickMic(micModes.off);
  await settings('Voz');
  expect.soft(await toggle('Sonido al despertar').isDisabled(), 'con el micrófono apagado, el sonido al despertar no aplica').toBe(true);
  expect.soft(await toggle('Ignorar lo que suena en el PC').isDisabled(), 'con el micrófono apagado, ignorar lo que suena no aplica').toBe(true);
  await pickMic(micModes.ptt);
  if (mutedBefore) {
    await settings('Voz');
    await toggle('Silenciar su voz').click();
    expect(await until(async () => (await get('/settings/general')).voiceMuted === false), 'la voz queda activa para la prueba').toBe(true);
  }
  for (const [tab, label, key] of [
    ['General', 'Al cerrar la ventana, seguir en la bandeja', 'closeToTray'], ['Voz', 'Sonido al despertar', 'wakeSound'],
    ['Voz', 'Ignorar lo que suena en el PC', 'echoCancel'], ['Voz', 'Decir «Un momento»', 'waitNotice'],
    ['Voz', 'Silenciar su voz', 'voiceMuted'], ['Privacidad', 'Búsqueda web', 'web'], ['Privacidad', 'Clima', 'weather'],
    ['Privacidad', 'Mirar la pantalla', 'screen'],
  ] as const) {
    await settings(tab);
    const was = (await get('/settings/general'))[key];
    await toggle(label).click();
    expect.soft(await until(async () => (await get('/settings/general'))[key] !== was), `${label} cambia`).toBe(true);
    await toggle(label).click();
    expect.soft(await until(async () => (await get('/settings/general'))[key] === was), `${label} vuelve`).toBe(true);
  }
  if (mutedBefore) {
    await settings('Voz');
    await toggle('Silenciar su voz').click();
    expect.soft(await until(async () => (await get('/settings/general')).voiceMuted === true), 'la voz vuelve a quedar silenciada').toBe(true);
  }
  await pickMic(micBefore === micModes.wake ? micModes.wake : micBefore === micModes.off ? micModes.off : micModes.ptt);
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
  await unfold('Apariencia');
  await page.getByRole('button', { name: 'Claro', exact: true }).click();
  expect(await page.evaluate(() => document.documentElement.classList.contains('lt'))).toBe(true);
  await page.getByRole('button', { name: 'Oscuro', exact: true }).click();
  expect(await page.evaluate(() => document.documentElement.classList.contains('lt'))).toBe(false);

  // interfaz v5: Normal or Sin frenos, one choice; Sin frenos asks once more before it is sent
  await settings('Confirmación');
  const bypass = (await get('/confirmation')).confirmationPolicy === 'bypass';
  const toBypass = async () => {
    await page.getByRole('radio', { name: 'Sin frenos', exact: true }).click();
    await page.getByRole('button', { name: 'Sí, activar sin frenos' }).click();
  };
  if (bypass) await page.getByRole('radio', { name: 'Normal', exact: true }).click(); else await toBypass();
  expect.soft(await until(async () => ((await get('/confirmation')).confirmationPolicy === 'bypass') !== bypass), 'confirmación cambia').toBe(true);
  if (bypass) await toBypass(); else await page.getByRole('radio', { name: 'Normal', exact: true }).click();
  expect.soft(await until(async () => ((await get('/confirmation')).confirmationPolicy === 'bypass') === bypass), 'confirmación vuelve').toBe(true);

  await settings('Accesibilidad');
  const accessible = (await get('/accessibility')).active === 'accessible';
  // the mode is one choice in cards (design board 22): Normal or Accesible
  const mode = (on: boolean) => page.getByRole('radiogroup', { name: 'Modo accesible' }).getByRole('radio', { name: on ? 'Accesible' : 'Normal', exact: true }).click();
  await mode(!accessible);
  expect.soft(await until(async () => ((await get('/accessibility')).active === 'accessible') !== accessible), 'modo accesible cambia').toBe(true);
  await toggle('Alto contraste').click();
  expect.soft(await page.evaluate(() => document.documentElement.classList.contains('hc'))).toBe(true);
  await toggle('Alto contraste').click();
  await mode(accessible);
  expect.soft(await until(async () => ((await get('/accessibility')).active === 'accessible') === accessible), 'modo accesible vuelve').toBe(true);

  await settings('Privacidad');
  await unfold('Memoria');
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
  await page.getByRole('radiogroup', { name: 'Micrófono' }).getByRole('radio', { name: 'Siempre', exact: true }).click();
  expect.soft(await until(async () => (await get('/voice/status')).mode === 'wake', 20_000), 'ajustes: siempre').toBe(true);
  await page.getByRole('radiogroup', { name: 'Micrófono' }).getByRole('radio', { name: 'Apagado', exact: true }).click();
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

test('rail: Propuestas; Sin frenos se elige en Ajustes con un segundo sí, se ve arriba y se apaga; reposo', async () => {
  await esc();
  // the rail's «Propuestas» opens them in Settings › Comportamiento
  await page.locator('.bx-mod', { hasText: 'Propuestas' }).click();
  await expect(page.locator('.settings-tab.on')).toHaveText('Comportamiento');
  await esc();
  // interfaz v5 (V5.md D4): the mode left the rail; Settings › Confirmación asks once more before Sin frenos
  const policy = (await get('/confirmation')).confirmationPolicy;
  await page.click('.bx-gear');
  await page.locator('.settings-tab', { hasText: 'Confirmación' }).click();
  if (policy === 'bypass') {
    await page.locator('.panel button', { hasText: 'Normal' }).first().click();
    expect.soft(await until(async () => (await get('/confirmation')).confirmationPolicy === 'normal'), 'a Normal').toBe(true);
  }
  await page.locator('.panel button', { hasText: 'Sin frenos' }).first().click();
  // nothing is sent before the second yes
  await page.waitForTimeout(500);
  expect.soft((await get('/confirmation')).confirmationPolicy).toBe('normal');
  await page.locator('.bxs-ask button', { hasText: 'Sí, activar sin frenos' }).click();
  expect.soft(await until(async () => (await get('/confirmation')).confirmationPolicy === 'bypass'), 'sin frenos').toBe(true);
  await esc();
  await expect(page.locator('.bx-bypass-pill')).toBeVisible();
  if (policy !== 'bypass') {
    await page.locator('.bx-bypass-pill').click();
    await page.locator('.panel button', { hasText: 'Normal' }).first().click();
    expect.soft(await until(async () => (await get('/confirmation')).confirmationPolicy === 'normal'), 'vuelve a Normal').toBe(true);
    await esc();
    await expect(page.locator('.bx-bypass-pill')).toHaveCount(0);
  }
  await page.click('.power-row');
  expect.soft(await until(async () => (await get('/agent/status')).powered === false && /reposo/i.test(await state()), 20_000), 'reposo').toBe(true);
  await page.click('.power-row');
  expect.soft(await until(async () => (await get('/agent/status')).powered !== false && !/reposo/i.test(await state()), 20_000), 'activo').toBe(true);
});

test('paneles: propuestas (en Ajustes › Comportamiento), catálogo, historial y memoria', async () => {
  await esc();
  await page.click('.bx-gear');
  await page.locator('.settings-tab', { hasText: 'Comportamiento' }).click();
  const p = await get('/proposals');
  const games = page.getByRole('switch', { name: 'Juegos' });
  await games.click();
  expect.soft(await until(async () => (await get('/proposals')).ctx?.game !== p.ctx?.game), 'no interrumpir cambia').toBe(true);
  await games.click();
  expect.soft(await until(async () => (await get('/proposals')).ctx?.game === p.ctx?.game), 'no interrumpir vuelve').toBe(true);
  await page.locator('.panel button', { hasText: '30 min' }).click();
  expect.soft(await until(async () => (await get('/proposals')).quiet === '30m'), 'silenciar').toBe(true);
  await page.locator('.panel button', { hasText: '30 min' }).click();
  expect.soft(await until(async () => !(await get('/proposals')).quiet), 'volver a activas').toBe(true);
  await esc();

  await page.locator('.bx-mod', { hasText: 'Capacidades' }).click();
  await page.locator('.panel input').fill('volumen');
  await expect(page.locator('.panel')).toContainText(/volumen/i);
  await esc();

  await page.locator('.bx-mod', { hasText: 'Historial' }).click();
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
  // the grid slides the conversation back in (0.6 s): the window buttons move with it, and a click aimed before it ends lands
  // half on the old place
  await page.waitForTimeout(800);
  // Whatever state this machine left the window in: the button says it, a press changes it, and a second one puts it back.
  const first = await page.locator('button[title="Maximizar"], button[title="Restaurar"]').first().getAttribute('title');
  const other = first === 'Maximizar' ? 'Restaurar' : 'Maximizar';
  expect(await page.evaluate(() => (window as unknown as { pywebview: { api: { win_is_maximized: () => Promise<boolean> } } }).pywebview.api.win_is_maximized()))
    .toBe(first === 'Restaurar');
  await page.locator(`button[title="${first}"]`).click();
  await expect(page.locator(`button[title="${other}"]`)).toHaveCount(1);
  await page.locator(`button[title="${other}"]`).click();
  await expect(page.locator(`button[title="${first}"]`)).toHaveCount(1);
  expect(app.errors).toEqual([]);
});
