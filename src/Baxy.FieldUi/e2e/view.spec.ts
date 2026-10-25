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
