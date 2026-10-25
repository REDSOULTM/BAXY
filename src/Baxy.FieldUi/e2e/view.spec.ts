import { expect, test } from '@playwright/test';
import { card, openView, stopHost, type Host } from './host';

/* The view's logic against a stand-in host (host.ts): what the person does reaches the host once, for the right card,
   and nothing the view started stays alive. Headless; it never needs BAXY running. */

let h: Host;
test.afterEach(async () => { await h?.close(); });
test.afterAll(async () => { await stopHost(); });

const answers = () => h.calls.filter((c) => c.path === '/confirmation/answer').map((c) => c.body);

test('Enter sobre el botón «No» de una tarjeta responde No, no Sí', async () => {
  h = await openView({ items: [card('c1')] });
  await h.page.locator('.bx-card .bx-btn', { hasText: 'No' }).focus();
  await h.page.keyboard.press('Enter');
  await expect.poll(answers).toHaveLength(1);
  expect(answers()).toEqual([{ approve: false, card: 'c1' }]);
});

test('Enter en la caja de texto vacía responde Sí; Esc sobre un botón responde No', async () => {
  h = await openView({ items: [card('c1'), card('c2')] });
  await h.page.locator('input[aria-label="Escribe a BAXY"]').focus();
  await h.page.keyboard.press('Enter');
  await expect.poll(answers).toEqual([{ approve: true, card: 'c2' }]);
  h.emit({ type: 'item', item: card('c2', { status: 'yes' }) });
  await expect(h.page.locator('.bx-card.s-pending')).toHaveCount(1);
  await h.page.locator('.bx-card.s-pending .bx-btn', { hasText: 'Sí' }).focus();
  await h.page.keyboard.press('Escape');
  await expect.poll(answers).toEqual([{ approve: true, card: 'c2' }, { approve: false, card: 'c1' }]);
});

test('una tarjeta se responde una vez: el segundo Sí no llega al host ni dice que no se tomó', async () => {
  h = await openView({ items: [card('c1')] });
  let n = 0;
  h.reply('/confirmation/answer', () => (n++ === 0 ? { body: { ok: true } } : { status: 409 }));
  await h.page.locator('.bx-card .bx-btn', { hasText: 'Sí' }).dblclick();
  await h.page.keyboard.press('Enter');
  await h.page.waitForTimeout(400);
  expect(answers()).toEqual([{ approve: true, card: 'c1' }]);
  await expect(h.page.locator('.bx-notice')).toHaveCount(0);
});

test('una respuesta que el host rechazó se dice y se puede dar otra vez', async () => {
  h = await openView({ items: [card('c1')] });
  let n = 0;
  h.reply('/confirmation/answer', () => (n++ === 0 ? { status: 409 } : { body: { ok: true } }));
  await h.page.locator('.bx-card .bx-btn', { hasText: 'Sí' }).click();
  await expect(h.page.locator('.bx-notice')).toContainText('no se tomó tu respuesta');
  await h.page.locator('.bx-card .bx-btn', { hasText: 'Sí' }).click();
  await expect.poll(answers).toEqual([{ approve: true, card: 'c1' }, { approve: true, card: 'c1' }]);
});

const voice = () => h.calls.filter((c) => c.path === '/voice/trigger' || c.path === '/voice/release').map((c) => c.path);

test('mantener para hablar: si la ventana pierde el foco con el espacio pulsado, el oído se suelta', async () => {
  h = await openView({ mic: 'ptt' });
  await h.page.keyboard.down(' ');
  await expect.poll(voice).toEqual(['/voice/trigger']);
  // Alt+Tab with the space held: the key's release goes to another window
  await h.page.evaluate(() => window.dispatchEvent(new Event('blur')));
  await expect.poll(voice).toEqual(['/voice/trigger', '/voice/release']);
});

test('mantener para hablar: un toque que el sistema cancela suelta el oído', async () => {
  h = await openView({ mic: 'ptt' });
  const mic = h.page.locator('.bx-mic');
  await mic.dispatchEvent('pointerdown', { pointerId: 1, pointerType: 'touch', isPrimary: true, button: 0 });
  await expect.poll(voice).toEqual(['/voice/trigger']);
  await mic.dispatchEvent('pointercancel', { pointerId: 1, pointerType: 'touch', isPrimary: true });
  await expect.poll(voice).toEqual(['/voice/trigger', '/voice/release']);
});

async function renaming() {
  h.reply('/sessions', () => ({ body: { sessions: [{ id: 's1', label: 'Mañana', ts: '10:00', current: true, turn_count: 2 }, { id: 's2', label: 'Ayer', ts: 'ayer', current: false, turn_count: 5 }] } }));
  await h.page.locator('button', { hasText: 'Sesiones' }).first().click();
  await h.page.locator('.bx-mem-row', { hasText: 'Ayer' }).locator('.bx-lnk').click();
  const input = h.page.locator('input[aria-label="Nombre de la sesión"]');
  await input.fill('Compras');
  return input;
}
const renames = () => h.calls.filter((c) => c.path === '/sessions/rename').map((c) => c.body);

test('sesiones: Esc al renombrar deja el nombre como estaba y el panel abierto', async () => {
  h = await openView();
  const input = await renaming();
  await input.press('Escape');
  await h.page.waitForTimeout(300);
  expect(renames()).toEqual([]);
  await expect(h.page.locator('.panel', { hasText: 'Sesiones' })).toBeVisible();
});

test('sesiones: Enter al renombrar renombra una vez', async () => {
  h = await openView();
  const input = await renaming();
  await input.press('Enter');
  await h.page.waitForTimeout(300);
  expect(renames()).toEqual([{ id: 's2', title: 'Compras' }]);
});

test('Esc con el menú del micrófono abierto cierra el menú y no rechaza la tarjeta', async () => {
  h = await openView({ items: [card('c1')] });
  await h.page.locator('.bx-caret').click();
  await expect(h.page.locator('.bx-micmenu')).toBeVisible();
  await h.page.keyboard.press('Escape');
  await expect(h.page.locator('.bx-micmenu')).toHaveCount(0);
  await h.page.waitForTimeout(300);
  expect(answers()).toEqual([]);
});

const box = () => h.page.locator('input[aria-label="Escribe a BAXY"]');

test('un pedido que el host no tomó vuelve a la caja, no se pierde', async () => {
  h = await openView();
  h.reply('/turn', () => ({ status: 503 }));
  await box().fill('abre la calculadora');
  await box().press('Enter');
  await expect(h.page.locator('.bx-notice')).toContainText('no pudo recibir el pedido');
  await expect(box()).toHaveValue('abre la calculadora');
});

test('un pedido que el host tomó deja la caja vacía', async () => {
  h = await openView();
  await box().fill('abre la calculadora');
  await box().press('Enter');
  await expect.poll(() => h.calls.filter((c) => c.path === '/turn').map((c) => c.body)).toEqual([{ text: 'abre la calculadora' }]);
  await expect(box()).toHaveValue('');
});

test('la caja no admite más de lo que el host acepta (4096 caracteres)', async () => {
  // MissionInput.MaximumCharacters: a longer request is refused as invalid_text
  h = await openView();
  await box().fill('a'.repeat(5000));
  await box().press('Enter');
  await expect.poll(() => h.calls.filter((c) => c.path === '/turn').map((c) => (c.body as { text: string }).text.length)).toEqual([4096]);
});

test('accesibilidad: la opción elegida de cada selector y lo que despliega cada botón se anuncian', async () => {
  h = await openView({ items: [{ who: 'baxy', id: 'b1', ts: '12:00', text: 'Listo.', steps: [{ id: 'st1', label: 'Abrir la calculadora', fam: 'apps', status: 'ok', obs: 'Ventana a la vista' }] }] });
  const p = h.page;
  // a step's chip opens what it observed
  const chip = p.getByRole('button', { name: /Abrir la calculadora/ });
  await expect(chip).toHaveAttribute('aria-expanded', 'false');
  await chip.click();
  await expect(chip).toHaveAttribute('aria-expanded', 'true');
  // the microphone's menu
  const caret = p.getByRole('button', { name: 'Modo de micrófono' });
  await expect(caret).toHaveAttribute('aria-expanded', 'false');
  await caret.click();
  await expect(caret).toHaveAttribute('aria-expanded', 'true');
  await p.keyboard.press('Escape');
  // Ajustes: the theme chosen
  await p.locator('.bx-gear').click();
  await expect(p.getByRole('button', { name: 'Oscuro', pressed: true })).toHaveCount(1);
  await expect(p.getByRole('button', { name: 'Claro', pressed: false })).toHaveCount(1);
});

const surfaces = (memory_revision: number) => ({ type: 'surfaces', sessions: 2, memory: 1, memory_revision, tools: 10, triggers: 0 });
const later = (ms: number) => new Promise((r) => setTimeout(r, ms));

test('memoria: una lectura vieja que llega tarde no tapa la nueva', async () => {
  h = await openView();
  h.emit(surfaces(1));
  let n = 0, saved = false;
  h.reply('/memory', async () => {
    n++;
    const first = !saved;
    if (first) await later(900);
    return { body: { enabled: true, total: 1, items: [{ key: 'k', value: first ? 'color: azul' : 'color: verde', updated_at: '', kind: 'preference' }] } };
  });
  await h.page.locator('button', { hasText: 'Memoria' }).first().click();
  await expect.poll(() => n).toBeGreaterThan(0);
  saved = true;
  h.emit(surfaces(2)); // BAXY saved something while the panel read
  await expect(h.page.locator('.bx-mem-row')).toContainText('verde');
  await h.page.waitForTimeout(1200);
  await expect(h.page.locator('.bx-mem-row')).toContainText('verde');
});
