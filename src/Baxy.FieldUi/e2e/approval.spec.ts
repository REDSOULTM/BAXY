import { expect, test } from '@playwright/test';
import { card, openView, stopHost, type Host } from './host';

/* OVL1: the Sí of a card authorizes an effect, so a press meant for something else must not reach it. It takes a
   press, of the mouse or of a key, only if the person made it after the Sí was drawn lit, and it is drawn lit only once
   it has been in its place, off, for its whole wait (approval.ts; the overlay's rule, ApprovalGuard.cs). No and Esc
   are never held. Against the stand-in host (host.ts): headless, it never needs BAXY running. */

let h: Host;
test.afterEach(async () => { await h?.close(); });
test.afterAll(async () => { await stopHost(); });

const WAIT = 1000;
/** What the page itself noted, by its own clock: a loaded machine can hold the test up for longer than the Sí's wait,
 *  so what the Sí looked like and when a press came are read from here, not from when the test got to look. */
type Noted = { pressedAt: number; looks: { at: number; off: boolean; held: boolean; how: string }[]; look: () => void };
const open = async (init?: Parameters<typeof openView>[0]) => {
  h = await openView(init);
  await h.page.evaluate(() => {
    const w = window as unknown as Noted;
    w.pressedAt = -1;
    w.looks = [];
    for (const type of ['pointerdown', 'keydown', 'click']) window.addEventListener(type, (e) => { w.pressedAt = e.timeStamp; }, true);
    w.look = () => {
      const si = document.querySelector('.bx-card.s-pending .bx-btn.yes');
      if (!si) return;
      const s = getComputedStyle(si);
      w.looks.push({ at: performance.now(), off: si.classList.contains('off'), held: si.getAttribute('aria-disabled') === 'true', how: s.backgroundColor + ' ' + s.cursor });
    };
    new MutationObserver(w.look).observe(document.body, { subtree: true, childList: true, attributes: true, attributeFilter: ['class', 'aria-disabled'] });
  });
};
const answers = () => h.calls.filter((c) => c.path === '/confirmation/answer').map((c) => c.body);
const yes = () => h.page.locator('.bx-card.s-pending .bx-btn.yes');
/** the page's clock now: taken before what turns the Sí off, it is a time the Sí's wait cannot have begun before. */
const mark = () => h.page.evaluate(() => { const at = performance.now(); (window as unknown as Noted).look(); return at; });
/** How the Sí looked when, since that mark (and before that time, if given), it was off and said it took no press. */
const dark = (since: number, before = Number.MAX_VALUE) => h.page.evaluate(
  ([from, to]) => (window as unknown as Noted).looks.find((l) => l.at >= from && l.at < to && l.off && l.held)?.how ?? null, [since, before]);
const off = (since: number) => expect.poll(() => dark(since), { message: 'el Sí se apagó' }).not.toBeNull();
/** the Sí looks ready and, drawn so, says it takes presses. */
const lit = async () => { await expect(yes()).not.toHaveClass(/\boff\b/); await expect(yes()).toHaveAttribute('aria-disabled', 'false'); };
/** the mouse itself on the middle of a button, as a hand does it: no waiting for the button to be ready. */
const press = async (label: string) => {
  const b = (await h.page.locator('.bx-card.s-pending .bx-btn', { hasText: label }).boundingBox())!;
  await h.page.mouse.click(b.x + b.width / 2, b.y + b.height / 2);
};
/** A press that by the page's clock did not come before the Sí's wait could be over proves nothing about early
 *  presses: the test is skipped saying so, neither failed nor passed. */
const early = (at: number, since: number) => test.skip(at - since >= WAIT,
  `la máquina retuvo la prueba: ${Math.round(at - since)} ms desde la marca, ya no es una pulsación temprana`);
/** Nothing was answered; `since` is the mark the press just made had to come early after. */
const nothing = async (since?: number) => {
  await h.page.waitForTimeout(300);
  if (since !== undefined) early(await h.page.evaluate(() => (window as unknown as Noted).pressedAt), since);
  expect(answers()).toEqual([]);
};
const arrives = async (id: string) => {
  const since = await mark();
  h.emit({ type: 'item', item: card(id) });
  await expect(yes()).toBeVisible();
  return since;
};

test('un clic al Sí recién aparecido no aprueba, y el Sí se ve apagado; pasada su espera, aprueba', async () => {
  await open();
  const since = await arrives('c1');
  await press('Sí');
  await nothing(since);
  // how it looked from its arrival until that press
  const was = await dark(since, await h.page.evaluate(() => (window as unknown as Noted).pressedAt));
  expect(was, 'el Sí llegó apagado').not.toBeNull();
  await lit();
  const ready = await yes().evaluate((b) => { const s = getComputedStyle(b); return s.backgroundColor + ' ' + s.cursor; });
  expect(ready, 'apagado no se ve como encendido').not.toBe(was);
  expect(ready).toContain('pointer');
  expect(was).not.toContain('pointer');
  await press('Sí');
  await expect.poll(answers).toEqual([{ approve: true, card: 'c1' }]);
});

test('Enter con la tarjeta recién llegada no aprueba; pasada la espera, sí', async () => {
  await open();
  await h.page.locator('.bx-line > input').focus();
  const since = await arrives('c1');
  await h.page.keyboard.press('Enter');
  await nothing(since);
  await lit();
  await h.page.keyboard.press('Enter');
  await expect.poll(answers).toEqual([{ approve: true, card: 'c1' }]);
});

test('Espacio o Enter con el foco recién puesto en el Sí no aprueban; pasada la espera, Espacio sí', async () => {
  await open();
  const since = await arrives('c1');
  await yes().focus();
  await h.page.keyboard.press(' ');
  await h.page.keyboard.press('Enter');
  await nothing(since);
  await lit();
  await expect(yes()).toBeFocused();
  await h.page.keyboard.press(' ');
  await expect.poll(answers).toEqual([{ approve: true, card: 'c1' }]);
});

test('No y Esc responden en cualquier momento', async () => {
  await open();
  await arrives('c1');
  await press('No');
  await expect.poll(answers).toEqual([{ approve: false, card: 'c1' }]);
  h.emit({ type: 'item', item: card('c1', { status: 'no' }) });
  await arrives('c2');
  await h.page.waitForTimeout(150); // the keys follow the card once the view's effects ran
  await h.page.keyboard.press('Escape');
  await expect.poll(answers).toEqual([{ approve: false, card: 'c1' }, { approve: false, card: 'c2' }]);
});

// The cause in the overlay (VIVO2 9c): the thread was busy when the card arrived, and a click made 240 ms after the Sí
// was painted was handled 560 ms after it, past the guard. What counts is when the person pressed: the time the event
// carries. Events made with the Sí off and delivered once it is lit are that press, whatever held them up.
test('cuenta cuándo se hizo la pulsación, no cuándo se atiende', async () => {
  await open();
  const since = await arrives('c1');
  const make = () => h.page.evaluate(() => {
    const r = document.querySelector('.bx-card.s-pending .bx-btn.yes')!.getBoundingClientRect();
    const at = { bubbles: true, cancelable: true, clientX: r.left + r.width / 2, clientY: r.top + r.height / 2, button: 0 };
    (window as unknown as { made: Event[] }).made = [new PointerEvent('pointerdown', { ...at, pointerId: 1, pointerType: 'mouse' }), new MouseEvent('click', at),
      new KeyboardEvent('keydown', { bubbles: true, cancelable: true, key: 'Enter' })];
  });
  const deliver = (from: number, to: number) => h.page.evaluate(([a, b]) => {
    const si = document.querySelector('.bx-card.s-pending .bx-btn.yes')!;
    for (const e of (window as unknown as { made: Event[] }).made.slice(a, b)) (e.type === 'keydown' ? document.body : si).dispatchEvent(e);
  }, [from, to]);
  await make();
  await lit();
  await deliver(0, 2);
  await nothing(since);
  await lit();
  await deliver(2, 3); // the Enter of then
  await nothing(since);
  await lit();
  await make(); // the same events, made with the Sí lit
  await deliver(0, 2);
  await expect.poll(answers).toEqual([{ approve: true, card: 'c1' }]);
  h.emit({ type: 'item', item: card('c1', { status: 'yes' }) });
  await arrives('c2');
  await lit();
  await make();
  await deliver(2, 3);
  await expect.poll(answers).toEqual([{ approve: true, card: 'c1' }, { approve: true, card: 'c2' }]);
});

test('una pulsación hecha con el hilo ocupado y el Sí aún apagado no aprueba por tarde que se atienda', async () => {
  await open();
  await h.page.evaluate(() => {
    window.addEventListener('pointerdown', (e) => { Object.assign(window, { downAt: e.timeStamp, late: performance.now() - e.timeStamp }); }, true);
  });
  await arrives('c1');
  const b = (await yes().boundingBox())!;
  await h.page.mouse.move(b.x + b.width / 2, b.y + b.height / 2);
  await h.page.waitForTimeout(350);
  // nothing is drawn while the thread is busy: a Sí off when the burst begins is off for every press made before its end
  const busy = h.page.evaluate(() => {
    const dark = document.querySelector('.bx-card.s-pending .bx-btn.yes')!.classList.contains('off');
    const end = performance.now() + 1400;
    while (performance.now() < end) { /* a burst of work */ }
    return { dark, end };
  });
  await h.page.waitForTimeout(150);
  await h.page.mouse.down();
  await h.page.mouse.up();
  const burst = await busy;
  await h.page.waitForTimeout(300);
  const down = await h.page.evaluate(() => { const w = window as unknown as { downAt: number; late: number }; return { at: w.downAt, late: w.late }; });
  test.skip(!burst.dark || down.at >= burst.end, 'la máquina retuvo la prueba: la pulsación no cayó con el hilo ocupado y el Sí apagado');
  expect(answers()).toEqual([]);
  expect(down.late, 'la pulsación se atendió tarde').toBeGreaterThan(500);
  await lit();
  await press('Sí');
  await expect.poll(answers).toEqual([{ approve: true, card: 'c1' }]);
});

test('una tecla que sigue pulsada desde antes no aprueba al repetirse; soltada y pulsada de nuevo, sí', async () => {
  await open();
  await h.page.locator('.bx-line > input').focus();
  const since = await arrives('c1');
  await h.page.keyboard.down('Enter');
  early(await h.page.evaluate(() => (window as unknown as Noted).pressedAt), since);
  await lit();
  await h.page.keyboard.down('Enter'); // the same press, repeating
  await h.page.keyboard.down('Enter');
  await nothing();
  await h.page.keyboard.up('Enter');
  await lit();
  await h.page.keyboard.press('Enter');
  await expect.poll(answers).toEqual([{ approve: true, card: 'c1' }]);
});

// What a tool does that presses the button without a mouse (an assistive tool's invoke, a script's click()).
test('un clic sin pulsación de ratón cuenta desde que se atiende', async () => {
  await open();
  const since = await arrives('c1');
  const invoke = () => yes().evaluate((b: HTMLElement) => b.click());
  await invoke();
  await nothing(since);
  await lit();
  await invoke();
  await expect.poll(answers).toEqual([{ approve: true, card: 'c1' }]);
});

test('Enter no aprueba a través de un Sí que no está a la vista; al volver a verse, empieza su espera', async () => {
  await open({ items: [card('c1')] });
  await h.page.locator('.bx-line > input').focus();
  await lit();
  const show = (how: string) => h.page.locator('.bx-card.s-pending').evaluate((c: HTMLElement, v) => { c.style.visibility = v; }, how);
  await show('hidden'); // drawn nowhere, its place kept: as the conversation folded away
  await h.page.waitForTimeout(1300);
  await h.page.keyboard.press('Enter');
  await nothing();
  let since = await mark();
  await show('');
  await off(since);
  await h.page.keyboard.press('Enter');
  await nothing(since);
  await lit();

  // under something else: a press on its middle would not reach it
  await h.page.evaluate(() => {
    const r = document.querySelector('.bx-card.s-pending .bx-btn.yes')!.getBoundingClientRect();
    const over = document.createElement('div');
    over.id = 'over';
    over.style.cssText = `position:fixed;z-index:99999;left:${r.left - 4}px;top:${r.top - 4}px;width:${r.width + 8}px;height:${r.height + 8}px;background:#123`;
    document.body.append(over);
  });
  await h.page.waitForTimeout(1300);
  await h.page.keyboard.press('Enter');
  await nothing();
  since = await mark();
  await h.page.evaluate(() => document.getElementById('over')!.remove());
  await off(since);
  await h.page.keyboard.press('Enter');
  await nothing(since);
  await lit();
  await h.page.keyboard.press('Enter');
  await expect.poll(answers).toEqual([{ approve: true, card: 'c1' }]);
});

test('con la ventana recién enfocada, ni Enter ni el ratón aprueban hasta pasada la espera', async () => {
  await open({ items: [card('c1')] });
  await h.page.locator('.bx-line > input').focus();
  await lit();
  const focused = () => h.page.evaluate(() => {
    const hint = () => document.querySelector('.bx-card.s-pending .bx-btn.yes kbd')!.classList.contains('off');
    window.dispatchEvent(new Event('blur'));
    window.dispatchEvent(new Event('focus'));
    // the hint of the Sí's Enter, once the view drew what the focus changed
    return new Promise<boolean>((seen) => requestAnimationFrame(() => requestAnimationFrame(() => seen(hint()))));
  });
  const since = await mark();
  expect(await focused(), 'la pista de Enter se apaga').toBe(true);
  await h.page.keyboard.press('Enter');
  await nothing(since);
  await lit();
  await expect(yes().locator('kbd')).not.toHaveClass(/\boff\b/);
  await h.page.keyboard.press('Enter');
  await expect.poll(answers).toEqual([{ approve: true, card: 'c1' }]);

  // the click that brings the window up was meant for whatever was over it: the Sí is off and waits again
  h.emit({ type: 'item', item: card('c1', { status: 'yes' }) });
  await arrives('c2');
  await lit();
  const again = await mark();
  await focused();
  await off(again);
  await press('Sí');
  await h.page.waitForTimeout(300);
  early(await h.page.evaluate(() => (window as unknown as Noted).pressedAt), again);
  expect(answers()).toEqual([{ approve: true, card: 'c1' }]);
  await lit();
  await press('Sí');
  await expect.poll(answers).toEqual([{ approve: true, card: 'c1' }, { approve: true, card: 'c2' }]);
});

test('sin el foco la ventana puede estar tapada: el Sí sigue apagado por mucho que espere, y espera de nuevo al volver el foco', async () => {
  await open({ items: [card('c1')] });
  await lit();
  const since = await mark();
  await h.page.evaluate(() => {
    Object.defineProperty(document, 'hasFocus', { value: () => false, configurable: true });
    window.dispatchEvent(new Event('blur'));
  });
  await off(since);
  await h.page.waitForTimeout(WAIT + 500);
  await expect(yes()).toHaveClass(/\boff\b/);
  await press('Sí');
  await h.page.waitForTimeout(300);
  expect(answers(), 'un clic sobre el Sí de una ventana sin el foco no aprueba').toEqual([]);

  await h.page.evaluate(() => {
    delete (document as unknown as { hasFocus?: unknown }).hasFocus;
    window.dispatchEvent(new Event('focus'));
  });
  await lit();
  await press('Sí');
  await expect.poll(answers).toEqual([{ approve: true, card: 'c1' }]);
});

test('un Sí que se movió, que cambió de tamaño, que vuelve a verse o que es de otra confirmación empieza su espera otra vez', async () => {
  await open({ items: [card('c1')] });
  await lit();
  const box = async () => { const b = (await yes().boundingBox())!; return [b.x, b.y, b.width, b.height]; };
  let was = await box();
  let since = await mark();
  await h.page.locator('.bx-card.s-pending').evaluate((c) => { c.style.marginBottom = '40px'; });
  let now = await box();
  expect(now.slice(0, 2), 'la tarjeta se movió').not.toEqual(was.slice(0, 2));
  expect(now.slice(2), 'y no cambió de tamaño').toEqual(was.slice(2));
  await off(since);
  await press('Sí');
  await nothing(since);
  await lit();

  was = now;
  since = await mark();
  await yes().evaluate((b: HTMLElement) => { b.style.minWidth = `${b.offsetWidth + 24}px`; }); // as a larger text size does
  now = await box();
  expect(now.slice(2), 'el Sí cambió de tamaño').not.toEqual(was.slice(2));
  await off(since);
  await press('Sí');
  await nothing(since);
  await lit();

  since = await mark();
  await h.page.evaluate(() => document.dispatchEvent(new Event('visibilitychange')));
  await off(since);
  await press('Sí');
  await nothing(since);
  await lit();

  h.emit({ type: 'item', item: card('c1', { status: 'no' }) });
  since = await arrives('c2');
  await off(since);
  await press('Sí');
  await nothing(since);
  await lit();

  was = await box();
  since = await mark();
  h.emit({ type: 'item', item: card('c2', { title: 'Borrar todo.txt' }) }); // the same card, asking for something else
  await expect(h.page.locator('.bx-card.s-pending .ti')).toHaveText('Borrar todo.txt');
  expect(await box(), 'el Sí sigue en su sitio').toEqual(was);
  await off(since);
  await press('Sí');
  await nothing(since);
  await lit();
  await press('Sí');
  await expect.poll(answers).toEqual([{ approve: true, card: 'c2' }]);
});
