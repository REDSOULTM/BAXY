import { expect, test, type Page } from '@playwright/test';
import { card, openView, stopHost, type Host, type Reply } from './host';
import { CONFIRM_CARD } from './app';

/* The view's logic against a stand-in host (host.ts): what the person does reaches the host once, for the right card,
   and nothing the view started stays alive. Headless; it never needs BAXY running. */

let h: Host;
test.afterEach(async () => { await h?.close(); });
test.afterAll(async () => { await stopHost(); });

const answers = () => h.calls.filter((c) => c.path === '/confirmation/answer').map((c) => c.body);
/** OVL1 (approval.spec): the Sí of the card waiting takes a press or its Enter only once it has been drawn in its
 *  place, off, for its wait. Bringing it into view moves it, so that comes first. */
const siReady = async (page: Page) => {
  const yes = page.locator('.bx-card.s-pending .bx-btn.yes').last();
  await yes.scrollIntoViewIfNeeded();
  await page.evaluate(() => new Promise((seen) => requestAnimationFrame(() => requestAnimationFrame(seen))));
  await expect(yes).toHaveAttribute('aria-disabled', 'false');
};

test('Enter sobre el botón «No» de una tarjeta responde No, no Sí', async () => {
  h = await openView({ items: [card('c1')] });
  await h.page.locator('.bx-card .bx-btn', { hasText: 'No' }).focus();
  await h.page.keyboard.press('Enter');
  await expect.poll(answers).toHaveLength(1);
  expect(answers()).toEqual([{ approve: false, card: 'c1' }]);
});

test('Enter en la caja de texto vacía responde Sí; Esc sobre un botón responde No', async () => {
  h = await openView({ items: [card('c1'), card('c2')] });
  await h.page.locator('.bx-line > input').focus();
  await siReady(h.page);
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
  await siReady(h.page);
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
  await siReady(h.page);
  await h.page.locator('.bx-card .bx-btn', { hasText: 'Sí' }).click();
  await expect(h.page.locator('.bx-notice')).toContainText('no se tomó tu respuesta');
  await siReady(h.page);
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

test('siempre activo: un clic en la ventana no abre el oído como mantener para hablar', async () => {
  // Uso real 03-11: the owner clicked the window to focus it and BAXY took it as the held space, transcribing all he
  // said. Only the wake word, the held space or the microphone button open the ear.
  h = await openView({ mic: 'always' });
  h.emit({ type: 'voice', available: true, mode: 'wake', speaking: false });
  await h.page.locator('.bx-graph').click();
  await h.page.waitForTimeout(300);
  expect(voice()).toEqual([]);
});

test('sin palabra de activación, «Siempre activo» dice por qué no responde y lo sigue diciendo', async () => {
  // V132 (1.3.2): the product's wake folder gone or changed: the ear starts without it, the person's «Siempre activo»
  // (the default) could not start, and the view showed the microphone off and nothing more.
  h = await openView({ mic: 'always' });
  h.reply('/voice/start', () => ({ body: { running: false } }));
  h.emit({ type: 'voice', available: true, mode: 'off', speaking: false, last_error: 'wake_unavailable', no_wake: true, wake_problem: 'wake_missing' });
  const p = h.page;
  await expect(p.locator('.bx-notice')).toContainText('Sin palabra de activación');
  await expect(p.locator('.bx-notice')).toContainText('falta su detector');
  await p.waitForTimeout(3200); // longer than a passing notice lasts
  await expect(p.locator('.bx-notice')).toContainText('Sin palabra de activación');
  await expect(p.locator('.bx-line > input')).not.toHaveAttribute('placeholder', /BAXY»/);
  await p.locator('.bx-caret').click();
  await expect(p.locator('.bx-micmenu button', { hasText: 'Siempre activo' })).toBeDisabled();
  await expect(p.locator('.bx-micmenu button', { hasText: 'Siempre activo' })).toContainText('falta su detector');
  await expect(p.locator('.bx-micmenu button').nth(2)).toContainText('O la barra espaciadora');
  await expect(p.locator('.bx-micmenu button').nth(2)).toBeEnabled();
  // the person's own choice ends it
  await p.locator('.bx-micmenu button', { hasText: 'Apagado' }).click();
  await p.waitForTimeout(3200);
  await expect(p.locator('.bx-notice')).toHaveCount(0);
});

test('un detector que no es el instalado se dice como tal, y con la palabra de activación no hay aviso', async () => {
  h = await openView({ mic: 'always' });
  h.emit({ type: 'voice', available: true, mode: 'off', speaking: false, no_wake: true, wake_problem: 'wake_changed' });
  await expect(h.page.locator('.bx-notice')).toContainText('no es el que se instaló');
  h.emit({ type: 'voice', available: true, mode: 'wake', speaking: false, no_wake: false });
  await expect(h.page.locator('.bx-notice')).toHaveCount(0);
});

test('sin palabra de activación: nada mientras la mente arranca otra vez, y Ajustes no aplica «Siempre» y dice por qué', async () => {
  // Review (V132): a mind starting again still had the last one's ear; Ajustes offered «Siempre» as if it worked.
  h = await openView({ mic: 'always' });
  const p = h.page;
  h.emit({ type: 'boot', stt: null, wake: null, tts: null, model: false, startedAt: 1, readyAt: null });
  h.emit({ type: 'voice', available: true, mode: 'off', speaking: false, no_wake: true, wake_problem: 'wake_missing' });
  await p.waitForTimeout(600);
  await expect(p.locator('.bx-notice', { hasText: 'Sin palabra de activación' })).toHaveCount(0);
  h.emit({ type: 'boot', stt: true, wake: false, tts: true, model: true, startedAt: 1, readyAt: 2 });
  await expect(p.locator('.bx-notice')).toContainText('Sin palabra de activación');
  await p.locator('.bx-gear').click();
  await p.locator('.settings-panel button', { hasText: /^Voz$/ }).click();
  await expect(p.locator('.settings-panel')).toContainText('falta su detector');
  await p.getByRole('radio', { name: 'Al pulsar' }).click();
  await expect.poll(() => h.calls.some((c) => c.path === '/voice/stop')).toBe(true);
  const starts = h.calls.filter((c) => c.path === '/voice/start').length;
  await p.getByRole('radio', { name: 'Siempre' }).click();
  await p.waitForTimeout(400);
  expect(h.calls.filter((c) => c.path === '/voice/start').length).toBe(starts);
});

test('sin reconocedor, el menú del micrófono dice que falta el reconocimiento, no que no hay micrófono', async () => {
  // N23 (uso-116) said it on the host, and the view's store dropped it on the way.
  h = await openView();
  h.emit({ type: 'voice', available: false, mode: 'off', speaking: false, no_recognizer: true });
  await h.page.locator('.bx-caret').click();
  await expect(h.page.locator('.bx-micmenu')).toContainText('Falta el reconocimiento de voz');
});

async function renaming() {
  h.reply('/sessions', () => ({ body: { sessions: [{ id: 's1', label: 'Mañana', ts: '10:00', current: true, turn_count: 2 }, { id: 's2', label: 'Ayer', ts: 'ayer', current: false, turn_count: 5 }] } }));
  await h.page.locator('button', { hasText: 'Historial' }).first().click();
  await h.page.locator('.bx-mem-row', { hasText: 'Ayer' }).locator('.bx-lnk').click();
  const input = h.page.locator('input[aria-label="Nombre de la sesión"]');
  await input.fill('Compras');
  return input;
}
const renames = () => h.calls.filter((c) => c.path === '/sessions/rename').map((c) => c.body);

// Owner, 2026-11-08: «me falta un botón de volver a ver las conversaciones anteriores … una rueda de tiempo … así vuelvo
// a la conversación anterior que estaba teniendo». A clock beside «Nueva conversación» opens them, with name and date.
test('conversaciones anteriores: el reloj del chat abre la lista y elegir una vuelve a ella', async () => {
  h = await openView();
  h.reply('/sessions', () => ({ body: { sessions: [{ id: 's1', label: 'Conversación nueva', ts: 'ahora', current: true, turn_count: 0 }, { id: 's2', label: 'Clima de mañana en Viña', ts: 'ayer, 21:40', current: false, turn_count: null }] } }));
  await h.page.getByRole('button', { name: 'Conversaciones anteriores' }).click();
  const panel = h.page.locator('.panel', { hasText: 'Historial de conversaciones' });
  await expect(panel.locator('.bx-mem-row', { hasText: 'Clima de mañana en Viña' })).toContainText('ayer, 21:40');
  await panel.getByRole('button', { name: 'Clima de mañana en Viña', exact: true }).click();
  await expect.poll(() => h.calls.filter((c) => c.path === '/sessions/load').map((c) => c.body)).toEqual([{ id: 's2' }]);
});

test('conversaciones anteriores: el nombre que pone el modelo al cerrarla aparece en la lista abierta', async () => {
  h = await openView();
  let label = 'qué tiempo hace mañana en viña';
  h.reply('/sessions', () => ({ body: { sessions: [{ id: 's1', label: 'Conversación nueva', ts: 'ahora', current: true, turn_count: 0 }, { id: 's2', label, ts: '21:40', current: false, turn_count: null }] } }));
  await h.page.getByRole('button', { name: 'Conversaciones anteriores' }).click();
  await expect(h.page.locator('.bx-mem-row', { hasText: label })).toBeVisible();
  label = 'Clima de mañana en Viña';
  h.emit({ type: 'surfaces', sessions: 2, memory: null, tools: 40, triggers: null, sessions_revision: 1 });
  await expect(h.page.locator('.bx-mem-row', { hasText: 'Clima de mañana en Viña' })).toBeVisible();
});

// REV_APP ASY-b / HIS-1 (2026-11-09): a conversation the disk did not take looked kept until BAXY closed.
test('conversaciones anteriores: una que no se pudo guardar lo dice, y deja de decirlo cuando se guarda', async () => {
  h = await openView();
  let unsaved = true;
  h.reply('/sessions', () => ({ body: { sessions: [{ id: 's1', label: 'hola', ts: 'ahora', current: true, turn_count: 1 }], unsaved } }));
  await h.page.getByRole('button', { name: 'Conversaciones anteriores' }).click();
  const panel = h.page.locator('.panel', { hasText: 'Historial de conversaciones' });
  await expect(panel.getByRole('status')).toContainText('No pude guardar esta conversación en el disco');
  unsaved = false;
  h.emit({ type: 'surfaces', sessions: 1, memory: null, tools: 40, triggers: null, sessions_revision: 1 });
  await expect(panel.locator('.bx-mem-row', { hasText: 'hola' })).toBeVisible();
  await expect(panel.getByText('No pude guardar esta conversación')).toHaveCount(0);
});

test('sesiones: Esc al renombrar deja el nombre como estaba y el panel abierto', async () => {
  h = await openView();
  const input = await renaming();
  await input.press('Escape');
  await h.page.waitForTimeout(300);
  expect(renames()).toEqual([]);
  await expect(h.page.locator('.panel', { hasText: 'Historial' })).toBeVisible();
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

const box = () => h.page.locator('.bx-line > input');

test('un pedido que el host rechazó vuelve a la caja, no se pierde', async () => {
  h = await openView();
  h.reply('/turn', () => ({ status: 409, body: { ok: false, error: 'agent_not_ready' } }));
  await box().fill('abre la calculadora');
  await box().press('Enter');
  await expect(h.page.locator('.bx-notice')).toContainText('no pudo recibir el pedido');
  await expect(box()).toHaveValue('abre la calculadora');
});

test('un pedido sin respuesta del host (plazo del puente agotado) no vuelve a la caja: pudo haberse tomado', async () => {
  h = await openView();
  // field-native-bridge.js: a request that timed out or failed in the bridge answers 503 with no host refusal
  h.reply('/turn', () => ({ status: 503, body: { error: 'Error: BAXY native request timed out: http' } }));
  await box().fill('abre la calculadora');
  await box().press('Enter');
  await expect(h.page.locator('.bx-notice')).toContainText('no pudo recibir el pedido');
  await expect(box()).toHaveValue('');
});

test('un pedido que el host tomó deja la caja vacía', async () => {
  h = await openView();
  await box().fill('abre la calculadora');
  await box().press('Enter');
  await expect.poll(() => h.calls.filter((c) => c.path === '/turn').map((c) => c.body)).toEqual([{ text: 'abre la calculadora' }]);
  await expect(box()).toHaveValue('');
});

test('un pedido de más de 4096 caracteres no se recorta ni se envía: se dice por qué y queda en la caja', async () => {
  // MissionInput.MaximumCharacters (UTF-16): the host refuses a longer request as invalid_text
  h = await openView();
  await box().fill('a'.repeat(5000));
  await box().press('Enter');
  await expect(h.page.locator('.bx-notice')).toContainText('4096');
  expect(h.calls.filter((c) => c.path === '/turn')).toEqual([]);
  await expect(box()).toHaveValue('a'.repeat(5000));
});

test('COX-1: 7.000 caracteres pegados dicen el límite mientras sigan en la caja, no sólo un momento', async () => {
  // VIVO4 D4: the notice lasted 2.6 s and the text stayed in the box; whoever looked a moment later saw no reason
  h = await openView();
  const pasted = 'Texto pegado de un documento largo. '.repeat(200).slice(0, 6999) + '.';
  await box().focus();
  await h.page.keyboard.insertText(pasted);
  await expect(h.page.locator('.bx-notice')).toContainText('máximo 4096 caracteres');
  await box().press('Enter');
  await h.page.waitForTimeout(3500);
  await expect(h.page.locator('.bx-notice')).toContainText('máximo 4096 caracteres');
  await expect(h.page.getByRole('status')).toContainText('4096');
  expect(h.calls.filter((c) => c.path === '/turn')).toEqual([]);
  await expect(box()).toHaveValue(pasted);
  // shortened to the limit, the notice goes and the request is sent whole
  await box().fill(pasted.slice(0, 4096));
  await expect(h.page.locator('.bx-notice')).toHaveCount(0);
  await box().press('Enter');
  await expect.poll(() => h.calls.filter((c) => c.path === '/turn').map((c) => (c.body as { text: string }).text.length)).toEqual([pasted.slice(0, 4096).trim().length]);
});

test('accesibilidad: la opción elegida de cada selector y lo que despliega cada botón se anuncian', async () => {
  h = await openView({ items: [{ who: 'baxy', id: 'b1', ts: '12:00', text: 'Listo.', steps: [{ id: 'st1', label: 'Abrir la calculadora', fam: 'apps', status: 'ok', obs: 'Ventana a la vista' }] }] });
  const p = h.page;
  // interfaz v5: «Cómo lo comprobé» opens each step with what it observed; the card says how the request ended
  await expect(p.locator('.bx-c4-baxy')).toHaveAttribute('aria-label', 'Respuesta de BAXY: Hecho y comprobado');
  const how = p.getByRole('button', { name: /Cómo lo comprobé/ });
  await expect(how).toHaveAttribute('aria-expanded', 'false');
  await how.click();
  await expect(how).toHaveAttribute('aria-expanded', 'true');
  await expect(p.locator('.bx-how-s')).toContainText('Abrir la calculadora');
  await expect(p.locator('.bx-how-s')).toContainText('Ventana a la vista');
  // the microphone's menu
  const caret = p.getByRole('button', { name: 'Modo de micrófono' });
  await expect(caret).toHaveAttribute('aria-expanded', 'false');
  await caret.click();
  await expect(caret).toHaveAttribute('aria-expanded', 'true');
  await p.keyboard.press('Escape');
  // Ajustes: the theme chosen, in its section (folded: its arrow is announced too)
  await p.locator('.bx-gear').click();
  const appearance = p.getByRole('button', { name: /^Apariencia/ });
  await expect(appearance).toHaveAttribute('aria-expanded', 'false');
  await appearance.click();
  await expect(appearance).toHaveAttribute('aria-expanded', 'true');
  await expect(p.getByRole('button', { name: 'Oscuro', pressed: true })).toHaveCount(1);
  await expect(p.getByRole('button', { name: 'Claro', pressed: false })).toHaveCount(1);
});

// INT13: the detail's title says «Cómo lo comprobé» only when every step was checked or read; a step that was sent
// without a check, failed or did not run is told as what was done, not as a check that did not happen
test('el detalle de una respuesta sólo dice «Cómo lo comprobé» cuando todo se comprobó', async () => {
  h = await openView({ items: [
    { who: 'baxy', id: 'b1', ts: '12:00', text: 'Enviado.', steps: [{ id: 'st1', label: 'Enviar el mensaje', fam: 'apps', status: 'sent', obs: 'Pulsé Enviar' }] },
  ] });
  const p = h.page;
  await expect(p.locator('.bx-c4-baxy')).toHaveAttribute('aria-label', 'Respuesta de BAXY: Hecho, sin poder comprobarlo');
  await expect(p.getByRole('button', { name: /Cómo lo comprobé/ })).toHaveCount(0);
  await expect(p.getByRole('button', { name: /Qué hice · 1 paso/ })).toHaveCount(1);
});

// COR1 (VIVO3 A3): a turn that changed one of BAXY's own settings shows it without a click, never only inside the fold
test('un ajuste de BAXY que cambió en el turno se ve sin abrir «Qué hice»', async () => {
  h = await openView({ items: [
    { who: 'baxy', id: 'b1', ts: '12:00', text: 'Listo, ya puedo buscar en internet.', steps: [{ id: 'st1', label: 'Cambiar un ajuste de BAXY · Búsqueda web: activar', fam: 'ventanas', status: 'ok', obs: 'Verificado', pin: true }] },
    { who: 'baxy', id: 'b2', ts: '12:01', text: 'Abierta.', steps: [{ id: 'st2', label: 'Abrir la calculadora', fam: 'apps', status: 'ok', obs: 'Ventana a la vista' }] },
  ] });
  const p = h.page;
  const folds = p.getByRole('button', { name: /Cómo lo comprobé/ });
  await expect(folds.nth(0)).toHaveAttribute('aria-expanded', 'true');
  await expect(p.locator('.bx-how-s')).toHaveCount(1);
  await expect(p.locator('.bx-how-s')).toContainText('Búsqueda web: activar');
  await expect(folds.nth(1)).toHaveAttribute('aria-expanded', 'false');
});

const surfaces =(memory_revision: number) => ({ type: 'surfaces', sessions: 2, memory: 1, memory_revision, tools: 10, triggers: 0 });
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

test('sesiones: una lista vieja que llega tarde no tapa la nueva', async () => {
  h = await openView();
  h.emit({ type: 'session', id: 's1', label: 'Mañana' });
  let n = 0, renamed = false;
  h.reply('/sessions', async () => {
    n++;
    const first = !renamed;
    if (first) await later(900);
    return { body: { sessions: [{ id: 's1', label: first ? 'Mañana' : 'Compras', ts: '10:00', current: true, turn_count: 2 }] } };
  });
  await h.page.locator('button', { hasText: 'Historial' }).first().click();
  await expect.poll(() => n).toBeGreaterThan(0);
  renamed = true;
  h.emit({ type: 'session', id: 's1', label: 'Compras' }); // renamed by BAXY meanwhile
  await expect(h.page.locator('.bx-sess-t')).toHaveText('Compras');
  await h.page.waitForTimeout(1200);
  await expect(h.page.locator('.bx-sess-t')).toHaveText('Compras');
});

test('memoria: olvidar un recuerdo llamado «all» no pregunta por olvidar todo', async () => {
  h = await openView();
  h.reply('/memory', () => ({ body: { enabled: true, total: 2, items: [
    { key: 'all', value: 'all: todos los días a las 8', updated_at: '', kind: 'rule' },
    { key: 'color', value: 'color: verde', updated_at: '', kind: 'preference' },
  ] } }));
  await h.page.locator('button', { hasText: 'Memoria' }).first().click();
  await h.page.locator('.bx-mem-row', { hasText: 'todos los días' }).getByRole('button', { name: 'Olvidar' }).click();
  await expect(h.page.locator('.bx-mem-row', { hasText: 'todos los días' })).toContainText('¿Olvidar?');
  await expect(h.page.locator('.panel-footer')).not.toContainText('¿Olvidar todo?');
});

test('ajustes: una lectura de los ajustes empezada antes de un cambio no lo deshace en la vista', async () => {
  h = await openView();
  const host = { autostart: false, closeToTray: true, voiceMuted: false, wakeSound: true, waitNotice: true, web: false, weather: true, screen: false };
  let slow = false, reads = 0;
  h.reply('/settings/general', async (c) => {
    if (c.method === 'PUT') { Object.assign(host, c.body); return { body: { ...host } }; }
    const seen = { ...host }; // read before the change below lands
    reads++;
    if (slow) await later(900);
    return { body: seen };
  });
  await h.page.locator('.bx-gear').click();
  await h.page.locator('.settings-tab', { hasText: 'Privacidad' }).click();
  const web = h.page.locator('button.toggle[aria-label="Búsqueda web"]');
  await expect(web).toBeEnabled();
  slow = true;
  const before = reads;
  await expect.poll(() => reads, { timeout: 8000 }).toBeGreaterThan(before); // the periodic read is on its way
  await web.click();
  await expect(web).toHaveAttribute('aria-checked', 'true');
  // until the next periodic read (4 s) the switch must not go back to what it was
  const seen: (string | null)[] = [];
  for (let i = 0; i < 14; i++) { seen.push(await web.getAttribute('aria-checked')); await h.page.waitForTimeout(100); }
  expect(seen.filter((v) => v !== 'true'), 'el interruptor volvió atrás').toEqual([]);
});

const EXTERNAL = {
  provider: 'anthropic', model: 'claude-opus-5-5', url: '', enabled: false, hasKey: false, active: false, activeModel: null, activeLocal: false, switching: false,
  problem: null, lastError: null, spentUsd: 0, ceilingUsd: null, ceilingHolds: true,
  providers: [{ id: 'anthropic', label: 'Anthropic', hasKey: false, model: 'claude-opus-5-5' }, { id: 'openai', label: 'OpenAI', hasKey: false, model: '' },
    { id: 'google', label: 'Google', hasKey: false, model: '' }, { id: 'local', label: 'Local', hasKey: false, model: '' }, { id: 'compatible', label: 'Otra', hasKey: false, model: '' }],
};

// Settings › Modelo says where BAXY thinks with one choice (design boards 13 to 16): each place's settings show once picked.
const pickWhere = (p: Page, where: RegExp) => p.getByRole('radiogroup', { name: /Dónde piensa BAXY|Where BAXY thinks/ }).getByRole('radio', { name: where }).click();

const TUNED = {
  available: true, file: 'BAXY-Qwen3.5-4B-c4-Q4_K_M.gguf', bytes: 2740937440, license: 'Apache-2.0', source: 'huggingface.co',
  repo: 'REDSOULTM/BAXY-Qwen3.5-4B-GGUF', installed: false, use: false, active: false, problem: null, downloading: false,
  downloadedBytes: 0, downloadBytesPerSecond: null as number | null, downloadSecondsLeft: null as number | null,
  downloadProblem: null, needBytes: 2808046304, switching: false,
};

// The legal texts (hub/steam-depot 4d6d2b569: THIRD_PARTY_NOTICES, EULA, NOTAS_1.3.2, ATRIBUCIONES_MODELOS) say how the
// tuned model was trained; the dialog before its download says the same, in both languages, still unofficial and
// optional with the stock Qwen by default, and names no other model's maker.
const TRAINED = {
  es: 'El ajuste se entrenó con conversaciones sintéticas con recibos de trazas reales; no se usó texto privado de ninguna persona.',
  en: 'The fine-tune was trained on synthetic conversations whose tool receipts are taken from real traces; no private user text was used.',
};
test('modelo ajustado: antes de descargar dice cómo se entrenó, como los textos legales, en español y en inglés', async () => {
  h = await openView();
  h.reply('/settings/tuned-model', () => ({ body: { ...TUNED } }));
  const p = h.page;
  await p.locator('.bx-gear').click();
  await p.locator('.settings-tab', { hasText: 'Modelo' }).click();
  await pickWhere(p, /Ajustado|Tuned/);
  await p.getByRole('button', { name: 'Instalar', exact: true }).click();
  const es = p.getByRole('dialog', { name: 'Antes de descargar' });
  await expect(es).toContainText(TRAINED.es);
  await expect(es).toContainText('extra no oficial');
  await expect(es).toContainText('Es opcional: si no lo instalas, BAXY usa Qwen3.5-4B de serie.');
  await expect(es).not.toContainText(/Claude|Anthropic/);
  // V-12: the first Escape is the ask's «Cancelar», the second closes Settings
  await p.keyboard.press('Escape');
  await expect(es).toHaveCount(0);
  await p.keyboard.press('Escape');
  h.reply('/settings/general', () => ({ body: { language: 'en', languageInUse: 'en' } }));
  await expect(p.locator('.bx-gear')).toHaveAttribute('aria-label', 'Settings', { timeout: 10_000 });
  await p.locator('.bx-gear').click();
  await p.locator('.settings-tab', { hasText: 'Model' }).click();
  await pickWhere(p, /Ajustado|Tuned/);
  await p.getByRole('button', { name: 'Install', exact: true }).click();
  const en = p.getByRole('dialog', { name: 'Before downloading' });
  await expect(en).toContainText(TRAINED.en);
  await expect(en).toContainText('unofficial extra');
  await expect(en).toContainText('It’s optional: unless you install it, BAXY uses the stock Qwen3.5-4B.');
  await expect(en).not.toContainText(/Claude|Anthropic/);
});

test('modelo ajustado: Instalar avisa antes de bajar nada, y usarlo cambia el modelo', async () => {
  h = await openView();
  let host = { ...TUNED };
  h.reply('/settings/tuned-model/install', () => {
    host = { ...host, downloading: true, downloadedBytes: 1_200_000_000, downloadBytesPerSecond: 12_500_000, downloadSecondsLeft: 124 };
    return { body: host };
  });
  h.reply('/settings/tuned-model', (c) => {
    // «cancel» is a request, not a state of the host's
    if (c.method === 'PUT' && !(c.body as { cancel?: boolean }).cancel) host = { ...host, ...(c.body as object) };
    return { body: host };
  });
  const p = h.page;
  await p.locator('.bx-gear').click();
  await p.locator('.settings-tab', { hasText: 'Modelo' }).click();
  await pickWhere(p, /Ajustado/);
  // INT11 (owner's order of 2026-11-08): the tuned model sits under unofficial extras, with a one-line notice before anything.
  await expect(p.locator('.panel-sec-head', { hasText: 'Extras no oficiales' })).toBeVisible();
  await expect(p.getByText('Modelo ajustado a BAXY (extra no oficial)', { exact: true })).toBeVisible();
  await expect(p.getByText('El modelo ajustado no forma parte del producto oficial ni de lo que se vende: lo publica el autor aparte en Hugging Face y usarlo es opcional.', { exact: true })).toBeVisible();
  await expect(p.getByText('Opcional. No viene con BAXY: se descarga solo si lo pides')).toBeVisible();
  await p.getByRole('button', { name: 'Instalar', exact: true }).click();
  await expect(p.getByRole('dialog', { name: 'Antes de descargar' })).toHaveText(/Descarga de 2,6 GB desde Hugging Face \(REDSOULTM\/BAXY-Qwen3\.5-4B-GGUF\)\. Licencia Apache-2\.0: es una obra derivada de Qwen3\.5-4B, de Alibaba Cloud\. Se comprueba con SHA-256 antes de usarlo\. Necesitas 2,6 GB libres/);
  await expect(p.getByRole('dialog', { name: 'Antes de descargar' })).toContainText('ajustado por el autor de BAXY, que lo publica aparte como extra no oficial');
  expect(h.calls.filter((c) => c.path.startsWith('/settings/tuned-model/install'))).toEqual([]);
  await p.getByRole('button', { name: 'Descargar' }).click();
  // MOD1 D6 / REV_VISTA V-06: the same bar as a model of Ollama's, with its percentage, speed, time left and «Detener»; it
  // said only «Llevo 1,1 GB de 2,6 GB».
  const bar = p.getByRole('group', { name: 'Descarga de BAXY ajustado' });
  await expect(bar).toContainText('Descargando BAXY ajustado');
  await expect(bar).toContainText('43 %');
  await expect(bar).toContainText('1,12 GB de 2,55 GB · 11,9 MB/s · quedan 3 min');
  await expect(bar.getByRole('progressbar')).toHaveAttribute('aria-valuenow', '43');
  await expect(p.getByRole('button', { name: 'Detener' })).toHaveCount(1);
  // seen from the other places too, as a model's download is
  await pickWhere(p, /De serie/);
  await expect(bar).toContainText('43 %');
  await bar.getByRole('button', { name: 'Detener' }).click();
  await expect.poll(() => h.calls.filter((c) => c.method === 'PUT' && c.path === '/settings/tuned-model').map((c) => c.body)).toContainEqual({ cancel: true });
  await pickWhere(p, /Ajustado/);
  host = { ...host, downloading: false, installed: true };
  await expect(p.getByText('Comprobado con SHA-256. Se aplica al momento')).toBeVisible();
  await p.locator('button.toggle[aria-label="Usar el modelo ajustado"]').click();
  await expect.poll(() => h.calls.filter((c) => c.method === 'PUT' && c.path === '/settings/tuned-model').map((c) => c.body)).toContainEqual({ use: true });
});

// Owner, 2026-11-08 (capture of Extras): a mono «Cambiando…» box, the switch and «Quitar» side by side looked bad. The
// state is a small tag by the title, the switch stands alone, and removing the 2.7 GB file is a quiet line that asks first.
test('modelo ajustado: el estado va junto al título, el interruptor solo, y Quitar pregunta antes de borrar', async () => {
  h = await openView();
  let host = { ...TUNED, installed: true, use: true, active: true };
  h.reply('/settings/tuned-model', (c) => {
    if (c.method === 'PUT') host = { ...host, ...(c.body as object) };
    return { body: host };
  });
  const p = h.page;
  await p.locator('.bx-gear').click();
  await p.locator('.settings-tab', { hasText: 'Modelo' }).click();
  const row = p.locator('.bxs-row', { hasText: 'Modelo ajustado a BAXY' });
  await expect(row.locator('.bx-tag.on')).toHaveText('En uso');
  await expect(row.locator('.bxs-fixed')).toHaveCount(0);
  await expect(row.locator('.bxs-c > *')).toHaveCount(1);
  await expect(row.locator('.bxs-c button.toggle[aria-label="Usar el modelo ajustado"]')).toBeVisible();
  await expect(p.getByText('Ocupa 2,6 GB en este PC')).toBeVisible();
  await p.getByRole('button', { name: 'Quitar del PC' }).click();
  await expect(p.locator('.bxs-ask')).toContainText('Se borra el archivo de 2,6 GB');
  expect(h.calls.filter((c) => c.method === 'PUT' && (c.body as { remove?: boolean })?.remove)).toEqual([]);
  await p.getByRole('button', { name: 'Sí, quitarlo' }).click();
  await expect.poll(() => h.calls.filter((c) => c.method === 'PUT' && c.path === '/settings/tuned-model').map((c) => c.body)).toContainEqual({ remove: true });
});

test('modelo ajustado: mientras cambia, la etiqueta lo dice y no se puede quitar', async () => {
  h = await openView();
  h.reply('/settings/tuned-model', () => ({ body: { ...TUNED, installed: true, use: true, switching: true } }));
  const p = h.page;
  await p.locator('.bx-gear').click();
  await p.locator('.settings-tab', { hasText: 'Modelo' }).click();
  const row = p.locator('.bxs-row', { hasText: 'Modelo ajustado a BAXY' });
  await expect(row.locator('.bx-tag.busy')).toHaveText('Cambiando…');
  await expect(p.getByRole('button', { name: 'Quitar del PC' })).toBeDisabled();
});

test('modelo ajustado dañado: el arranque sigue con el de serie y lo dice mientras sea así', async () => {
  h = await openView();
  const p = h.page;
  h.emit({ type: 'boot', stt: true, wake: true, tts: true, model: false, startedAt: 1, readyAt: null, tunedProblem: 'ajustado_danado' });
  await p.waitForTimeout(300);
  await expect(p.locator('.bx-notice')).toHaveCount(0); // nothing while the model starts
  h.emit({ type: 'boot', stt: true, wake: true, tts: true, model: true, startedAt: 1, readyAt: 2, tunedProblem: 'ajustado_danado' });
  await expect(p.locator('.bx-notice')).toContainText('El modelo ajustado está dañado y no lo voy a usar: BAXY sigue con el modelo de serie');
  await p.waitForTimeout(3200); // longer than a passing notice lasts
  await expect(p.locator('.bx-notice')).toContainText('modelo de serie');
  h.emit({ type: 'boot', stt: true, wake: true, tts: true, model: true, startedAt: 1, readyAt: 2, tunedProblem: null });
  await expect(p.locator('.bx-notice')).toHaveCount(0);
});

test('otro modelo: elegir de la lista conecta, y lo que no cabe se dice', async () => {
  h = await openView();
  let host = { ...EXTERNAL, provider: 'local', model: '', url: 'http://127.0.0.1:11434', ceilingHolds: false };
  h.reply('/settings/external-model/models', () => ({ body: { models: [
    { id: 'grande:4b', label: 'grande:4b · 5.2 GB', fits: true }, { id: 'visual', label: 'visual · 5.2 GB', fits: false, why: 'no sabe usar herramientas' }] } }));
  h.reply('/settings/external-model', (c) => {
    if (c.method === 'PUT') host = { ...host, ...(c.body as object) };
    return { body: host };
  });
  const p = h.page;
  await p.locator('.bx-gear').click();
  await p.locator('.settings-tab', { hasText: 'Modelo' }).click();
  await pickWhere(p, /Local/);
  const list = p.getByRole('combobox', { name: 'Modelo', exact: true });
  await expect(list.locator('option')).toHaveText(['Elige un modelo', 'grande:4b · 5.2 GB', 'visual · 5.2 GB · no sabe usar herramientas']);
  await expect(list.locator('option', { hasText: 'visual' })).toBeDisabled();
  await list.selectOption('grande:4b');
  await expect.poll(() => h.calls.filter((c) => c.method === 'PUT').map((c) => c.body)).toContainEqual({ provider: 'local', model: 'grande:4b', enabled: true });
  await expect(p.getByRole('radio', { name: /Local/ })).toHaveAttribute('aria-checked', 'true');
});

test('otro modelo: cada contexto dice su VRAM antes de hablarle, y elegirlo se aplica', async () => {
  h = await openView();
  let host = { ...EXTERNAL, provider: 'local', model: 'grande:4b', url: 'http://127.0.0.1:11434', enabled: true, ceilingHolds: false, context: null as number | null };
  h.reply('/settings/external-model/models', () => ({ body: { models: [{ id: 'grande:4b', label: 'grande:4b · 5,2 GB', fits: true }] } }));
  h.reply('/settings/external-model/estimate', () => ({ body: {
    contextLength: 262144, recommended: 78000,
    options: [{ context: 64000, bytes: 4_700_000_000 }, { context: 78000, bytes: 5_000_000_000 }, { context: 200000, bytes: 7_500_000_000 }],
    vramTotalBytes: 2 ** 33, vramFreeBytes: 6_000_000_000 } }));
  h.reply('/settings/external-model', (c) => {
    if (c.method === 'PUT') host = { ...host, ...(c.body as object) };
    return { body: host };
  });
  const p = h.page;
  await p.locator('.bx-gear').click();
  await p.locator('.settings-tab', { hasText: 'Modelo' }).click();
  await pickWhere(p, /Local/);
  const context = p.getByLabel('Contexto', { exact: true });
  await expect(context.locator('option')).toHaveText(['64.000 tokens · unos 4,4 GB de VRAM', '78.000 tokens · unos 4,7 GB de VRAM · recomendado', '200.000 tokens · unos 7,0 GB de VRAM']);
  await expect(context).toHaveValue('78000');
  await expect(p.getByText('Deja unos 29.000 tokens para la conversación. Tu tarjeta tiene 8,0 GB y hay 5,6 GB libres')).toBeVisible();
  await context.selectOption('200000');
  await expect.poll(() => h.calls.filter((c) => c.method === 'PUT').map((c) => c.body)).toContainEqual({ context: 200000 });
  // Ollama's own count (no bytesFrom «cabecera»): nothing stops it, and Ollama puts the rest in RAM.
  await expect(p.getByText('No cabe entero: lo demás irá a la RAM')).toBeVisible();
});

// VIVO2, blind review: with a smaller profile a short model is recommended its own 32,768, and a fixed 49,000 made it «Deja
// unos -16.232 tokens»; the host says what the chosen profile's prompt takes.
test('otro modelo con un perfil menor: lo que deja para la conversación sale del prompt de ese perfil', async () => {
  h = await openView();
  const host = { ...EXTERNAL, provider: 'local', model: 'corto:7b', url: 'http://127.0.0.1:11434', enabled: true, ceilingHolds: false, context: null as number | null };
  h.reply('/settings/external-model/models', () => ({ body: { models: [{ id: 'corto:7b', label: 'corto:7b · 3,8 GB', fits: true }] } }));
  h.reply('/settings/external-model/estimate', () => ({ body: {
    contextLength: 32768, recommended: 32768, promptTokens: 22661,
    options: [{ context: 26245, bytes: 3_000_000_000 }, { context: 32768, bytes: 3_400_000_000 }],
    vramTotalBytes: 2 ** 33, vramFreeBytes: 6_000_000_000 } }));
  h.reply('/settings/external-model', () => ({ body: host }));
  const p = h.page;
  await p.locator('.bx-gear').click();
  await p.locator('.settings-tab', { hasText: 'Modelo' }).click();
  await pickWhere(p, /Local/);
  await expect(p.getByText(/Deja unos 10\.107 tokens para la conversación/)).toBeVisible();
});

test('otro modelo: sin memoria libre en el PC, la opción lo dice antes de elegirla', async () => {
  h = await openView();
  const host = { ...EXTERNAL, provider: 'local', model: 'grande:4b', url: 'http://127.0.0.1:11434', enabled: false, ceilingHolds: false, context: 200000 };
  h.reply('/settings/external-model/models', () => ({ body: { models: [{ id: 'grande:4b', label: 'grande:4b · 5,2 GB', fits: true }] } }));
  h.reply('/settings/external-model/estimate', () => ({ body: {
    contextLength: 262144, recommended: 78000, commitFreeBytes: 2 ** 33,
    options: [{ context: 78000, bytes: 2 ** 31 }, { context: 200000, bytes: 2 ** 33 }], vramTotalBytes: 2 ** 34, vramFreeBytes: 2 ** 34 } }));
  h.reply('/settings/external-model', () => ({ body: host }));
  const p = h.page;
  await p.locator('.bx-gear').click();
  await p.locator('.settings-tab', { hasText: 'Modelo' }).click();
  await pickWhere(p, /Local/);
  await expect(p.getByLabel('Contexto', { exact: true }).locator('option')).toHaveText(['78.000 tokens · unos 2,0 GB de VRAM · recomendado', '200.000 tokens · unos 8,0 GB de VRAM · sin memoria']);
  await expect(p.getByText('Este PC tiene 8,0 GB de RAM libre (con el archivo de paginación): no se conectará con este contexto')).toBeVisible();
});

// INT18 blind review: the view said «sin memoria» by the rule the translator dropped (×1.7 + 3 GiB), so a small model it then
// refused was offered as connecting. The translator's rule (external_model.memory_problem, VRAM_ESTIMADA.md): whole on the card,
// its size + 2.75 GiB + 3 GiB; partly in RAM (only past the free VRAM, and with the person's yes), ×1.7 + 3 GiB.
test('otro modelo: «sin memoria» con la misma regla que el traductor, entero en la tarjeta o en parte en la RAM', async () => {
  h = await openView();
  const host = { ...EXTERNAL, provider: 'local', model: 'grande:4b', url: 'http://127.0.0.1:11434', enabled: false, ceilingHolds: false, context: 78000 };
  h.reply('/settings/external-model/models', () => ({ body: { models: [{ id: 'grande:4b', label: 'grande:4b · 5,2 GB', fits: true }] } }));
  h.reply('/settings/external-model/estimate', () => ({ body: {
    contextLength: 262144, recommended: 78000, commitFreeBytes: 2 ** 33, bytesFrom: 'cabecera',
    options: [{ context: 64000, bytes: 2 ** 31 }, { context: 78000, bytes: 2.7 * 2 ** 30 }, { context: 200000, bytes: 4 * 2 ** 30 }],
    vramTotalBytes: 2 ** 33, vramFreeBytes: 3 * 2 ** 30 } }));
  h.reply('/settings/external-model', (c) => {
    if (c.method === 'PUT') Object.assign(host, c.body);
    return { body: host };
  });
  const p = h.page;
  await p.locator('.bx-gear').click();
  await p.locator('.settings-tab', { hasText: 'Modelo' }).click();
  await pickWhere(p, /Local/);
  // 2,0 + 2,75 + 3 = 7,75 of 8 GiB: it connects. 2,7 + 2,75 + 3 = 8,45: it does not (×1.7 said 7,6 and «it connects»).
  // 4,0 is past the 3,0 free on the card: only partly in RAM, 4,0 × 1,7 + 3 = 9,8.
  await expect(p.getByLabel('Contexto', { exact: true }).locator('option')).toHaveText(['64.000 tokens · unos 2,0 GB de VRAM', '78.000 tokens · unos 2,7 GB de VRAM · sin memoria · recomendado', '200.000 tokens · unos 4,0 GB de VRAM · sin memoria']);
  await expect(p.getByText('Este PC tiene 8,0 GB de RAM libre (con el archivo de paginación): no se conectará con este contexto')).toBeVisible();
  // BAXY's own estimate past the free VRAM: the App stops before connecting and asks (no_cabe_vram).
  await p.getByLabel('Contexto', { exact: true }).selectOption('200000');
  await expect(p.getByText('No cabe entero: no lo conectaré sin preguntarte')).toBeVisible();
});

test('otro modelo: con la VRAM libre sin saber, «sin memoria» cuenta la regla mayor, como el traductor', async () => {
  h = await openView();
  const host = { ...EXTERNAL, provider: 'local', model: 'grande:4b', url: 'http://127.0.0.1:11434', enabled: false, ceilingHolds: false, context: 78000 };
  h.reply('/settings/external-model/models', () => ({ body: { models: [{ id: 'grande:4b', label: 'grande:4b · 5,2 GB', fits: true }] } }));
  // 6 GiB: whole on the card 6 + 2,75 + 3 = 11,75; split 6 × 1,7 + 3 = 13,2; Windows can promise 12,5. Nothing says where it goes.
  h.reply('/settings/external-model/estimate', () => ({ body: {
    contextLength: 262144, recommended: 78000, commitFreeBytes: 12.5 * 2 ** 30, bytesFrom: 'cabecera',
    options: [{ context: 78000, bytes: 6 * 2 ** 30 }] } }));
  h.reply('/settings/external-model', () => ({ body: host }));
  const p = h.page;
  await p.locator('.bx-gear').click();
  await p.locator('.settings-tab', { hasText: 'Modelo' }).click();
  await pickWhere(p, /Local/);
  await expect(p.getByLabel('Contexto', { exact: true }).locator('option')).toHaveText(['78.000 tokens · unos 6,0 GB de VRAM · sin memoria · recomendado']);
});

test('otro modelo: pasar de lo que el modelo declara se dice, y lo que no cabe pide menos contexto', async () => {
  h = await openView();
  const host = { ...EXTERNAL, provider: 'local', model: 'qwen3:8b', url: 'http://127.0.0.1:11434', enabled: true, ceilingHolds: false, context: 200000 };
  h.reply('/settings/external-model/models', () => ({ body: { models: [{ id: 'qwen3:8b', label: 'qwen3:8b · 5,2 GB', fits: true }] } }));
  h.reply('/settings/external-model/estimate', () => ({ body: {
    contextLength: 40960, recommended: 78000,
    options: [{ context: 64000, bytes: 10_000_000_000 }, { context: 78000, bytes: 11_000_000_000 }, { context: 200000, bytes: 20_000_000_000 }],
    vramTotalBytes: 2 ** 34, vramFreeBytes: 15_000_000_000 } }));
  h.reply('/settings/external-model', () => ({ body: host }));
  const p = h.page;
  await p.locator('.bx-gear').click();
  await p.locator('.settings-tab', { hasText: 'Modelo' }).click();
  await pickWhere(p, /Local/);
  await expect(p.getByText('No cabe: elige menos contexto. El modelo declara 40.960: BAXY le amplía el límite')).toBeVisible();
});

test('otro modelo local: avisa que un modelo pequeño acierta menos, busca en Hugging Face e instala con un clic', async () => {
  h = await openView();
  let host = { ...EXTERNAL, provider: 'local', model: '', url: 'http://127.0.0.1:11434', ceilingHolds: false, open: {
    ollamaVersion: '0.40.15', ollamaBytes: 1614941966, ollamaOwn: true, ollamaRunning: '0.40.15', ollamaInstalling: false, ollamaDownloadedBytes: 0,
    ollamaProblem: null, pulling: null as string | null, pullTotal: 0, pullDone: 0, pullProblem: null,
    pullBytesPerSecond: undefined as number | undefined, pullSecondsLeft: undefined as number | undefined } };
  h.reply('/settings/external-model', () => ({ body: host }));
  h.reply('/settings/external-model/models', () => ({ body: { models: [] } }));
  h.reply('/settings/external-model/search', () => ({ body: { results: [
    { repo: 'unsloth/Qwen3.5-2B-GGUF', file: 'Qwen3.5-2B-Q4_K_M.gguf', quant: 'Q4_K_M', name: 'unsloth/Qwen3.5-2B-GGUF:Q4_K_M',
      visionName: 'hf.co/unsloth/Qwen3.5-2B-GGUF:Q4_K_M', sha256: 'a'.repeat(64), bytes: 1_280_000_000,
      projectorBytes: 670_000_000, projectorVramBytes: 1_005_544_320, license: 'mit', context: 262144, tools: true, vramBytes: 3_600_000_000,
      vramContext: 78000, fit: 'cabe', why: null },
    { repo: 'alguien/SinHerramientas-GGUF', file: 'm-Q4_K_M.gguf', quant: 'Q4_K_M', name: 'alguien/SinHerramientas-GGUF:Q4_K_M', visionName: null,
      sha256: 'b'.repeat(64), bytes: 1_000_000_000, projectorBytes: 0, license: null, context: 131072, tools: false, vramBytes: null, vramContext: 78000, fit: 'desconocido',
      why: 'sin_herramientas' }] } }));
  h.reply('/settings/external-model/install', (c) => {
    host = { ...host, open: { ...host.open, pulling: `${(c.body as { repo: string }).repo}:Q4_K_M`, pullTotal: 100, pullDone: 40,
      pullBytesPerSecond: 12_500_000, pullSecondsLeft: 90 } };
    return { body: host };
  });
  const p = h.page;
  await p.locator('.bx-gear').click();
  await p.locator('.settings-tab', { hasText: 'Modelo' }).click();
  await pickWhere(p, /Local/);
  await expect(p.getByText('Los modelos más pequeños que el de serie aciertan menos y pueden equivocarse.')).toBeVisible();
  const box = p.getByRole('textbox', { name: 'Nombre del modelo a buscar' });
  await box.fill('qwen3.5 2b');
  await box.press('Enter');
  const found = p.locator('ul[aria-label="Modelos encontrados"] li');
  await expect(found).toHaveCount(2);
  await expect(found.first()).toContainText('1,2 GB · usa unos 3,4 GB de VRAM con 78.000 tokens de contexto · visión aparte, opcional: 0,6 GB más y unos 0,9 GB más de VRAM · licencia mit · admite 262.144 tokens · cabe en tu tarjeta');
  await expect(found.nth(1)).toContainText('sin licencia declarada');
  await expect(found.nth(1).getByRole('button', { name: 'Instalar y usar' })).toBeDisabled();
  await found.first().getByRole('button', { name: 'Instalar y usar' }).click();
  // Owner, 2026-11-08: «un porcentaje de descarga que se vea bonito»: a bar with its percentage, speed and time left.
  const bar = p.getByRole('group', { name: 'Descarga de unsloth/Qwen3.5-2B-GGUF:Q4_K_M' });
  await expect(bar).toContainText('Descargando unsloth/Qwen3.5-2B-GGUF:Q4_K_M');
  await expect(bar).toContainText('40 %');
  await expect(bar).toContainText('11,9 MB/s · quedan 2 min');
  await expect(bar.getByRole('progressbar')).toHaveAttribute('aria-valuenow', '40');
  await expect(bar.getByRole('button', { name: 'Detener' })).toBeVisible();
  expect(h.calls.filter((c) => c.path === '/settings/external-model/search').map((c) => c.body)).toEqual([{ q: 'qwen3.5 2b' }]);
  expect(h.calls.filter((c) => c.path === '/settings/external-model/install').map((c) => (c.body as { repo: string }).repo)).toEqual(['unsloth/Qwen3.5-2B-GGUF']);
});

// Owner, 2026-11-08: «al buscar un modelo haya una selección de cabe o no cabe en tu tarjeta… así yo me traslado solamente a
// los que caben»: on by default with the free VRAM known, what does not fit is left out and counted.
test('otro modelo local: «Sólo los que caben en mi tarjeta» deja fuera lo que no cabe en la VRAM libre', async () => {
  h = await openView();
  const host = { ...EXTERNAL, provider: 'local', model: '', ceilingHolds: false, open: {
    ollamaVersion: '0.40.15', ollamaBytes: 1614941966, ollamaOwn: true, ollamaRunning: '0.40.15', ollamaInstalling: false, ollamaDownloadedBytes: 0,
    ollamaProblem: null, pulling: null, pullTotal: 0, pullDone: 0, pullProblem: null } };
  h.reply('/settings/external-model', () => ({ body: host }));
  h.reply('/settings/external-model/models', () => ({ body: { models: [] } }));
  h.reply('/settings/external-model/search', () => ({ body: { vramTotalBytes: 6_442_450_944, vramFreeBytes: 5_900_000_000, results: [
    { repo: 'unsloth/Qwen3-1.7B-GGUF', file: 'Qwen3-1.7B-Q4_K_M.gguf', quant: 'Q4_K_M', name: 'hf.co/unsloth/Qwen3-1.7B-GGUF:Q4_K_M', bytes: 1_107_409_472,
      projectorBytes: 0, license: 'mit', context: 40960, tools: true, vramBytes: 4_200_000_000, vramContext: 78000, fit: 'cabe', why: null },
    { repo: 'bartowski/Llama-3.2-3B-Instruct-GGUF', file: 'Llama-3.2-3B-Instruct-Q4_K_M.gguf', quant: 'Q4_K_M', name: 'hf.co/bartowski/Llama-3.2-3B-Instruct-GGUF:Q4_K_M',
      bytes: 2_019_377_696, projectorBytes: 0, license: 'llama3.2', context: 131072, tools: true, vramBytes: 11_400_000_000, vramContext: 78000, fit: 'no_cabe', why: null }] } }));
  const p = h.page;
  await p.locator('.bx-gear').click();
  await p.locator('.settings-tab', { hasText: 'Modelo' }).click();
  // interfaz-v5: Local is one of the places BAXY thinks, picked above (INT17).
  await pickWhere(p, /Local/);
  const box = p.getByRole('textbox', { name: 'Nombre del modelo a buscar' });
  await box.fill('3b');
  await box.press('Enter');
  const only = p.getByRole('checkbox', { name: 'Sólo los que caben en mi tarjeta (5,5 GB libres de 6,0 GB)' });
  await expect(only).toBeChecked();
  const found = p.locator('ul[aria-label="Modelos encontrados"] li');
  await expect(found).toHaveCount(1);
  await expect(found.first()).toContainText('usa unos 3,9 GB de VRAM con 78.000 tokens de contexto');
  await expect(p.getByText('1 más no caben en este PC')).toBeVisible();
  await only.uncheck();
  await expect(found).toHaveCount(2);
  await expect(found.nth(1)).toContainText('usa unos 10,6 GB de VRAM con 78.000 tokens de contexto · sin visión · licencia llama3.2 · admite 131.072 tokens · no cabe en tu tarjeta');
});

test('otro modelo local: una descarga detenida se reanuda desde donde quedó', async () => {
  h = await openView();
  let host = { ...EXTERNAL, provider: 'local', model: '', ceilingHolds: false, open: {
    ollamaVersion: '0.40.15', ollamaBytes: 1614941966, ollamaOwn: true, ollamaRunning: '0.40.15', ollamaInstalling: false, ollamaDownloadedBytes: 0,
    ollamaProblem: null, pulling: null as string | null, pullTotal: 2_000_000_000, pullDone: 800_000_000,
    pullStopped: 'hf.co/a/b-GGUF:Q4_K_M' as string | null, pullProblem: null } };
  h.reply('/settings/external-model', () => ({ body: host }));
  h.reply('/settings/external-model/models', () => ({ body: { models: [] } }));
  h.reply('/settings/external-model/pull', (c) => {
    host = { ...host, open: { ...host.open, pulling: (c.body as { name: string }).name, pullStopped: null } };
    return { body: host };
  });
  const p = h.page;
  await p.locator('.bx-gear').click();
  await p.locator('.settings-tab', { hasText: 'Modelo' }).click();
  // interfaz-v5: Local is one of the places BAXY thinks, picked above (INT17).
  await pickWhere(p, /Local/);
  const bar = p.getByRole('group', { name: 'Descarga de a/b-GGUF:Q4_K_M' });
  await expect(bar).toContainText('Descarga detenida: a/b-GGUF:Q4_K_M');
  await expect(bar).toContainText('40 %');
  await expect(bar).toContainText('0,75 GB de 1,86 GB · detenida: sigue desde aquí');
  await bar.getByRole('button', { name: 'Reanudar' }).click();
  await expect(p.getByRole('group', { name: 'Descarga de a/b-GGUF:Q4_K_M' })).toContainText('Descargando a/b-GGUF:Q4_K_M');
  expect(h.calls.filter((c) => c.path === '/settings/external-model/pull').map((c) => c.body)).toEqual([{ name: 'hf.co/a/b-GGUF:Q4_K_M', bytes: 2_000_000_000 }]);
});


// INT12: the three branches that grew Settings are there together: Behavior (baxy-abierta), Model → Local
// (modelos-abiertos) and the unofficial extras (INT11), and Ollama's download is not called «MIT» alone.
// REV_VISTA V-05 (P1, 2026-11-09): what was written without «Guardar» (Behavior's text, the API's key and address, the custom
// profile) went with Escape, a click outside or another tab, under a footer that said «Los cambios se guardan al momento».
// The draft is kept for when the person comes back; Escape in a box leaves the box; the footer says what is not saved.
const BEHAVIOR_HOST = { identity: 'Soy BAXY.', factory: { personality: 'Texto de fábrica de prueba.', replies: 'Respuestas de fábrica.', preferences: '' },
  texts: { personality: null, replies: null, preferences: null }, maxChars: 1200, switching: false };

test('ajustes: lo escrito en Comportamiento sin guardar vuelve al volver, y Escape en la caja no cierra Ajustes', async () => {
  h = await openView();
  h.reply('/settings/behavior', () => ({ body: BEHAVIOR_HOST }));
  const p = h.page;
  const settings = p.locator('.settings-panel');
  const box = p.getByLabel('Personalidad y tono');
  await p.locator('.bx-gear').click();
  await p.locator('.settings-tab', { hasText: 'Comportamiento' }).click();
  await expect(p.locator('.bxs-foot')).not.toContainText('Los cambios se guardan al momento');
  await box.fill('Con humor seco y muy paciente');
  await expect(p.locator('.bxs-foot')).toHaveText(/^Sin guardar: Comportamiento/);
  // Escape inside the box leaves the box; Settings stays
  await box.press('Escape');
  await expect(settings).toBeVisible();
  await expect(box).not.toBeFocused();
  // another tab and back
  await p.locator('.settings-tab', { hasText: 'General' }).click();
  await p.locator('.settings-tab', { hasText: 'Comportamiento' }).click();
  await expect(box).toHaveValue('Con humor seco y muy paciente');
  // Escape out of Settings, and a click outside: back again, it is there
  await p.keyboard.press('Escape');
  await expect(settings).toHaveCount(0);
  await p.locator('.bx-gear').click();
  await p.locator('.settings-tab', { hasText: 'Comportamiento' }).click();
  await expect(box).toHaveValue('Con humor seco y muy paciente');
  await p.locator('.panel-shroud').click({ position: { x: 5, y: 5 } });
  await expect(settings).toHaveCount(0);
  await p.locator('.bx-gear').click();
  await p.locator('.settings-tab', { hasText: 'Comportamiento' }).click();
  await expect(box).toHaveValue('Con humor seco y muy paciente');
  expect(h.calls.filter((c) => c.method === 'PUT' && c.path === '/settings/behavior')).toEqual([]);
  // saved, it is no draft any more
  h.reply('/settings/behavior', (c) => ({ body: c.method === 'PUT' ? { ...BEHAVIOR_HOST, texts: { ...BEHAVIOR_HOST.texts, ...(c.body as object) } } : BEHAVIOR_HOST }));
  await box.locator('xpath=ancestor::div[contains(@class,"bxs-text")]').getByRole('button', { name: 'Guardar' }).click();
  await expect(p.locator('.bxs-foot')).not.toContainText('Sin guardar');
});

test('ajustes: la clave escrita y la selección personalizada sin guardar siguen ahí al volver de otra pestaña', async () => {
  h = await openView();
  h.reply('/settings/external-model', () => ({ body: { ...EXTERNAL } }));
  h.reply('/settings/tools', () => ({ body: { profile: 'completo', on: ['app.open', 'web.search'] } }));
  h.reply('/catalog', () => ({ body: { total: 2, groups: [{ name: 'Apps', items: [{ name: 'app.open', title: 'Abrir una app', level: 1 }, { name: 'web.search', title: 'Buscar en la web', level: 2 }] }] } }));
  const p = h.page;
  await p.locator('.bx-gear').click();
  await p.locator('.settings-tab', { hasText: 'Modelo' }).click();
  await pickWhere(p, /API/);
  await p.getByLabel('Clave de la API').fill('sk-a-medias');
  await p.locator('.settings-tab', { hasText: 'Herramientas' }).click();
  await p.getByRole('radio', { name: /Personalizado/ }).click();
  await p.getByRole('checkbox', { name: 'Buscar en la web' }).uncheck();
  await expect(p.locator('.bxs-foot')).toHaveText(/^Sin guardar: Modelo · Herramientas/);
  await p.locator('.settings-tab', { hasText: 'General' }).click();
  await p.locator('.settings-tab', { hasText: 'Herramientas' }).click();
  await expect(p.getByRole('radio', { name: /Personalizado/ })).toHaveAttribute('aria-checked', 'true');
  await expect(p.getByRole('checkbox', { name: 'Buscar en la web' })).not.toBeChecked();
  await p.locator('.settings-tab', { hasText: 'Modelo' }).click();
  await pickWhere(p, /API/);
  await expect(p.getByLabel('Clave de la API')).toHaveValue('sk-a-medias');
  expect(h.calls.filter((c) => c.method === 'PUT')).toEqual([]);
});

// VIS2 blind review (P2): Escape in a box that saves when it is left (the API's address, model and cap) saved what was being
// written; it leaves the box and keeps the draft, unsaved.
test('ajustes: Escape en la dirección de la API no la guarda: queda como borrador', async () => {
  h = await openView();
  h.reply('/settings/external-model', () => ({ body: { ...EXTERNAL, provider: 'compatible', url: 'https://antes.invalid/v1', ceilingHolds: false } }));
  const p = h.page;
  await p.locator('.bx-gear').click();
  await p.locator('.settings-tab', { hasText: 'Modelo' }).click();
  await pickWhere(p, /API/);
  const url = p.getByLabel('Dirección de la API');
  await url.fill('https://a-medias.invalid/v1');
  await url.press('Escape');
  await expect(url).not.toBeFocused();
  await expect(p.locator('.bxs-foot')).toHaveText(/^Sin guardar: Modelo/);
  await p.waitForTimeout(300);
  expect(h.calls.filter((c) => c.method === 'PUT' && c.path === '/settings/external-model')).toEqual([]);
  await expect(url).toHaveValue('https://a-medias.invalid/v1');
});

test('ajustes: vaciar un texto de Comportamiento y guardarlo vuelve al de fábrica, sin borrador', async () => {
  h = await openView();
  let texts: Record<string, string | null> = { personality: 'Mío.', replies: null, preferences: null };
  h.reply('/settings/behavior', (c) => {
    if (c.method === 'PUT') texts = { ...texts, ...(c.body as object) };
    // as PersonBehavior: an empty text is no text of the person's
    for (const k of Object.keys(texts)) if (!texts[k]?.trim()) texts[k] = null;
    return { body: { ...BEHAVIOR_HOST, texts } };
  });
  const p = h.page;
  await p.locator('.bx-gear').click();
  await p.locator('.settings-tab', { hasText: 'Comportamiento' }).click();
  const box = p.getByLabel('Personalidad y tono');
  await box.fill('');
  await box.locator('xpath=ancestor::div[contains(@class,"bxs-text")]').getByRole('button', { name: 'Guardar' }).click();
  await expect(box).toHaveValue('Texto de fábrica de prueba.');
  await expect(p.locator('.bxs-foot')).not.toContainText('Sin guardar');
});

test('ajustes: una clave escrita para una empresa no aparece bajo otra', async () => {
  h = await openView();
  let provider = 'anthropic';
  h.reply('/settings/external-model', () => ({ body: { ...EXTERNAL, provider } }));
  const p = h.page;
  await p.locator('.bx-gear').click();
  await p.locator('.settings-tab', { hasText: 'Modelo' }).click();
  await pickWhere(p, /API/);
  await p.getByLabel('Clave de la API').fill('sk-de-anthropic');
  await pickWhere(p, /De serie/);
  provider = 'openai';
  await p.locator('.settings-tab', { hasText: 'General' }).click();
  await p.locator('.settings-tab', { hasText: 'Modelo' }).click();
  await pickWhere(p, /API/);
  await expect(p.locator('.bxs-seg button.on', { hasText: 'OpenAI' })).toHaveCount(1);
  await expect(p.getByLabel('Clave de la API')).toHaveValue('');
});

test('ajustes: guardar el tope de gasto no se lleva la clave que se estaba escribiendo', async () => {
  h = await openView();
  let host: Record<string, unknown> = { ...EXTERNAL };
  h.reply('/settings/external-model', (c) => { if (c.method === 'PUT') host = { ...host, ...(c.body as object) }; return { body: host }; });
  const p = h.page;
  await p.locator('.bx-gear').click();
  await p.locator('.settings-tab', { hasText: 'Modelo' }).click();
  await pickWhere(p, /API/);
  await p.getByLabel('Clave de la API').fill('sk-a-medias');
  const cap = p.getByLabel('Tope de gasto en USD');
  await cap.fill('7');
  await cap.blur();
  await expect.poll(() => h.calls.filter((c) => c.method === 'PUT').map((c) => c.body)).toContainEqual({ ceilingUsd: 7 });
  await expect(p.getByLabel('Clave de la API')).toHaveValue('sk-a-medias');
  // what the footer promises: kept while BAXY stays open
  await expect(p.locator('.bxs-foot')).toContainText('mientras BAXY siga abierto');
});

test('ventana: cerrar BAXY con algo escrito sin guardar pregunta antes, y en la bandeja no hace falta', async () => {
  h = await openView();
  h.reply('/settings/behavior', () => ({ body: BEHAVIOR_HOST }));
  let tray = false;
  h.reply('/settings/general', (c) => {
    if (c.method === 'PUT' && typeof (c.body as { closeToTray?: boolean }).closeToTray === 'boolean') tray = (c.body as { closeToTray: boolean }).closeToTray;
    return { body: { language: 'es', languageInUse: 'es', closeToTray: tray } };
  });
  const p = h.page;
  await p.evaluate(() => {
    const w = window as unknown as { pywebview: unknown; closings: number };
    w.closings = 0;
    w.pywebview = { api: { win_is_maximized: async () => false, win_toggle_maximize: async () => true, win_minimize: async () => true,
      win_close: async () => { w.closings++; return true; }, win_exit: async () => true } };
  });
  const closed = () => p.evaluate(() => (window as unknown as { closings: number }).closings);
  await p.locator('.bx-gear').click();
  await p.locator('.settings-tab', { hasText: 'Comportamiento' }).click();
  await p.getByLabel('Personalidad y tono').fill('Muy breve');
  await p.keyboard.press('Escape');
  await p.keyboard.press('Escape');
  await p.getByRole('button', { name: 'Cerrar BAXY' }).click();
  const ask = p.getByRole('dialog', { name: '¿Cerrar BAXY sin guardar?' });
  await expect(ask).toBeVisible();
  await expect(ask.getByRole('button', { name: 'Volver a Ajustes' })).toBeFocused();
  expect(await closed()).toBe(0);
  await ask.getByRole('button', { name: 'Volver a Ajustes' }).click();
  await expect(p.getByLabel('Personalidad y tono')).toHaveValue('Muy breve');
  await p.keyboard.press('Escape');
  await p.keyboard.press('Escape');
  await p.getByRole('button', { name: 'Cerrar BAXY' }).click();
  await ask.getByRole('button', { name: 'Cerrar sin guardar' }).click();
  await expect.poll(closed).toBe(1);
  // to the tray the view lives on, and the draft with it: nothing to ask
  await p.locator('.bx-gear').click();
  await p.locator('.settings-tab', { hasText: 'General' }).click();
  await p.getByRole('switch', { name: 'Al cerrar la ventana, seguir en la bandeja' }).click();
  await expect.poll(() => tray).toBe(true);
  await p.keyboard.press('Escape');
  await p.getByRole('button', { name: 'Cerrar BAXY' }).click();
  await expect(ask).toHaveCount(0);
  await expect.poll(closed).toBe(2);
});

test('ajustes: Comportamiento, Modelo → Local y los extras no oficiales están juntos', async () => {
  h = await openView();
  const factory = { personality: 'Texto de fábrica de prueba.', replies: 'Respuestas de fábrica de prueba.', preferences: '' };
  h.reply('/settings/behavior', () => ({ body: { identity: 'Soy BAXY.', factory, texts: { personality: null, replies: null, preferences: null }, maxChars: 1200, switching: false } }));
  h.reply('/settings/tuned-model', () => ({ body: { ...TUNED } }));
  h.reply('/settings/external-model', () => ({ body: { ...EXTERNAL, provider: 'local', model: '', url: 'http://127.0.0.1:11434', ceilingHolds: false, open: {
    ollamaVersion: '0.40.15', ollamaBytes: 1614941966, ollamaOwn: true, ollamaRunning: null, ollamaInstalling: false, ollamaDownloadedBytes: 0,
    ollamaProblem: null, pulling: null, pullTotal: 0, pullDone: 0, pullProblem: null } } }));
  h.reply('/settings/external-model/models', () => ({ body: { ollama: 'missing' } }));
  const p = h.page;
  await p.locator('.bx-gear').click();
  await p.locator('.settings-tab', { hasText: 'Comportamiento' }).click();
  await expect(p.getByText('Personalidad y tono', { exact: true })).toBeVisible();
  await expect(p.getByText('Ver el texto de fábrica').first()).toBeVisible();
  // INT14: the fixed name was said to override the person's texts, while 00_IDENTIDAD measures 164 of 192 and a text with
  // a ready-made answer winning about half of the time
  await expect(p.getByText(/abre las instrucciones y, si cambias algún texto, una regla fija del nombre las cierra; aun así, un texto tuyo puede hacer que a veces diga otro nombre/)).toBeVisible();
  await expect(p.getByText(/manda sobre tus textos/)).toHaveCount(0);
  await p.locator('.settings-tab', { hasText: 'Modelo' }).click();
  await pickWhere(p, /Local/);
  await expect(p.getByText('Los modelos más pequeños que el de serie aciertan menos y pueden equivocarse.')).toBeVisible();
  await expect(p.getByRole('textbox', { name: 'Nombre del modelo a buscar' })).toBeVisible();
  await expect(p.getByText(/su código es MIT y trae bibliotecas CUDA de NVIDIA con su propia licencia/)).toBeVisible();
  await pickWhere(p, /Ajustado/);
  await expect(p.locator('.panel-sec-head', { hasText: 'Extras no oficiales' })).toBeVisible();
  await expect(p.getByText('Modelo ajustado a BAXY (extra no oficial)', { exact: true })).toBeVisible();
  // INT13: interfaz v5's tab of the same name says the tuned model is not the official product, and promises no warranty
  await p.locator('.settings-tab', { hasText: 'Extras no oficiales' }).click();
  await expect(p.getByText(/No están probados como el resto de BAXY/)).toBeVisible();
  await expect(p.getByText(/Lo publica su autor aparte y no forma parte del producto oficial/)).toBeVisible();
  await expect(p.getByText(/garantiza/)).toHaveCount(0);
});

test('otro modelo local: mientras no se sabe si hay Ollama, «Instalar y usar» espera', async () => {
  // INT12V 2026-11-08: the row said «Buscando tus modelos de Ollama…» and the first result could already be installed.
  h = await openView();
  const host = { ...EXTERNAL, provider: 'local', model: '', url: 'http://127.0.0.1:11434', ceilingHolds: false, open: {
    ollamaVersion: '0.40.15', ollamaBytes: 1614941966, ollamaOwn: false, ollamaRunning: null, ollamaInstalling: false, ollamaDownloadedBytes: 0,
    ollamaProblem: null, pulling: null, pullTotal: 0, pullDone: 0, pullProblem: null } };
  let answer: (v: { body: unknown }) => void = () => {};
  h.reply('/settings/external-model', () => ({ body: host }));
  h.reply('/settings/external-model/models', () => new Promise((r) => { answer = r; }));
  h.reply('/settings/external-model/search', () => ({ body: { results: [
    { repo: 'unsloth/gemma-4-E2B-it-GGUF', file: 'gemma-4-E2B-it-Q4_K_M.gguf', quant: 'Q4_K_M', name: 'hf.co/unsloth/gemma-4-E2B-it-GGUF:Q4_K_M', bytes: 3_100_000_000,
      projectorBytes: 0, license: 'apache-2.0', context: 131072, tools: true, fit: 'cabe', why: null }] } }));
  const p = h.page;
  await p.locator('.bx-gear').click();
  await p.locator('.settings-tab', { hasText: 'Modelo' }).click();
  await pickWhere(p, /Local/);
  await expect(p.getByText('Buscando tus modelos de Ollama…')).toBeVisible();
  const box = p.getByRole('textbox', { name: 'Nombre del modelo a buscar' });
  await box.fill('gemma');
  await box.press('Enter');
  const install = p.locator('ul[aria-label="Modelos encontrados"] li').first().getByRole('button', { name: 'Instalar y usar' });
  await expect(install).toBeDisabled();
  answer({ body: { models: [] } });
  await expect(install).toBeEnabled();
});

// VIVO2 F14: connected to Qwen3.5-2B (no vision), the tab said «Este modelo no ve» twice, in two wordings: the box of the model
// in use says it, and the Local section only while nothing is connected.
test('un modelo conectado que no ve lo dice una vez', async () => {
  h = await openView();
  const host = { ...EXTERNAL, provider: 'local', model: 'unsloth/Qwen3.5-2B-GGUF:Q4_K_M', url: 'http://127.0.0.1:11434', ceilingHolds: false, sees: false,
    enabled: true, active: true, activeModel: 'unsloth/Qwen3.5-2B-GGUF:Q4_K_M', activeLocal: true };
  h.reply('/settings/external-model', () => ({ body: host }));
  h.reply('/settings/external-model/models', () => ({ body: { models: [
    { id: 'unsloth/Qwen3.5-2B-GGUF:Q4_K_M', label: 'unsloth/Qwen3.5-2B-GGUF:Q4_K_M · 1,2 GB', fits: true, why: null, vision: false }] } }));
  const p = h.page;
  await p.locator('.bx-gear').click();
  await p.locator('.settings-tab', { hasText: 'Modelo' }).click();
  await expect(p.locator('.settings-body').getByText('Conectado')).toBeVisible();
  await expect(p.locator('.settings-body').getByText(/^Este modelo no ve/)).toHaveCount(1);
});

test('otro modelo local: se instala el modelo solo, su visión aparte si la quiere, y uno que no ve lo dice', async () => {
  // Pedido del dueño 2026-11-08: «si un modelo tiene visión, se instala el modelo y después la visión; si no, sin visión… BAXY ya no
  // podrá usar la visión, y listo».
  h = await openView();
  const host = { ...EXTERNAL, provider: 'local', model: 'unsloth/Qwen3.5-2B-GGUF:Q4_K_M', url: 'http://127.0.0.1:11434', ceilingHolds: false, sees: false,
    open: { ollamaVersion: '0.40.15', ollamaBytes: 1614941966, ollamaOwn: true, ollamaRunning: '0.40.15', ollamaInstalling: false, ollamaDownloadedBytes: 0,
      ollamaProblem: null, pulling: null, pullTotal: 0, pullDone: 0, pullProblem: null } };
  h.reply('/settings/external-model', () => ({ body: host }));
  h.reply('/settings/external-model/models', () => ({ body: { models: [
    { id: 'unsloth/Qwen3.5-2B-GGUF:Q4_K_M', label: 'unsloth/Qwen3.5-2B-GGUF:Q4_K_M · 1,3 GB', fits: true, why: null, vision: false }] } }));
  h.reply('/settings/external-model/search', () => ({ body: { results: [
    { repo: 'unsloth/Qwen3.5-2B-GGUF', file: 'Qwen3.5-2B-Q4_K_M.gguf', quant: 'Q4_K_M', name: 'unsloth/Qwen3.5-2B-GGUF:Q4_K_M',
      visionName: 'hf.co/unsloth/Qwen3.5-2B-GGUF:Q4_K_M', sha256: 'a'.repeat(64), bytes: 1_280_000_000, projectorBytes: 670_000_000,
      license: 'apache-2.0', context: 262144, tools: true, fit: 'cabe', why: null },
    { repo: 'openai/gpt-oss-20b-GGUF', file: 'gpt-oss-20b-Q4_K_M.gguf', quant: 'Q4_K_M', name: 'openai/gpt-oss-20b-GGUF:Q4_K_M', visionName: null,
      sha256: 'b'.repeat(64), bytes: 1_900_000_000, projectorBytes: 0, license: 'apache-2.0', context: 131072, tools: true, fit: 'cabe', why: null }] } }));
  h.reply('/settings/external-model/install', () => ({ body: host }));
  h.reply('/settings/external-model/pull', () => ({ body: host }));
  const p = h.page;
  await p.locator('.bx-gear').click();
  await p.locator('.settings-tab', { hasText: 'Modelo' }).click();
  await pickWhere(p, /Local/);
  await expect(p.getByText('Este modelo no ve: BAXY no describirá capturas ni buscará botones por su imagen, y lee el texto de la pantalla igual')).toBeVisible();
  const box = p.getByRole('textbox', { name: 'Nombre del modelo a buscar' });
  await box.fill('qwen');
  await box.press('Enter');
  const found = p.locator('ul[aria-label="Modelos encontrados"] li');
  await expect(found.first()).toContainText('1,2 GB · visión aparte, opcional: 0,6 GB más');
  await expect(found.nth(1)).toContainText('1,8 GB · sin visión');
  await expect(found.nth(1).getByRole('button', { name: 'Añadir visión' })).toHaveCount(0);
  await found.first().getByRole('button', { name: 'Instalar y usar' }).click();
  await found.first().getByRole('button', { name: 'Añadir visión' }).click();
  expect(h.calls.filter((c) => c.path === '/settings/external-model/install').map((c) => c.body)).toEqual([
    { repo: 'unsloth/Qwen3.5-2B-GGUF', file: 'Qwen3.5-2B-Q4_K_M.gguf', sha256: 'a'.repeat(64), bytes: 1_280_000_000, quant: 'Q4_K_M' }]);
  expect(h.calls.filter((c) => c.path === '/settings/external-model/pull').map((c) => c.body)).toEqual([{ name: 'hf.co/unsloth/Qwen3.5-2B-GGUF:Q4_K_M', bytes: 1_950_000_000 }]);
});

test('otro modelo: sin Ollama lo dice, y una API sin clave pide la clave antes de su lista', async () => {
  h = await openView();
  let host = { ...EXTERNAL, provider: 'local', model: '', ceilingHolds: false };
  h.reply('/settings/external-model/models', () => ({ body: host.provider === 'local' ? { ollama: 'missing' } : { needsKey: true } }));
  h.reply('/settings/external-model', (c) => {
    if (c.method === 'PUT') host = { ...host, ...(c.body as object) };
    return { body: host };
  });
  const p = h.page;
  await p.locator('.bx-gear').click();
  await p.locator('.settings-tab', { hasText: 'Modelo' }).click();
  await pickWhere(p, /Local/);
  await expect(p.getByText('No encontré Ollama en este PC')).toBeVisible();
  await pickWhere(p, /API/);
  await p.locator('.bxs-seg button', { hasText: 'OpenAI' }).click();
  await expect(p.getByText('Guarda tu clave y aquí aparecerán los modelos')).toBeVisible();
});

test('otro modelo local: sin clave ni gasto, dice que nada sale y «todo local» sigue siendo verdad', async () => {
  h = await openView();
  const host = { ...EXTERNAL, provider: 'local', model: 'qwen', url: 'http://127.0.0.1:11434', enabled: true, active: true, activeModel: 'qwen', activeLocal: true, ceilingHolds: false };
  h.reply('/settings/external-model', () => ({ body: host }));
  h.reply('/settings/external-model/models', () => ({ body: { models: [{ id: 'qwen', label: 'qwen · 5.2 GB', fits: true }] } }));
  const p = h.page;
  await expect(p.locator('.bx-priv')).toHaveText('Todo local');
  await p.locator('.bx-gear').click();
  await p.locator('.settings-tab', { hasText: 'Modelo' }).click();
  await expect(p.locator('.bx-inuse')).toContainText('qwen');
  await expect(p.locator('.bx-inuse')).toContainText('Local · Ollama');
  await expect(p.getByText('Conectado', { exact: true })).toBeVisible();
  await expect(p.getByText('Límite de memoria')).toHaveCount(0);
  await expect(p.getByText('la conversación no sale de este PC')).toBeVisible();
  await expect(p.getByLabel('Clave de la API')).toHaveCount(0);
  await expect(p.getByLabel('Tope de gasto en USD')).toHaveCount(0);
  await expect(p.getByText('también la conversación que ya tuviste')).toHaveCount(0);
  await p.locator('.settings-tab', { hasText: 'Privacidad' }).click();
  await expect(p.locator('button.toggle[aria-label="El modelo corre en este PC"]')).toHaveAttribute('aria-checked', 'true');
});

test('modelo por API: con la variable en 0 la sección no existe y la privacidad sigue igual', async () => {
  h = await openView();
  h.reply('/settings/external-model', () => ({ status: 404, body: { error: 'not_found' } }));
  await h.page.locator('.bx-gear').click();
  await h.page.locator('.settings-tab', { hasText: 'Modelo' }).click();
  await expect(h.page.getByRole('radio', { name: /Local|API/ })).toHaveCount(0);
  await expect(h.page.getByLabel('Clave de la API')).toHaveCount(0);
});

test('modelo por API: la clave se envía una vez, no se muestra de vuelta, y un rechazo se dice', async () => {
  h = await openView();
  let host = { ...EXTERNAL };
  h.reply('/settings/external-model', (c) => {
    if (c.method !== 'PUT') return { body: host };
    const body = c.body as Record<string, unknown>;
    if (body.enabled === true && !body.key && !host.hasKey) return { status: 409, body: { ok: false, error: 'external_model_no_key' } };
    host = { ...host, hasKey: host.hasKey || !!body.key, enabled: body.enabled === undefined ? host.enabled : !!body.enabled };
    return { body: host };
  });
  const p = h.page;
  await p.locator('.bx-gear').click();
  await p.locator('.settings-tab', { hasText: 'Modelo' }).click();
  await pickWhere(p, /API/);
  const use = p.getByRole('button', { name: 'Usar esta API' });
  await expect(p.getByText('también la conversación que ya tuviste')).toBeVisible();
  await use.click();
  await expect(p.getByRole('alert')).toHaveText('Primero guarda la clave');
  await expect(use).toBeVisible();

  const key = p.getByLabel('Clave de la API');
  await expect(key).toHaveAttribute('type', 'password');
  await key.fill('sk-secreta');
  await p.getByRole('button', { name: 'Guardar' }).click();
  await expect(key).toHaveValue('');
  await expect(p.getByText('Guardada y protegida en este PC')).toBeVisible();
  expect(h.calls.filter((c) => c.method === 'PUT' && (c.body as { key?: string }).key === 'sk-secreta')).toHaveLength(1);

  await use.click();
  await expect(p.locator('.bx-tag.on', { hasText: 'En uso' })).toBeVisible();
});

test('modelo por API: sin tope salvo que la persona escriba uno, y vaciarlo lo quita', async () => {
  h = await openView();
  let host: typeof EXTERNAL | (Omit<typeof EXTERNAL, 'ceilingUsd'> & { ceilingUsd: number | null }) = { ...EXTERNAL };
  h.reply('/settings/external-model', (c) => {
    if (c.method === 'PUT') host = { ...host, ...(c.body as object) };
    return { body: host };
  });
  const p = h.page;
  await p.locator('.bx-gear').click();
  await p.locator('.settings-tab', { hasText: 'Modelo' }).click();
  await pickWhere(p, /API/);
  const tope = p.getByLabel('Tope de gasto en USD');
  await expect(tope).toHaveValue('');
  await expect(tope).toHaveAttribute('placeholder', 'Sin tope');
  await tope.fill('7');
  await tope.blur();
  await expect.poll(() => h.calls.filter((c) => c.method === 'PUT').map((c) => c.body)).toContainEqual({ ceilingUsd: 7 });
  await tope.fill('');
  await tope.blur();
  await expect.poll(() => h.calls.filter((c) => c.method === 'PUT').map((c) => c.body)).toContainEqual({ ceilingUsd: null });
});

test('modelo por API: activo, la privacidad deja de decir que el modelo corre aquí', async () => {
  h = await openView();
  h.reply('/settings/external-model', () => ({ body: { ...EXTERNAL, enabled: true, hasKey: true, active: true, activeModel: 'claude-opus-5-5' } }));
  const p = h.page;
  await p.locator('.bx-gear').click();
  await p.locator('.settings-tab', { hasText: 'Privacidad' }).click();
  await expect(p.locator('button.toggle[aria-label="El modelo corre en este PC"]')).toHaveAttribute('aria-checked', 'false');
  await expect(p.getByText('Ahora no: usas claude-opus-5-5 por API')).toBeVisible();
  await expect(p.getByText('La conversación sale hacia la API en cada turno.')).toBeVisible();
  await expect(p.getByText('Ninguna. Todo se ha quedado en este PC.')).toHaveCount(0);
  await p.locator('.settings-tab', { hasText: 'Modelo' }).click();
  await expect(p.locator('.bx-inuse')).toContainText('claude-opus-5-5');
  await expect(p.locator('.bx-inuse')).toContainText('Por API · sale a internet');
  await expect(p.getByText('Conectado a la API')).toBeVisible();
  await p.locator('.settings-panel .bx-ib.plain').click();
  await expect(p.locator('.bx-priv')).toHaveText('Modelo por API');
});

test('modelo por API: apagado después de usarlo, la privacidad no dice que nada salió', async () => {
  h = await openView();
  h.reply('/settings/external-model', () => ({ body: { ...EXTERNAL, hasKey: true, apiThisRun: true } }));
  const p = h.page;
  await p.locator('.bx-gear').click();
  await p.locator('.settings-tab', { hasText: 'Privacidad' }).click();
  await expect(p.getByText('Desde que se abrió BAXY se conectó un modelo por API')).toBeVisible();
  await expect(p.getByText('Ninguna. Todo se ha quedado en este PC.')).toHaveCount(0);
});

// REV_VISTA V-03 (P1, 2026-11-09): with the API off again, the header said «N pedidos · todo local» and the rail «Todo local» of
// a conversation that had gone to it. The host marks each turn by API (FieldTranscript, kept with the conversation); the header
// speaks of this conversation (it counts its requests), the rail of now and of this conversation. Everything before the last
// turn by API went with it (the API gets the conversation it joins: 00_IDENTIDAD «la conversación que ya tenía»).
const API_TURNS = [
  { who: 'you', id: 'y1', ts: '12:00', text: 'hola' },
  { who: 'baxy', id: 'b1', ts: '12:00', text: 'Hola.', steps: [] },
  { who: 'you', id: 'y2', ts: '12:01', text: 'resume esto', api: true },
  { who: 'baxy', id: 'b2', ts: '12:01', text: 'Resumen.', steps: [], api: true },
];

test('modelo por API: una conversación que pasó por la API no se dice «todo local» al apagarla', async () => {
  h = await openView({ items: [...API_TURNS,
    { who: 'you', id: 'y3', ts: '12:02', text: 'gracias' }, { who: 'baxy', id: 'b3', ts: '12:02', text: 'De nada.', steps: [] }] });
  // a conversation opened again after BAXY restarted: nothing went out in this run
  h.reply('/settings/external-model', () => ({ body: { ...EXTERNAL, hasKey: true, apiThisRun: false } }));
  const p = h.page;
  await expect(p.locator('.bx-c4-tt .mt')).toHaveText('3 pedidos · parte salió por API');
  await expect(p.locator('.bx-priv')).toHaveText('Salió por API');
  await expect(p.locator('.bx-priv')).toHaveAttribute('title', /En esta conversación.*salió hacia esa empresa/);
  await p.locator('.bx-gear').click();
  await p.locator('.settings-tab', { hasText: 'Privacidad' }).click();
  await expect(p.getByText('En esta conversación, lo que le pasaste mientras usabas un modelo por API salió de este PC.')).toBeVisible();
  await expect(p.getByText('Ninguna. Todo se ha quedado en este PC.')).toHaveCount(0);
});

test('modelo por API: si nada vino después del último turno por API, salió entera, y en inglés también', async () => {
  h = await openView({ items: API_TURNS });
  h.reply('/settings/general', () => ({ body: { language: 'en', languageInUse: 'en' } }));
  h.reply('/settings/external-model', () => ({ body: { ...EXTERNAL, hasKey: true, apiThisRun: true } }));
  const p = h.page;
  await expect(p.locator('.bx-c4-tt .mt')).toHaveText('2 requests · went out by API');
  await expect(p.locator('.bx-priv')).toHaveText('Went out by API');
  // on now: the requests go out, the earlier ones with them
  h.reply('/settings/external-model', () => ({ body: { ...EXTERNAL, hasKey: true, enabled: true, active: true, activeModel: 'claude-opus-5-5', apiThisRun: true } }));
  await expect(p.locator('.bx-c4-tt .mt')).toHaveText('2 requests · going out by API');
  await expect(p.locator('.bx-priv')).toHaveText('Model by API');
});

// VIS2 blind review (P1): a long conversation drops its oldest items (the host keeps 400, the view 150) and with them the
// turns by API: «todo local» came back. The first item kept carries «apiBefore».
test('modelo por API: en una conversación larga, lo que salió por API antes de lo que se ve se sigue diciendo', async () => {
  const local = (n: number) => Array.from({ length: n }, (_, i) => i % 2
    ? { who: 'baxy', id: 'b' + i, ts: '12:00', text: 'Listo.', steps: [] } : { who: 'you', id: 'y' + i, ts: '12:00', text: 'local ' + i });
  // the host already dropped them: its first item says so
  h = await openView({ items: [{ ...local(1)[0], id: 'first', apiBefore: true }, ...local(9).slice(1)] });
  h.reply('/settings/external-model', () => ({ body: { ...EXTERNAL, hasKey: true } }));
  await expect(h.page.locator('.bx-c4-tt .mt')).toHaveText('5 pedidos · parte salió por API');
  await expect(h.page.locator('.bx-priv')).toHaveText('Salió por API');
  // the view's own shorter list drops them: the mark stays
  h.emit({ type: 'transcript', items: [...API_TURNS, ...local(160)] });
  await expect(h.page.locator('.bx-c4-tt .mt')).toContainText('parte salió por API');
});

test('modelo por API: una conversación nueva tras apagarla sí es «todo local», y la privacidad dice lo de antes', async () => {
  h = await openView({ items: [{ who: 'you', id: 'y1', ts: '12:00', text: 'hola' }, { who: 'baxy', id: 'b1', ts: '12:00', text: 'Hola.', steps: [] }] });
  h.reply('/settings/external-model', () => ({ body: { ...EXTERNAL, hasKey: true, apiThisRun: true } }));
  const p = h.page;
  await expect(p.locator('.bx-c4-tt .mt')).toHaveText('1 pedido · todo local');
  await expect(p.locator('.bx-priv')).toHaveText('Todo local');
  await p.locator('.bx-gear').click();
  await p.locator('.settings-tab', { hasText: 'Privacidad' }).click();
  await expect(p.getByText('Desde que se abrió BAXY se conectó un modelo por API')).toBeVisible();
  await expect(p.getByText('En esta conversación')).toHaveCount(0);
});

test('modelo por API: apagar no depende de lo que esté escrito', async () => {
  h = await openView();
  let host = { ...EXTERNAL, provider: 'compatible', model: 'm', url: 'https://ejemplo.com/v1', hasKey: true, enabled: true, active: true, activeModel: 'm', ceilingHolds: false };
  h.reply('/settings/external-model', (c) => {
    if (c.method !== 'PUT') return { body: host };
    const body = c.body as { url?: string; enabled?: boolean };
    if (body.url?.startsWith('http://')) return { status: 409, body: { ok: false, error: 'external_model_invalid_url' } };
    if (body.enabled !== undefined) host = { ...host, enabled: body.enabled, active: body.enabled };
    return { body: host };
  });
  const p = h.page;
  await p.locator('.bx-gear').click();
  await p.locator('.settings-tab', { hasText: 'Modelo' }).click();
  await pickWhere(p, /API/);
  await p.getByLabel('Dirección de la API').fill('http://no-vale.com/v1');
  await pickWhere(p, /De serie/);
  await expect.poll(() => h.calls.filter((c) => c.method === 'PUT').map((c) => c.body)).toContainEqual({ enabled: false });
});

test('teclado: un panel abierto toma el foco y al cerrarse lo devuelve a lo que lo abrió', async () => {
  h = await openView();
  const p = h.page;
  const inPanel = () => p.evaluate(() => !!document.activeElement?.closest('.panel'));
  await p.locator('.bx-gear').focus();
  await p.keyboard.press('Enter');
  await expect(p.locator('.settings-panel')).toBeVisible();
  await expect.poll(inPanel, 'Ajustes tiene el foco').toBe(true);
  await p.keyboard.press('Escape');
  await expect(p.locator('.settings-panel')).toHaveCount(0);
  await expect(p.locator('.bx-gear')).toBeFocused();
  const memory = p.locator('button', { hasText: 'Memoria' }).first();
  await memory.focus();
  await p.keyboard.press('Enter');
  await expect.poll(inPanel, 'Memoria tiene el foco').toBe(true);
  await p.keyboard.press('Escape');
  await expect(memory).toBeFocused();
});

test('Enter con el foco en un botón fuera de la tarjeta (el engranaje tras cerrar Ajustes) responde Sí', async () => {
  h = await openView();
  const p = h.page;
  await p.locator('.bx-gear').focus();
  await p.keyboard.press('Enter');
  await expect(p.locator('.settings-panel')).toBeVisible();
  await p.keyboard.press('Escape');
  await expect(p.locator('.bx-gear')).toBeFocused();
  h.emit({ type: 'item', item: card('c1') });
  await expect(p.locator('.bx-card.s-pending')).toHaveCount(1);
  await siReady(p);
  await p.keyboard.press('Enter');
  await expect.poll(answers).toEqual([{ approve: true, card: 'c1' }]);
  await expect(p.locator('.settings-panel')).toHaveCount(0);
});

test('el estado de BAXY se lee entero arriba de la cara', async () => {
  // VIVO1 (2026-11-09): in the real App «Listo» was not seen and «Hablando» read «Hab»: the label was 14 px wide.
  h = await openView();
  const label = h.page.locator('.bx-statel');
  const whole = () => label.evaluate((e) => ({ shown: e.clientWidth, needs: e.scrollWidth }));
  await expect(label).toContainText('Listo');
  const idle = await whole();
  expect(idle.needs, `«Listo» cabe en ${idle.shown} px`).toBeLessThanOrEqual(idle.shown);
  h.emit({ type: 'state', value: 'speaking' });
  await expect(label).toContainText('Hablando');
  const speaking = await whole();
  expect(speaking.needs, `«Hablando» cabe en ${speaking.shown} px`).toBeLessThanOrEqual(speaking.shown);
});

test('un error de voz es un estado de la interfaz: nada en el subtítulo de BAXY ni una frase como si la dijera él', async () => {
  h = await openView();
  h.emit({ type: 'voice', available: true, mode: 'wake', speaking: false, last_error: 'voice_error' });
  await expect(h.page.locator('.bx-statel')).toContainText('Falló la escucha');
  await expect(h.page.locator('.bx-cap')).toHaveText('');
  const shown = await h.page.locator('body').innerText();
  expect(shown).not.toMatch(/entend|lo repites/i);
});

test('ningún aviso ni etiqueta fija de la vista habla como BAXY en primera persona', async () => {
  const firstPerson = /\b(me pongo|me activo|no pude|te oí|estaba ocupado|pregunto|escucho|necesito|te aviso)\b/i;
  h = await openView({ items: [card('c1')] });
  const p = h.page;
  await expect(p.locator('.bx-card .tag')).not.toHaveText(firstPerson);
  h.reply('/power', () => ({ status: 409, body: { ok: false, error: 'turn_in_progress' } }));
  await p.locator('button', { hasText: 'Activo' }).first().click();
  await expect(p.locator('.bx-notice')).toBeVisible();
  await expect(p.locator('.bx-notice')).not.toHaveText(firstPerson);
  await expect(p.locator('.bx-notice')).toHaveCount(0);
  h.emit({ type: 'voice', available: true, mode: 'wake', speaking: false, last_error: 'voice_dropped_busy' });
  await expect(p.locator('.bx-notice')).toContainText('ocupad');
  await expect(p.locator('.bx-notice')).not.toHaveText(firstPerson);
});

test('el catálogo no habla como BAXY («Qué puedo hacer») y su nombre cabe en el riel a cada ancho', async () => {
  h = await openView();
  const p = h.page;
  const rail = p.locator('.bx2 button', { hasText: /puedo hacer|Capacidades/ }).first();
  await expect(rail).not.toContainText(/puedo/i);
  for (const [w, ht] of [[1280, 720], [1100, 700], [900, 640], [1920, 1080]]) {
    await p.setViewportSize({ width: w, height: ht });
    await p.waitForTimeout(150);
    // no label of the rail's panel buttons overflows its button
    const over = await p.evaluate(() => [...document.querySelectorAll<HTMLElement>('.bx2 button')]
      .filter((b) => /Historial|Memoria|Alarmas|Capacidades|Propuestas|Ajustes|puedo/.test(b.innerText))
      .flatMap((b) => [...b.querySelectorAll<HTMLElement>('span')].filter((s) => s.scrollWidth > s.clientWidth + 1 || s.getBoundingClientRect().right > b.getBoundingClientRect().right + 1).map((s) => s.innerText)));
    expect(over, `${w}×${ht}`).toEqual([]);
  }
});

test('el panel del catálogo se titula «Capacidades de BAXY»', async () => {
  h = await openView();
  h.reply('/catalog', () => ({ body: { total: 1, groups: [{ name: 'Apps', items: [{ name: 'app.open', title: 'Abrir una app', confirm: 'never' }] }] } }));
  await h.page.getByRole('button', { name: /Capacidades/ }).click();
  await expect(h.page.locator('.panel-title')).toHaveText('Capacidades de BAXY');
});

test('ajustes: la pestaña Confirmación dice que sólo pregunta antes de lo destructivo o peligroso', async () => {
  h = await openView();
  await h.page.locator('.bx-gear').click();
  await h.page.locator('.settings-tab', { hasText: 'Confirmación' }).click();
  const tip = h.page.locator('.settings-panel .st-tip');
  await expect(tip).toContainText('sólo antes de lo destructivo o peligroso');
  for (const w of ['vaciar la papelera', 'desinstalar', 'comprar o pagar', 'forzar el cierre']) await expect(tip).toContainText(w);
  // creating a calendar event goes straight through since the owner's decision of 2026-10-25
  await expect(tip).not.toContainText(/calendario/i);
});

test('sin tarjeta gráfica el arranque dice por qué tarda y cuánto lleva; nada de eso con una que sirve', async () => {
  h = await openView();
  const boot = { type: 'boot', stt: true, wake: true, tts: true, model: false, startedAt: Date.now(), readyAt: null };
  h.emit({ type: 'agent', built: true, ready: false, powered: true });
  h.emit({ ...boot, reading: { done: 16500, total: 48500, seconds_left: 660 }, onProcessor: true });
  const panel = h.page.locator('.bx-boot');
  await expect(panel).toContainText('Preparando el modelo · 34 % · quedan unos 11 min');
  await expect(panel).toContainText('no está usando una tarjeta gráfica');
  h.emit({ ...boot, reading: { done: 2048, total: 48500, seconds_left: 30 }, onProcessor: false });
  await expect(panel).toContainText('Preparando el modelo · 4 % · queda menos de 1 min');
  await expect(panel).not.toContainText('tarjeta gráfica');
});

test('un equipo demasiado lento dice la causa y qué hacer, sin contar arranques que no hubo', async () => {
  h = await openView();
  h.emit({ type: 'agent', built: true, ready: false, powered: true, failure: 'engine_unavailable', failureCause: 'lectura_lenta',
    failureRead: { tokens_per_s: 20, minutes: 41 } });
  const card = h.page.locator('.bx-breakdown');
  await expect(card).toContainText('este equipo lee el modelo demasiado lento: prepararlo tardaría unos 41 min');
  await expect(card).toContainText('tarjeta gráfica dedicada con 4 GB');
  await expect(card).not.toContainText('varias veces');
  await expect(card.locator('.bx-btn', { hasText: 'Reintentar' })).toBeVisible();
});

test('la avería de un equipo lento dice además que no usa tarjeta gráfica cuando no la usa', async () => {
  h = await openView();
  h.emit({ type: 'boot', stt: true, wake: true, tts: true, model: false, startedAt: 1, readyAt: null, failed: 'mind_unavailable',
    lastFailure: 'lectura_lenta', failureRead: { tokens_per_s: 46, minutes: 54 }, onProcessor: true });
  h.emit({ type: 'agent', built: true, ready: false, powered: true, failure: 'engine_unavailable', failureCause: 'lectura_lenta',
    failureRead: { tokens_per_s: 46, minutes: 54 } });
  const card = h.page.locator('.bx-breakdown');
  await expect(card).toContainText('no está usando una tarjeta gráfica');
  await expect(card).toContainText('prepararlo tardaría unos 54 min');
});

test('otra avería del arranque sigue diciendo que falló varias veces', async () => {
  h = await openView();
  h.emit({ type: 'agent', built: true, ready: false, powered: true, failure: 'engine_unavailable', failureCause: 'ram_insuficiente' });
  await expect(h.page.locator('.bx-breakdown')).toContainText('varias veces');
});

test('DEP5: la tarjeta de confirmación que buscan las pruebas de la App real es la que pinta la vista', async () => {
  h = await openView({ items: [card('c1')] });
  await expect(h.page.locator(CONFIRM_CARD)).toHaveCount(1);
});

test('DEP5: lo que salió a internet se dice una vez en la tarjeta, también con «Cómo lo comprobé» abierto', async () => {
  const net = 'búsqueda «quién escribió Cien años de soledad»';
  h = await openView({ items: [{ who: 'baxy', id: 'b1', ts: '12:00', text: 'La escribió Gabriel García Márquez.', net,
    steps: [{ id: 's1', label: 'Buscar en la web', fam: 'web', status: 'read', obs: 'Leído', net }] }] });
  const p = h.page;
  await p.getByRole('button', { name: /Cómo lo comprobé/ }).click();
  await expect(p.locator('.bx-how-s')).toContainText('Buscar en la web');
  await expect(p.locator('.bx-c4-baxy', { hasText: 'salió a internet' }).getByText('salió a internet')).toHaveCount(1);
});

// INT15: the credit a search's source asks for (e36378f9e; THIRD_PARTY_NOTICES: DuckDuckGo, OpenStreetMap, Wikipedia)
// reaches the v5 detail with the step's observation, as SourceCreditTests leaves it in the step the App sends, and is
// not dropped as an observation that only repeats the status
test('INT15: el paso de una búsqueda dice la fuente que contestó en «Cómo lo comprobé»', async () => {
  const net = 'búsqueda «farmacias cerca de la Plaza Mayor»';
  h = await openView({ items: [{ who: 'baxy', id: 'b1', ts: '12:00', text: 'Encontré tres farmacias.', net,
    steps: [{ id: 's1', label: 'Buscar lugares', fam: 'web', status: 'read', obs: 'Leído · Fuente: OpenStreetMap', net }] }] });
  const p = h.page;
  await p.getByRole('button', { name: /Cómo lo comprobé/ }).click();
  await expect(p.locator('.bx-how-s')).toContainText('Buscar lugares');
  // said once, on the card's face (OSMF): the step's line does not repeat it
  await expect(p.locator('.bx-c4-baxy').getByText('OpenStreetMap')).toHaveCount(1);
});

// INT15 «Abierto»: the OSMF's Attribution Guidelines (osmfoundation.org/wiki/Licence/Attribution_Guidelines, edited
// 10-09-2026): the attribution «should not require individuals to interact» with the work to see it, and «must be placed
// in the vicinity of the produced work». The source is on the card itself, with «Cómo lo comprobé» closed.
test('OSMF: la fuente de una respuesta se ve en la tarjeta sin abrir nada', async () => {
  h = await openView({ items: [{ who: 'baxy', id: 'b1', ts: '12:00', text: 'Encontré tres farmacias.', net: 'búsqueda «farmacias»',
    steps: [{ id: 's1', label: 'Buscar lugares', fam: 'web', status: 'read', obs: 'Leído · Fuente: OpenStreetMap', net: 'búsqueda «farmacias»' }] }] });
  const p = h.page;
  await expect(p.getByRole('button', { name: /Cómo lo comprobé/ })).toHaveAttribute('aria-expanded', 'false');
  await expect(p.locator('.bx-c4-baxy .bx-src')).toHaveText('Fuente: OpenStreetMap');
  await expect(p.locator('.bx-c4-baxy .bx-src')).toBeVisible();
});

// VIVO2 F16: the model's reply «…rápida:\n\n1. …\n\n2. …» was drawn as one paragraph («…rápida: 1. … 2. …»): the line breaks it
// wrote are kept (CSS Text 3, white-space: pre-line), the rest of its spaces collapse as before.
test('una respuesta con párrafos se ve en párrafos, no corrida en una sola línea', async () => {
  h = await openView({ items: [{ who: 'baxy', id: 'b1', ts: '12:00', text: '\nTres ideas para cenar:\n\n1. Ensalada de quinoa.\n\n2. Tacos de frijoles.\n', steps: [] }] });
  const tx = h.page.locator('.bx-c4-baxy .tx');
  await expect(tx).toBeVisible();
  // its own breaks, and none before or after it; F16: its numbered list is a list (CommonMark 5.2-5.3)
  expect(await tx.innerText()).toMatch(/^Tres ideas para cenar:\n+Ensalada de quinoa\.\n+Tacos de frijoles\.$/);
  await expect(tx.locator('ol > li')).toHaveText(['Ensalada de quinoa.', 'Tacos de frijoles.']);
});

// ABIERTOS_VIVO H1 / VIVO2 F16 (P1, 2026-11-09): lists came out run together and the model's «**» showed as they were. The view
// renders the marks the model writes (CommonMark: emphasis, lists, code, headings); nothing of the answer is rewritten.
// REV_VISTA V-12 (P2, 2026-11-09): the asks inside Settings (role=dialog) took no Escape and let the focus out (Escape closed
// all of Settings); the sections were buttons with aria-pressed, not tabs; the cards (role=radio) took no arrows.
// WAI-ARIA APG: dialog-modal, tabs (vertical, automatic activation), radio (roving tabindex).
test('V-12: un aviso dentro de Ajustes atiende Escape, encierra el foco y lo devuelve', async () => {
  h = await openView();
  const p = h.page;
  await p.locator('.bx-gear').click();
  await p.locator('.settings-tab', { hasText: 'Confirmación' }).click();
  const brakes = p.getByRole('radio', { name: 'Sin frenos' });
  await brakes.click();
  const ask = p.getByRole('alertdialog', { name: '¿Activar sin frenos?' });
  await expect(ask.getByRole('button', { name: 'Cancelar' })).toBeFocused();
  await p.keyboard.press('Tab');
  await expect(ask.getByRole('button', { name: 'Sí, activar sin frenos' })).toBeFocused();
  await p.keyboard.press('Tab');
  await expect(ask.getByRole('button', { name: 'Cancelar' })).toBeFocused();
  await p.keyboard.press('Shift+Tab');
  await expect(ask.getByRole('button', { name: 'Sí, activar sin frenos' })).toBeFocused();
  await p.keyboard.press('Escape');
  await expect(ask).toHaveCount(0);
  await expect(p.locator('.settings-panel')).toBeVisible();
  await expect(brakes).toBeFocused();
  expect(h.calls.filter((c) => c.method === 'PUT' && c.path === '/confirmation')).toEqual([]);
});

test('V-12: las secciones de Ajustes son pestañas y se recorren con las flechas, Inicio y Fin', async () => {
  h = await openView();
  const p = h.page;
  await p.locator('.bx-gear').click();
  const list = p.getByRole('tablist', { name: 'Secciones de ajustes' });
  await expect(list).toHaveAttribute('aria-orientation', 'vertical');
  const general = list.getByRole('tab', { name: 'General' });
  await expect(general).toHaveAttribute('aria-selected', 'true');
  await expect(list.locator('[role=tab][tabindex="0"]')).toHaveCount(1);
  await expect(p.getByRole('tabpanel', { name: 'General' })).toBeVisible();
  await general.focus();
  await p.keyboard.press('ArrowDown');
  const second = list.getByRole('tab', { name: 'Personalización' });
  await expect(second).toBeFocused();
  await expect(second).toHaveAttribute('aria-selected', 'true');
  await expect(p.getByRole('tabpanel', { name: 'Personalización' })).toBeVisible();
  await p.keyboard.press('End');
  await expect(list.getByRole('tab').last()).toBeFocused();
  await expect(list.getByRole('tab').last()).toHaveAttribute('aria-selected', 'true');
  await p.keyboard.press('Home');
  await expect(general).toBeFocused();
  await p.keyboard.press('ArrowUp');
  await expect(list.getByRole('tab').last()).toBeFocused();
});

test('V-12: las tarjetas se recorren con las flechas; las que cambian el modelo sólo eligen con Espacio', async () => {
  h = await openView();
  h.reply('/settings/external-model', () => ({ body: { ...EXTERNAL } }));
  const p = h.page;
  await p.locator('.bx-gear').click();
  const lang = p.getByRole('radiogroup', { name: 'Idioma de la interfaz' });
  await expect(lang.locator('[role=radio][tabindex="0"]')).toHaveCount(1);
  await lang.locator('[role=radio][tabindex="0"]').focus();
  await p.keyboard.press('ArrowRight');
  // a choice that only changes how the view looks or talks: the arrow chooses it (APG radio)
  await expect.poll(() => h.calls.filter((c) => c.method === 'PUT' && c.path === '/settings/language').length).toBeGreaterThan(0);
  await p.locator('.settings-tab', { hasText: 'Modelo' }).click();
  const where = p.getByRole('radiogroup', { name: 'Dónde piensa BAXY' });
  const stock = where.getByRole('radio', { name: /De serie/ });
  await expect(stock).toHaveAttribute('tabindex', '0');
  await stock.focus();
  await p.keyboard.press('ArrowDown');
  const local = where.getByRole('radio', { name: /Local/ });
  await expect(local).toBeFocused();
  // where BAXY thinks: the arrow only moves; Space chooses
  await expect(local).toHaveAttribute('aria-checked', 'false');
  await p.keyboard.press('Space');
  await expect(local).toHaveAttribute('aria-checked', 'true');
});

// REV_LEGAL LEG-15 (2026-11-09): the licenses and the privacy policy went in the package's folder and nothing in the App
// opened them. Settings › Privacidad asks the host for one of two words, never a path.
// VIS3 (VIVO6 fila 4): the policy is PRIVACIDAD.md, and a Windows with no program for .md showed «Open with» instead of it.
// Its text is read here (GET /settings/legal/privacy) and drawn, in the view's language; only the licenses' folder is opened.
const POLICY = '# BAXY: política de privacidad / Privacy policy\n\nÚltima actualización · Last updated\n\n## Español\n\n**Qué guarda.** Tus conversaciones, en este PC.\n\n| Cuando pides | Servicio |\n|---|---|\n| El tiempo | Un servicio meteorológico |\n\n## English\n\n**What it keeps.** Your conversations, on this PC.\n';
test('privacidad: la política se lee dentro de Ajustes y las licencias abren su carpeta', async () => {
  h = await openView();
  let found = true;
  h.reply('/settings/legal/open', () => (found ? { body: { ok: true } } : { status: 404, body: { error: 'legal_not_found' } }));
  h.reply('/settings/legal/privacy', () => (found ? { body: { text: POLICY } } : { status: 404, body: { error: 'legal_not_found' } }));
  const p = h.page;
  await p.locator('.bx-gear').click();
  await p.locator('.settings-tab', { hasText: 'Privacidad' }).click();
  await p.locator('.bx-fold-h', { hasText: 'Privacidad y licencias' }).click();
  await p.getByRole('button', { name: 'Abrir la política de privacidad' }).click();
  const policy = p.getByRole('region', { name: 'Política de privacidad' });
  await expect(policy.locator('strong', { hasText: 'Qué guarda.' })).toBeVisible();
  await expect(policy).not.toContainText('**');
  await expect(policy).not.toContainText('##');
  await expect(policy.getByRole('cell', { name: 'Un servicio meteorológico' })).toBeVisible();
  await expect(policy).not.toContainText('|');
  await expect(policy).not.toContainText('What it keeps');
  await p.getByRole('button', { name: 'Cerrar la política de privacidad' }).click();
  await expect(policy).toHaveCount(0);
  await p.getByRole('button', { name: 'Abrir las licencias' }).click();
  await expect.poll(() => h.calls.filter((c) => c.path === '/settings/legal/open').map((c) => c.body)).toEqual([{ doc: 'licenses' }]);
  found = false;
  await p.getByRole('button', { name: 'Abrir la política de privacidad' }).click();
  await expect(p.getByRole('alert').filter({ hasText: 'No encontré los textos legales' })).toBeVisible();
  await expect(policy).toHaveCount(0);
  found = true;
  h.reply('/settings/general', () => ({ body: { language: 'en', languageInUse: 'en' } }));
  await p.keyboard.press('Escape');
  await p.locator('.bx-gear').click();
  await p.locator('.settings-tab', { hasText: 'Privacy' }).click();
  // the fold stays as it was left (open)
  await p.getByRole('button', { name: 'Open the privacy policy' }).click();
  const english = p.getByRole('region', { name: 'Privacy policy' });
  await expect(english.locator('strong', { hasText: 'What it keeps.' })).toBeVisible();
  await expect(english).not.toContainText('Qué guarda');
  expect(h.calls.filter((c) => c.path === '/settings/legal/open').map((c) => c.body)).toEqual([{ doc: 'licenses' }]);
});

// VIS3 (VIVO6 fila 4): Settings › Versión said no number until «Buscar actualizaciones» asked GitHub. The installed version is
// the App's own stamp, in General's settings: it is said before any check, with no request to /update, and stays said after.
test('versión: la fila dice la versión instalada sin buscar, y la sigue diciendo tras buscar, en los dos idiomas', async () => {
  h = await openView();
  h.reply('/settings/general', () => ({ body: { language: 'es', languageInUse: 'es', version: '1.3.2' } }));
  h.reply('/update', () => ({ body: { ok: true, channel: 'github', installed: '1.3.2', latest: '1.4.0', newer: true, downloadBytes: 83886080 } }));
  const p = h.page;
  await p.locator('.bx-gear').click();
  const hint = p.locator('.bxs-row', { hasText: 'Versión' }).locator('.h').first();
  await expect(hint).toHaveText('Instalada: 1.3.2');
  expect(h.calls.filter((c) => c.path === '/update')).toEqual([]);
  await p.getByRole('button', { name: 'Buscar actualizaciones' }).click();
  await expect(hint).toHaveText('Instalada: 1.3.2 · Hay una versión nueva: 1.4.0 (instalador de 80 MB)');
  h.reply('/update', () => ({ body: { ok: false, error: 'baxy_update_already_latest', channel: 'github', installed: '1.3.2', latest: '1.3.2', newer: false } }));
  h.reply('/settings/general', () => ({ body: { language: 'en', languageInUse: 'en', version: '1.3.2' } }));
  await p.keyboard.press('Escape');
  await p.locator('.bx-gear').click();
  const en = p.locator('.bxs-row', { hasText: 'Version' }).locator('.h').first();
  await expect(en).toHaveText('Installed: 1.3.2');
  await p.getByRole('button', { name: 'Check for updates' }).click();
  await expect(en).toHaveText('You have the latest version (1.3.2)');
});

// VIS4 (owner, 2026-11-10: «al lado del baxy arriba a la izquierda ... la version»): the rail says the installed version
// beside its «BAXY», on that line's baseline, smaller and in the network line's muted colour, and only once the App gave
// it (GET /settings/general «version», VIS3's). On screen the number alone, without a build's «+…»; a screen reader hears
// «versión 1.3.3». If it does not fit whole it is not shown, and it never moves the network line under it.
test('versión en el carril: junto a «BAXY» en su línea, sólo cuando la App la dio, entera o nada, en los dos temas e idiomas', async () => {
  h = await openView();
  const p = h.page;
  const ver = p.locator('.left-header .bx-ver');
  const read = () => p.evaluate(() => {
    const q = (s: string) => document.querySelector(s) as HTMLElement | null;
    const baseline = (e: HTMLElement) => {
      const m = document.createElement('span');
      m.style.cssText = 'display:inline-block;width:0;height:0;vertical-align:baseline';
      e.appendChild(m);
      const y = m.getBoundingClientRect().top;
      m.remove();
      return y;
    };
    const name = q('.left-header .name')!, row = q('.left-header .row')!, priv = q('.bx-priv')!, v = q('.left-header .bx-ver');
    const r = row.getBoundingClientRect(), n = name.getBoundingClientRect(), b = v?.getBoundingClientRect();
    const shown = v ? [...v.childNodes].filter((c) => c.nodeType === Node.TEXT_NODE).map((c) => c.textContent).join('') : null;
    return {
      privTop: priv.getBoundingClientRect().top, shown,
      whole: b ? b.left >= n.right && b.right <= r.right + 0.5 && b.top >= r.top - 0.5 && b.bottom <= r.bottom + 0.5 : null,
      none: b ? b.right <= r.left || b.left >= r.right || b.top >= r.bottom || b.bottom <= r.top : null,
      sameLine: v ? Math.abs(baseline(name) - baseline(v)) <= 1 : null,
      smaller: v ? parseFloat(getComputedStyle(v).fontSize) < parseFloat(getComputedStyle(name).fontSize) : null,
      muted: v ? getComputedStyle(v).color === getComputedStyle(priv).color && getComputedStyle(v).color !== getComputedStyle(name).color : null,
    };
  });
  // before the App gives it: no number, no «—»
  await expect(p.locator('.left-header .name')).toBeVisible();
  await expect(ver).toHaveCount(0);
  await expect(p.locator('.left-header .row')).toHaveText('baxy');
  const before = await read();
  h.reply('/settings/general', () => ({ body: { language: 'es', languageInUse: 'es', version: '1.3.3+c2a4c76ac' } }));
  await expect(ver).toHaveText('versión 1.3.3');
  await expect(p.locator('.left-header')).toMatchAriaSnapshot('- text: baxy versión 1.3.3 Todo local');
  const dark = await read();
  expect(dark).toEqual({ privTop: before.privTop, shown: '1.3.3', whole: true, none: false, sameLine: true, smaller: true, muted: true });
  // the full stamp the App gave stays Settings' own
  await p.locator('.bx-gear').click();
  await expect(p.locator('.bxs-row', { hasText: 'Versión' }).locator('.h').first()).toHaveText('Instalada: 1.3.3+c2a4c76ac');
  await p.getByRole('button', { name: /^Apariencia/ }).click();
  await p.locator('.bxs-seg button', { hasText: 'Claro' }).click();
  await expect(p.locator('html')).toHaveClass(/(^| )lt( |$)/);
  await p.keyboard.press('Escape');
  expect(await read()).toEqual(dark);
  // a rail too narrow for it, or a version too long: whole or not at all, and the network line stays where it was
  for (const [rail, version, fits] of [['120px', '1.3.3', true], ['100px', '1.3.3', false], ['204px', '2026.11.10-nightly.12345', false]] as const) {
    h.reply('/settings/general', () => ({ body: { language: 'es', languageInUse: 'es', version } }));
    await p.locator('.bx2').evaluate((e, w) => e.style.setProperty('--rail', w), rail);
    await expect(ver).toHaveText('versión ' + version);
    await expect.poll(async () => { const r = await read(); return [r.privTop, fits ? r.whole : r.none]; }).toEqual([before.privTop, true]);
  }
  h.reply('/settings/general', () => ({ body: { language: 'en', languageInUse: 'en', version: '1.3.3' } }));
  await p.locator('.bx2').evaluate((e) => e.style.setProperty('--rail', '204px'));
  await expect(ver).toHaveText('version 1.3.3');
  await expect(p.locator('.left-header')).toMatchAriaSnapshot('- text: baxy version 1.3.3 All local');
  expect((await read()).whole).toBe(true);
});

// LEG1 §5 (INFORME_LEG1, «Para INS1», 2026-11-09): four texts of the view said what the agreements no longer say. Each now
// says the agreements' own sentence (licenses/PRIVACIDAD.md, documentacion/itchio/LEGAL.md §5 as LEG1 left them).
test('textos legales en la vista: itch.io, la búsqueda de versión, lo que sale del PC y una copia de tienda', async () => {
  h = await openView();
  h.reply('/update', () => ({ body: { ok: true, channel: 'itch', installed: '1.3.1', latest: null, newer: false } }));
  h.reply('/settings/general', () => ({ body: { language: 'es', languageInUse: 'es', autostart: null, autostartBlocked: 'steam_copy' } }));
  const p = h.page;
  await p.locator('.bx-gear').click();
  const version = p.locator('.bxs-row', { hasText: 'Versión' }).locator('.h').first();
  await p.getByRole('button', { name: 'Buscar actualizaciones' }).click();
  await expect(version).toContainText('BAXY instalado con la app de itch.io lo actualiza esa app');
  await expect(version).toContainText('Si lo bajaste de la página de itch.io sin su app, nada lo actualiza solo');
  const notice = p.locator('.bxs-row', { hasText: 'Avisar de versiones nuevas' });
  await expect(notice).toContainText('Buscar una versión nueva no manda nada de lo que dices ni de tus archivos: sólo la versión de BAXY, desde tu IP');
  await expect(notice).not.toContainText('no envía nada tuyo');
  const autostart = p.locator('.bxs-row', { hasText: 'Arrancar con Windows' });
  await expect(autostart).toContainText('Steam');
  await expect(autostart).not.toContainText(/desarrollo|run_renew/);
  await p.locator('.settings-tab', { hasText: 'Privacidad' }).click();
  const here = p.locator('.bxs-row', { hasText: 'El modelo corre en este PC' });
  await expect(here).toContainText('Lo que dices, tus archivos, tu pantalla y tus recuerdos no salen de tu computador, salvo en los casos que dice la política de privacidad');
  await expect(here).not.toContainText('Nada de lo tuyo sale sin que lo pidas');
});

// REV_VISTA V-13: the spending and the rail's readings wrote a decimal point in Spanish too (toFixed).
test('números: el gasto y la memoria del carril con coma en español y punto en inglés', async () => {
  h = await openView();
  h.reply('/settings/external-model', () => ({ body: { ...EXTERNAL, hasKey: true, spentUsd: 1.5 } }));
  h.reply('/metrics', () => ({ body: { cpu: 20, gpu: 10, temp: 50, model_vram_gb: 4.8, model_ram_gb: 1.25 } }));
  const p = h.page;
  await expect(p.locator('.bx-gauge[title*="Modelo BAXY"], [title*="Modelo BAXY"]').first()).toHaveAttribute('title', /vídeo 4,8 GB · RAM 1,3 GB/);
  await p.locator('.bx-gear').click();
  await p.locator('.settings-tab', { hasText: 'Modelo' }).click();
  await pickWhere(p, /API/);
  await expect(p.getByText('1,50 USD').first()).toBeVisible();
  h.reply('/settings/general', () => ({ body: { language: 'en', languageInUse: 'en' } }));
  await p.keyboard.press('Escape');
  await expect(p.locator('[title*="BAXY model"]').first()).toHaveAttribute('title', /VRAM 4\.8 GB · RAM 1\.3 GB/);
  await p.locator('.bx-gear').click();
  await p.locator('.settings-tab', { hasText: 'Model' }).click();
  await pickWhere(p, /API/);
  await expect(p.getByText('1.50 USD').first()).toBeVisible();
});

// REV_VISTA V-09: an update that failed says what happened and what to do, never its code.
test('actualizar: un fallo dice su causa y la salida, nunca su código, en los dos idiomas', async () => {
  h = await openView();
  let error = 'baxy_update_source_unknown';
  h.reply('/update', () => ({ body: { ok: false, error, channel: 'github', installed: '1.3.1' } }));
  const p = h.page;
  await p.locator('.bx-gear').click();
  const hint = p.locator('.bxs-row', { hasText: 'Versión' }).locator('.h').first();
  await p.getByRole('button', { name: 'Buscar actualizaciones' }).click();
  await expect(hint).toContainText('no sabe dónde se publicó');
  await expect(hint).not.toContainText('baxy_update');
  error = 'baxy_update_store_not_opened';
  await p.getByRole('button', { name: 'Buscar actualizaciones' }).click();
  await expect(hint).toContainText('Windows no abrió la tienda');
  h.reply('/settings/general', () => ({ body: { language: 'en', languageInUse: 'en' } }));
  await p.keyboard.press('Escape');
  await p.locator('.bx-gear').click();
  error = 'baxy_update_by_itch_app';
  await p.getByRole('button', { name: 'Check for updates' }).click();
  await expect(p.locator('.bxs-row', { hasText: 'Version' }).locator('.h').first()).toContainText('itch.io app');
  await expect(p.locator('.bxs-row', { hasText: 'Version' }).locator('.h').first()).not.toContainText('baxy_update');
});

test('F16: el marcado que escribe el modelo se ve como marcado: negrita, cursiva, listas y código, sin asteriscos', async () => {
  const text = 'Para tu cena:\n\n## Rápidas\n\n**Opción rápida**: tacos.\n\n- Quinoa *tibia*\n- Tacos con `salsa`\n\n3. Tres\n4. Cuatro\n\n```\nnpm run build\n```';
  h = await openView({ items: [{ who: 'baxy', id: 'b1', ts: '12:00', text, steps: [] }] });
  const tx = h.page.locator('.bx-c4-baxy .tx');
  await expect(tx.locator('strong', { hasText: 'Opción rápida' })).toHaveCount(1);
  await expect(tx.locator('em')).toHaveText('tibia');
  await expect(tx.locator('ul > li')).toHaveText(['Quinoa tibia', 'Tacos con salsa']);
  await expect(tx.locator('ol > li')).toHaveText(['Tres', 'Cuatro']);
  await expect(tx.locator('ol')).toHaveAttribute('start', '3');
  await expect(tx.locator('li code')).toHaveText('salsa');
  await expect(tx.locator('pre code')).toHaveText('npm run build');
  await expect(tx.locator('[role=heading]')).toHaveText('Rápidas');
  expect(await tx.innerText()).not.toMatch(/\*|`|#/);
});

test('F16: lo que el modelo escribe como HTML, enlace o imagen se ve como texto: nada se ejecuta, se abre ni se descarga', async () => {
  const text = 'Mira <img src="http://ejemplo.invalid/x.png" onerror="window.__f16=1"> y <b>esto</b>.\n\n'
    + '[la página](http://ejemplo.invalid/a) ![una foto](http://ejemplo.invalid/f.png) www.ejemplo.invalid\n\n<script>window.__f16=2</script>';
  const asked: string[] = [];
  h = await openView();
  h.page.on('request', (r) => { if (r.url().includes('ejemplo.invalid')) asked.push(r.url()); });
  h.emit({ type: 'transcript', items: [{ who: 'baxy', id: 'b1', ts: '12:00', text, steps: [] }] });
  const tx = h.page.locator('.bx-c4-baxy .tx');
  await expect(tx).toContainText('la página (http://ejemplo.invalid/a)');
  await expect(tx).toContainText('una foto (http://ejemplo.invalid/f.png)');
  await expect(tx).toContainText('<b>esto</b>');
  await expect(tx).toContainText('<script>window.__f16=2</script>');
  await expect(tx.locator('a, img, script, b, iframe')).toHaveCount(0);
  expect(await h.page.evaluate(() => (window as unknown as { __f16?: number }).__f16)).toBeUndefined();
  expect(asked).toEqual([]);
});

test('F16: los subtítulos bajo la cara dicen la respuesta sin sus marcas, como la voz', async () => {
  h = await openView();
  h.emit({ type: 'state', value: 'speaking' });
  h.emit({ type: 'item', item: { who: 'baxy', id: 'b9', ts: '12:00', text: '**Listo**: abrí `Steam` y *el juego*.', steps: [] } });
  await expect(h.page.locator('.bx-sub')).toHaveText(/^\s*Listo: abrí Steam y el juego\.\s*$/);
});

test('DEP5: la memoria de vídeo del modelo se dice tal cual, sin un tope de 4 GB que la pinte de rojo', async () => {
  h = await openView();
  h.reply('/metrics', () => ({ body: { cpu: 20, gpu: 10, temp: 50, model_vram_gb: 4.8, model_ram_gb: 1.2 } }));
  const p = h.page;
  await p.locator('.bx-gear').click();
  await p.locator('.settings-tab', { hasText: 'Modelo' }).click();
  const body = p.locator('.settings-body');
  await expect(body).toContainText('4,8 GB');
  await expect(body).not.toContainText('/ 4 GB');
  await expect(body).not.toContainText('Lo máximo que puede ocupar');
  // owner, 2026-11-08: the RAM is no longer one row about the model's processes (INT15) but all of BAXY's, piece by piece,
  // in «Toda la memoria de BAXY» (tested below); no row says RAM of only a part
  await expect(body.locator('.bxs-row', { hasText: /^RAM/ })).toHaveCount(0);
  await expect(p.locator('.settings-body .hot')).toHaveCount(0);
});

// ALR1: an alarm ringing now is a card with its words, Stop and Snooze; each press reaches the host once as
// schedule.alarms' answer for that ring's id, and the card says how it ended. A reminder's buttons are Done and Remind.
const ringItem = (status: string, kind = 'alarm') => ({
  who: 'ring', id: 'ring-0123456789abcdef0123456789abcdef', ts: '07:00',
  ring: { id: '89abcdef', kind, title: 'sal a trabajar', clock: '07:00', words: 'Alarma de las 7:00: sal a trabajar', status },
});
const rings = () => h.calls.filter((c) => c.path === '/ring/answer').map((c) => c.body);

test('una alarma que suena se para o se pospone desde su tarjeta y la tarjeta dice cómo acabó', async () => {
  h = await openView({ items: [ringItem('ringing')] });
  h.reply('/ring/answer', () => ({ body: { ok: true } }));
  const ringCard = h.page.locator('.bx-card.k-ring');
  await expect(ringCard).toContainText('sal a trabajar');
  await expect(ringCard).toHaveAttribute('role', 'alert');
  await ringCard.locator('.bx-btn', { hasText: 'Posponer 10 min' }).click();
  await ringCard.locator('.bx-btn', { hasText: 'Parar' }).click();
  await expect.poll(rings).toEqual([{ id: '89abcdef', action: 'snooze' }, { id: '89abcdef', action: 'stop' }]);
  h.emit({ type: 'item', item: ringItem('stopped') });
  await expect(ringCard.locator('.bx-btn')).toHaveCount(0);
  await expect(ringCard).toContainText('Parada');
});

test('un recordatorio que suena ofrece Listo y Recordar en 10 min, y una respuesta rechazada se dice', async () => {
  h = await openView({ items: [ringItem('ringing', 'reminder')] });
  h.reply('/ring/answer', () => ({ status: 409 }));
  const ringCard = h.page.locator('.bx-card.k-ring');
  await expect(ringCard.locator('.bx-btn', { hasText: 'Recordar en 10 min' })).toHaveCount(1);
  await ringCard.locator('.bx-btn', { hasText: 'Listo' }).click();
  await expect.poll(rings).toEqual([{ id: '89abcdef', action: 'stop' }]);
  await expect(h.page.locator('.bx-notice')).toContainText('no se pudo: ya no suena o BAXY no respondió');
});

// INT16, blind review: with a card waiting and an alarm ringing, an Enter or an Esc given to silence the alarm answered
// the waiting card (Enter approved a deletion). While something rings the keys answer neither; each card's own buttons do.
test('con una alarma sonando, Enter y Esc no contestan la tarjeta que espera; sus botones sí', async () => {
  h = await openView({ items: [card('c1'), ringItem('ringing')] });
  h.reply('/ring/answer', () => ({ body: { ok: true } }));
  await expect(h.page.locator('.bx-card.k-ring')).toHaveAttribute('role', 'alert');
  await h.page.evaluate(() => (document.activeElement as HTMLElement | null)?.blur());
  await h.page.keyboard.press('Enter');
  await h.page.keyboard.press('Escape');
  await h.page.locator('.bx-line > input').focus();
  await h.page.keyboard.press('Enter');
  await h.page.waitForTimeout(400);
  expect(answers()).toEqual([]);
  expect(rings()).toEqual([]);
  await h.page.locator('.bx-card.s-pending:not(.k-ring) .bx-btn', { hasText: 'No' }).click();
  await expect.poll(answers).toEqual([{ approve: false, card: 'c1' }]);
  // once it no longer rings, Enter is the waiting card's Sí again
  h.emit({ type: 'item', item: card('c2') });
  h.emit({ type: 'item', item: ringItem('stopped') });
  await expect(h.page.locator('.bx-card.k-ring .bx-btn')).toHaveCount(0);
  await h.page.locator('.bx-line > input').focus();
  await siReady(h.page);
  await h.page.keyboard.press('Enter');
  await expect.poll(answers).toEqual([{ approve: false, card: 'c1' }, { approve: true, card: 'c2' }]);
});

// INT16, second blind review: a conversation saved while an alarm rang comes back with that ring «ended» (FieldTranscript):
// it says so, offers no Parar, and Enter answers the card again.
test('una alarma guardada mientras sonaba vuelve como «Ya no suena» y Enter contesta la tarjeta', async () => {
  h = await openView({ items: [ringItem('ended'), card('c1')] });
  const ringCard = h.page.locator('.bx-card.k-ring');
  await expect(ringCard).toContainText('Ya no suena');
  await expect(ringCard.locator('.bx-btn')).toHaveCount(0);
  await h.page.locator('.bx-line > input').focus();
  await siReady(h.page);
  await h.page.keyboard.press('Enter');
  await expect.poll(answers).toEqual([{ approve: true, card: 'c1' }]);
});

// APP1 (ALR-1 and ALR-2): an alarm the App took and could not sound is said on its card, with who rings it instead
// (Windows' notification) or that nothing could; it offers no Parar, since it no longer rings here.
test('una alarma que BAXY no pudo hacer sonar lo dice en su tarjeta: la avisa Windows, o nada pudo', async () => {
  h = await openView({ items: [ringItem('ringing')] });
  const ringCard = h.page.locator('.bx-card.k-ring');
  h.emit({ type: 'item', item: ringItem('windows') });
  await expect(ringCard).toContainText('BAXY no pudo hacerla sonar: te avisa Windows');
  await expect(ringCard.locator('.bx-btn')).toHaveCount(0);
  h.emit({ type: 'item', item: ringItem('failed') });
  await expect(ringCard).toContainText('BAXY no pudo hacerla sonar');
  await expect(ringCard).not.toContainText('Windows');
});

// The owner (2026-11-08): a place in Settings to personalise the view: the size of BAXY's replies and of the person's
// messages, the conversation's width, the steps open, the captions and the rail's readings. Kept in this view only.
test('personalización: el tamaño de las respuestas, el ancho del chat y los pasos abiertos se eligen en Ajustes y se ven', async () => {
  h = await openView({ items: [{ who: 'you', id: 'y1', ts: '12:00', text: 'abre la calculadora' },
    { who: 'baxy', id: 'b1', ts: '12:00', text: 'Listo.', steps: [{ id: 's1', label: 'Abrir la calculadora', fam: 'apps', status: 'ok', obs: 'Ventana a la vista' }] }] });
  const p = h.page;
  const size = (sel: string) => p.locator(sel).evaluate((e) => getComputedStyle(e).fontSize);
  const before = await size('.bx-c4-baxy.last .tx');
  await p.locator('.bx-gear').click();
  await p.locator('.settings-tab', { hasText: 'Personalización' }).click();
  await p.getByRole('group', { name: 'Tamaño de las respuestas de BAXY' }).getByRole('button', { name: 'Muy grande' }).click();
  await p.getByRole('button', { name: /^Conversación/ }).click();
  await p.getByRole('group', { name: 'Ancho de la conversación' }).getByRole('button', { name: 'Ancha' }).click();
  await p.getByRole('switch', { name: 'Abrir siempre «Cómo lo comprobé»' }).click();
  await p.getByRole('switch', { name: 'Medidores del sistema en la barra' }).click();
  await p.keyboard.press('Escape');
  expect(parseFloat(await size('.bx-c4-baxy.last .tx'))).toBeGreaterThan(parseFloat(before) + 2);
  await expect.poll(() => p.locator('.bx-right').evaluate((e) => Math.abs((e as HTMLElement).offsetWidth - 450) <= 2)).toBe(true);
  await expect(p.getByRole('button', { name: /Cómo lo comprobé/ })).toHaveAttribute('aria-expanded', 'true');
  await expect(p.locator('.bx-gauges')).toHaveCount(0);
  // kept for the next start
  expect(await p.evaluate(() => JSON.parse(localStorage.getItem('baxy.look') ?? '{}'))).toMatchObject({ reply: 'xl', chat: 'w', steps: true, gauges: false });
});

// Owner, 2026-11-08: the coloured light that runs round the window's border is the person's to control.
test('personalización: el borde de color se puede dejar quieto, más lento o apagar', async () => {
  h = await openView();
  const p = h.page;
  await p.locator('.bx-gear').click();
  await p.locator('.settings-tab', { hasText: 'Personalización' }).click();
  await p.getByRole('group', { name: 'Borde de color' }).getByRole('button', { name: 'Apagado' }).click();
  await expect(p.locator('.app-frame.bx-ring-off')).toHaveCount(1);
  await expect(p.locator('.bd-ring')).toBeHidden();
  await p.getByRole('group', { name: 'Borde de color' }).getByRole('button', { name: 'Quieto' }).click();
  await expect(p.locator('.app-frame.bx-ring-off')).toHaveCount(0);
  // the speed is the running border's: still, it does not apply and is off (owner, 2026-11-09: nothing on against the choice)
  await expect(p.getByRole('group', { name: 'Velocidad del borde' }).getByRole('button', { name: 'Lenta' })).toBeDisabled();
  await p.getByRole('group', { name: 'Borde de color' }).getByRole('button', { name: 'Animado' }).click();
  await p.getByRole('group', { name: 'Velocidad del borde' }).getByRole('button', { name: 'Lenta' }).click();
  expect(await p.evaluate(() => JSON.parse(localStorage.getItem('baxy.look') ?? '{}'))).toMatchObject({ ring: 'on', ringSpeed: 'slow' });
});


test('ajustes: al minimizar, la ventana puede irse a la bandeja', async () => {
  h = await openView();
  let host = { language: 'es', languageInUse: 'es', closeToTray: true, minimizeToTray: false };
  h.reply('/settings/general', (c) => { if (c.method === 'PUT') host = { ...host, ...(c.body as object) }; return { body: host }; });
  const p = h.page;
  await p.locator('.bx-gear').click();
  await p.getByRole('switch', { name: 'Al minimizar, ir a la bandeja' }).click();
  await expect.poll(() => h.calls.filter((c) => c.method === 'PUT' && c.path === '/settings/general').map((c) => c.body)).toContainEqual({ minimizeToTray: true });
  await expect(p.getByRole('switch', { name: 'Al minimizar, ir a la bandeja' })).toHaveAttribute('aria-checked', 'true');
});

// REV_APP TRG-a (2026-11-09): «Cancelar» names an alarm by its clock; two at the same clock were «No se pudo cancelar»
// with no cause, and a cancel with no answer (it may have happened) said the same.
test('alarmas: cancelar dice por qué no se pudo, y sin respuesta no dice que no', async () => {
  h = await openView();
  const two = { count: 2, truncated: false, items: [
    { kind: 'alarm', title: null, next_local: '2026-11-11 07:00', state: 'Ready' },
    { kind: 'alarm', title: null, next_local: '2026-11-12 07:00', state: 'Ready' }] };
  let list = two;
  let answer: { status: number; body?: unknown } = { status: 409, body: { ok: false, error: 'notification_clock_ambiguous' } };
  h.reply('/triggers', () => ({ body: list }));
  h.reply('/triggers/cancel', () => answer);
  const p = h.page;
  await p.locator('.bx-mod', { hasText: 'Alarmas' }).click();
  const panel = p.locator('.panel', { hasText: 'Alarmas y recordatorios' });
  await panel.getByRole('button', { name: 'Cancelar la alarma de 2026-11-11 07:00' }).click();
  await panel.getByRole('button', { name: 'Sí, cancelar' }).click();
  await expect(panel.getByRole('status')).toContainText('Hay otra a la misma hora');
  await expect(panel.getByRole('status')).toContainText('no se canceló ninguna');

  answer = { status: 503, body: { ok: false, error: 'bridge_timeout' } };
  list = { count: 1, truncated: false, items: [two.items[1]] };
  await panel.getByRole('button', { name: 'Cancelar la alarma de 2026-11-11 07:00' }).click();
  await panel.getByRole('button', { name: 'Sí, cancelar' }).click();
  await expect(panel.getByRole('status')).toContainText('no sé si se canceló');
  await expect(panel.getByText('2026-11-11 07:00')).toHaveCount(0);
  await expect(panel.getByText('No se pudo cancelar')).toHaveCount(0);
});

// REV_APP ASY-b (2026-11-09): a switch the host could not write to its file was not said; the old value came back alone.
test('ajustes: un cambio que no se pudo guardar en el disco lo dice, y deja de decirlo cuando se guarda', async () => {
  h = await openView();
  let host = { language: 'es', languageInUse: 'es', closeToTray: true, minimizeToTray: false, unsaved: false };
  let written = false;
  h.reply('/settings/general', (c) => {
    if (c.method === 'PUT') { host = { ...host, ...(c.body as object), unsaved: !written }; }
    return { body: host };
  });
  const p = h.page;
  await p.locator('.bx-gear').click();
  await expect(p.getByText('No pude guardar este cambio en el disco')).toHaveCount(0);
  await p.getByRole('switch', { name: 'Al minimizar, ir a la bandeja' }).click();
  await expect(p.locator('.settings-body').getByRole('status')).toContainText('No pude guardar este cambio en el disco');
  written = true;
  await p.getByRole('switch', { name: 'Al minimizar, ir a la bandeja' }).click();
  await expect(p.getByText('No pude guardar este cambio en el disco')).toHaveCount(0);
});

// Owner, 2026-11-08 (second look): «toda esta línea de arriba» moves the window, as in any program: the whole band at
// the top of the centre, from «Listo · Sin frenos» to the window's buttons, and the conversation's head end to end. They
// are WebView2's draggable regions (CSS app-region: drag, CoreWebView2Settings.IsNonClientRegionSupportEnabled):
// Windows moves the window from them, double-click maximizes; the controls inside them stay pressable (no-drag).
test('la franja de arriba entera mueve la ventana y sus botones siguen siendo botones', async () => {
  h = await openView();
  const p = h.page;
  await p.setViewportSize({ width: 1280, height: 800 });
  await p.waitForTimeout(700); // the columns settle (grid transition .45 s) before points are read
  const region = (x: number, y: number) => p.evaluate(([px, py]) => {
    let e: Element | null = document.elementFromPoint(px, py);
    while (e) {
      const st = getComputedStyle(e) as CSSStyleDeclaration & Record<string, string>;
      const r = st.getPropertyValue('app-region') || st.getPropertyValue('-webkit-app-region') || st['webkitAppRegion'] || '';
      if (r === 'drag' || r === 'no-drag') return r;
      e = e.parentElement;
    }
    return 'none';
  }, [x, y] as const);
  const c = await p.locator('.bx-center').evaluate((e) => { const r = e.getBoundingClientRect(); return { l: r.left, r: r.right }; });
  const right = await p.locator('.bx-right').evaluate((e) => { const r = e.getBoundingClientRect(); return { l: r.left, r: r.right }; });
  for (const x of [c.l + 40, (c.l + c.r) / 2, c.r - 160]) for (const y of [16, 40]) expect(await region(x, y), `centro ${Math.round(x)},${y}`).toBe('drag');
  for (const x of [right.l + 30, right.l + 140]) expect(await region(x, 30), `conversación ${Math.round(x)}`).toBe('drag');
  expect(await region(60, 26), 'cabeza del carril').toBe('drag');
  for (const sel of ['button[aria-label="Minimizar"]', 'button[title="Nueva conversación"]']) {
    const b = await p.locator(sel).evaluate((e) => { const r = e.getBoundingClientRect(); return { x: r.left + r.width / 2, y: r.top + r.height / 2 }; });
    expect(await region(b.x, b.y), sel).toBe('no-drag');
  }
});

// Owner, 2026-11-08: Settings › Modelo shows the model by its name with the video memory it uses, and then all the
// memory BAXY uses, RAM and video, piece by piece (GET /metrics/breakdown, OwnMemory in the App).
test('ajustes › modelo: el modelo por su nombre con su memoria de vídeo, y toda la memoria de BAXY por pieza', async () => {
  h = await openView();
  h.reply('/settings', () => ({ body: { modelAlias: 'Qwen3.5-4B-Q4_K_M' } }));
  h.reply('/metrics', () => ({ body: { cpu: 20, gpu: 10, temp: 50, model_vram_gb: 4.8, model_ram_gb: 1.2 } }));
  h.reply('/metrics/breakdown', () => ({ body: { ramGb: 3.4, vramGb: 5.1, parts: [
    { piece: 'app', name: null, ramGb: 0.3, vramGb: null }, { piece: 'view', name: null, ramGb: 0.6, vramGb: 0.2 },
    { piece: 'mind', name: null, ramGb: 1.1, vramGb: 0.1 }, { piece: 'model', name: null, ramGb: 1.4, vramGb: 4.8 },
  ] } }));
  const p = h.page;
  await p.locator('.bx-gear').click();
  await p.locator('.settings-tab', { hasText: 'Modelo' }).click();
  const inUse = p.locator('.bx-inuse');
  await expect(inUse).toContainText('Qwen3.5-4B-Q4_K_M');
  await expect(inUse.locator('.bx-fact', { hasText: 'Memoria de vídeo' })).toContainText('4,8 GB');
  // Owner, 2026-11-08: «ni siquiera hay una flechita para desplegar o contraer»: BAXY's memory is folded, with its summary
  const fold = p.getByRole('button', { name: /Toda la memoria de BAXY/ });
  await expect(fold).toHaveAttribute('aria-expanded', 'false');
  await expect(fold).toContainText('RAM 3,4 GB · VRAM 5,1 GB');
  await expect(p.locator('.bx-mem-all')).toHaveCount(0);
  await fold.click();
  await expect(fold).toHaveAttribute('aria-expanded', 'true');
  const all = p.locator('.bx-mem-all');
  await expect(all).toContainText('3,4 GB');
  await expect(all).toContainText('5,1 GB');
  await expect(all.locator('tr', { hasText: 'Mente y voz' })).toContainText('1,1 GB');
  await expect(all.locator('tr', { hasText: 'Qwen3.5-4B-Q4_K_M' })).toContainText('4,8 GB');
  await expect(all.locator('tr', { hasText: 'La App de BAXY' })).toContainText('—');
  // INT16, blind review: a piece that could not be read («—») is not counted as 0: the total says «al menos»
  const total = all.locator('tfoot tr td');
  await expect(total.nth(1)).toHaveText('3,4 GB');
  await expect(total.nth(2)).toHaveText('al menos 5,1 GB');
});

// Owner, 2026-11-08 (design boards 13 to 16, approved): Settings wear BAXY's identity, and the Model tab says where BAXY
// thinks with one choice, never two models on at once.
test('ajustes con la identidad de BAXY: la cabecera dice BAXY y Ajustes, con su cara', async () => {
  h = await openView();
  const p = h.page;
  await p.locator('.bx-gear').click();
  const head = p.locator('.bxs .panel-head');
  await expect(head.locator('.bxs-brand')).toHaveText(/BAXY\s*Ajustes/i);
  await expect(head.locator('svg.bxs-face')).toBeVisible();
});

test('modelo: dónde piensa BAXY es una sola elección, y De serie apaga el ajustado y el otro modelo', async () => {
  h = await openView();
  let ext = { ...EXTERNAL, provider: 'local', model: 'llama3.2:3b', url: 'http://127.0.0.1:11434', enabled: true, active: true, activeModel: 'llama3.2:3b', activeLocal: true, ceilingHolds: false };
  let tuned = { ...TUNED, installed: true };
  h.reply('/settings/external-model', (c) => { if (c.method === 'PUT') ext = { ...ext, ...(c.body as object) }; return { body: ext }; });
  h.reply('/settings/external-model/models', () => ({ body: { models: [{ id: 'llama3.2:3b', label: 'llama3.2:3b', fits: true }] } }));
  h.reply('/settings/tuned-model', (c) => { if (c.method === 'PUT') tuned = { ...tuned, ...(c.body as object) }; return { body: tuned }; });
  const p = h.page;
  await p.locator('.bx-gear').click();
  await p.locator('.settings-tab', { hasText: 'Modelo' }).click();
  const pick = p.getByRole('radiogroup', { name: 'Dónde piensa BAXY' });
  await expect(pick.getByRole('radio')).toHaveCount(4);
  await expect(pick.getByRole('radio', { checked: true })).toHaveCount(1);
  await expect(pick.getByRole('radio', { name: /Local/ })).toHaveAttribute('aria-checked', 'true');
  await expect(p.locator('button.toggle[aria-label="Usar otro modelo"]')).toHaveCount(0);
  await pick.getByRole('radio', { name: /De serie/ }).click();
  await expect.poll(() => h.calls.filter((c) => c.method === 'PUT' && c.path === '/settings/external-model').map((c) => c.body)).toContainEqual({ enabled: false });
  await expect(pick.getByRole('radio', { name: /De serie/ })).toHaveAttribute('aria-checked', 'true');
  await pick.getByRole('radio', { name: /Ajustado/ }).click();
  await expect.poll(() => h.calls.filter((c) => c.method === 'PUT' && c.path === '/settings/tuned-model').map((c) => c.body)).toContainEqual({ use: true });
});

test('modelo: desinstalar un modelo del PC pide un sí que dice cuánto libera', async () => {
  h = await openView();
  const ext = { ...EXTERNAL, provider: 'local', model: 'llama3.2:3b', url: 'http://127.0.0.1:11434', enabled: true, active: true, activeModel: 'llama3.2:3b', activeLocal: true, ceilingHolds: false };
  h.reply('/settings/external-model', () => ({ body: ext }));
  h.reply('/settings/external-model/models', () => ({ body: { models: [
    { id: 'llama3.2:3b', label: 'llama3.2:3b', fits: true, vision: false, bytes: 2_019_000_000 },
    { id: 'gpt-oss:20b', label: 'gpt-oss:20b', fits: true, vision: false, bytes: 11_600_000_000 }] } }));
  h.reply('/settings/external-model/remove', () => ({ body: ext }));
  const p = h.page;
  await p.locator('.bx-gear').click();
  await p.locator('.settings-tab', { hasText: 'Modelo' }).click();
  const list = p.locator('.bx-installed');
  await expect(list.locator('.bx-irow', { hasText: 'llama3.2:3b' }).getByRole('button', { name: 'Desinstalar' })).toBeDisabled();
  await list.locator('.bx-irow', { hasText: 'gpt-oss:20b' }).getByRole('button', { name: 'Desinstalar' }).click();
  const ask = p.getByRole('dialog', { name: 'Desinstalar gpt-oss:20b' });
  // INT17, revisión ciega: Ollama keeps a file another model still uses (docs/api.md, «Delete a Model»), and the list is every
  // model of the person's Ollama, also one another program uses: «hasta», and who else loses it.
  await expect(ask).toContainText('Se borra de Ollama en este PC, también para otros programas que lo usen, y libera hasta 10,8 GB: menos si otro modelo comparte sus archivos.');
  expect(h.calls.filter((c) => c.path === '/settings/external-model/remove')).toEqual([]);
  await ask.getByRole('button', { name: 'Sí, desinstalar' }).click();
  await expect.poll(() => h.calls.filter((c) => c.path === '/settings/external-model/remove').map((c) => c.body)).toEqual([{ name: 'gpt-oss:20b' }]);
});

test('modelo: tras desinstalar uno, los demás modelos del PC siguen en la lista', async () => {
  // VIVO1 (2026-11-09): after uninstalling a model not in use, «Modelos en este PC» said 1 and hid the rest of Ollama
  // until Settings was opened again.
  h = await openView();
  const ext = { ...EXTERNAL, provider: 'local', model: 'llama3.2:3b', url: 'http://127.0.0.1:11434', enabled: true, active: true, activeModel: 'llama3.2:3b', activeLocal: true, ceilingHolds: false };
  let models = [
    { id: 'llama3.2:3b', label: 'llama3.2:3b', fits: true, vision: false, bytes: 2_019_000_000 },
    { id: 'gpt-oss:20b', label: 'gpt-oss:20b', fits: true, vision: false, bytes: 11_600_000_000 },
    { id: 'mistral:latest', label: 'mistral:latest', fits: true, vision: false, bytes: 4_113_000_000 }];
  h.reply('/settings/external-model', () => ({ body: ext }));
  h.reply('/settings/external-model/models', () => ({ body: { models } }));
  h.reply('/settings/external-model/remove', (c) => { models = models.filter((m) => m.id !== (c.body as { name: string }).name); return { body: ext }; });
  const p = h.page;
  await p.locator('.bx-gear').click();
  await p.locator('.settings-tab', { hasText: 'Modelo' }).click();
  const list = p.locator('.bx-installed');
  await list.locator('.bx-irow', { hasText: 'gpt-oss:20b' }).getByRole('button', { name: 'Desinstalar' }).click();
  await p.getByRole('dialog', { name: 'Desinstalar gpt-oss:20b' }).getByRole('button', { name: 'Sí, desinstalar' }).click();
  await expect(list.locator('.bx-irow', { hasText: 'gpt-oss:20b' })).toHaveCount(0);
  await expect(list.locator('.bx-irow', { hasText: 'mistral:latest' })).toHaveCount(1);
  await expect(list.locator('.bx-irow', { hasText: 'llama3.2:3b' })).toHaveCount(1);
});

// VIVO1 F4 (2026-11-09): mistral:latest (32.768) was offered with Completo, «Conectado», and every turn refused with nothing said.
test('modelo: uno corto para el perfil dice por qué y ofrece el perfil que le cabe', async () => {
  h = await openView();
  const ext = { ...EXTERNAL, provider: 'local', url: 'http://127.0.0.1:11434', ceilingHolds: false };
  h.reply('/settings/external-model', () => ({ body: ext }));
  h.reply('/settings/external-model/models', () => ({ body: { models: [
    { id: 'mistral:latest', label: 'mistral:latest · 4,1 GB', fits: false, context: 32768, profile: 'esencial', bytes: 4_113_000_000,
      why: 'admite 32.768 tokens de contexto y el perfil de herramientas elegido necesita unos 52.670' }] } }));
  h.reply('/settings/tools', () => ({ body: { profile: 'esencial', on: [] } }));
  const p = h.page;
  await p.locator('.bx-gear').click();
  await p.locator('.settings-tab', { hasText: 'Modelo' }).click();
  const row = p.locator('.bx-installed .bx-irow', { hasText: 'mistral:latest' });
  await expect(row.getByRole('button', { name: 'Usar', exact: true })).toBeDisabled();
  await expect(row).toContainText('necesita un perfil más pequeño');
  await row.getByRole('button', { name: 'Usar con Esencial' }).click();
  // VIVO2 F15: the model and its profile in one request, which the App takes whole or not at all; the profile alone, sent
  // first, stayed changed when the model was then refused or did not connect.
  await expect.poll(() => h.calls.filter((c) => c.method === 'PUT' && c.path === '/settings/external-model').map((c) => c.body))
    .toEqual([{ provider: 'local', model: 'mistral:latest', enabled: true, profile: 'esencial' }]);
  expect(h.calls.filter((c) => c.method === 'PUT' && c.path === '/settings/tools')).toEqual([]);
});

// VIVO2 F15 (notebook, 2026-11-09): «Usar con Esencial» did not connect, and the person was left on Esencial with BAXY's own
// model and nothing said. The App puts back the profile they had (ExternalModel.Settle) and the tab says it; the model's own
// ways out of «no cabe» ask for it with that profile again.
test('modelo: si el modelo pedido con un perfil no se conecta, se dice que el perfil volvió al de antes', async () => {
  h = await openView();
  const ext = { ...EXTERNAL, provider: 'local', model: 'mistral:latest', enabled: true, url: 'http://127.0.0.1:11434', ceilingHolds: false, open: OPEN_IDLE,
    problem: 'no_cabe_vram', vramShort: { context: 32768, needBytes: 7_800_000_000, freeBytes: 6_000_000_000, fittingContext: 28000, partialPossible: true },
    profileBack: { model: 'mistral:latest', profile: 'esencial', back: 'completo' } };
  h.reply('/settings/external-model', () => ({ body: ext }));
  h.reply('/settings/external-model/models', () => ({ body: { models: [
    { id: 'mistral:latest', label: 'mistral:latest · 4,1 GB', fits: false, context: 32768, profile: 'esencial', bytes: 4_113_000_000,
      why: 'admite 32.768 tokens de contexto y el perfil de herramientas elegido necesita unos 52.670' }] } }));
  const p = h.page;
  await p.locator('.bx-gear').click();
  await p.locator('.settings-tab', { hasText: 'Modelo' }).click();
  const inUse = p.locator('.bx-inuse');
  await expect(inUse).toContainText('Volví al perfil de herramientas Completo, el que tenías: Esencial era sólo para usar mistral:latest, que no se conectó');
  await p.getByRole('button', { name: 'Usar 28.000 tokens, que caben, con el perfil Esencial' }).click();
  await expect.poll(() => h.calls.filter((c) => c.method === 'PUT' && c.path === '/settings/external-model').map((c) => c.body))
    .toEqual([{ context: 28000, profile: 'esencial' }]);
  await p.getByRole('button', { name: 'Cargarlo en parte en la RAM (mucho más lento), con el perfil Esencial' }).click();
  await expect.poll(() => h.calls.filter((c) => c.method === 'PUT' && c.path === '/settings/external-model').map((c) => c.body).at(-1))
    .toEqual({ partialRam: true, profile: 'esencial' });
});

test('modelo: sin perfil devuelto no se dice nada de perfiles, y lo que no cabe se pide como siempre', async () => {
  h = await openView();
  const ext = { ...EXTERNAL, provider: 'local', model: 'mistral:latest', enabled: true, url: 'http://127.0.0.1:11434', ceilingHolds: false, open: OPEN_IDLE,
    problem: 'no_cabe_vram', vramShort: { context: 32768, needBytes: 7_800_000_000, freeBytes: 6_000_000_000, fittingContext: 28000, partialPossible: true }, profileBack: null };
  h.reply('/settings/external-model', () => ({ body: ext }));
  h.reply('/settings/external-model/models', () => ({ body: { models: [{ id: 'mistral:latest', label: 'mistral:latest · 4,1 GB', fits: true, bytes: 4_113_000_000 }] } }));
  const p = h.page;
  await p.locator('.bx-gear').click();
  await p.locator('.settings-tab', { hasText: 'Modelo' }).click();
  await expect(p.locator('.bx-inuse')).toContainText('No se conectó mistral:latest');
  await expect(p.locator('.bx-inuse')).not.toContainText('perfil');
  await p.getByRole('button', { name: 'Usar 28.000 tokens, que caben', exact: true }).click();
  await expect.poll(() => h.calls.filter((c) => c.method === 'PUT' && c.path === '/settings/external-model').map((c) => c.body)).toEqual([{ context: 28000 }]);
});

// REV_VISTA V-01 (P0, 2026-11-09): «Usar» on a model of this PC sent its name without its place. With an API chosen and its
// key saved, the host turned that API on under the local model's name: the conversation left for a company the person had
// not chosen. The place goes in the same PUT, and what the host refuses is said.
test('modelo: «Usar» en un modelo de este PC lo pide como local aunque la elegida sea una API, y un rechazo se dice', async () => {
  h = await openView();
  let ext: Record<string, unknown> = { ...EXTERNAL, provider: 'compatible', model: 'el-de-la-api', url: 'https://ejemplo.com/v1', hasKey: true, ceilingHolds: false,
    open: OPEN_IDLE };
  let refuse: string | null = null;
  h.reply('/settings/external-model', (c) => {
    if (c.method !== 'PUT') return { body: ext };
    if (refuse) return { status: 409, body: { error: refuse } };
    ext = { ...ext, ...(c.body as object) };
    return { body: ext };
  });
  h.reply('/settings/external-model/models', () => ({ body: { models: [
    { id: 'lumen:7b', label: 'lumen:7b', fits: true, vision: false, bytes: 4_113_000_000 },
    { id: 'brasa:3b', label: 'brasa:3b', fits: true, vision: false, bytes: 2_019_000_000 }] } }));
  const p = h.page;
  await p.locator('.bx-gear').click();
  await p.locator('.settings-tab', { hasText: 'Modelo' }).click();
  const puts = () => h.calls.filter((c) => c.method === 'PUT' && c.path === '/settings/external-model').map((c) => c.body);
  await p.locator('.bx-installed .bx-irow', { hasText: 'lumen:7b' }).getByRole('button', { name: 'Usar', exact: true }).click();
  await expect.poll(puts).toEqual([{ provider: 'local', model: 'lumen:7b', enabled: true }]);
  // every PUT that names a model names its place: none can be read as another place's
  expect(puts().filter((b) => 'model' in (b as object) && !('provider' in (b as object)))).toEqual([]);
  refuse = 'external_model_other_provider';
  await p.locator('.bx-installed .bx-irow', { hasText: 'brasa:3b' }).getByRole('button', { name: 'Usar', exact: true }).click();
  await expect(p.locator('.bx-installed [role=alert]')).toContainText('Ese modelo no es del proveedor elegido');
  // refused: the one in use is still the first, and the list says so
  await expect(p.locator('.bx-installed .bx-irow', { hasText: 'lumen:7b' }).locator('.live')).toHaveCount(1);
  await expect(p.locator('.bx-installed .bx-irow', { hasText: 'brasa:3b' }).locator('.live')).toHaveCount(0);
});

test('modelo: elegir el modelo de una API lo pide con su empresa, y sin clave dice que falta', async () => {
  h = await openView();
  h.reply('/settings/external-model', (c) => c.method === 'PUT' ? { status: 409, body: { error: 'external_model_no_key' } }
    : { body: { ...EXTERNAL, provider: 'openai', model: '', hasKey: true, ceilingHolds: false } });
  h.reply('/settings/external-model/models', () => ({ body: { models: [{ id: 'modelo-uno', label: 'modelo-uno', fits: true }] } }));
  const p = h.page;
  await p.locator('.bx-gear').click();
  await p.locator('.settings-tab', { hasText: 'Modelo' }).click();
  await p.getByRole('radiogroup', { name: 'Dónde piensa BAXY' }).getByRole('radio', { name: /API/ }).click();
  await p.getByRole('combobox', { name: 'Modelo' }).selectOption('modelo-uno');
  await expect.poll(() => h.calls.filter((c) => c.method === 'PUT' && c.path === '/settings/external-model').map((c) => c.body))
    .toEqual([{ provider: 'openai', model: 'modelo-uno', enabled: true }]);
  await expect(p.getByRole('alert').filter({ hasText: 'Primero guarda la clave' })).toHaveCount(1);
});

// REV_VISTA V-02 (P1, 2026-11-09): the App keeps one model (MainWindowViewModel.KeepOneModel: the one just chosen stays and
// the other goes off in the same request) and each request answers only its own state. The view kept the other one as it was:
// two «En uso» at once, and a «Usar» that sent nothing. This host does as the App does.
function oneModelHost(host: Host, external: Record<string, unknown>, tuned: Record<string, unknown>) {
  const now = { external, tuned };
  host.reply('/settings/external-model', (c) => {
    if (c.method === 'PUT') {
      now.external = { ...now.external, ...(c.body as object) };
      if (now.external.enabled) {
        now.external = { ...now.external, active: true, activeModel: now.external.model, activeLocal: now.external.provider === 'local' };
        now.tuned = { ...now.tuned, use: false, active: false };
      } else now.external = { ...now.external, active: false, activeModel: null, activeLocal: false };
    }
    return { body: now.external };
  });
  host.reply('/settings/tuned-model', (c) => {
    if (c.method === 'PUT') {
      now.tuned = { ...now.tuned, ...(c.body as object) };
      now.tuned = { ...now.tuned, active: !!now.tuned.use };
      if (now.tuned.use) now.external = { ...now.external, enabled: false, active: false, activeModel: null, activeLocal: false };
    }
    return { body: now.tuned };
  });
  host.reply('/settings/tuned-model/install', () => { now.tuned = { ...now.tuned, installed: true }; return { body: now.tuned }; });
  host.reply('/settings/external-model/models', () => ({ body: { models: [{ id: 'lumen:7b', label: 'lumen:7b', fits: true, vision: false, bytes: 4_113_000_000 }] } }));
  return now;
}
const LOCAL_IDLE = { provider: 'local', model: '', url: 'http://127.0.0.1:11434', ceilingHolds: false };

test('modelo: al elegir uno de Ollama con el ajustado en uso, queda uno solo en uso y «Usar» en el ajustado vuelve a él', async () => {
  h = await openView();
  oneModelHost(h, { ...EXTERNAL, ...LOCAL_IDLE, open: OPEN_IDLE }, { ...TUNED, installed: true, use: true, active: true });
  const p = h.page;
  await p.locator('.bx-gear').click();
  await p.locator('.settings-tab', { hasText: 'Modelo' }).click();
  const tunedRow = p.locator('.bx-installed .bx-irow', { hasText: 'BAXY ajustado' });
  await expect(tunedRow.locator('.live')).toHaveCount(1);
  await pickWhere(p, /Local/);
  await p.getByRole('combobox', { name: 'Modelo' }).selectOption('lumen:7b');
  await expect(p.locator('.bx-inuse .name')).toHaveText('lumen:7b');
  await expect(p.locator('.bx-installed .bx-irow', { hasText: 'lumen:7b' }).locator('.live')).toHaveCount(1);
  await expect(p.locator('.bx-installed .live')).toHaveCount(1);
  await expect(p.locator('.bx-pick .bx-pick-o.live')).toHaveText(/Local/);
  // the tuned one is off in the App: its row offers «Usar», and it asks for it
  await tunedRow.getByRole('button', { name: 'Usar', exact: true }).click();
  await expect.poll(() => h.calls.filter((c) => c.method === 'PUT' && c.path === '/settings/tuned-model').map((c) => c.body)).toEqual([{ use: true }]);
  await expect(p.locator('.bx-inuse .name')).toHaveText('BAXY ajustado');
  await expect(p.locator('.bx-installed .live')).toHaveCount(1);
  await expect(tunedRow.locator('.live')).toHaveCount(1);
  await expect(p.locator('.bx-pick .bx-pick-o.live')).toHaveText(/Ajustado/);
});

test('modelo: al encender el ajustado con uno de Ollama en uso, el de Ollama deja de decirse en uso', async () => {
  h = await openView();
  oneModelHost(h, { ...EXTERNAL, ...LOCAL_IDLE, model: 'lumen:7b', enabled: true, active: true, activeModel: 'lumen:7b', activeLocal: true, open: OPEN_IDLE }, { ...TUNED });
  const p = h.page;
  await p.locator('.bx-gear').click();
  await p.locator('.settings-tab', { hasText: 'Modelo' }).click();
  await expect(p.locator('.bx-inuse .name')).toHaveText('lumen:7b');
  await pickWhere(p, /Ajustado/);
  await p.getByRole('button', { name: 'Instalar', exact: true }).click();
  await p.getByRole('button', { name: 'Descargar' }).click();
  await p.locator('button.toggle[aria-label="Usar el modelo ajustado"]').click();
  await expect(p.locator('.bx-inuse .name')).toHaveText('BAXY ajustado');
  await expect(p.locator('.bx-installed .live')).toHaveCount(1);
  await expect(p.locator('.bx-installed .bx-irow', { hasText: 'BAXY ajustado' }).locator('.live')).toHaveCount(1);
  await expect(p.locator('.bx-pick .bx-pick-o.live')).toHaveText(/Ajustado/);
  await expect(p.locator('.bx-inuse')).not.toContainText('Conectado');
});

// «Instalar y usar» ends in the App by itself (MainWindowViewModel.UseModelPulled): the model that finished downloading is
// chosen and the tuned one goes off, with no request from the view; and the download's bar is kept up wherever the person looks.
test('modelo: cuando una descarga termina y la App pasa a ese modelo, el ajustado deja de decirse en uso', async () => {
  h = await openView();
  const pulling = { ...OPEN_IDLE, pulling: 'hf.co/autor/lumen-GGUF:Q4_K_M', pullDone: 1_000_000_000, pullTotal: 4_000_000_000 };
  const now = oneModelHost(h, { ...EXTERNAL, ...LOCAL_IDLE, open: pulling }, { ...TUNED, installed: true, use: true, active: true });
  const p = h.page;
  await p.locator('.bx-gear').click();
  await p.locator('.settings-tab', { hasText: 'Modelo' }).click();
  // looking at the tuned one, not at Local: the bar above still moves
  await expect(p.locator('.dl-percent')).toHaveText('25 %');
  now.external = { ...now.external, open: { ...pulling, pullDone: 3_000_000_000 } };
  await expect(p.locator('.dl-percent')).toHaveText('75 %');
  now.external = { ...now.external, model: 'lumen:7b', enabled: true, active: true, activeModel: 'lumen:7b', activeLocal: true, open: OPEN_IDLE };
  now.tuned = { ...now.tuned, use: false, active: false };
  await expect(p.locator('.bx-inuse .name')).toHaveText('lumen:7b');
  await expect(p.locator('.bx-installed .bx-irow', { hasText: 'BAXY ajustado' }).locator('.live')).toHaveCount(0);
  await expect(p.locator('.bx-installed .live')).toHaveCount(1);
  await expect(p.locator('.bx-pick .bx-pick-o.live')).toHaveText(/Local/);
});

// REV_VISTA V-04 (P1, 2026-11-09): in English, the box «Model in use» and the turn's failure said the translator's Spanish line
// for 7 kinds (ollama, plantilla, …) and the turn's reason always; «modelo» said «The company» of Ollama on this PC.
test('modelo: en inglés, por qué no se conectó o rechaza los turnos se dice en inglés, y uno local no es «la empresa»', async () => {
  h = await openView();
  h.reply('/settings/general', () => ({ body: { language: 'en', languageInUse: 'en' } }));
  let host: Record<string, unknown> = { ...EXTERNAL, provider: 'local', model: 'lumen:7b', url: 'http://127.0.0.1:11434', enabled: true, ceilingHolds: false,
    open: OPEN_IDLE, lastError: 'ERROR[ollama]: Ollama no responde' };
  h.reply('/settings/external-model', () => ({ body: host }));
  h.reply('/settings/external-model/models', () => ({ body: { models: [] } }));
  const p = h.page;
  const why = 'El servidor local no puede usar lumen:7b con las herramientas de BAXY: la plantilla de chat del modelo no acepta la conversación. Elige otro modelo';
  h.emit({ type: 'agent', built: true, ready: true, powered: true, failure: 'model_refused', failureWhy: why, failureKind: 'plantilla' });
  h.emit({ type: 'state', value: 'error' });
  await expect(p.getByText('The model refused the turn: The local server can’t use lumen:7b with BAXY’s tools').first()).toBeVisible();
  await expect(p.getByText(/plantilla/)).toHaveCount(0);
  await p.locator('.bx-gear').click();
  await p.locator('.settings-tab', { hasText: 'Model' }).click();
  const inUse = p.locator('.bx-inuse');
  await expect(inUse).toContainText('lumen:7b didn’t connect');
  await expect(inUse).toContainText('Ollama doesn’t answer');
  await expect(inUse).not.toContainText('no responde');
  host = { ...host, active: true, activeModel: 'lumen:7b', activeLocal: true, lastError: 'ERROR[modelo]: Ollama no tiene el modelo lumen:7b; tiene: brasa:3b' };
  await p.locator('.settings-tab', { hasText: 'General' }).click();
  await p.locator('.settings-tab', { hasText: 'Model' }).click();
  await expect(inUse).toContainText('Ollama doesn’t have the model lumen:7b');
  await expect(inUse).not.toContainText(/company|tiene/i);
});

test('modelo: si el servidor rechaza los turnos, la pestaña no dice «Conectado» y el turno dice por qué', async () => {
  h = await openView();
  const why = 'El servidor local no puede usar mistral:latest con las herramientas de BAXY: la plantilla de chat del modelo no acepta la conversación. Elige otro modelo';
  h.reply('/settings/external-model', () => ({ body: { ...EXTERNAL, provider: 'local', model: 'mistral:latest', url: 'http://127.0.0.1:11434', enabled: true,
    active: true, activeModel: 'mistral:latest', activeLocal: true, ceilingHolds: false, lastError: 'ERROR[plantilla]: ' + why } }));
  h.reply('/settings/external-model/models', () => ({ body: { models: [] } }));
  const p = h.page;
  h.emit({ type: 'agent', built: true, ready: true, powered: true, failure: 'model_refused', failureWhy: why });
  h.emit({ type: 'state', value: 'error' });
  await expect(p.getByText('El modelo rechazó el turno: ' + why).first()).toBeVisible();
  await expect(p.locator('[role=status][aria-live=polite]').first()).toContainText('El modelo rechazó el turno: ' + why);
  await p.locator('.bx-gear').click();
  await p.locator('.settings-tab', { hasText: 'Modelo' }).click();
  await expect(p.locator('.bx-inuse')).toContainText('Rechaza los turnos');
  await expect(p.locator('.bx-inuse')).toContainText(why);
  await expect(p.locator('.bx-inuse').getByText('Conectado', { exact: true })).toHaveCount(0);
});

test('turno: si el modelo rechaza el turno después de que BAXY actuó, se dice que actuó y por qué lo rechazó', async () => {
  // REV_APP TUR-1 (2026-11-09): refused after a call ran, the screen said only «El modelo rechazó el turno».
  h = await openView();
  const why = 'El servidor local no puede usar lumen:7b con las herramientas de BAXY';
  h.emit({ type: 'agent', built: true, ready: true, powered: true, failure: 'model_refused_after_call', failureWhy: why });
  h.emit({ type: 'state', value: 'error' });
  await expect(h.page.locator('[role=status][aria-live=polite]').first()).toContainText('El modelo rechazó el turno después de actuar: ' + why);
});

// INT17 (encargo: «un solo modelo activo: ningún estado con dos»): what the person chose and what still runs while BAXY
// switches, in every pair the host can say (MainWindowViewModel.KeepOneModel keeps one chosen; the mind runs one), never
// shows two models in use: one place lit in the picker and at most one row «En uso» in the models on this PC.
const OLLAMA_ON = { provider: 'local', model: 'llama3.2:3b', url: 'http://127.0.0.1:11434', ceilingHolds: false };
const ONE_MODEL_STATES: [string, Record<string, unknown>, Record<string, unknown>][] = [
  ['de serie', {}, {}],
  ['ajustado en uso', {}, { use: true, active: true }],
  ['ajustado elegido, cargando', {}, { use: true, switching: true }],
  ['Ollama conectado', { ...OLLAMA_ON, enabled: true, active: true, activeModel: 'llama3.2:3b', activeLocal: true }, {}],
  ['Ollama elegido, conectando', { ...OLLAMA_ON, enabled: true, switching: true }, {}],
  ['de serie elegido, Ollama aún corre', { ...OLLAMA_ON, active: true, activeModel: 'llama3.2:3b', activeLocal: true, switching: true }, {}],
  ['ajustado elegido, Ollama aún corre', { ...OLLAMA_ON, active: true, activeModel: 'llama3.2:3b', activeLocal: true, switching: true }, { use: true }],
  ['Ollama elegido, el ajustado aún corre', { ...OLLAMA_ON, enabled: true, switching: true }, { active: true }],
  ['API conectada', { enabled: true, hasKey: true, active: true, activeModel: 'claude-opus-5-5' }, {}],
];
for (const [name, ext, tuned] of ONE_MODEL_STATES) {
  test(`modelo: un solo modelo en uso (${name})`, async () => {
    h = await openView();
    h.reply('/settings/external-model', () => ({ body: { ...EXTERNAL, ...ext } }));
    h.reply('/settings/tuned-model', () => ({ body: { ...TUNED, installed: true, ...tuned } }));
    h.reply('/settings/external-model/models', () => ({ body: { models: [
      { id: 'llama3.2:3b', label: 'llama3.2:3b', fits: true, vision: false, bytes: 2_019_000_000 },
      { id: 'gpt-oss:20b', label: 'gpt-oss:20b', fits: true, vision: false, bytes: 11_600_000_000 }] } }));
    const p = h.page;
    await p.locator('.bx-gear').click();
    await p.locator('.settings-tab', { hasText: 'Modelo' }).click();
    await expect(p.locator('.bx-installed .bx-irow').first()).toBeVisible();
    await expect(p.locator('.bx-pick .bx-pick-o.live')).toHaveCount(1);
    expect(await p.locator('.bx-installed .live').count()).toBeLessThanOrEqual(1);
    expect(await p.getByRole('radio', { checked: true }).count()).toBe(1);
  });
}

test('modelo: uno que no ve lo dice en el modelo en uso', async () => {
  h = await openView();
  h.reply('/settings/external-model', () => ({ body: { ...EXTERNAL, provider: 'local', model: 'llama3.2:3b', url: 'http://127.0.0.1:11434', enabled: true, active: true, activeModel: 'llama3.2:3b', activeLocal: true, ceilingHolds: false, sees: false } }));
  const p = h.page;
  await p.locator('.bx-gear').click();
  await p.locator('.settings-tab', { hasText: 'Modelo' }).click();
  await expect(p.locator('.bx-inuse')).toContainText('Sin visión');
  await expect(p.locator('.bx-inuse')).toContainText('BAXY no podrá ver la pantalla ni imágenes');
});

// Owner, 2026-11-09 («trasladar esta orden … a todas las pestañas de ajustes»; boards 17 to 24): every tab folds by sections
// with their summary, and what does not apply under the choice made is turned off, never left on against it.
test('ajustes: cada pestaña se pliega por secciones, y plegada dice su resumen', async () => {
  h = await openView();
  const p = h.page;
  await p.locator('.bx-gear').click();
  await expect(p.getByRole('button', { name: /^Idioma/ })).toHaveAttribute('aria-expanded', 'true');
  const look = p.getByRole('button', { name: /^Apariencia/ });
  await expect(look).toHaveAttribute('aria-expanded', 'false');
  await expect(look).toContainText('Oscuro');
  await look.click();
  await expect(p.locator('.bxs-seg button', { hasText: 'Claro' })).toBeVisible();
  for (const [tab, section] of [['Personalización', 'Textos'], ['Voz', 'Micrófono'], ['Accesibilidad', 'Modo'], ['Privacidad', 'Salidas a internet'], ['Extras no oficiales', 'Modelo ajustado a BAXY']]) {
    await p.locator('.settings-tab', { hasText: tab }).click();
    await expect(p.locator('.bx-fold-h', { hasText: section }).first()).toBeVisible();
  }
});

test('ajustes: lo que no aplica a lo elegido se apaga', async () => {
  h = await openView();
  h.reply('/settings/general', () => ({ body: { language: 'es', languageInUse: 'es', voiceMuted: true, wakeSound: true, waitNotice: true, echoCancel: true } }));
  const p = h.page;
  await p.locator('.bx-gear').click();
  await p.locator('.settings-tab', { hasText: 'Personalización' }).click();
  await p.getByRole('group', { name: 'Borde de color' }).getByRole('button', { name: 'Apagado' }).click();
  await expect(p.getByRole('group', { name: 'Velocidad del borde' }).getByRole('button', { name: 'Normal' })).toBeDisabled();
  await p.locator('.settings-tab', { hasText: 'Accesibilidad' }).click();
  await expect(p.getByRole('group', { name: 'Tamaño del texto' }).getByRole('button', { name: 'Grande', exact: true })).toBeDisabled();
  await p.locator('.settings-tab', { hasText: 'Voz' }).click();
  await expect(p.locator('button.toggle[aria-label="Decir «Un momento»"]')).toBeDisabled();
});

// controls.spec in the real App, 2026-11-09: the window was already maximized and the button said «Maximizar»; the first
// press restored it. The button says the window's real state, asked of the host when the view starts and when the window
// changes size (a double click on the top band or a drag to the screen's edge maximize it without the button).
test('ventana: el botón de maximizar dice el estado real de la ventana, aunque cambie sin él', async () => {
  h = await openView();
  const p = h.page;
  await expect(p.getByRole('button', { name: 'Maximizar' })).toHaveCount(1);
  await p.evaluate(() => {
    let max = true;
    (window as unknown as { pywebview: unknown }).pywebview = { api: {
      win_is_maximized: async () => max,
      win_toggle_maximize: async () => { max = !max; return max; },
      win_minimize: async () => true, win_close: async () => true, win_exit: async () => true,
    } };
  });
  await p.setViewportSize({ width: 1300, height: 820 });
  await expect(p.getByRole('button', { name: 'Restaurar' })).toHaveCount(1);
  await p.getByRole('button', { name: 'Restaurar' }).click();
  await expect(p.getByRole('button', { name: 'Maximizar' })).toHaveCount(1);
});

// Owner, 2026-11-09 («hazlo como en los tableros»): the choices the boards draw as cards are cards, one checked each.
test('ajustes: las elecciones únicas van en tarjetas: idioma, antes de actuar, micrófono y modo', async () => {
  h = await openView();
  let mode = 'normal';
  h.reply('/accessibility', (c) => { if (c.method === 'PUT') mode = (c.body as { mode: string }).mode; return { body: { active: mode } }; });
  const p = h.page;
  await p.locator('.bx-gear').click();
  for (const [tab, group, count] of [['General', 'Idioma de la interfaz', 3], ['Confirmación', 'Antes de actuar', 2], ['Voz', 'Micrófono', 3], ['Accesibilidad', 'Modo accesible', 2]] as const) {
    await p.locator('.settings-tab', { hasText: tab }).click();
    const pick = p.getByRole('radiogroup', { name: group });
    await expect(pick.locator('.bx-pick-o')).toHaveCount(count);
    await expect(pick.getByRole('radio', { checked: true })).toHaveCount(1);
  }
  await p.getByRole('radiogroup', { name: 'Modo accesible' }).getByRole('radio', { name: 'Accesible' }).click();
  await expect(p.getByRole('radiogroup', { name: 'Modo accesible' }).getByRole('radio', { name: 'Accesible' })).toHaveAttribute('aria-checked', 'true');
  await expect(p.getByRole('group', { name: 'Tamaño del texto' }).getByRole('button', { name: 'Grande', exact: true })).toBeEnabled();
  await p.locator('.settings-tab', { hasText: 'Confirmación' }).click();
  await p.getByRole('radio', { name: 'Sin frenos' }).click();
  await expect(p.getByRole('alertdialog', { name: '¿Activar sin frenos?' })).toBeVisible();
});

// The owner, using the dev BAXY (2026-11-09, captures of Settings › Modelo), on four things the tab said wrong or did not say.
const OPEN_IDLE = { ollamaVersion: '0.40.15', ollamaBytes: 1614941966, ollamaOwn: true, ollamaRunning: '0.40.15', ollamaInstalling: false, ollamaDownloadedBytes: 0,
  ollamaProblem: null, pulling: null as string | null, pullTotal: 0, pullDone: 0, pullBytesPerSecond: null as number | null, pullSecondsLeft: null as number | null,
  pullStopped: null as string | null, pullProblem: null };

// «Me puse a descargar un modelo, pero no veo su barra de progreso… ¿cómo el usuario va a saber que la estoy descargando?»
test('modelo: lo que se descarga se ve con su barra en la pestaña, en su sección plegada y en su resultado', async () => {
  h = await openView();
  const open = { ...OPEN_IDLE, pulling: 'tvall43/Qwen3.5-9B-GGUF:Q4_K_M', pullTotal: 8_500_000_000, pullDone: 1_400_000_000, pullBytesPerSecond: 21_000_000, pullSecondsLeft: 338 };
  h.reply('/settings/external-model', () => ({ body: { ...EXTERNAL, provider: 'local', model: '', url: 'http://127.0.0.1:11434', ceilingHolds: false, open } }));
  h.reply('/settings/external-model/models', () => ({ body: { models: [] } }));
  const p = h.page;
  await p.locator('.bx-gear').click();
  await p.locator('.settings-tab', { hasText: 'Modelo' }).click();
  // whatever place is chosen, the tab says what downloads
  const top = p.getByRole('group', { name: 'Descarga de tvall43/Qwen3.5-9B-GGUF:Q4_K_M' }).first();
  await expect(top).toContainText('16 %');
  await expect(top.getByRole('progressbar')).toHaveAttribute('aria-valuenow', '16');
  await expect(top).toContainText('20 MB/s · quedan 6 min');
  await pickWhere(p, /Local/);
  const search = p.getByRole('button', { name: /^Buscar y descargar/ });
  await expect(search).toContainText('16 %');
  await search.click();
  await expect(search).toHaveAttribute('aria-expanded', 'false');
  await expect(search).toContainText('16 %');
});

// «De serie» said «BAXY-Qwen3.5-4B-ft-c2e1-Q4_K_M»: the development launcher gives the mind a tuned file as BAXY's own.
test('modelo: De serie es siempre Qwen3.5-4B, y si el perfil usa otro archivo lo dice', async () => {
  h = await openView();
  h.reply('/settings', () => ({ body: { modelAlias: 'BAXY-Qwen3.5-4B-ft-c2e1-Q4_K_M', stockName: 'Qwen3.5-4B', ownIsStock: false } }));
  const p = h.page;
  await p.locator('.bx-gear').click();
  await p.locator('.settings-tab', { hasText: 'Modelo' }).click();
  const stock = p.getByRole('radio', { name: /De serie/ });
  await expect(stock).toContainText('Qwen3.5-4B');
  await expect(stock).not.toContainText('ft-c2e1');
  await expect(p.locator('.bx-installed .bx-irow').first()).toContainText('Qwen3.5-4B');
  await expect(p.locator('.bx-inuse')).toContainText('BAXY-Qwen3.5-4B-ft-c2e1-Q4_K_M');
  await expect(p.locator('.bx-inuse')).toContainText('no es el modelo de serie');
});

// «Conectando…» above and «No se conectó… BAXY sigue con su modelo» below: the state says what happened.
test('modelo: si el otro modelo no se conectó, el modelo en uso es el que sigue, y lo dice', async () => {
  h = await openView();
  h.reply('/settings', () => ({ body: { modelAlias: 'Qwen3.5-4B-Q4_K_M', stockName: 'Qwen3.5-4B', ownIsStock: true } }));
  h.reply('/settings/external-model', () => ({ body: { ...EXTERNAL, provider: 'local', model: 'gpt-oss:20b', url: 'http://127.0.0.1:11434', enabled: true, active: false,
    ceilingHolds: false, lastError: 'ERROR[memoria]: gpt-oss:20b necesita unos 21,4 GB de RAM libre' } }));
  const p = h.page;
  await p.locator('.bx-gear').click();
  await p.locator('.settings-tab', { hasText: 'Modelo' }).click();
  const inUse = p.locator('.bx-inuse');
  await expect(inUse).toContainText('Qwen3.5-4B-Q4_K_M');
  await expect(inUse).toContainText('No se conectó gpt-oss:20b');
  await expect(inUse).not.toContainText('Conectando');
  await expect(p.getByRole('radio', { name: /Local/ })).not.toContainText('En uso');
});

// «8,5 GB … 262.144 tokens de contexto · cabe en tu tarjeta»: with that context it does not fit; the estimate says so.
test('modelo: un resultado dice su contexto máximo frente al recomendado, y cabe sólo con la estimación', async () => {
  h = await openView();
  h.reply('/settings/external-model', () => ({ body: { ...EXTERNAL, provider: 'local', model: '', url: 'http://127.0.0.1:11434', ceilingHolds: false, open: OPEN_IDLE } }));
  h.reply('/settings/external-model/models', () => ({ body: { models: [] } }));
  h.reply('/settings/external-model/search', () => ({ body: { vramTotalBytes: 8_589_934_592, vramFreeBytes: 7_000_000_000, results: [
    { repo: 'tvall43/Qwen3.5-9B-GGUF', file: 'q.gguf', quant: 'Q4_K_M', name: 'tvall43/Qwen3.5-9B-GGUF:Q4_K_M', visionName: null, sha256: 'c'.repeat(64),
      bytes: 8_500_000_000, projectorBytes: 0, license: 'apache-2.0', context: 262144, tools: true, vramBytes: 9_900_000_000, vramContext: 52000, fit: 'no_cabe', why: null,
      contexts: { native: 262144, recommended: 52000, why: 'no_cabe', options: [{ tokens: 52000, vramBytes: 9_900_000_000, fitsCard: false }] } }] } }));
  const p = h.page;
  await p.locator('.bx-gear').click();
  await p.locator('.settings-tab', { hasText: 'Modelo' }).click();
  await pickWhere(p, /Local/);
  const box = p.getByRole('textbox', { name: 'Nombre del modelo a buscar' });
  await box.fill('qwen 9b');
  await box.press('Enter');
  // «Sólo los que caben» hides it, as it should: shown on asking
  await expect(p.locator('ul[aria-label="Modelos encontrados"] li')).toHaveCount(0);
  await p.getByRole('checkbox', { name: /Sólo los que caben/ }).uncheck();
  const row = p.locator('ul[aria-label="Modelos encontrados"] li').first();
  await expect(row).toContainText('contexto máximo 262.144 tokens, recomendado 52.000');
  await expect(row).toContainText('no cabe en tu tarjeta');
  await expect(row).not.toContainText('· cabe en tu tarjeta');
});

// AMD2 (installed 1.3.2 on an RX 7600, 2026-11-09): Qwen/Qwen3-14B-GGUF read «contexto máximo 40.960 tokens, recomendado 52.000
// en tu tarjeta». BAXY's least context is above what the model takes (why «poco_contexto», ModelMemory.Recommend never goes
// under it), so no context is recommended for it: it says its maximum and why BAXY can't use it.
test('modelo: un resultado que admite menos contexto del que BAXY necesita no recomienda uno mayor que su máximo', async () => {
  h = await openView();
  h.reply('/settings/external-model', () => ({ body: { ...EXTERNAL, provider: 'local', model: '', url: 'http://127.0.0.1:11434', ceilingHolds: false, open: OPEN_IDLE } }));
  h.reply('/settings/external-model/models', () => ({ body: { models: [] } }));
  h.reply('/settings/external-model/search', () => ({ body: { vramTotalBytes: 8_548_958_208, vramFreeBytes: 7_117_074_432, results: [
    { repo: 'Qwen/Qwen3-14B-GGUF', file: 'q.gguf', quant: 'Q4_K_M', name: 'Qwen/Qwen3-14B-GGUF:Q4_K_M', visionName: null, sha256: 'd'.repeat(64),
      bytes: 9_001_752_960, projectorBytes: 0, license: 'apache-2.0', context: 40960, tools: true, vramBytes: 14_253_021_568, vramContext: 52000, fit: 'no_cabe', why: 'poco_contexto',
      contexts: { native: 40960, recommended: 52000, why: 'no_cabe', options: [{ tokens: 52000, vramBytes: 14_253_021_568, fitsCard: false }] } }] } }));
  const p = h.page;
  await p.locator('.bx-gear').click();
  await p.locator('.settings-tab', { hasText: 'Modelo' }).click();
  await pickWhere(p, /Local/);
  const box = p.getByRole('textbox', { name: 'Nombre del modelo a buscar' });
  await box.fill('qwen3 14b');
  await box.press('Enter');
  await p.getByRole('checkbox', { name: /Sólo los que caben/ }).uncheck();
  const row = p.locator('ul[aria-label="Modelos encontrados"] li').first();
  await expect(row).toContainText('contexto máximo 40.960 tokens');
  await expect(row).toContainText('admite muy poco contexto para BAXY');
  await expect(row).not.toContainText('recomendado');
});

// VIVO2 F13 (notebook, 2026-11-09): «contexto máximo 40.960 tokens, recomendado 52.000 en tu tarjeta · admite muy poco contexto
// para BAXY», with nothing to install; the same model, once in Ollama, was offered «Usar con Esencial». The search says it too.
test('modelo: un modelo al que no le cabe el perfil elegido se ofrece con el que sí, y sin contexto de más', async () => {
  h = await openView();
  h.reply('/settings/external-model', () => ({ body: { ...EXTERNAL, provider: 'local', model: '', url: 'http://127.0.0.1:11434', ceilingHolds: false, open: OPEN_IDLE } }));
  h.reply('/settings/external-model/models', () => ({ body: { models: [] } }));
  h.reply('/settings/external-model/install', () => ({ body: { ...EXTERNAL, provider: 'local', model: '', url: 'http://127.0.0.1:11434', ceilingHolds: false, open: OPEN_IDLE } }));
  h.reply('/settings/external-model/pull', () => ({ body: { ...EXTERNAL, provider: 'local', model: '', url: 'http://127.0.0.1:11434', ceilingHolds: false, open: OPEN_IDLE } }));
  const found = (repo: string, more: Record<string, unknown>) => ({ repo, file: 'm.gguf', quant: 'Q4_K_M', name: `${repo}:Q4_K_M`, visionName: null, sha256: 'd'.repeat(64),
    bytes: 1_100_000_000, projectorBytes: 0, license: 'apache-2.0', tools: true, fit: 'cabe', why: null, ...more });
  h.reply('/settings/external-model/search', () => ({ body: { vramTotalBytes: 8_589_934_592, vramFreeBytes: 7_000_000_000, needContext: 52670, results: [
    found('lumen/Corto-GGUF', { context: 40960, vramBytes: 3_900_000_000, vramContext: 40960, profile: 'esencial', visionName: 'lumen/Corto-GGUF:Q4_K_M-vision', projectorBytes: 600_000_000,
      contexts: { native: 40960, recommended: 40960, why: 'nativo', options: [{ tokens: 40960, vramBytes: 3_900_000_000, fitsCard: true }] } }),
    found('lumen/Minimo-GGUF', { context: 8192, vramBytes: 1_500_000_000, vramContext: 8192, why: 'poco_contexto',
      contexts: { native: 8192, recommended: 8192, why: 'nativo', options: [{ tokens: 8192, vramBytes: 1_500_000_000, fitsCard: true }] } }),
    found('lumen/Largo-GGUF', { context: 131072, vramBytes: 4_900_000_000, vramContext: 52670,
      contexts: { native: 131072, recommended: 52670, why: 'tarjeta', options: [{ tokens: 52670, vramBytes: 4_900_000_000, fitsCard: true }] } })] } }));
  const p = h.page;
  await p.locator('.bx-gear').click();
  await p.locator('.settings-tab', { hasText: 'Modelo' }).click();
  await pickWhere(p, /Local/);
  const box = p.getByRole('textbox', { name: 'Nombre del modelo a buscar' });
  await box.fill('lumen');
  await box.press('Enter');
  const rows = p.locator('ul[aria-label="Modelos encontrados"] li');
  await expect(rows).toHaveCount(3);
  const short = rows.filter({ hasText: 'lumen/Corto-GGUF' });
  await expect(short).toContainText('contexto máximo 40.960 tokens, recomendado 40.960 en tu tarjeta');
  await expect(short).toContainText('con 40.960 tokens de contexto');
  await expect(short).toContainText('sólo le cabe el perfil Esencial de herramientas: el que tienes elegido necesita unos 52.670 tokens');
  await expect(short).not.toContainText('muy poco contexto');
  // The model with the profile it works with, in one gesture; the one that holds the chosen profile is asked as always
  await expect(short.getByRole('button', { name: 'Instalar y usar', exact: true })).toHaveCount(0);
  await short.getByRole('button', { name: 'Instalar y usar con Esencial' }).click();
  await expect.poll(() => h.calls.filter((c) => c.path === '/settings/external-model/install').map((c) => c.body)).toEqual([
    { repo: 'lumen/Corto-GGUF', file: 'm.gguf', sha256: 'd'.repeat(64), bytes: 1_100_000_000, quant: 'Q4_K_M', profile: 'esencial' }]);
  await short.getByRole('button', { name: 'Añadir visión' }).click();
  await expect.poll(() => h.calls.filter((c) => c.path === '/settings/external-model/pull').map((c) => c.body)).toEqual([
    { name: 'lumen/Corto-GGUF:Q4_K_M-vision', bytes: 1_700_000_000, profile: 'esencial' }]);
  const least = rows.filter({ hasText: 'lumen/Minimo-GGUF' });
  await expect(least).toContainText('contexto máximo 8.192 tokens');
  await expect(least).toContainText('admite muy poco contexto para BAXY: ni el perfil de herramientas más pequeño le cabe');
  await expect(least.getByRole('button', { name: /Instalar y usar/ })).toBeDisabled();
  const long = rows.filter({ hasText: 'lumen/Largo-GGUF' });
  await expect(long).not.toContainText('perfil');
  await long.getByRole('button', { name: 'Instalar y usar', exact: true }).click();
  await expect.poll(() => h.calls.filter((c) => c.path === '/settings/external-model/install').map((c) => c.body).at(-1)).toEqual(
    { repo: 'lumen/Largo-GGUF', file: 'm.gguf', sha256: 'd'.repeat(64), bytes: 1_100_000_000, quant: 'Q4_K_M' });
});

// The user test of INT17 (vram-contexto, 2026-11-09): «Modelos en este PC» said 1 with De serie though 6 were installed, the
// weight showed twice, and the rail read «0.0gb» for BAXY's model with an Ollama model in use.
const OLLAMA_MODELS = { models: [
  { id: 'qwen2.5:7b', label: 'qwen2.5:7b · 4,7 GB', fits: true, vision: false, bytes: 4_700_000_000, diskBytes: 4_700_000_000 },
  { id: 'gemma3:1b', label: 'gemma3:1b · 0,8 GB', fits: true, vision: false, bytes: 800_000_000, diskBytes: 800_000_000 }] };

test('modelo: los modelos de este PC se ven con cualquier lugar elegido, cada uno con su peso una vez', async () => {
  h = await openView();
  h.reply('/settings/external-model', () => ({ body: { ...EXTERNAL, open: { ...OPEN_IDLE, ollamaRunning: '0.40.15' } } }));
  h.reply('/settings/external-model/models', () => ({ body: OLLAMA_MODELS }));
  const p = h.page;
  await p.locator('.bx-gear').click();
  await p.locator('.settings-tab', { hasText: 'Modelo' }).click();
  await expect(p.getByRole('radio', { name: /De serie/ })).toHaveAttribute('aria-checked', 'true');
  const rows = p.locator('.bx-installed .bx-irow');
  await expect(rows).toHaveCount(3);
  const qwen = rows.filter({ hasText: 'qwen2.5:7b' });
  await expect(qwen).toContainText('4,4 GB');
  await expect(qwen).not.toContainText('· 4,4 GB');
  // MOD1 V-07, control: what the App did not say is not said (no size of the stock file, no VRAM of any)
  await expect(rows.filter({ hasText: 'De serie' }).locator('.w')).toHaveText('—');
  await expect(p.locator('.bx-installed')).not.toContainText('VRAM');
});

// MOD1 V-07 / VIVO2 F11 (REV_VISTA, 2026-11-09): «Modelos en este PC» gave one unlabelled figure per row, its weight on disk,
// and «—» for the stock model. Each row says what it takes on disk, named so, and on the card: measured for the one in use,
// else the App's estimate from the model's own file, with the context it is for.
test('modelo: cada modelo de este PC dice lo que ocupa en disco y en la tarjeta, también el de serie', async () => {
  h = await openView();
  const gib = 2 ** 30;
  h.reply('/metrics', () => ({ body: { cpu: 10, gpu: 20, temp: 50, model_vram_gb: 4.8, model_ram_gb: 1.2 } }));
  h.reply('/settings/external-model', () => ({ body: { ...EXTERNAL, open: { ...OPEN_IDLE, ollamaRunning: '0.40.15' } } }));
  h.reply('/settings/external-model/models', () => ({ body: { models: [
    { ...OLLAMA_MODELS.models[0], vramBytes: 6.3 * gib, vramContext: 52670 }, OLLAMA_MODELS.models[1]] } }));
  h.reply('/settings/tuned-model', () => ({ body: { ...TUNED, installed: true } }));
  h.reply('/settings/local-context', () => ({ body: { chosen: null, automatic: 77824, prefixTokens: 49086, minimum: 52670,
    cardBytes: 6 * gib, cardKnown: true, switching: false,
    options: [{ context: 77824, vramBytes: 5.03 * gib, vision: true, slower: false, room: 25154, fits: true }],
    stock: { bytes: 2_740_937_888, vramBytes: 5.03 * gib, vramContext: 77824 },
    tuned: { bytes: 2_740_937_888, vramBytes: 5.1 * gib, vramContext: 77824 } } }));
  const p = h.page;
  await p.locator('.bx-gear').click();
  await p.locator('.settings-tab', { hasText: 'Modelo' }).click();
  const rows = p.locator('.bx-installed .bx-irow');
  await expect(rows).toHaveCount(4);
  const stock = rows.filter({ hasText: 'De serie' });
  await expect(stock.locator('.w')).toContainText('2,6 GB');
  await expect(stock.locator('.w')).toContainText('en disco');
  // the one in use: what the card holds of it now, as the box above reads it
  await expect(stock).toContainText('4,8 GB de VRAM ahora');
  const tuned = rows.filter({ hasText: 'BAXY ajustado' });
  await expect(tuned.locator('.w')).toContainText('en disco');
  await expect(tuned).toContainText('unos 5,1 GB de VRAM con 77.824 tokens de contexto');
  // a model of Ollama's is connected with the context the card holds: its least is what the chosen tool profile takes
  const qwen = rows.filter({ hasText: 'qwen2.5:7b' });
  await expect(qwen.locator('.w')).toContainText('4,4 GB');
  await expect(qwen.locator('.w')).toContainText('en disco');
  await expect(qwen).toContainText('desde unos 6,3 GB de VRAM, con 52.670 tokens de contexto');
  const gemma = rows.filter({ hasText: 'gemma3:1b' });
  await expect(gemma.locator('.w')).toContainText('en disco');
  await expect(gemma).not.toContainText('VRAM');
});

// VIVO1 F7 (2026-11-09): in the same tab the card read «6,3 GB» (10⁹) and «5,9 GB» (2³⁰). Every size of the tab is in 2³⁰,
// as Windows (Task Manager, Explorer) and nvidia-smi count them, so a weight, a download and the card can be compared.
test('modelo: todos los tamaños de la pestaña en la misma unidad, la de Windows (2³⁰)', async () => {
  h = await openView();
  h.reply('/settings/external-model', () => ({ body: { ...EXTERNAL, open: { ...OPEN_IDLE, ollamaRunning: '0.40.15' } } }));
  h.reply('/settings/external-model/models', () => ({ body: OLLAMA_MODELS }));
  h.reply('/settings/tuned-model', () => ({ body: { ...TUNED, installed: true } }));
  const p = h.page;
  await p.locator('.bx-gear').click();
  await p.locator('.settings-tab', { hasText: 'Modelo' }).click();
  const rows = p.locator('.bx-installed .bx-irow');
  await expect(rows.filter({ hasText: 'qwen2.5:7b' })).toContainText('4,4 GB');
  await expect(rows.filter({ hasText: 'gemma3:1b' })).toContainText('0,7 GB');
  await expect(rows.filter({ hasText: 'BAXY ajustado' })).toContainText('2,6 GB');
});

test('modelo: con Ollama cerrado, los suyos se piden con un botón, sin abrirlo solo', async () => {
  h = await openView();
  h.reply('/settings/external-model', () => ({ body: { ...EXTERNAL, open: { ...OPEN_IDLE, ollamaRunning: null } } }));
  h.reply('/settings/external-model/models', () => ({ body: OLLAMA_MODELS }));
  const p = h.page;
  await p.locator('.bx-gear').click();
  await p.locator('.settings-tab', { hasText: 'Modelo' }).click();
  await expect(p.locator('.bx-installed .bx-irow:not(.note)')).toHaveCount(1);
  await p.waitForTimeout(300);
  expect(h.calls.filter((c) => c.path === '/settings/external-model/models')).toEqual([]);
  await p.getByRole('button', { name: 'Ver los modelos de Ollama' }).click();
  await expect(p.locator('.bx-installed .bx-irow:not(.note)')).toHaveCount(3);
});

test('carril: con otro modelo en uso, la memoria del modelo de BAXY no se dice 0', async () => {
  h = await openView();
  h.reply('/settings/external-model', () => ({ body: { ...EXTERNAL, provider: 'local', model: 'qwen2.5:7b', enabled: true, active: true, activeModel: 'qwen2.5:7b', activeLocal: true } }));
  h.reply('/metrics', () => ({ body: { cpu: 10, gpu: 5, temp: 50, model_vram_gb: 0, model_ram_gb: 0 } }));
  const p = h.page;
  const gauge = p.locator('.bx-left [title*="Otro modelo en uso"]');
  await expect(gauge).toHaveCount(1);
  await expect(gauge).toContainText('—');
  await expect(gauge).not.toContainText('0.0');
});

// Seen in the real App, 2026-11-09: chosen and still connecting, the model in use was said to be the stock one.
test('modelo: elegido y conectando, el modelo en uso es el elegido, nunca el de serie', async () => {
  h = await openView();
  h.reply('/settings', () => ({ body: { modelAlias: 'Qwen3.5-4B-Q4_K_M' } }));
  h.reply('/settings/external-model', () => ({ body: { ...EXTERNAL, provider: 'local', model: 'mistral-nemo:12b', url: 'http://127.0.0.1:11434', enabled: true, active: false, ceilingHolds: false } }));
  const p = h.page;
  await p.locator('.bx-gear').click();
  await p.locator('.settings-tab', { hasText: 'Modelo' }).click();
  const inUse = p.locator('.bx-inuse');
  await expect(inUse).toContainText('mistral-nemo:12b');
  await expect(inUse).toContainText('Conectando…');
  await expect(inUse).not.toContainText('De serie');
});

// Owner, 2026-11-08: the overlay (design boards 11 and 12) is set in Settings › Personalización: on, its corner, size,
// see-through, how long the end stays, off full-screen windows, answering from it, and a «Probar» that shows it.
test('personalización: el overlay se elige con su esquina, tamaño y tiempos, y se puede probar', async () => {
  h = await openView();
  let host = { on: true, corner: 'br', size: 'm', opacity: 78, hideSeconds: 8, notFullscreen: true, answer: false };
  h.reply('/settings/overlay', (c) => { if (c.method === 'PUT') host = { ...host, ...(c.body as object) }; return { body: host }; });
  const p = h.page;
  await p.locator('.bx-gear').click();
  await p.locator('.settings-tab', { hasText: 'Personalización' }).click();
  await p.getByRole('button', { name: /^Overlay mientras trabaja/ }).click();
  await expect(p.getByRole('switch', { name: 'Mostrar el overlay' })).toHaveAttribute('aria-checked', 'true');
  await p.getByRole('radio', { name: 'Arriba a la izquierda' }).click();
  await p.getByRole('group', { name: 'Tamaño del overlay' }).getByRole('button', { name: 'Grande' }).click();
  await p.getByRole('group', { name: 'Ocultar al terminar' }).getByRole('button', { name: 'Nunca' }).click();
  await p.getByRole('button', { name: 'Probar el overlay' }).click();
  const puts = () => h.calls.filter((c) => c.method === 'PUT' && c.path === '/settings/overlay').map((c) => c.body);
  await expect.poll(puts).toEqual([{ corner: 'tl' }, { size: 'l' }, { hideSeconds: 0 }]);
  await expect.poll(() => h.calls.filter((c) => c.path === '/settings/overlay/preview').length).toBe(1);
  await expect(p.getByRole('radio', { name: 'Arriba a la izquierda' })).toHaveAttribute('aria-checked', 'true');
});


// Owner, 2026-11-08: «que se calcule bien el contexto y la VRAM… al momento de seleccionarlo con el contexto». Each preset says
// the VRAM from the model's header with its vision when it goes on the card, and one past the person's card says so.
test('ajustes › modelo: cada contexto dice su VRAM con la visión, y el que no cabe en tu tarjeta lo dice', async () => {
  h = await openView();
  const gib = 2 ** 30;
  const options = [
    { context: 77824, vramBytes: 5.03 * gib, vision: true, slower: false, room: 25154, fits: true },
    { context: 262144, vramBytes: 9.4 * gib, vision: false, slower: false, room: 209474, fits: true },
  ];
  h.reply('/settings/local-context', () => ({ body: { chosen: 262144, automatic: 77824, prefixTokens: 49086, minimum: 52670,
    cardBytes: 6 * gib, cardKnown: true, options, switching: false } }));
  const p = h.page;
  await p.locator('.bx-gear').click();
  await p.locator('.settings-tab', { hasText: 'Modelo' }).click();
  const select = p.getByRole('combobox', { name: 'Contexto' });
  await expect(select.locator('option').first()).toHaveText('Automático (de fábrica) · 77.824 tokens · unos 5,0 GB de VRAM con la visión');
  await expect(p.getByText(/No cabe en tu tarjeta de 6,0 GB: lo que sobre irá a la memoria compartida, mucho más lento/)).toBeVisible();
  await expect(p.getByText(/en una RTX 3060 y una RTX 4060 Ti salió igual o mayor que lo medido/)).toBeVisible();
});

// MOD1 D5 (AMD2 §5, 2026-11-09): after a change of context the model read its instructions again for 754 s on an RX 7600, and
// nothing said so before. The wait is said before the change with what this PC took the last time (the App's lastRead); from
// a minute on the change asks first, and «Cancelar» changes nothing.
test('ajustes › modelo: cambiar el contexto dice antes lo que tarda en este PC, y si son minutos pregunta', async () => {
  h = await openView();
  const gib = 2 ** 30;
  const options = [
    { context: 61440, vramBytes: 4.2 * gib, vision: true, slower: false, room: 8770, fits: true },
    { context: 98304, vramBytes: 5.3 * gib, vision: true, slower: true, room: 45634, fits: true },
  ];
  let host: Record<string, unknown> = { chosen: null, automatic: 61440, prefixTokens: 49086, minimum: 52670, cardBytes: 8 * gib, cardKnown: true, options, switching: false,
    lastRead: { tokens: 49086, seconds: 754 } };
  h.reply('/settings/local-context', (c) => {
    if (c.method === 'PUT') host = { ...host, chosen: (c.body as { context: number | null }).context };
    return { body: host };
  });
  const p = h.page;
  // Settings reads the context's state as it opens
  const open = async () => { await p.keyboard.press('Escape'); await p.locator('.bx-gear').click(); await p.locator('.settings-tab', { hasText: 'Modelo' }).click(); };
  const puts = () => h.calls.filter((c) => c.method === 'PUT' && c.path === '/settings/local-context').map((c) => c.body);
  await p.locator('.bx-gear').click();
  await p.locator('.settings-tab', { hasText: 'Modelo' }).click();
  const select = p.getByRole('combobox', { name: 'Contexto' });
  await expect(p.getByText(/antes de responder lee otra vez sus instrucciones y herramientas, salvo que vuelvas al contexto de justo antes: la última vez este PC tardó unos 13 minutos en leerlas\./)).toBeVisible();
  await select.selectOption('98304');
  const ask = p.getByRole('dialog', { name: 'Cambiar el contexto' });
  await expect(ask).toContainText('¿Cambiar el contexto a 98.304 tokens? El modelo se reinicia y lee otra vez sus instrucciones y herramientas: la última vez este PC tardó unos 13 minutos, y hasta que termine BAXY no responde.');
  await expect(ask.getByRole('button', { name: 'Cancelar' })).toBeFocused();
  expect(puts()).toEqual([]);
  await ask.getByRole('button', { name: 'Cancelar' }).click();
  await expect(ask).toHaveCount(0);
  await expect(select).toHaveValue('');
  expect(puts()).toEqual([]);
  await select.selectOption('98304');
  await ask.getByRole('button', { name: 'Sí, cambiar' }).click();
  await expect.poll(puts).toEqual([{ context: 98304 }]);
  await expect(select).toHaveValue('98304');
  await select.selectOption('');
  await expect(ask).toContainText('¿Volver al contexto automático?');
  await ask.getByRole('button', { name: 'Cancelar' }).click();

  // seconds, not minutes: said, and the change applies at once
  host = { ...host, chosen: null, lastRead: { tokens: 49086, seconds: 18 } };
  await open();
  await expect(p.getByText(/la última vez este PC tardó unos 18 segundos en leerlas\./)).toBeVisible();
  await select.selectOption('98304');
  await expect.poll(puts).toEqual([{ context: 98304 }, { context: 98304 }]);
  await expect(ask).toHaveCount(0);

  // control: no read measured on this PC yet, no figure is said and nothing is asked
  host = { ...host, chosen: null, lastRead: null };
  await open();
  await expect(p.getByText(/salvo que vuelvas al contexto de justo antes: en una tarjeta lenta son minutos\./)).toBeVisible();
  await expect(p.getByText(/la última vez este PC/)).toHaveCount(0);
  await select.selectOption('98304');
  await expect.poll(() => puts().length).toBe(3);
  await expect(ask).toHaveCount(0);
});

// Owner's order 2026-11-09: a model whose estimate does not fit the free VRAM at its context is not loaded; the view says what it
// needs and what is free, and offers a context that fits or running it partly in RAM.
test('otro modelo local: lo que no cabe en la VRAM no se carga y ofrece un contexto que cabe o la RAM', async () => {
  h = await openView();
  const gib = 2 ** 30;
  const host = { ...EXTERNAL, provider: 'local', model: 'gpt-oss:20b', enabled: true, active: false, problem: 'no_cabe_vram', context: 131072,
    vramShort: { context: 131072, needBytes: 15.6 * gib, freeBytes: 11.2 * gib, fittingContext: 70656, partialPossible: true } };
  h.reply('/settings/external-model', () => ({ body: host }));
  h.reply('/settings/external-model/models', () => ({ body: { models: [{ id: 'gpt-oss:20b', label: 'gpt-oss:20b · 13,8 GB', fits: true }] } }));
  const p = h.page;
  await p.locator('.bx-gear').click();
  await p.locator('.settings-tab', { hasText: 'Modelo' }).click();
  // REV_VISTA V-08: said once, with the model in use, where its state is
  const alert = p.getByLabel('Modelo en uso').getByRole('alert');
  await expect(alert).toContainText('Con 131.072 tokens de contexto necesita unos 15,6 GB de VRAM y tu tarjeta tiene 11,2 GB libres: no lo cargué.');
  await alert.getByRole('button', { name: 'Cargarlo en parte en la RAM (mucho más lento)' }).click();
  await alert.getByRole('button', { name: 'Usar 70.656 tokens, que caben' }).click();
  const puts = h.calls.filter((c) => c.method === 'PUT' && c.path === '/settings/external-model').map((c) => c.body);
  expect(puts).toEqual([{ partialRam: true }, { context: 70656 }]);
  // Seen in the real App: while another model is being switched to, the last one's warning is not said as if it were its.
  host.switching = true;
  await p.locator('.settings-tab', { hasText: 'General' }).click();
  await p.locator('.settings-tab', { hasText: 'Modelo' }).click();
  await expect(p.getByText(/no lo cargué/)).toHaveCount(0);
});

// Seen in the real App on the PC (2026-11-09): a model that did not connect (the translator refused it for RAM) was shown
// «Conectando…» as the model in use, while BAXY had gone back to its own. A failed start says so, and the stock one is in use.
test('otro modelo local: si no se conectó, el modelo en uso es el de serie y dice por qué, no «Conectando…»', async () => {
  h = await openView();
  const host = { ...EXTERNAL, provider: 'local', model: 'unsloth/Qwen3.5-9B-GGUF:Q4_K_M', enabled: true, active: false, switching: false,
    problem: 'traductor_no_arranca', lastError: 'ERROR: unsloth/Qwen3.5-9B-GGUF:Q4_K_M necesita unos 12,0 GB de RAM libre (RAM y archivo de paginación, donde Windows cuenta también lo que va a la tarjeta), contando lo que debe quedar para tus programas, y este PC tiene 8,6 GB: elige otro modelo o menos contexto' };
  h.reply('/settings/external-model', () => ({ body: host }));
  h.reply('/settings/external-model/models', () => ({ body: { models: [] } }));
  const p = h.page;
  await p.locator('.bx-gear').click();
  await p.locator('.settings-tab', { hasText: 'Modelo' }).click();
  const inUse = p.getByLabel('Modelo en uso');
  await expect(inUse).toContainText('De serie · en este PC');
  await expect(inUse).toContainText('No se conectó');
  await expect(inUse).not.toContainText('Conectando');
  await expect(p.getByRole('radio', { name: /De serie/ })).toContainText('En uso');
  await expect(p.getByText(/necesita unos 12,0 GB de RAM libre/).first()).toBeVisible();
});

// REV_VISTA V-08 (2026-11-09): why a model did not connect was said up to three times (the state of the model in use, and
// «No se conectó: …» and «No lo cargué: …» in its section, far below). Said once, with the model in use, and its ways out there.
test('modelo: por qué no se conectó un modelo se dice una sola vez, con el modelo en uso', async () => {
  h = await openView();
  const gib = 2 ** 30;
  const stale = 'ERROR[memoria]: gpt-oss:20b necesita unos 21,4 GB de RAM libre';
  let host: Record<string, unknown> = { ...EXTERNAL, provider: 'local', model: 'gpt-oss:20b', url: 'http://127.0.0.1:11434', enabled: true, active: false,
    ceilingHolds: false, problem: 'traductor_no_arranca', lastError: stale };
  h.reply('/settings/external-model', () => ({ body: host }));
  h.reply('/settings/external-model/models', () => ({ body: { models: [{ id: 'gpt-oss:20b', label: 'gpt-oss:20b · 13,8 GB', fits: true }] } }));
  const p = h.page;
  const again = async () => { await p.locator('.settings-tab', { hasText: 'General' }).click(); await p.locator('.settings-tab', { hasText: 'Modelo' }).click(); };
  await p.locator('.bx-gear').click();
  await p.locator('.settings-tab', { hasText: 'Modelo' }).click();
  const inUse = p.getByLabel('Modelo en uso');
  await expect(inUse).toContainText('No se conectó gpt-oss:20b');
  await expect(inUse.getByRole('alert')).toHaveText('gpt-oss:20b necesita unos 21,4 GB de RAM libre');
  await expect(p.getByText(/necesita unos 21,4 GB de RAM libre/)).toHaveCount(1);
  await expect(p.getByText(/No se conectó/)).toHaveCount(1);

  // what does not fit the card: its figures and its ways out, once; a line an older start left in the log is not its reason
  host = { ...host, problem: 'no_cabe_vram', context: 131072,
    vramShort: { context: 131072, needBytes: 15.6 * gib, freeBytes: 11.2 * gib, fittingContext: 70656, partialPossible: true } };
  await again();
  await expect(inUse.getByRole('alert')).toContainText('Con 131.072 tokens de contexto necesita unos 15,6 GB de VRAM y tu tarjeta tiene 11,2 GB libres: no lo cargué.');
  await expect(inUse.getByRole('alert').getByRole('button')).toHaveCount(2);
  await expect(p.getByText(/necesita unos 15,6 GB de VRAM/)).toHaveCount(1);
  await expect(p.getByText(/o lo cargué/)).toHaveCount(1);
  await expect(p.getByText(/No se conectó/)).toHaveCount(1);
  await expect(p.getByText(/21,4 GB de RAM libre/)).toHaveCount(0);

  // the translator did not start and left no line: its problem, once
  host = { ...host, problem: 'traductor_no_arranca', lastError: null, vramShort: null };
  await again();
  await expect(inUse.getByRole('alert')).toHaveText('El traductor no arrancó: BAXY sigue con su modelo');
  await expect(p.getByText(/El traductor no arrancó/)).toHaveCount(1);

  // connected, and its turns refused: the state says so and the reason is beside it, once
  host = { ...EXTERNAL, provider: 'anthropic', hasKey: true, enabled: true, active: true, activeModel: 'claude-opus-5-5', activeLocal: false,
    lastError: 'ERROR[clave]: La empresa rechazó la clave: revisa que la copiaste entera' };
  await again();
  await expect(inUse).toContainText('Rechaza los turnos');
  await expect(p.getByText(/La empresa rechazó la clave/)).toHaveCount(1);
  await expect(inUse).toContainText('La empresa rechazó la clave: revisa que la copiaste entera');

  // a failure the translator wrote without a kind (a turn cut on the way) is said too, as a turn that failed
  host = { ...host, lastError: 'ERROR: la conexión con la API se cortó (ReadTimeout)' };
  await again();
  await expect(inUse).toContainText('Falló el último turno');
  await expect(inUse).toContainText('la conexión con la API se cortó (ReadTimeout)');
  await expect(p.getByText(/la conexión con la API se cortó/)).toHaveCount(1);

  // control: connected and answering, nothing of this is said
  host = { ...host, lastError: null };
  await again();
  await expect(inUse).toContainText('Conectado a la API');
  await expect(inUse.getByRole('alert')).toHaveCount(0);
  await expect(p.getByText(/No se conectó|rechazó|se cortó/)).toHaveCount(0);
});

// Blind review of MOD1 (2026-11-09): the ways out of «no cabe» say their own refusal beside them (it showed far below, in the
// list of models), and «Detener» with no answer is not said as a download that may not have started.
test('otro modelo local: una salida de «no cabe» rechazada lo dice junto a ella, y «Detener» sin respuesta no habla de empezar', async () => {
  h = await openView();
  const gib = 2 ** 30;
  let host: Record<string, unknown> = { ...EXTERNAL, provider: 'local', model: 'gpt-oss:20b', url: 'http://127.0.0.1:11434', enabled: true, active: false, ceilingHolds: false,
    problem: 'no_cabe_vram', context: 131072, vramShort: { context: 131072, needBytes: 15.6 * gib, freeBytes: 11.2 * gib, fittingContext: 70656, partialPossible: true },
    open: { ...OPEN_IDLE } };
  let put: { status: number; body: Record<string, unknown> } | null = { status: 409, body: { error: 'external_model_invalid_context' } };
  h.reply('/settings/external-model', (c) => (c.method === 'PUT' && put ? put : { body: host }));
  h.reply('/settings/external-model/models', () => ({ body: { models: [{ id: 'gpt-oss:20b', label: 'gpt-oss:20b · 13,8 GB', fits: true }] } }));
  let cancel: { status: number; body: Record<string, unknown> } = { status: 503, body: {} };
  h.reply('/settings/external-model/cancel', () => cancel);
  const p = h.page;
  await p.locator('.bx-gear').click();
  await p.locator('.settings-tab', { hasText: 'Modelo' }).click();
  const inUse = p.getByLabel('Modelo en uso');
  await inUse.getByRole('button', { name: 'Usar 70.656 tokens, que caben' }).click();
  await expect(inUse.getByText('Ese contexto no sirve')).toBeVisible();
  await expect(p.locator('.bx-installed').getByRole('alert')).toHaveCount(0);
  // accepted: its refusal goes
  put = null;
  await inUse.getByRole('button', { name: 'Cargarlo en parte en la RAM (mucho más lento)' }).click();
  await expect(inUse.getByText('Ese contexto no sirve')).toHaveCount(0);

  // a download under way, and «Detener» that gets no answer
  host = { ...EXTERNAL, provider: 'local', model: '', url: 'http://127.0.0.1:11434', ceilingHolds: false,
    open: { ...OPEN_IDLE, pulling: 'hf.co/a/b-GGUF:Q4_K_M', pullTotal: 2_000_000_000, pullDone: 800_000_000 } };
  await p.keyboard.press('Escape');
  await p.locator('.bx-gear').click();
  await p.locator('.settings-tab', { hasText: 'Modelo' }).click();
  await pickWhere(p, /Local/);
  const bar = p.getByRole('group', { name: 'Descarga de a/b-GGUF:Q4_K_M' });
  await bar.getByRole('button', { name: 'Detener' }).click();
  await expect(p.getByRole('alert')).toHaveText('No supe si se detuvo: BAXY no respondió');
  // …and what the App says next is not hidden behind that notice: the download ended, cut
  cancel = { status: 200, body: host };
  host = { ...host, open: { ...OPEN_IDLE, pullStopped: 'hf.co/a/b-GGUF:Q4_K_M', pullProblem: 'cortado', pullTotal: 2_000_000_000, pullDone: 800_000_000 } };
  await expect(p.getByText('No supe si se detuvo: BAXY no respondió')).toHaveCount(0);
  await expect(p.getByRole('group', { name: 'Descarga de a/b-GGUF:Q4_K_M' })).toContainText('Descarga detenida');
});

// Blind review of MOD1: with another model running, a change of BAXY's own context restarts nothing now (it is for when its own
// model runs again), so it does not ask «el modelo se reinicia… BAXY no responde».
test('ajustes › modelo: con otro modelo en uso, cambiar el contexto del modelo de BAXY no pregunta por un reinicio que no ocurre', async () => {
  h = await openView();
  const gib = 2 ** 30;
  const options = [
    { context: 61440, vramBytes: 4.2 * gib, vision: true, slower: false, room: 8770, fits: true },
    { context: 98304, vramBytes: 5.3 * gib, vision: true, slower: true, room: 45634, fits: true },
  ];
  h.reply('/settings/local-context', () => ({ body: { chosen: null, automatic: 61440, prefixTokens: 49086, minimum: 52670, cardBytes: 8 * gib, cardKnown: true, options, switching: false,
    lastRead: { tokens: 49086, seconds: 754 } } }));
  h.reply('/settings/tuned-model', () => ({ body: { ...TUNED } }));
  h.reply('/settings/external-model', () => ({ body: { ...EXTERNAL, provider: 'local', model: 'llama3.2:3b', url: 'http://127.0.0.1:11434', enabled: true, active: true,
    activeModel: 'llama3.2:3b', activeLocal: true, ceilingHolds: false } }));
  h.reply('/settings/external-model/models', () => ({ body: { models: [{ id: 'llama3.2:3b', label: 'llama3.2:3b', fits: true }] } }));
  const p = h.page;
  await p.locator('.bx-gear').click();
  await p.locator('.settings-tab', { hasText: 'Modelo' }).click();
  // «Ajustado», not installed: nothing changes, and the context of BAXY's own model is shown
  await pickWhere(p, /Ajustado/);
  await p.getByRole('combobox', { name: 'Contexto' }).selectOption('98304');
  await expect.poll(() => h.calls.filter((c) => c.method === 'PUT' && c.path === '/settings/local-context').map((c) => c.body)).toEqual([{ context: 98304 }]);
  await expect(p.getByRole('dialog', { name: 'Cambiar el contexto' })).toHaveCount(0);
});

// REV_VISTA V-10 (2026-11-09): whatever the App refused on installing or downloading was said as «ya hay una descarga en curso
// o falta espacio», also when the cause was another. Its code says which (OpenModels: open_models_busy, _no_space,
// _invalid_name; FieldProductChannel: invalid_settings), and a request that got no answer is not said as a refusal.
test('otro modelo local: lo que la App rechaza al instalar o bajar se dice con su causa', async () => {
  h = await openView();
  let host: Record<string, unknown> = { ...EXTERNAL, provider: 'local', model: '', url: 'http://127.0.0.1:11434', ceilingHolds: false, open: { ...OPEN_IDLE, ollamaRunning: null } };
  h.reply('/settings/external-model', () => ({ body: host }));
  let list: Record<string, unknown> = { models: [], ollama: 'missing' };
  h.reply('/settings/external-model/models', () => ({ body: list }));
  h.reply('/settings/external-model/search', () => ({ body: { results: [
    { repo: 'unsloth/Qwen3.5-2B-GGUF', file: 'Qwen3.5-2B-Q4_K_M.gguf', quant: 'Q4_K_M', name: 'unsloth/Qwen3.5-2B-GGUF:Q4_K_M', visionName: null, sha256: 'a'.repeat(64),
      bytes: 1_280_000_000, projectorBytes: 0, license: 'mit', context: 262144, tools: true, vramBytes: 3_600_000_000, vramContext: 78000, fit: 'cabe', why: null }] } }));
  let refusal: { status: number; body: Record<string, unknown> } = { status: 409, body: { error: 'open_models_no_space' } };
  h.reply('/settings/external-model/ollama', () => refusal);
  h.reply('/settings/external-model/install', () => refusal);
  const p = h.page;
  await p.locator('.bx-gear').click();
  await p.locator('.settings-tab', { hasText: 'Modelo' }).click();
  await pickWhere(p, /Local/);
  const said = p.getByRole('alert');
  await p.getByRole('button', { name: 'Instalar Ollama' }).click();
  await expect(said).toHaveText('No se pudo empezar: falta espacio en el disco');

  list = { models: [] };
  host = { ...host, open: { ...OPEN_IDLE } };
  await p.locator('.settings-tab', { hasText: 'General' }).click();
  await p.locator('.settings-tab', { hasText: 'Modelo' }).click();
  await pickWhere(p, /Local/);
  const box = p.getByRole('textbox', { name: 'Nombre del modelo a buscar' });
  await box.fill('qwen3.5 2b');
  await box.press('Enter');
  const install = p.locator('ul[aria-label="Modelos encontrados"] li').first().getByRole('button', { name: 'Instalar y usar' });
  refusal = { status: 409, body: { error: 'open_models_busy' } };
  await install.click();
  await expect(said).toHaveText('No se pudo empezar: ya hay una descarga en curso. Espera a que termine o detenla');
  refusal = { status: 409, body: { error: 'open_models_invalid_name' } };
  await install.click();
  await expect(said).toHaveText('No se pudo empezar: ese nombre no sirve para Ollama. Busca el modelo otra vez');
  refusal = { status: 400, body: { error: 'invalid_settings' } };
  await install.click();
  await expect(said).toHaveText('No se pudo empezar: a BAXY le faltó un dato del modelo. Búscalo otra vez');
  // no answer (the bridge's 503): the App may have taken it; not said as a refusal with a cause it did not give
  refusal = { status: 503, body: {} };
  await install.click();
  await expect(said).toHaveText('No supe si empezó: BAXY no respondió. Mira si aparece la descarga antes de pedirla otra vez');
  // control: taken, nothing is said
  refusal = { status: 200, body: { ...host, open: { ...OPEN_IDLE, pulling: 'unsloth/Qwen3.5-2B-GGUF:Q4_K_M', pullTotal: 100, pullDone: 40 } } };
  await install.click();
  await expect(p.getByRole('group', { name: 'Descarga de unsloth/Qwen3.5-2B-GGUF:Q4_K_M' })).toBeVisible();
  await expect(said).toHaveCount(0);
});

// REV_VISTA V-10, the same on uninstalling: «No se pudo desinstalar» for every refusal but one.
test('modelo: lo que la App rechaza al desinstalar se dice con su causa', async () => {
  h = await openView();
  const ext = { ...EXTERNAL, provider: 'local', model: 'llama3.2:3b', url: 'http://127.0.0.1:11434', enabled: true, active: true, activeModel: 'llama3.2:3b', activeLocal: true, ceilingHolds: false };
  h.reply('/settings/external-model', () => ({ body: ext }));
  h.reply('/settings/external-model/models', () => ({ body: { models: [
    { id: 'llama3.2:3b', label: 'llama3.2:3b', fits: true, vision: false, bytes: 2_019_000_000 },
    { id: 'gpt-oss:20b', label: 'gpt-oss:20b', fits: true, vision: false, bytes: 11_600_000_000 }] } }));
  let refusal: { status: number; body: Record<string, unknown> } = { status: 409, body: { error: 'open_models_busy' } };
  h.reply('/settings/external-model/remove', () => refusal);
  const p = h.page;
  await p.locator('.bx-gear').click();
  await p.locator('.settings-tab', { hasText: 'Modelo' }).click();
  const list = p.locator('.bx-installed');
  const remove = async () => {
    await list.locator('.bx-irow', { hasText: 'gpt-oss:20b' }).getByRole('button', { name: 'Desinstalar' }).click();
    await p.getByRole('dialog', { name: 'Desinstalar gpt-oss:20b' }).getByRole('button', { name: 'Sí, desinstalar' }).click();
  };
  await remove();
  await expect(list.getByRole('alert')).toHaveText('No se desinstaló: hay una descarga en curso. Espera a que termine o detenla');
  refusal = { status: 409, body: { error: 'open_models_no_ollama' } };
  await remove();
  await expect(list.getByRole('alert')).toHaveText('No se desinstaló: Ollama no respondió');
  refusal = { status: 409, body: { error: 'open_models_not_found' } };
  await remove();
  await expect(list.getByRole('alert')).toHaveText('Ollama ya no tenía ese modelo: no había nada que desinstalar');
  refusal = { status: 409, body: { error: 'open_models_failed' } };
  await remove();
  await expect(list.getByRole('alert')).toHaveText('No se desinstaló: Ollama no pudo borrarlo');
  refusal = { status: 409, body: { error: 'open_models_in_use' } };
  await remove();
  await expect(list.getByRole('alert')).toHaveText('Está en uso: elige otro antes de desinstalarlo');
});

// REV_VISTA V-10, the tuned model's install: its refusal with its cause, and no answer not said as a refusal.
test('modelo ajustado: un rechazo al instalar dice su causa, y sin respuesta no se dice que no se pudo', async () => {
  h = await openView();
  h.reply('/settings/tuned-model', () => ({ body: { ...TUNED } }));
  let refusal: { status: number; body: Record<string, unknown> } = { status: 409, body: { error: 'tuned_model_no_space' } };
  h.reply('/settings/tuned-model/install', () => refusal);
  const p = h.page;
  await p.locator('.bx-gear').click();
  await p.locator('.settings-tab', { hasText: 'Modelo' }).click();
  await pickWhere(p, /Ajustado/);
  const install = async () => {
    await p.getByRole('button', { name: 'Instalar', exact: true }).click();
    await p.getByRole('button', { name: 'Descargar' }).click();
  };
  await install();
  await expect(p.getByRole('alert')).toHaveText('Falta espacio en el disco. Libera espacio y vuelve a intentarlo. Lo que ya bajé no se pierde');
  refusal = { status: 503, body: {} };
  await install();
  await expect(p.getByRole('alert')).toHaveText('No supe si se hizo: BAXY no respondió');
  // REV_APP TUN-a: the file to replace is still held by the model that is closing
  refusal = { status: 409, body: { error: 'tuned_model_file_busy' } };
  await install();
  await expect(p.getByRole('alert')).toHaveText('El archivo anterior todavía está en uso: espera un momento y vuelve a intentarlo');
});

// REV_VISTA V-11 (2026-11-09): «BAXY le envía unos 49.000 tokens solo con sus herramientas, así que el contexto parte en
// 64.000» whatever tool profile was chosen (Esencial sends 22,661) and though the default context is another. The App says what
// the chosen profile's prompt takes (promptTokens), and the view says that, or no figure when it is not told.
test('otro modelo local: lo que BAXY le envía se dice con la cifra del perfil elegido, no una fija', async () => {
  h = await openView();
  let host: Record<string, unknown> = { ...EXTERNAL, provider: 'local', model: '', url: 'http://127.0.0.1:11434', ceilingHolds: false, promptTokens: 22661 };
  h.reply('/settings/external-model', () => ({ body: host }));
  h.reply('/settings/external-model/models', () => ({ body: { models: [] } }));
  const p = h.page;
  await p.locator('.bx-gear').click();
  await p.locator('.settings-tab', { hasText: 'Modelo' }).click();
  await pickWhere(p, /Local/);
  await expect(p.getByText(/BAXY le envía unos 22\.661 tokens con sus instrucciones y las herramientas del perfil elegido, así que el contexto no puede ser menor\./)).toBeVisible();
  await expect(p.getByText(/49\.000|64\.000/)).toHaveCount(0);
  // control: a host that does not say it gets no figure
  host = { ...host, promptTokens: undefined };
  await p.keyboard.press('Escape');
  await p.locator('.bx-gear').click();
  await p.locator('.settings-tab', { hasText: 'Modelo' }).click();
  await pickWhere(p, /Local/);
  await expect(p.getByText(/BAXY le envía sus instrucciones y las herramientas del perfil elegido antes de la conversación, así que el contexto no puede ser menor que ellas\./)).toBeVisible();
  await expect(p.getByText(/49\.000|64\.000|22\.661/)).toHaveCount(0);
});

// REV_APP DL-c (2026-11-09): a download the disk failed (not full: a file held, a device error) was said as the network's.
test('modelo: un fallo del disco al bajar se dice como del disco, no de la conexión', async () => {
  h = await openView();
  h.reply('/settings/tuned-model', () => ({ body: { ...TUNED, downloadProblem: 'sin_disco' } }));
  h.reply('/settings/external-model', () => ({ body: { ...EXTERNAL, provider: 'local', model: '', url: 'http://127.0.0.1:11434', ceilingHolds: false,
    open: { ...OPEN_IDLE, pullProblem: 'sin_disco' } } }));
  h.reply('/settings/external-model/models', () => ({ body: { models: [] } }));
  const p = h.page;
  await p.locator('.bx-gear').click();
  await p.locator('.settings-tab', { hasText: 'Modelo' }).click();
  const said = 'Windows dio un error al guardarlo en el disco: puede que otro programa tenga el archivo abierto. Vuelve a intentarlo';
  await pickWhere(p, /Local/);
  await expect(p.getByRole('alert')).toHaveText(said);
  await pickWhere(p, /Ajustado/);
  await expect(p.locator('.bxs-row', { hasText: 'Modelo ajustado a BAXY' }).locator('.h')).toHaveText(said);
  await expect(p.getByText(/No logré conectarme/)).toHaveCount(0);
});

// Seen in the real App on the PC (2026-11-09): «cabe en tu tarjeta», 5.7 GB downloaded, then refused for RAM. Said before.
test('otro modelo local: lo que cabe en la tarjeta pero no en la RAM libre lo dice antes de bajarlo', async () => {
  h = await openView();
  const gib = 2 ** 30;
  const host = { ...EXTERNAL, provider: 'local', model: '', ceilingHolds: false, open: {
    ollamaVersion: '0.40.15', ollamaBytes: 1614941966, ollamaOwn: true, ollamaRunning: '0.40.15', ollamaInstalling: false, ollamaDownloadedBytes: 0,
    ollamaProblem: null, pulling: null, pullTotal: 0, pullDone: 0, pullProblem: null } };
  h.reply('/settings/external-model', () => ({ body: host }));
  h.reply('/settings/external-model/models', () => ({ body: { models: [] } }));
  h.reply('/settings/external-model/search', () => ({ body: { vramTotalBytes: 16 * gib, vramFreeBytes: 11 * gib, ramFreeBytes: 8.6 * gib, results: [
    { repo: 'unsloth/Qwen3.5-9B-GGUF', file: 'Qwen3.5-9B-Q4_K_M.gguf', quant: 'Q4_K_M', name: 'unsloth/Qwen3.5-9B-GGUF:Q4_K_M', bytes: 5_680_000_000,
      projectorBytes: 0, license: 'mit', context: 262144, tools: true, vramBytes: 10.9 * gib, vramContext: 125952, ramBytes: 12 * gib, fit: 'no_cabe_ram', why: null }] } }));
  const p = h.page;
  await p.locator('.bx-gear').click();
  await p.locator('.settings-tab', { hasText: 'Modelo' }).click();
  await pickWhere(p, /Local/);
  const box = p.getByRole('textbox', { name: 'Nombre del modelo a buscar' });
  await box.fill('qwen3.5 9b');
  await box.press('Enter');
  await expect(p.getByText(/Ninguno de los encontrados cabe en este PC/)).toBeVisible();
  await p.getByRole('checkbox', { name: /Sólo los que caben en mi tarjeta/ }).uncheck();
  await expect(p.locator('ul[aria-label="Modelos encontrados"] li').first())
    .toContainText('cabe en tu tarjeta, pero para conectarlo Windows debe poder reservar unos 12,0 GB de RAM y archivo de paginación, y hay 8,6 GB');
});

// Seen in the real App on the PC (2026-11-09): with a model of Ollama's in use the card said «Memoria de vídeo —» and not the
// context it connected with (BAXY chose the one recommended for the card). Both are said, the VRAM as measured.
test('otro modelo local: en uso, la tarjeta dice su VRAM medida y el contexto con que conectó', async () => {
  h = await openView();
  const host = { ...EXTERNAL, provider: 'local', model: 'unsloth/Qwen3.5-0.8B-GGUF:Q4_K_M', enabled: true, active: true, activeLocal: true,
    activeModel: 'unsloth/Qwen3.5-0.8B-GGUF:Q4_K_M', context: null, activeContext: 112640, problem: null, switching: false };
  h.reply('/settings/external-model', () => ({ body: host }));
  h.reply('/settings/external-model/models', () => ({ body: { models: [] } }));
  h.reply('/metrics', () => ({ body: { cpu: 10, gpu: 20, temp: 50, model_vram_gb: 3.6, model_ram_gb: 1.2 } }));
  const p = h.page;
  await p.locator('.bx-gear').click();
  await p.locator('.settings-tab', { hasText: 'Modelo' }).click();
  const inUse = p.getByLabel('Modelo en uso');
  await expect(inUse).toContainText('112.640 tokens');
  await expect(inUse).toContainText('3,6 GB');
});

test('ajustes › modelo: el contexto que no cabe en tu tarjeta lo dice en la lista, antes de elegirlo', async () => {
  // VIVO1 (2026-11-09): on a 6 GB card 262.144 tokens (7,9 GB) was offered as the others and only said so once chosen;
  // chosen, BAXY took 15 minutes to start, its cache in shared memory.
  h = await openView();
  const gib = 2 ** 30;
  const options = [
    { context: 77824, vramBytes: 5.03 * gib, vision: true, slower: false, room: 25154, fits: true },
    { context: 262144, vramBytes: 7.9 * gib, vision: false, slower: false, room: 209474, fits: true },
  ];
  h.reply('/settings/local-context', () => ({ body: { chosen: null, automatic: 77824, prefixTokens: 49086, minimum: 52670,
    cardBytes: 5.85 * gib, cardKnown: true, options, switching: false } }));
  const p = h.page;
  await p.locator('.bx-gear').click();
  await p.locator('.settings-tab', { hasText: 'Modelo' }).click();
  const select = p.getByRole('combobox', { name: 'Contexto' });
  await expect(select.locator('option[value="262144"]')).toHaveText('262.144 tokens · unos 7,9 GB de VRAM · puede no caber en tu tarjeta');
  await expect(select.locator('option[value="77824"]')).toHaveText('77.824 tokens · unos 5,0 GB de VRAM con la visión');
});

// actualizar-ordenes-app (owner, 2026-11-09: «un botón de actualizar»): a newer BAXY is only a pill in the header that opens
// Settings › General; there «Buscar actualizaciones» asks the host (GET /update) and only «Actualizar a …» installs
// (POST /update/install, the person's yes). Steam's BAXY only opens Steam.
test('versión: el aviso abre General, buscar no instala y sólo «Actualizar» lo pide al host', async () => {
  h = await openView();
  h.reply('/update', () => ({ body: { ok: true, channel: 'github', installed: '1.3.2', latest: '1.4.0', newer: true, downloadBytes: 81_450_121 } }));
  h.reply('/update/install', () => ({ body: { ok: true, channel: 'github', installed: '1.3.2', latest: '1.4.0', installerStarted: true } }));
  const p = h.page;
  h.emit({ type: 'update', latest: '1.4.0', installed: '1.3.2' });
  await p.getByRole('button', { name: /Hay una versión nueva de BAXY, la 1\.4\.0/ }).click();
  await p.getByRole('button', { name: 'Buscar actualizaciones' }).click();
  // INT19: in the view's one unit (size.ts, 2³⁰ for GB), 81.450.121 bytes are 77,7 MB as Windows writes them, not 81.
  await expect(p.getByText('Hay una versión nueva: 1.4.0 (instalador de 78 MB)')).toBeVisible();
  // APP1: opening the panel reads whether an install runs (GET); only the button asks for one (POST)
  expect(h.calls.filter((c) => c.method !== 'GET' && c.path === '/update/install')).toHaveLength(0);
  await p.getByRole('button', { name: 'Actualizar a 1.4.0' }).click();
  await expect.poll(() => h.calls.filter((c) => c.method === 'POST' && c.path === '/update/install').length).toBe(1);
  await expect(p.getByText('BAXY se cierra y el instalador la reemplaza; tus datos se quedan')).toBeVisible();
});

test('versión: en Steam no se baja nada, se abre Steam', async () => {
  h = await openView();
  h.reply('/update', () => ({ body: { ok: true, channel: 'steam', installed: '1.3.2', updatedBy: 'steam', storeUpdatesItself: true } }));
  h.reply('/update/install', () => ({ body: { ok: true, channel: 'steam', installed: '1.3.2', opened: 'steam_library' } }));
  const p = h.page;
  await p.locator('.bx-gear').click();
  await p.getByRole('button', { name: 'Buscar actualizaciones' }).click();
  await expect(p.getByText('Steam mantiene BAXY al día y la actualiza solo')).toBeVisible();
  await p.getByRole('button', { name: 'Abrir en Steam' }).click();
  await expect(p.getByText('Abrí Steam: ahí se ve si hay una versión nueva')).toBeVisible();
});

/* VIS1 (2026-11-09, the whole view before the final version): what a person presses and no test without the real App
   had pressed. Measured with V8's coverage of this spec: Settings › Herramientas and the alarms' panel were never drawn,
   and the buttons below were never pressed (controls.spec presses some, only with BAXY running). */

const TOOLS = { total: 7, groups: [
  { name: 'BAXY', items: [{ name: 'baxy.settings.open', title: 'Abrir los ajustes de BAXY', level: 0 }] },
  { name: 'Sistema', items: [{ name: 'system.volume.set', title: 'Cambiar el volumen', level: 1 }, { name: 'files.search', title: 'Buscar ficheros', level: 2 }] },
  { name: 'Ventanas y consola', items: [{ name: 'input.visible.click', title: 'Hacer clic', level: 3 }, { name: 'input.visible.controls', title: 'Ver los controles', level: 3 },
    { name: 'shell.command.run', title: 'Consola', level: 4 }, { name: 'package.install', title: 'Instalar programas', level: 4 }] },
] };
const TOOL_LEVEL: Record<string, number> = { esencial: 1, diario: 2, avanzado: 3, completo: 4 };

/** the host's Settings › Tools as ToolProfile keeps it: a preset keeps the tools up to its level, Personalizado the ones
 *  named, and BAXY's own (level 0) are in every profile. `refuse` answers the next PUT instead; `switching` is said back. */
function toolsHost(start = 'completo') {
  const all = TOOLS.groups.flatMap((g) => g.items);
  let kept: { profile: string; on?: string[] } = { profile: start };
  const host = {
    refuse: null as Reply | null,
    switching: false,
    puts: () => h.calls.filter((c) => c.method === 'PUT' && c.path === '/settings/tools').map((c) => c.body),
  };
  h.reply('/catalog', () => ({ body: TOOLS }));
  h.reply('/settings/tools', (c) => {
    if (c.method === 'PUT') { if (host.refuse) return host.refuse; kept = c.body as typeof kept; }
    const on = all.filter((i) => i.level === 0 || (kept.profile === 'personalizado' ? kept.on?.includes(i.name) : i.level <= TOOL_LEVEL[kept.profile])).map((i) => i.name);
    return { body: { profile: kept.profile, on, switching: host.switching } };
  });
  return host;
}

async function openTools() {
  await h.page.locator('.bx-gear').click();
  await h.page.locator('.settings-tab', { hasText: 'Herramientas' }).click();
  return h.page.getByRole('radiogroup', { name: 'Perfil de herramientas' });
}

test('herramientas: cada perfil dice cuántas herramientas ve el modelo, y elegir uno se aplica una vez', async () => {
  h = await openView();
  const host = toolsHost();
  const profiles = await openTools();
  await expect(profiles.getByRole('radio')).toHaveCount(5);
  await expect(profiles.getByRole('radio', { checked: true })).toHaveCount(1);
  await expect(profiles.getByRole('radio', { name: /^Completo/ })).toHaveAttribute('aria-checked', 'true');
  for (const [name, count] of [['Esencial', 2], ['Diario', 3], ['Avanzado', 5], ['Completo', 7]] as const) {
    await expect(profiles.getByRole('radio', { name: new RegExp('^' + name) })).toContainText(`${count} herramientas`);
  }
  const fold = h.page.getByRole('button', { name: /^Perfil/ });
  await expect(fold).toContainText('Completo · 7 herramientas');
  await profiles.getByRole('radio', { name: /^Diario/ }).click();
  await expect(profiles.getByRole('radio', { name: /^Diario/ })).toHaveAttribute('aria-checked', 'true');
  await expect(profiles.getByRole('radio', { checked: true })).toHaveCount(1);
  await expect(fold).toContainText('Diario · 3 herramientas');
  // the one already chosen is not sent again
  await profiles.getByRole('radio', { name: /^Diario/ }).click();
  await h.page.waitForTimeout(300);
  expect(host.puts()).toEqual([{ profile: 'diario' }]);
});

test('herramientas: un perfil que el host no guardó se dice, y la elección sigue siendo la que hay', async () => {
  h = await openView();
  const host = toolsHost();
  const profiles = await openTools();
  const said = h.page.locator('.settings-body').getByRole('alert');
  host.refuse = { status: 409, body: { error: 'tool_profile_not_saved' } };
  await profiles.getByRole('radio', { name: /^Esencial/ }).click();
  await expect(said).toHaveText('No se guardó ese perfil');
  await expect(profiles.getByRole('radio', { name: /^Completo/ })).toHaveAttribute('aria-checked', 'true');
  // the bridge's 503 is no answer: the host may have taken it, and that is not said as a refusal
  host.refuse = { status: 503 };
  await profiles.getByRole('radio', { name: /^Esencial/ }).click();
  await expect(said).toHaveText('BAXY no respondió: inténtalo otra vez');
  host.refuse = null;
  await profiles.getByRole('radio', { name: /^Esencial/ }).click();
  await expect(profiles.getByRole('radio', { name: /^Esencial/ })).toHaveAttribute('aria-checked', 'true');
  await expect(said).toHaveCount(0);
});

test('herramientas: mientras BAXY cambia de perfil lo dice y no deja elegir otro', async () => {
  h = await openView();
  const host = toolsHost();
  const profiles = await openTools();
  const changing = h.page.locator('.settings-body').getByRole('status').filter({ hasText: 'Cambiando de perfil' });
  await expect(changing).toHaveCount(0);
  host.switching = true;
  await profiles.getByRole('radio', { name: /^Avanzado/ }).click();
  await expect(changing).toBeVisible();
  for (const name of ['Esencial', 'Diario', 'Avanzado', 'Completo', 'Personalizado']) {
    await expect(profiles.getByRole('radio', { name: new RegExp('^' + name) })).toBeDisabled();
  }
  // the mind came back with the new profile: the state, read every second, says so
  host.switching = false;
  await expect(changing).toHaveCount(0);
  await expect(profiles.getByRole('radio', { name: /^Esencial/ })).toBeEnabled();
  await expect(profiles.getByRole('radio', { name: /^Avanzado/ })).toHaveAttribute('aria-checked', 'true');
});

test('herramientas: Personalizado apaga una a una, avisa de lo que otra deja pasar y sólo se guarda con su botón', async () => {
  h = await openView();
  const host = toolsHost();
  const profiles = await openTools();
  const p = h.page;
  await profiles.getByRole('radio', { name: /^Personalizado/ }).click();
  await expect(profiles.getByRole('radio', { name: /^Personalizado/ })).toHaveAttribute('aria-checked', 'true');
  await expect(profiles.getByRole('radio', { checked: true })).toHaveCount(1);
  // BAXY's own tools are in every profile: on, and not the person's to turn off
  const own = p.getByRole('checkbox', { name: /Abrir los ajustes de BAXY/ });
  await expect(own).toBeChecked();
  await expect(own).toBeDisabled();
  await expect(p.getByRole('checkbox', { checked: true })).toHaveCount(7);
  const warning = p.locator('.settings-body').getByRole('alert');
  await expect(warning).toHaveCount(0);
  await p.getByRole('checkbox', { name: 'Instalar programas' }).uncheck();
  await expect(warning).toContainText('Con la consola encendida, BAXY puede instalar programas aunque «instalar» esté apagado');
  await p.getByRole('checkbox', { name: 'Consola' }).uncheck();
  await expect(warning).toHaveCount(0);
  await p.getByRole('checkbox', { name: 'Ver los controles' }).uncheck();
  await expect(warning).toContainText('sin «ver los controles» los clics fallarán más');
  await expect(profiles.getByRole('radio', { name: /^Personalizado/ })).toContainText('4 herramientas');
  // nothing is kept until its button
  expect(host.puts()).toEqual([]);
  await p.getByRole('button', { name: 'Guardar mi selección' }).click();
  // only what the person can turn off is named: BAXY's own are the host's to keep
  await expect.poll(host.puts).toEqual([{ profile: 'personalizado', on: ['system.volume.set', 'files.search', 'input.visible.click'] }]);
  await expect(p.getByRole('button', { name: /^Perfil/ })).toContainText('Personalizado · 4 herramientas');
  await expect(p.getByRole('button', { name: 'Guardar mi selección' })).toBeDisabled();
  await expect(p.getByRole('button', { name: 'Descartar' })).toHaveCount(0);
  await expect(p.getByRole('checkbox', { name: 'Consola' })).not.toBeChecked();
});

test('herramientas: «Apagar todas» apaga las de su grupo, y Descartar vuelve al perfil sin enviar nada', async () => {
  h = await openView();
  const host = toolsHost('diario');
  const profiles = await openTools();
  const p = h.page;
  await expect(profiles.getByRole('radio', { name: /^Diario/ })).toHaveAttribute('aria-checked', 'true');
  await profiles.getByRole('radio', { name: /^Personalizado/ }).click();
  const system = p.locator('fieldset', { hasText: 'Sistema' });
  const windows = p.locator('fieldset', { hasText: 'Ventanas y consola' });
  await expect(system.getByRole('checkbox', { checked: true })).toHaveCount(2);
  await expect(windows.getByRole('checkbox', { checked: true })).toHaveCount(0);
  await system.getByRole('button', { name: 'Apagar todas' }).click();
  await expect(system.getByRole('checkbox', { checked: true })).toHaveCount(0);
  await windows.getByRole('button', { name: 'Encender todas' }).click();
  await expect(windows.getByRole('checkbox', { checked: true })).toHaveCount(4);
  await expect(windows.getByRole('button', { name: 'Apagar todas' })).toBeVisible();
  // BAXY's own group has nothing to turn off, so no button
  await expect(p.locator('fieldset', { hasText: 'Abrir los ajustes de BAXY' }).getByRole('button')).toHaveCount(0);
  await p.getByRole('button', { name: 'Descartar' }).click();
  await expect(profiles.getByRole('radio', { name: /^Diario/ })).toHaveAttribute('aria-checked', 'true');
  await expect(p.getByRole('button', { name: /^Una a una/ })).toHaveCount(0);
  await expect(p.getByRole('button', { name: /^Perfil/ })).toContainText('Diario · 3 herramientas');
  expect(host.puts()).toEqual([]);
});

test('herramientas: si el host no dice el perfil, la pestaña lo dice en vez de quedar vacía', async () => {
  h = await openView();
  h.reply('/settings/tools', () => ({ status: 503 }));
  await h.page.locator('.bx-gear').click();
  await h.page.locator('.settings-tab', { hasText: 'Herramientas' }).click();
  await expect(h.page.locator('.settings-body')).toContainText('No se pudo leer este ajuste');
  await expect(h.page.getByRole('radiogroup', { name: 'Perfil de herramientas' })).toHaveCount(0);
});

const TRIGGERS = { count: 2, truncated: false, items: [
  { kind: 'alarm', title: null, next_local: '2026-11-10 07:00', state: 'Ready' },
  { kind: 'reminder', title: 'Llamar a Ana', next_local: '2026-11-09 18:30', state: 'Ready' },
] };
const cancels = () => h.calls.filter((c) => c.path === '/triggers/cancel').map((c) => c.body);
async function openTriggers() {
  await h.page.locator('button', { hasText: 'Alarmas' }).first().click();
  return h.page.getByRole('dialog', { name: /Alarmas y recordatorios/ });
}

test('alarmas: el panel lista lo que la persona creó, y cancelar una pide un sí antes y la quita', async () => {
  h = await openView();
  h.reply('/triggers', () => ({ body: TRIGGERS }));
  h.reply('/triggers/cancel', () => ({ body: { count: 1, truncated: false, items: [TRIGGERS.items[1]] } }));
  const panel = await openTriggers();
  const rows = panel.locator('.bx-trig');
  await expect(rows).toHaveCount(2);
  await expect(rows.nth(0)).toContainText('Alarma · 2026-11-10 07:00');
  await expect(rows.nth(0)).toContainText('Suena en este PC');
  await expect(rows.nth(1)).toContainText('Recordatorio · 2026-11-09 18:30');
  await expect(rows.nth(1)).toContainText('Llamar a Ana');
  // the first press only asks, and «No» leaves the alarm
  await panel.getByRole('button', { name: 'Cancelar la alarma de 2026-11-10 07:00' }).click();
  const ask = panel.getByRole('group', { name: '¿Cancelar?' });
  await expect(ask.getByRole('button', { name: 'No' })).toBeFocused();
  await ask.getByRole('button', { name: 'No' }).click();
  await expect(ask).toHaveCount(0);
  expect(cancels()).toEqual([]);
  await panel.getByRole('button', { name: 'Cancelar la alarma de 2026-11-10 07:00' }).click();
  await ask.getByRole('button', { name: 'Sí, cancelar' }).click();
  await expect.poll(cancels).toEqual([{ at: '2026-11-10 07:00', kind: 'alarm' }]);
  await expect(rows).toHaveCount(1);
  await expect(rows.first()).toContainText('Llamar a Ana');
});

test('alarmas: una cancelación que el host rechazó se dice y la alarma sigue en la lista', async () => {
  h = await openView();
  h.reply('/triggers', () => ({ body: TRIGGERS }));
  h.reply('/triggers/cancel', () => ({ status: 409, body: { error: 'trigger_not_cancelled' } }));
  const panel = await openTriggers();
  await panel.getByRole('button', { name: 'Cancelar el recordatorio de 2026-11-09 18:30' }).click();
  await panel.getByRole('group', { name: '¿Cancelar?' }).getByRole('button', { name: 'Sí, cancelar' }).click();
  // INT21: with APP1 (REV_APP TRG-a, c1d0ee19e) a refused cancellation says the alarm is still set.
  await expect(panel.getByRole('status')).toHaveText('No se pudo cancelar: sigue puesta.');
  await expect(panel.locator('.bx-trig')).toHaveCount(2);
  expect(cancels()).toEqual([{ at: '2026-11-09 18:30', kind: 'reminder' }]);
});

test('alarmas: sin ninguna lo dice, una lista cortada dice cuántas hay, y si no se pudo leer también', async () => {
  h = await openView();
  let answer: Reply = { body: { count: 0, truncated: false, items: [] } };
  h.reply('/triggers', () => answer);
  let panel = await openTriggers();
  await expect(panel).toContainText('No has creado alarmas ni recordatorios. Pídeselos a BAXY.');
  await h.page.keyboard.press('Escape');
  await expect(panel).toHaveCount(0);
  answer = { body: { ...TRIGGERS, count: 53, truncated: true } };
  panel = await openTriggers();
  await expect(panel).toContainText('Se muestran 2 de 53.');
  await panel.getByRole('button', { name: 'Cerrar' }).click();
  answer = { status: 503, body: { error: 'triggers_unavailable' } };
  panel = await openTriggers();
  await expect(panel.getByRole('status')).toHaveText('No se pudieron leer las alarmas y recordatorios.');
  await expect(panel.locator('.bx-trig')).toHaveCount(0);
});

type BehaviorField = 'personality' | 'replies' | 'preferences';
const FACTORY: Record<BehaviorField, string> = { personality: 'Eres directo y amable.', replies: 'Responde en una o dos frases.', preferences: '' };

/** the host's Settings › Behavior as PersonBehavior keeps it: a text given is kept trimmed, null or nothing is the factory's
 *  again, `reset` all of them; `factory` null is the mind still starting. */
function behaviorHost(own: Partial<Record<BehaviorField, string>> = {}, maxChars = 1200) {
  const host = {
    texts: { personality: null, replies: null, preferences: null, ...own } as Record<string, string | null>,
    factory: FACTORY as typeof FACTORY | null,
    refuse: null as Reply | null,
    switching: false,
    puts: () => h.calls.filter((c) => c.method === 'PUT' && c.path === '/settings/behavior').map((c) => c.body),
  };
  h.reply('/settings/behavior', (c) => {
    if (c.method === 'PUT') {
      if (host.refuse) return host.refuse;
      const body = c.body as Record<string, string | boolean | null>;
      if (body.reset === true) host.texts = { personality: null, replies: null, preferences: null };
      else for (const [field, text] of Object.entries(body)) host.texts[field] = typeof text === 'string' && text.trim() ? text.trim() : null;
    }
    return { body: { identity: host.factory ? 'Te llamas BAXY.' : null, factory: host.factory, texts: host.texts, maxChars, switching: host.switching } };
  });
  return host;
}

async function openBehavior() {
  await h.page.locator('.bx-gear').click();
  await h.page.locator('.settings-tab', { hasText: 'Comportamiento' }).click();
  return (field: BehaviorField) => h.page.locator('.bxs-text', { has: h.page.locator('#bxs-behavior-' + field) });
}

test('comportamiento: un texto tuyo se guarda con su botón, queda marcado «tuyo» y Restaurar vuelve al de fábrica', async () => {
  h = await openView();
  const host = behaviorHost();
  const box = (await openBehavior())('personality');
  const text = box.getByRole('textbox');
  const fold = h.page.getByRole('button', { name: /^Personalidad y respuestas/ });
  await expect(text).toHaveValue(FACTORY.personality);
  await expect(fold).toContainText('De fábrica');
  await expect(box.getByRole('button', { name: 'Guardar' })).toBeDisabled();
  await expect(box.getByRole('button', { name: 'Restaurar' })).toHaveCount(0);
  await text.fill('Con humor seco.');
  await expect(box.locator('.foot .n')).toHaveText('15 / 1200');
  // writing is not saving
  expect(host.puts()).toEqual([]);
  await box.getByRole('button', { name: 'Guardar' }).click();
  await expect(box.locator('em.ro')).toHaveText('tuyo');
  await expect(text).toHaveValue('Con humor seco.');
  await expect(fold).toContainText('Con tus textos');
  await expect(box.getByRole('button', { name: 'Guardar' })).toBeDisabled();
  // the factory's own words written back are no text of the person's
  await text.fill('  ' + FACTORY.personality + ' ');
  await box.getByRole('button', { name: 'Guardar' }).click();
  await expect(box.locator('em.ro')).toHaveCount(0);
  await expect(fold).toContainText('De fábrica');
  await text.fill('Muy paciente.');
  await box.getByRole('button', { name: 'Guardar' }).click();
  await box.getByRole('button', { name: 'Restaurar' }).click();
  await expect(text).toHaveValue(FACTORY.personality);
  await expect(box.getByRole('button', { name: 'Restaurar' })).toHaveCount(0);
  expect(host.puts()).toEqual([{ personality: 'Con humor seco.' }, { personality: null }, { personality: 'Muy paciente.' }, { personality: null }]);
});

test('comportamiento: un texto demasiado largo no se puede guardar, y lo que el host no guardó se dice sin perder lo escrito', async () => {
  h = await openView();
  const host = behaviorHost({}, 20);
  const box = (await openBehavior())('preferences');
  const text = box.getByRole('textbox');
  const save = box.getByRole('button', { name: 'Guardar' });
  const said = h.page.locator('.settings-body').getByRole('alert');
  await text.fill('x'.repeat(21));
  await expect(box.locator('.foot .n')).toHaveText('21 / 20 · demasiado largo');
  await expect(text).toHaveAttribute('aria-invalid', 'true');
  await expect(save).toBeDisabled();
  await text.fill('Llámame Ana.');
  await expect(text).toHaveAttribute('aria-invalid', 'false');
  for (const [refusal, words] of [
    [{ status: 409, body: { error: 'behavior_not_saved' } }, 'Windows no me dejó guardarlo'],
    [{ status: 409, body: { error: 'behavior_too_long' } }, 'Es demasiado largo'],
    [{ status: 503 }, 'No se pudo guardar']] as const) {
    host.refuse = refusal;
    await save.click();
    await expect(said).toHaveText(words);
    await expect(text).toHaveValue('Llámame Ana.');
    await expect(box.locator('em.ro')).toHaveCount(0);
  }
  host.refuse = null;
  await save.click();
  await expect(box.locator('em.ro')).toHaveText('tuyo');
  await expect(said).toHaveCount(0);
});

test('comportamiento: «Restaurar todo de fábrica» quita los tuyos, y mientras BAXY los aplica lo dice y no deja escribir', async () => {
  h = await openView();
  const host = behaviorHost({ personality: 'Con humor seco.', preferences: 'Llámame Ana.' });
  const box = await openBehavior();
  const p = h.page;
  const applying = p.locator('.settings-body').getByRole('status').filter({ hasText: 'Aplicando tus cambios' });
  await expect(box('personality').getByRole('textbox')).toHaveValue('Con humor seco.');
  await expect(box('replies').locator('em.ro')).toHaveCount(0);
  await expect(applying).toHaveCount(0);
  host.switching = true;
  await p.getByRole('button', { name: 'Restaurar todo de fábrica' }).click();
  await expect.poll(host.puts).toEqual([{ reset: true }]);
  await expect(applying).toBeVisible();
  for (const field of ['personality', 'replies', 'preferences'] as const) await expect(box(field).getByRole('textbox')).toBeDisabled();
  await expect(box('personality').getByRole('textbox')).toHaveValue(FACTORY.personality);
  // the mind is back on the factory's texts: the state, read every second, says so
  host.switching = false;
  await expect(applying).toHaveCount(0);
  await expect(box('personality').getByRole('textbox')).toBeEnabled();
  await expect(p.getByRole('button', { name: 'Restaurar todo de fábrica' })).toHaveCount(0);
  await expect(p.getByRole('button', { name: /^Personalidad y respuestas/ })).toContainText('De fábrica');
});

test('comportamiento: mientras BAXY arranca no hay texto de fábrica: lo dice, no deja escribir y lo muestra al llegar', async () => {
  h = await openView();
  const host = behaviorHost();
  host.factory = null;
  const box = await openBehavior();
  const text = box('replies').getByRole('textbox');
  await expect(h.page.locator('.bxs-fixedtext')).toHaveText('BAXY está arrancando…');
  await expect(text).toBeDisabled();
  await expect(text).toHaveAttribute('placeholder', 'BAXY está arrancando…');
  host.factory = FACTORY;
  await expect(text).toHaveValue(FACTORY.replies);
  await expect(text).toBeEnabled();
  await expect(h.page.locator('.bxs-fixedtext')).toHaveText('Te llamas BAXY.');
});

const MEMORIES = [
  { key: 'color favorito', value: 'Su color favorito es el verde', updated_at: '', kind: 'preference' },
  { key: 'reunion', label: 'Reunión', value: 'los lunes a las 9', updated_at: '', kind: 'rule' },
  { key: 'dato reservado', label: 'Número de la tarjeta', value: 'NO-DEBE-VERSE', updated_at: '', kind: 'fact', sensitivity: 'secret' },
];

/** the host's memory as MemoryPanel.cs answers the panel: every change says the list that is left. */
function memoryHost() {
  const host = { enabled: true, items: [...MEMORIES], refuse: null as Reply | null };
  const state = () => ({ body: { enabled: host.enabled, total: host.items.length, items: host.items } });
  h.reply('/memory', (c) => {
    if (c.method === 'DELETE') { if (host.refuse) return host.refuse; host.items = []; }
    return state();
  });
  h.reply('/memory/enabled', (c) => { if (host.refuse) return host.refuse; host.enabled = (c.body as { enabled: boolean }).enabled; return state(); });
  for (const m of MEMORIES) {
    h.reply('/memory/' + encodeURIComponent(m.key), () => { if (host.refuse) return host.refuse; host.items = host.items.filter((x) => x.key !== m.key); return state(); });
  }
  return host;
}
const forgets = () => h.calls.filter((c) => c.method === 'DELETE').map((c) => [c.path, c.body]);
async function openMemory() {
  await h.page.locator('button', { hasText: 'Memoria' }).first().click();
  return h.page.getByRole('dialog', { name: /^Memoria/ });
}

test('memoria: olvidar un recuerdo pide un sí en su fila y lo quita; un dato sensible nunca se muestra', async () => {
  h = await openView();
  memoryHost();
  const panel = await openMemory();
  await expect(panel.locator('.bx-mem-row')).toHaveCount(3);
  await expect(panel.locator('.panel-footer')).toContainText('3 recuerdos');
  await expect(panel.locator('.bx-mem-g.sens .bx-mem-row')).toHaveText(/Número de la tarjeta · ••••••/);
  await expect(panel).not.toContainText('NO-DEBE-VERSE');
  await panel.getByRole('button', { name: 'Olvidar: Su color favorito es el verde' }).click();
  const ask = panel.getByRole('group', { name: '¿Olvidar?' });
  await ask.getByRole('button', { name: 'No' }).click();
  await expect(ask).toHaveCount(0);
  expect(forgets()).toEqual([]);
  await panel.getByRole('button', { name: 'Olvidar: Su color favorito es el verde' }).click();
  await ask.getByRole('button', { name: 'Sí, olvidar' }).click();
  await expect(panel.locator('.bx-mem-row')).toHaveCount(2);
  await expect(panel.locator('.panel-footer')).toContainText('2 recuerdos');
  await panel.getByRole('button', { name: 'Olvidar: Reunión' }).click();
  await ask.getByRole('button', { name: 'Sí, olvidar' }).click();
  await expect(panel.locator('.panel-footer')).toContainText(/1 recuerdo(?!s)/);
  await expect.poll(() => forgets().map(([path]) => path)).toEqual(['/memory/color%20favorito', '/memory/reunion']);
});

// PRV1 D7 (INFORME_PRV1 §9, 2026-11-10): «Olvidar todo» was off with no memories, and it is also what deletes the kept
// conversations and the conversation's log: with none, nothing in the interface could. It is offered whenever the host keeps
// any of them (GET /kept), and off only when there is nothing to forget.
test('memoria: «Olvidar todo» se ofrece sin recuerdos si hay conversaciones o registros, y sólo se apaga sin nada', async () => {
  h = await openView();
  const host = memoryHost();
  host.items = [];
  let kept = { conversations: 2, log: true };
  h.reply('/kept', () => ({ body: kept }));
  h.reply('/memory', (c) => {
    if (c.method === 'DELETE') kept = { conversations: 0, log: false };
    return { body: { enabled: true, total: 0, items: [] } };
  });
  const panel = await openMemory();
  const all = panel.getByRole('button', { name: 'Olvidar todo' });
  await expect(all).toBeEnabled();
  await all.click();
  await panel.getByRole('group', { name: '¿Olvidar todo?' }).getByRole('button', { name: 'Sí, olvidar' }).click();
  await expect.poll(() => h.calls.filter((c) => c.method === 'DELETE' && c.path === '/memory').map((c) => c.body)).toEqual([{ scope: 'all' }]);
  // nothing left: nothing to offer
  await expect(all).toBeDisabled();
});

test('memoria: «Olvidar todo» pide un sí, y lo que no se pudo olvidar se dice y sigue en la lista', async () => {
  h = await openView();
  const host = memoryHost();
  const panel = await openMemory();
  const said = panel.getByRole('status');
  host.refuse = { status: 409, body: { ok: false, error: 'memory_protection_failed' } };
  await panel.getByRole('button', { name: 'Olvidar: Reunión' }).click();
  await panel.getByRole('group', { name: '¿Olvidar?' }).getByRole('button', { name: 'Sí, olvidar' }).click();
  await expect(said).toHaveText('No se pudo olvidar.');
  await expect(panel.locator('.bx-mem-row')).toHaveCount(3);
  await panel.getByRole('button', { name: 'Olvidar todo' }).click();
  const ask = panel.getByRole('group', { name: '¿Olvidar todo?' });
  await ask.getByRole('button', { name: 'Sí, olvidar' }).click();
  await expect(said).toHaveText('No se pudo olvidar todo.');
  await expect(panel.locator('.bx-mem-row')).toHaveCount(3);
  host.refuse = null;
  await panel.getByRole('button', { name: 'Olvidar todo' }).click();
  await ask.getByRole('button', { name: 'No' }).click();
  await expect(panel.locator('.bx-mem-row')).toHaveCount(3);
  await panel.getByRole('button', { name: 'Olvidar todo' }).click();
  await ask.getByRole('button', { name: 'Sí, olvidar' }).click();
  await expect(panel).toContainText('BAXY no recuerda nada.');
  await expect(said).toHaveCount(0);
  await expect(panel.locator('.panel-footer')).toContainText('0 recuerdos');
  await expect(panel.getByRole('button', { name: 'Olvidar todo' })).toBeDisabled();
  await expect.poll(() => forgets().filter(([path]) => path === '/memory')).toEqual([['/memory', { scope: 'all' }], ['/memory', { scope: 'all' }]]);
});

test('memoria: apagarla lo dice y deja de contar recuerdos; si no se pudo cambiar, el interruptor sigue como estaba', async () => {
  h = await openView();
  const host = memoryHost();
  const panel = await openMemory();
  const remember = panel.getByRole('switch', { name: 'Recordar cosas sobre ti' });
  await expect(remember).toHaveAttribute('aria-checked', 'true');
  await remember.click();
  await expect(remember).toHaveAttribute('aria-checked', 'false');
  await expect(panel).toContainText('La memoria está apagada: BAXY no lee ni guarda recuerdos.');
  await expect(panel.locator('.panel-footer')).not.toContainText('recuerdo');
  host.refuse = { status: 409, body: { ok: false, error: 'memory_protection_failed' } };
  await remember.click();
  await expect(panel.getByRole('status')).toHaveText('No se pudo activar.');
  await expect(remember).toHaveAttribute('aria-checked', 'false');
  host.refuse = null;
  await remember.click();
  await expect(remember).toHaveAttribute('aria-checked', 'true');
  await expect(panel.getByRole('status')).toHaveCount(0);
  await expect.poll(() => h.calls.filter((c) => c.path === '/memory/enabled').map((c) => c.body)).toEqual([{ enabled: false }, { enabled: true }, { enabled: true }]);
});

test('memoria: si no se pudo leer lo dice y no deja cambiarla; mientras BAXY arranca dice eso', async () => {
  h = await openView();
  // no answer in time: what field-native-bridge.js gives the view then
  let answer: Reply = { status: 503, body: { error: 'Error: BAXY native request timed out: http' } };
  h.reply('/memory', () => answer);
  let panel = await openMemory();
  await expect(panel.getByRole('status')).toHaveText('No se pudo leer la memoria.');
  await expect(panel.getByRole('switch', { name: 'Recordar cosas sobre ti' })).toBeDisabled();
  await expect(panel.getByRole('button', { name: 'Olvidar todo' })).toBeDisabled();
  await h.page.keyboard.press('Escape');
  // as the host says it (MemoryPanel.cs): refused, with its reason
  answer = { status: 409, body: { error: 'agent_not_ready', items: [] } };
  panel = await openMemory();
  await expect(panel.getByRole('status')).toHaveText('BAXY aún está arrancando.');
  await expect(panel.getByRole('switch', { name: 'Recordar cosas sobre ti' })).toBeDisabled();
  await h.page.keyboard.press('Escape');
  // a reason the view has no words for (the store's own, MemoryHandlers.cs) is not shown as it comes
  answer = { status: 409, body: { ok: false, error: 'memory_protection_failed' } };
  panel = await openMemory();
  await expect(panel.getByRole('status')).toHaveText('No se pudo leer la memoria.');
});

// VIS1 (segunda revisión ciega): the host answers `agent_not_ready` whenever the core is not ready, broken down too, and
// nothing read the memory again once BAXY had started.
test('memoria: con BAXY averiado no se dice que está arrancando; y al terminar de arrancar la memoria se lee sola', async () => {
  h = await openView();
  let ready = false;
  h.reply('/memory', () => (ready ? { body: { enabled: true, total: MEMORIES.length, items: MEMORIES } } : { status: 409, body: { error: 'agent_not_ready', items: [] } }));
  h.emit({ type: 'agent', built: true, ready: false, powered: true, failure: 'engine_unavailable' });
  await expect(h.page.getByRole('alertdialog')).toBeVisible();
  let panel = await openMemory();
  await expect(panel.getByRole('status')).toHaveText('No se pudo leer la memoria.');
  await h.page.keyboard.press('Escape');
  await expect(panel).toHaveCount(0);
  h.emit({ type: 'agent', built: true, ready: false, powered: true });
  await expect(h.page.getByRole('alertdialog')).toHaveCount(0);
  panel = await openMemory();
  await expect(panel.getByRole('status')).toHaveText('BAXY aún está arrancando.');
  await expect(panel.getByRole('switch', { name: 'Recordar cosas sobre ti' })).toBeDisabled();
  ready = true;
  h.emit({ type: 'agent', built: true, ready: true, powered: true });
  await expect(panel.locator('.bx-mem-row')).toHaveCount(3);
  await expect(panel).not.toContainText('arrancando');
  await expect(panel.getByRole('switch', { name: 'Recordar cosas sobre ti' })).toBeEnabled();
});

// VIS1 (segunda revisión ciega): a change that got no answer was said failed, though the host may have done it (its own
// rule, MemoryPanel.cs «Revisión M H8»). One the host refused, with its code, is still said failed.
test('memoria: un olvido sin respuesta no se dice fallido, se dice sin confirmar con lo que hay; uno rechazado, sí', async () => {
  h = await openView();
  const host = memoryHost();
  const panel = await openMemory();
  const said = panel.getByRole('status');
  const yes = panel.getByRole('group', { name: '¿Olvidar?' }).getByRole('button', { name: 'Sí, olvidar' });
  await expect(panel.locator('.bx-mem-row')).toHaveCount(3);
  // done by the host, and its answer never came: what field-native-bridge.js gives the view then
  h.reply('/memory/reunion', () => {
    host.items = host.items.filter((m) => m.key !== 'reunion');
    return { status: 503, body: { error: 'Error: BAXY native request timed out: http' } };
  });
  await panel.getByRole('button', { name: 'Olvidar: Reunión' }).click();
  await yes.click();
  await expect(said).toHaveText('No se pudo confirmar el cambio: esto es lo que hay ahora.');
  await expect(panel.locator('.bx-mem-row')).toHaveCount(2);
  await expect(panel).not.toContainText('Reunión');
  // refused by the host with its code (MemoryHandlers.cs: the request's protected arguments could not be opened): not done
  host.refuse = { status: 409, body: { ok: false, error: 'memory_protection_failed' } };
  await panel.getByRole('button', { name: 'Olvidar: Su color favorito es el verde' }).click();
  await yes.click();
  await expect(said).toHaveText('No se pudo olvidar.');
  await expect(panel.locator('.bx-mem-row')).toHaveCount(2);
});

test('sin frenos: se activa sólo con su sí, se ve arriba mientras dure y su etiqueta lleva al ajuste', async () => {
  h = await openView();
  let policy = 'normal';
  h.reply('/confirmation', (c) => {
    if (c.method === 'PUT') policy = (c.body as { confirmationPolicy: string }).confirmationPolicy;
    return { body: { confirmationPolicy: policy, confirmSeconds: 120, proposalSeconds: 60 } };
  });
  const puts = () => h.calls.filter((c) => c.method === 'PUT' && c.path === '/confirmation').map((c) => c.body);
  const p = h.page;
  const pill = p.locator('.bx-bypass-pill');
  await p.locator('.bx-gear').click();
  await p.locator('.settings-tab', { hasText: 'Confirmación' }).click();
  const pick = p.getByRole('radiogroup', { name: 'Antes de actuar' });
  const ask = p.getByRole('alertdialog', { name: '¿Activar sin frenos?' });
  await pick.getByRole('radio', { name: 'Sin frenos' }).click();
  await expect(ask.getByRole('button', { name: 'Cancelar' })).toBeFocused();
  await ask.getByRole('button', { name: 'Cancelar' }).click();
  await expect(ask).toHaveCount(0);
  await expect(pick.getByRole('radio', { name: 'Normal' })).toHaveAttribute('aria-checked', 'true');
  expect(puts()).toEqual([]);
  await expect(pill).toHaveCount(0);
  await pick.getByRole('radio', { name: 'Sin frenos' }).click();
  await ask.getByRole('button', { name: 'Sí, activar sin frenos' }).click();
  await expect(pill).toBeVisible();
  await expect(p.locator('.bx-notice')).toContainText('sin frenos hasta que lo apagues');
  await expect(pick.getByRole('radio', { name: 'Sin frenos' })).toHaveAttribute('aria-checked', 'true');
  await expect(p.getByRole('button', { name: /^Antes de actuar/ })).toContainText('Sin frenos');
  await p.getByRole('button', { name: 'Listo' }).click();
  // while it is on it stays in sight, and its label opens the setting that turns it off
  await pill.click();
  await expect(p.locator('.settings-tab', { hasText: 'Confirmación' })).toHaveAttribute('aria-selected', 'true');
  await pick.getByRole('radio', { name: 'Normal' }).click();
  await expect(pill).toHaveCount(0);
  await expect(p.locator('.bx-notice')).toContainText('BAXY pregunta antes de lo arriesgado');
  await expect.poll(() => puts()).toEqual([{ confirmationPolicy: 'bypass' }, { confirmationPolicy: 'normal' }]);
});

test('sin frenos: si el host no lo cambió, se dice y sigue en Normal', async () => {
  h = await openView();
  h.reply('/confirmation', (c) => (c.method === 'PUT' ? { status: 409, body: { error: 'confirmation_not_saved' } } : { body: { confirmationPolicy: 'normal', confirmSeconds: 120, proposalSeconds: 60 } }));
  const p = h.page;
  await p.locator('.bx-gear').click();
  await p.locator('.settings-tab', { hasText: 'Confirmación' }).click();
  await p.getByRole('radio', { name: 'Sin frenos' }).click();
  await p.getByRole('button', { name: 'Sí, activar sin frenos' }).click();
  await expect(p.locator('.bx-notice')).toContainText('no se pudo cambiar');
  await expect(p.getByRole('radio', { name: 'Normal' })).toHaveAttribute('aria-checked', 'true');
  await expect(p.locator('.bx-bypass-pill')).toHaveCount(0);
});

test('nueva conversación: su botón la pide al host, y si BAXY sigue ocupado se dice', async () => {
  h = await openView({ items: [{ who: 'you', id: 'y1', ts: '12:00', text: 'hola' }] });
  let busy = true;
  h.reply('/sessions/new', () => (busy ? { status: 409, body: { error: 'turn_in_progress' } } : { body: { ok: true } }));
  const p = h.page;
  const asked = () => h.calls.filter((c) => c.path === '/sessions/new').map((c) => c.method);
  await p.locator('button[title="Nueva conversación"]').click();
  await expect(p.locator('.bx-notice')).toContainText('espera a que BAXY termine');
  busy = false;
  await p.locator('button[title="Nueva conversación"]').click();
  await expect.poll(asked).toEqual(['POST', 'POST']);
  // from the list of earlier conversations too, and taken, the list closes
  await p.locator('button', { hasText: 'Historial' }).first().click();
  const list = p.getByRole('dialog');
  await list.getByRole('button', { name: /Nueva conversación/ }).click();
  await expect(list).toHaveCount(0);
  await expect.poll(() => asked()).toEqual(['POST', 'POST', 'POST']);
});

test('ajustes: cada interruptor de General, Voz y Privacidad envía su ajuste y sólo ese; lo que no se guardó se dice', async () => {
  h = await openView({ mic: 'ptt' });
  let host: Record<string, unknown> = { language: 'es', languageInUse: 'es', autostart: false, closeToTray: true, minimizeToTray: false, updateNotice: true,
    voiceMuted: false, wakeSound: true, waitNotice: true, echoCancel: true, web: false, weather: true, screen: false };
  let refuse = false;
  h.reply('/settings/general', (c) => {
    if (c.method === 'PUT') { if (refuse) return { status: 409, body: { error: 'settings_not_saved' } }; host = { ...host, ...(c.body as object) }; }
    return { body: host };
  });
  const p = h.page;
  await p.locator('.bx-gear').click();
  const sent: unknown[] = [];
  for (const [tab, name, patch] of [
    ['General', 'Arrancar con Windows', { autostart: true }],
    ['General', 'Al cerrar la ventana, seguir en la bandeja', { closeToTray: false }],
    ['Voz', 'Sonido al despertar', { wakeSound: false }],
    ['Voz', 'Ignorar lo que suena en el PC', { echoCancel: false }],
    ['Voz', 'Decir «Un momento»', { waitNotice: false }],
    ['Voz', 'Silenciar su voz', { voiceMuted: true }],
    ['Privacidad', 'Búsqueda web', { web: true }],
    ['Privacidad', 'Mirar la pantalla', { screen: true }],
    ['Privacidad', 'Clima', { weather: false }]] as const) {
    await p.locator('.settings-tab', { hasText: tab }).click();
    const toggle = p.getByRole('switch', { name, exact: true });
    const wanted = String(Object.values(patch)[0]);
    await expect(toggle).toHaveAttribute('aria-checked', String(wanted !== 'true'));
    await toggle.click();
    await expect(toggle).toHaveAttribute('aria-checked', wanted);
    sent.push(patch);
  }
  await expect.poll(() => h.calls.filter((c) => c.method === 'PUT' && c.path === '/settings/general').map((c) => c.body)).toEqual(sent);
  // each section says folded what is chosen in it
  await expect(p.getByRole('button', { name: /^Salidas a internet/ }).first()).toContainText('búsqueda');
  await expect(p.getByRole('button', { name: /^Salidas a internet/ }).first()).not.toContainText('clima');
  await p.locator('.settings-tab', { hasText: 'Voz' }).click();
  await expect(p.getByRole('button', { name: /^Su voz/ })).toContainText('Silenciada');
  await p.locator('.settings-tab', { hasText: 'General' }).click();
  await expect(p.getByRole('button', { name: /^Arranque y bandeja/ })).toContainText('Con Windows · cerrar: salir');
  refuse = true;
  await p.getByRole('switch', { name: 'Arrancar con Windows' }).click();
  await expect(p.locator('.bx-notice')).toContainText('no se pudo guardar');
  await expect(p.getByRole('switch', { name: 'Arrancar con Windows' })).toHaveAttribute('aria-checked', 'true');
});

test('ajustes: el idioma elegido lo guarda el host y la vista pasa a ese idioma; si no se guardó, se dice', async () => {
  h = await openView();
  let language = 'es', refuse = true;
  h.reply('/settings/general', () => ({ body: { language, languageInUse: language === 'auto' ? 'es' : language } }));
  h.reply('/settings/language', (c) => {
    if (refuse) return { status: 409, body: { error: 'language_not_saved' } };
    language = (c.body as { lang: string }).lang;
    return { body: { language } };
  });
  const p = h.page;
  await p.locator('.bx-gear').click();
  const pick = p.getByRole('radiogroup', { name: 'Idioma de la interfaz' });
  await expect(pick.getByRole('radio', { name: 'Español' })).toHaveAttribute('aria-checked', 'true');
  await pick.getByRole('radio', { name: 'English' }).click();
  await expect(p.locator('.bx-notice')).toContainText('no se pudo guardar');
  await expect(pick.getByRole('radio', { name: 'Español' })).toHaveAttribute('aria-checked', 'true');
  refuse = false;
  await pick.getByRole('radio', { name: 'English' }).click();
  const picked = p.getByRole('radiogroup', { name: 'Interface language' });
  await expect(picked.getByRole('radio', { name: 'English' })).toHaveAttribute('aria-checked', 'true');
  await expect(p.getByRole('button', { name: 'Done' })).toBeVisible();
  await expect(p.getByRole('button', { name: /^Language/ })).toContainText('English');
  // «Automático» is the host's to resolve: here its Windows is in Spanish
  await picked.getByRole('radio', { name: 'Automatic' }).click();
  await expect(pick.getByRole('radio', { name: 'Automático' })).toHaveAttribute('aria-checked', 'true');
  await expect.poll(() => h.calls.filter((c) => c.path === '/settings/language').map((c) => [c.method, c.body])).toEqual([['PUT', { lang: 'en' }], ['PUT', { lang: 'en' }], ['PUT', { lang: 'auto' }]]);
});

test('ajustes: el tema, el modo accesible, su tamaño y el alto contraste se ven al elegirlos y quedan para el próximo arranque', async () => {
  h = await openView();
  let mode = 'normal';
  h.reply('/accessibility', (c) => { if (c.method === 'PUT') mode = (c.body as { mode: string }).mode; return { body: { active: mode } }; });
  const p = h.page;
  const root = p.locator('html');
  const kept = (key: string) => p.evaluate((k) => localStorage.getItem(k), key);
  await p.locator('.bx-gear').click();
  await expect(root).not.toHaveClass(/(^| )lt( |$)/);
  await p.getByRole('button', { name: /^Apariencia/ }).click();
  await p.locator('.bxs-seg button', { hasText: 'Claro' }).click();
  await expect(root).toHaveClass(/(^| )lt( |$)/);
  await expect(p.getByRole('button', { name: /^Apariencia/ })).toContainText('Claro');
  expect(await kept('baxy.theme')).toBe('light');
  await p.locator('.bxs-seg button', { hasText: 'Oscuro' }).click();
  await expect(root).not.toHaveClass(/(^| )lt( |$)/);
  await p.locator('.settings-tab', { hasText: 'Accesibilidad' }).click();
  await p.getByRole('radio', { name: 'Accesible' }).click();
  await expect(root).toHaveClass(/(^| )a11y( |$)/);
  await expect(p.locator('.settings-body').getByRole('button', { name: /^Modo/ })).toContainText('Accesible');
  await p.getByRole('group', { name: 'Tamaño del texto' }).getByRole('button', { name: 'Muy grande' }).click();
  await expect(root).toHaveClass(/(^| )a11y-xl( |$)/);
  await p.getByRole('switch', { name: 'Alto contraste' }).click();
  await expect(root).toHaveClass(/(^| )hc( |$)/);
  expect([await kept('baxy.a11y.size'), await kept('baxy.a11y.contrast')]).toEqual(['xl', '1']);
  // back to Normal the size no longer applies, and the contrast, which is its own switch, stays
  await p.getByRole('radio', { name: 'Normal' }).click();
  await expect(root).not.toHaveClass(/a11y/);
  await expect(root).toHaveClass(/(^| )hc( |$)/);
  // the size and the contrast are this view's own; with each the host is told the mode again, and never another one
  const modes = () => h.calls.filter((c) => c.method === 'PUT' && c.path === '/accessibility').map((c) => (c.body as { mode: string }).mode);
  await expect.poll(() => modes().filter((m, i, all) => m !== all[i - 1])).toEqual(['accessible', 'normal']);
});

test('ventana: Minimizar y Cerrar piden cada uno lo suyo al host, una vez', async () => {
  h = await openView();
  const p = h.page;
  await p.evaluate(() => {
    const asked: string[] = [];
    const w = window as unknown as { pywebview: unknown; asked: string[] };
    w.asked = asked;
    w.pywebview = { api: {
      win_is_maximized: async () => false, win_toggle_maximize: async () => { asked.push('maximize'); return true; },
      win_minimize: async () => { asked.push('minimize'); return true; }, win_close: async () => { asked.push('close'); return true; },
      win_exit: async () => { asked.push('exit'); return true; },
    } };
  });
  const asked = () => p.evaluate(() => (window as unknown as { asked: string[] }).asked);
  await p.getByRole('button', { name: 'Minimizar' }).click();
  expect(await asked()).toEqual(['minimize']);
  await p.getByRole('button', { name: 'Cerrar BAXY' }).click();
  expect(await asked()).toEqual(['minimize', 'close']);
});

// the window's own commands (field-native-bridge.js), written down as they are asked
const windowAsks = async (p: Page) => {
  await p.evaluate(() => {
    const w = window as unknown as { pywebview: unknown; asked: string[] };
    w.asked = [];
    w.pywebview = { api: { win_is_maximized: async () => false, win_exit: async () => { w.asked.push('exit'); return true; } } };
  });
  return () => p.evaluate(() => (window as unknown as { asked: string[] }).asked);
};

test('avería: Reintentar pide otro arranque al host, y lo que el host rechazó se dice distinto de lo que no contestó', async () => {
  h = await openView();
  let answer: Reply = { status: 409, body: { ok: false, error: 'nothing_to_retry' } };
  h.reply('/engine/retry', () => answer);
  h.emit({ type: 'agent', built: true, ready: false, powered: true, failure: 'engine_unavailable' });
  const card = h.page.getByRole('alertdialog');
  const retry = card.getByRole('button', { name: 'Reintentar' });
  await retry.click();
  await expect(card).toContainText('No se pudo: vuelve a intentarlo.');
  // field-native-bridge.js: a request that timed out in the bridge answers 503, with no refusal of the host's
  answer = { status: 503, body: { error: 'Error: BAXY native request timed out: http' } };
  await retry.click();
  await expect(card).toContainText('BAXY no respondió: vuelve a intentarlo.');
  await expect(card).not.toContainText('No se pudo:');
  answer = { body: { ok: true } };
  await retry.click();
  await expect.poll(() => h.calls.filter((c) => c.path === '/engine/retry').map((c) => c.method)).toEqual(['POST', 'POST', 'POST']);
  // the card takes no press while it asks: once it does again the answer came, and it left nothing said
  await expect(retry).toBeEnabled();
  await expect(card).not.toContainText('BAXY no respondió');
  // the host's next state takes the card away
  h.emit({ type: 'agent', built: true, ready: true, powered: true });
  await expect(card).toHaveCount(0);
});

test('avería: datos que no se abren ofrecen un perfil nuevo y dicen si la carpeta no se apartó; Salir cierra BAXY; sin GPU sólo queda salir', async () => {
  h = await openView();
  let answer: Reply = { status: 409, body: { ok: false, error: 'profile_not_set_aside' } };
  h.reply('/profile/fresh', () => answer);
  const p = h.page;
  const asked = await windowAsks(p);
  h.emit({ type: 'agent', built: true, ready: false, powered: true, failure: 'profile_unreadable' });
  const card = p.getByRole('alertdialog');
  await expect(card).toContainText('Tus datos guardados no se pueden abrir');
  await expect(card).toContainText('el anterior no se borra, queda apartado en su carpeta con la fecha de hoy');
  const fresh = card.getByRole('button', { name: 'Empezar con un perfil nuevo' });
  await fresh.click();
  await expect(card).toContainText('No se pudo apartar la carpeta: puede que otra ventana la tenga abierta. Ciérrala y vuelve a intentarlo.');
  answer = { body: { ok: true, setAside: 'apartado' } };
  await fresh.click();
  await expect.poll(() => h.calls.filter((c) => c.path === '/profile/fresh').map((c) => c.method)).toEqual(['POST', 'POST']);
  await expect(fresh).toBeEnabled();
  await expect(card).not.toContainText('No se pudo apartar');
  expect(h.calls.filter((c) => c.path === '/engine/retry')).toEqual([]);
  expect(await asked()).toEqual([]);
  await card.getByRole('button', { name: 'Salir' }).click();
  expect(await asked()).toEqual(['exit']);

  h.emit({ type: 'agent', built: true, ready: false, powered: true, failure: 'no_supported_gpu' });
  await expect(card).toContainText('BAXY necesita una GPU compatible');
  await expect(card.getByRole('button')).toHaveText(['Salir']);
});

test('personalización: cada interruptor del overlay envía lo suyo, la opacidad se cambia con el teclado y se ve lo que el host guardó', async () => {
  h = await openView();
  let host = { on: true, corner: 'br', size: 'm', opacity: 78, hideSeconds: 8, notFullscreen: true, answer: false };
  h.reply('/settings/overlay', (c) => { if (c.method === 'PUT') host = { ...host, ...(c.body as object) }; return { body: host }; });
  const p = h.page;
  await p.locator('.bx-gear').click();
  await p.locator('.settings-tab', { hasText: 'Personalización' }).click();
  await p.getByRole('button', { name: /^Overlay mientras trabaja/ }).click();
  const puts = () => h.calls.filter((c) => c.method === 'PUT' && c.path === '/settings/overlay').map((c) => c.body);
  const sw = (name: string) => p.getByRole('switch', { name });
  await sw('Mostrar el overlay').click();
  await expect(sw('Mostrar el overlay')).toHaveAttribute('aria-checked', 'false');
  await sw('No mostrar en pantalla completa').click();
  await expect(sw('No mostrar en pantalla completa')).toHaveAttribute('aria-checked', 'false');
  await sw('Responder confirmaciones desde el overlay').click();
  await expect(sw('Responder confirmaciones desde el overlay')).toHaveAttribute('aria-checked', 'true');
  await expect.poll(() => puts()).toEqual([{ on: false }, { notFullscreen: false }, { answer: true }]);

  const opacity = p.getByRole('slider', { name: 'Opacidad del overlay' });
  const said = p.locator('.bxs-row', { has: opacity }).locator('.h');
  await expect(said).toHaveText('78 %');
  await opacity.focus();
  await p.keyboard.press('ArrowRight');
  await expect(said).toHaveText('80 %');
  await expect.poll(puts).toContainEqual({ opacity: 80 });
  // what shows is what the host kept, not what was pressed
  h.reply('/settings/overlay', () => ({ body: { ...host, opacity: 90, on: true } }));
  await p.keyboard.press('ArrowRight');
  await expect(said).toHaveText('90 %');
  await expect(sw('Mostrar el overlay')).toHaveAttribute('aria-checked', 'true');
});

test('personalización: lo que el host no guardó del overlay no queda mostrado como puesto, y se dice', async () => {
  h = await openView();
  let host = { on: true, corner: 'br', size: 'm', opacity: 78, hideSeconds: 8, notFullscreen: true, answer: false };
  // field-native-bridge.js: a request that timed out in the bridge answers 503; the host may or may not have taken it
  let answer: 'kept' | 'lost' | 'late' = 'lost';
  h.reply('/settings/overlay', (c) => {
    if (c.method !== 'PUT') return { body: host };
    if (answer === 'lost') return { status: 503, body: { error: 'Error: BAXY native request timed out: http' } };
    host = { ...host, ...(c.body as object) };
    return answer === 'late' ? { status: 503, body: { error: 'Error: BAXY native request timed out: http' } } : { body: host };
  });
  const p = h.page;
  await p.locator('.bx-gear').click();
  await p.locator('.settings-tab', { hasText: 'Personalización' }).click();
  await p.getByRole('button', { name: /^Overlay mientras trabaja/ }).click();
  const shown = p.getByRole('switch', { name: 'Mostrar el overlay' });
  const unsaved = p.getByRole('alert').filter({ hasText: 'No se pudo guardar' });
  await expect(shown).toHaveAttribute('aria-checked', 'true');
  await shown.click();
  await expect(shown).toHaveAttribute('aria-checked', 'true');
  await expect(unsaved).toBeVisible();
  // the same with the slider: the number goes back to the one the host has
  const opacity = p.getByRole('slider', { name: 'Opacidad del overlay' });
  const said = p.locator('.bxs-row', { has: opacity }).locator('.h');
  await opacity.focus();
  await p.keyboard.press('ArrowRight');
  await expect(unsaved).toBeVisible();
  await expect(said).toHaveText('78 %');
  await expect(opacity).toHaveValue('78');
  // no answer, but the host did take it: read again, it has it, and nothing is said as not saved
  answer = 'late';
  await p.getByRole('radio', { name: 'Arriba a la izquierda' }).click();
  await expect(unsaved).toHaveCount(0);
  await expect(p.getByRole('radio', { name: 'Arriba a la izquierda' })).toHaveAttribute('aria-checked', 'true');
  answer = 'lost';
  await shown.click();
  await expect(shown).toHaveAttribute('aria-checked', 'true');
  await expect(unsaved).toBeVisible();
  // the next one that is kept takes the note away
  answer = 'kept';
  await shown.click();
  await expect(shown).toHaveAttribute('aria-checked', 'false');
  await expect(unsaved).toHaveCount(0);
});

// VIS1 (revisión ciega): with no answer to the change nor to the reading after it, whether it was saved is not known, and
// «No se pudo guardar» said something nobody had told the view.
test('personalización: si BAXY no contesta ni al cambio del overlay ni al volver a leer, se dice que no contestó, no que no se guardó', async () => {
  h = await openView();
  let host = { on: true, corner: 'br', size: 'm', opacity: 78, hideSeconds: 8, notFullscreen: true, answer: false };
  const silent = { status: 503, body: { error: 'Error: BAXY native request timed out: http' } };
  let answers = true;
  h.reply('/settings/overlay', (c) => {
    if (!answers) return silent;
    if (c.method === 'PUT') host = { ...host, ...(c.body as object) };
    return { body: host };
  });
  const p = h.page;
  await p.locator('.bx-gear').click();
  await p.locator('.settings-tab', { hasText: 'Personalización' }).click();
  await p.getByRole('button', { name: /^Overlay mientras trabaja/ }).click();
  const shown = p.getByRole('switch', { name: 'Mostrar el overlay' });
  await expect(shown).toHaveAttribute('aria-checked', 'true');
  answers = false;
  await shown.click();
  const note = p.locator('.bx-fold-b', { has: shown }).getByRole('alert');
  await expect(note).toHaveText('BAXY no contestó: no se sabe si se guardó. Se muestra lo último que dijo.');
  await expect(shown).toHaveAttribute('aria-checked', 'true');
  // it answers again: the change is kept and nothing is left said
  answers = true;
  await shown.click();
  await expect(shown).toHaveAttribute('aria-checked', 'false');
  await expect(note).toHaveCount(0);
});

// VIS1 (segunda revisión ciega): a change the host refused is not one it did not answer, whatever the reading after it does.
test('personalización: un cambio del overlay que BAXY rechazó se dice no guardado, aunque después no conteste', async () => {
  h = await openView();
  const host = { on: true, corner: 'br', size: 'm', opacity: 78, hideSeconds: 8, notFullscreen: true, answer: false };
  let refuses = false;
  h.reply('/settings/overlay', (c) => {
    if (!refuses) return { body: host };
    // FieldProductChannel: what ApplyOverlay does not take is refused whole; then the bridge's own answer for no answer
    return c.method === 'PUT' ? { status: 400, body: { ok: false, error: 'invalid_overlay' } } : { status: 503, body: { error: 'Error: BAXY native request timed out: http' } };
  });
  const p = h.page;
  await p.locator('.bx-gear').click();
  await p.locator('.settings-tab', { hasText: 'Personalización' }).click();
  await p.getByRole('button', { name: /^Overlay mientras trabaja/ }).click();
  const shown = p.getByRole('switch', { name: 'Mostrar el overlay' });
  await expect(shown).toHaveAttribute('aria-checked', 'true');
  refuses = true;
  await shown.click();
  await expect(p.locator('.bx-fold-b', { has: shown }).getByRole('alert')).toHaveText('No se pudo guardar: se muestra lo que BAXY tiene.');
  await expect(shown).toHaveAttribute('aria-checked', 'true');
});

test('modelo: «Detener» para la descarga desde arriba de la pestaña y desde su sección, una vez cada una', async () => {
  h = await openView();
  const name = 'hf.co/a/b-GGUF:Q4_K_M';
  let open = { ...OPEN_IDLE, pulling: name as string | null, pullTotal: 2_000_000_000, pullDone: 800_000_000, pullBytesPerSecond: 10_000_000 as number | null, pullSecondsLeft: 120 as number | null };
  const body = () => ({ ...EXTERNAL, provider: 'local', model: '', url: 'http://127.0.0.1:11434', ceilingHolds: false, open });
  h.reply('/settings/external-model', () => ({ body: body() }));
  h.reply('/settings/external-model/models', () => ({ body: { models: [] } }));
  h.reply('/settings/external-model/cancel', () => { open = { ...open, pulling: null, pullStopped: name, pullBytesPerSecond: null, pullSecondsLeft: null }; return { body: body() }; });
  h.reply('/settings/external-model/pull', () => { open = { ...open, pulling: name, pullStopped: null }; return { body: body() }; });
  const p = h.page;
  await p.locator('.bx-gear').click();
  await p.locator('.settings-tab', { hasText: 'Modelo' }).click();
  const bar = p.getByRole('group', { name: 'Descarga de a/b-GGUF:Q4_K_M' });
  const cancels = () => h.calls.filter((c) => c.path === '/settings/external-model/cancel').map((c) => c.method);
  await expect(bar).toContainText('Descargando a/b-GGUF:Q4_K_M');
  await bar.getByRole('button', { name: 'Detener' }).click();
  // stopped, it is no longer said as downloading above; its own section keeps it, to go on from there
  await expect(bar).toHaveCount(0);
  expect(cancels()).toEqual(['POST']);
  await pickWhere(p, /Local/);
  await expect(bar).toContainText('Descarga detenida: a/b-GGUF:Q4_K_M');
  await expect(bar.getByRole('button', { name: 'Detener' })).toHaveCount(0);
  await bar.getByRole('button', { name: 'Reanudar' }).click();
  await expect(bar).toContainText('Descargando a/b-GGUF:Q4_K_M');
  await bar.getByRole('button', { name: 'Detener' }).click();
  await expect(bar).toContainText('Descarga detenida: a/b-GGUF:Q4_K_M');
  expect(cancels()).toEqual(['POST', 'POST']);
});

test('otro modelo local: «Instalar Ollama» lo pide una vez, su descarga se ve con su barra y se puede detener; lo que no empezó se dice', async () => {
  h = await openView();
  let open = { ...OPEN_IDLE, ollamaOwn: false, ollamaRunning: null as string | null, ollamaInstalling: false, ollamaBytesPerSecond: null as number | null, ollamaSecondsLeft: null as number | null };
  let refuse = true;
  const body = () => ({ ...EXTERNAL, provider: 'local', model: '', url: 'http://127.0.0.1:11434', ceilingHolds: false, open });
  h.reply('/settings/external-model', () => ({ body: body() }));
  h.reply('/settings/external-model/models', () => ({ body: { models: [], ollama: 'missing' } }));
  h.reply('/settings/external-model/ollama', () => {
    if (refuse) return { status: 409, body: { ok: false, error: 'open_models_no_space' } };
    open = { ...open, ollamaInstalling: true, ollamaDownloadedBytes: 404_000_000, ollamaBytesPerSecond: 12_000_000, ollamaSecondsLeft: 101 };
    return { body: body() };
  });
  h.reply('/settings/external-model/cancel', () => { open = { ...open, ollamaInstalling: false, ollamaDownloadedBytes: 0 }; return { body: body() }; });
  const p = h.page;
  await p.locator('.bx-gear').click();
  await p.locator('.settings-tab', { hasText: 'Modelo' }).click();
  await pickWhere(p, /Local/);
  const install = p.getByRole('button', { name: 'Instalar Ollama' });
  await install.click();
  // INT21: with MOD1 (REV_VISTA V-10) the refusal says its own cause, not «ya hay una descarga en curso o falta espacio».
  await expect(p.getByRole('alert').filter({ hasText: 'No se pudo empezar' })).toHaveText('No se pudo empezar: falta espacio en el disco');
  refuse = false;
  await install.click();
  const bar = p.getByRole('group', { name: 'Descarga de Ollama 0.40.15' });
  await expect(bar).toContainText('Descargando Ollama 0.40.15');
  await expect(bar).toContainText('25 %');
  await expect(bar).toContainText('0,38 GB de 1,50 GB · 11,4 MB/s · quedan 2 min'); // MOD1's bar: 12.000.000 B/s in MiB
  await expect(install).toHaveCount(0);
  await bar.getByRole('button', { name: 'Detener' }).click();
  await expect(bar).toHaveCount(0);
  await expect(install).toBeVisible();
  await expect.poll(() => h.calls.filter((c) => c.path === '/settings/external-model/ollama').map((c) => c.method)).toEqual(['POST', 'POST']);
  await expect.poll(() => h.calls.filter((c) => c.path === '/settings/external-model/cancel').map((c) => c.method)).toEqual(['POST']);
});

test('modelo ajustado: su descarga se detiene con «Detener», y Cancelar en el aviso no baja nada', async () => {
  h = await openView();
  let host = { ...TUNED };
  h.reply('/settings/tuned-model/install', () => { host = { ...host, downloading: true, downloadedBytes: 1_200_000_000 }; return { body: host }; });
  h.reply('/settings/tuned-model', (c) => {
    if (c.method === 'PUT' && (c.body as { cancel?: boolean }).cancel) host = { ...host, downloading: false };
    return { body: host };
  });
  const p = h.page;
  await p.locator('.bx-gear').click();
  await p.locator('.settings-tab', { hasText: 'Modelo' }).click();
  await pickWhere(p, /Ajustado/);
  await p.getByRole('button', { name: 'Instalar', exact: true }).click();
  const notice = p.getByRole('dialog', { name: 'Antes de descargar' });
  await notice.getByRole('button', { name: 'Cancelar' }).click();
  await expect(notice).toHaveCount(0);
  expect(h.calls.filter((c) => c.path === '/settings/tuned-model/install')).toEqual([]);
  await p.getByRole('button', { name: 'Instalar', exact: true }).click();
  await notice.getByRole('button', { name: 'Descargar' }).click();
  // INT21: with MOD1 (D6) the download is the bar of every other download here; it said «Llevo 1,1 GB de 2,6 GB».
  const bar = p.getByRole('group', { name: 'Descarga de BAXY ajustado' });
  await expect(bar).toContainText('1,12 GB de 2,55 GB');
  await bar.getByRole('button', { name: 'Detener' }).click();
  // stopped, what came down stays and the button goes on from there
  await expect(p.getByText('Bajé 1,1 GB de 2,6 GB: sigue desde ahí')).toBeVisible();
  await expect(p.getByRole('button', { name: 'Seguir instalando' })).toBeVisible();
  await expect.poll(() => h.calls.filter((c) => c.method === 'PUT' && c.path === '/settings/tuned-model').map((c) => c.body)).toEqual([{ cancel: true }]);
  await expect.poll(() => h.calls.filter((c) => c.path === '/settings/tuned-model/install')).toHaveLength(1);
});

test('modelo: Cancelar al desinstalar o al quitar el ajustado no borra nada', async () => {
  h = await openView();
  const ext = { ...EXTERNAL, provider: 'local', model: 'llama3.2:3b', url: 'http://127.0.0.1:11434', enabled: true, active: true, activeModel: 'llama3.2:3b', activeLocal: true, ceilingHolds: false };
  h.reply('/settings/external-model', () => ({ body: ext }));
  h.reply('/settings/external-model/models', () => ({ body: { models: [
    { id: 'llama3.2:3b', label: 'llama3.2:3b', fits: true, vision: false, bytes: 2_019_000_000 },
    { id: 'gpt-oss:20b', label: 'gpt-oss:20b', fits: true, vision: false, bytes: 11_600_000_000 }] } }));
  h.reply('/settings/tuned-model', () => ({ body: { ...TUNED, installed: true } }));
  const p = h.page;
  await p.locator('.bx-gear').click();
  await p.locator('.settings-tab', { hasText: 'Modelo' }).click();
  const list = p.locator('.bx-installed');
  await list.locator('.bx-irow', { hasText: 'gpt-oss:20b' }).getByRole('button', { name: 'Desinstalar' }).click();
  const ask = p.getByRole('dialog', { name: 'Desinstalar gpt-oss:20b' });
  await ask.getByRole('button', { name: 'Cancelar' }).click();
  await expect(ask).toHaveCount(0);
  await expect(list.locator('.bx-irow', { hasText: 'gpt-oss:20b' })).toHaveCount(1);
  // the tuned one says what it frees, and its Cancel deletes nothing either
  await list.locator('.bx-irow', { hasText: 'BAXY ajustado' }).getByRole('button', { name: 'Desinstalar' }).click();
  const askTuned = p.getByRole('dialog', { name: 'Desinstalar BAXY ajustado' });
  await expect(askTuned).toContainText('Se borra de este PC y libera 2,6 GB.');
  await askTuned.getByRole('button', { name: 'Cancelar' }).click();
  await pickWhere(p, /Ajustado/);
  await p.getByRole('button', { name: 'Quitar del PC' }).click();
  await p.locator('.bxs-ask').getByRole('button', { name: 'Cancelar' }).click();
  await expect(p.locator('.bxs-ask')).toHaveCount(0);
  await p.waitForTimeout(300);
  expect(h.calls.filter((c) => c.path === '/settings/external-model/remove')).toEqual([]);
  // choosing «Ajustado» with it installed is its own request; nothing asked to remove it
  await expect.poll(() => h.calls.filter((c) => c.method === 'PUT' && c.path === '/settings/tuned-model').map((c) => c.body)).toEqual([{ use: true }]);
});

test('modelo: el contexto de BAXY se elige de la lista, vuelve a Automático, y el que el host rechaza se dice sin cambiar la elección', async () => {
  h = await openView();
  const gib = 2 ** 30;
  const options = [
    { context: 61440, vramBytes: 4.4 * gib, vision: true, slower: false, room: 8770, fits: true },
    { context: 77824, vramBytes: 5.03 * gib, vision: true, slower: false, room: 25154, fits: true },
    { context: 131072, vramBytes: 6.4 * gib, vision: false, slower: false, room: 78402, fits: true },
  ];
  let host = { chosen: null as number | null, automatic: 77824, prefixTokens: 49086, minimum: 52670, cardBytes: 8 * gib, cardKnown: true, options, switching: false };
  let refuse: string | null = null;
  h.reply('/settings/local-context', (c) => {
    if (c.method !== 'PUT') return { body: host };
    if (refuse) return { status: 409, body: { ok: false, error: refuse } };
    host = { ...host, chosen: (c.body as { context: number | null }).context };
    return { body: host };
  });
  const p = h.page;
  await p.locator('.bx-gear').click();
  await p.locator('.settings-tab', { hasText: 'Modelo' }).click();
  const select = p.getByRole('combobox', { name: 'Contexto' });
  const row = p.locator('.bxs-row', { has: select });
  const puts = () => h.calls.filter((c) => c.method === 'PUT' && c.path === '/settings/local-context').map((c) => c.body);
  await expect(select).toHaveValue('');
  await expect(row).toContainText('Deja unos 25.154 tokens para la conversación');
  await select.selectOption('131072');
  await expect(select).toHaveValue('131072');
  await expect(row).toContainText('Deja unos 78.402 tokens para la conversación');
  await expect(p.getByRole('button', { name: /^Contexto/ })).toContainText('131.072 tokens');
  refuse = 'local_context_too_small';
  await select.selectOption('61440');
  await expect(row).toContainText('No deja sitio para sus instrucciones y herramientas');
  await expect(select).toHaveValue('131072');
  refuse = null;
  await select.selectOption('');
  await expect(select).toHaveValue('');
  await expect(p.getByRole('button', { name: /^Contexto/ })).toContainText('Automático');
  await expect.poll(() => puts()).toEqual([{ context: 131072 }, { context: 61440 }, { context: null }]);
});

test('modelo por API: «Borrar» quita la clave guardada, y sin lista el modelo se escribe a mano y se guarda al salir de la caja', async () => {
  h = await openView();
  let host = { ...EXTERNAL, hasKey: true };
  h.reply('/settings/external-model', (c) => {
    if (c.method !== 'PUT') return { body: host };
    const body = c.body as { forgetKey?: boolean; model?: string };
    host = { ...host, hasKey: body.forgetKey ? false : host.hasKey, model: body.model ?? host.model };
    return { body: host };
  });
  h.reply('/settings/external-model/models', () => ({ body: { error: 'sin_red' } }));
  const p = h.page;
  await p.locator('.bx-gear').click();
  await p.locator('.settings-tab', { hasText: 'Modelo' }).click();
  await pickWhere(p, /API/);
  const puts = () => h.calls.filter((c) => c.method === 'PUT' && c.path === '/settings/external-model').map((c) => c.body);
  await expect(p.getByText('Guardada y protegida en este PC. No se vuelve a mostrar')).toBeVisible();
  const model = p.getByRole('textbox', { name: 'Modelo', exact: true });
  await expect(model).toHaveValue('claude-opus-5-5');
  // leaving the box as it was writes nothing
  await model.focus();
  await p.getByLabel('Clave de la API').focus();
  await model.fill('claude-sonnet-5-5');
  await p.getByLabel('Clave de la API').focus();
  // INT21: with MOD1 (V-01) a model's name goes with its provider: alone, it went to the place chosen before.
  await expect.poll(puts).toEqual([{ provider: 'anthropic', model: 'claude-sonnet-5-5' }]);
  await p.getByRole('button', { name: 'Borrar', exact: true }).click();
  await expect(p.getByText('Se guarda protegida en este PC', { exact: true })).toBeVisible();
  await expect(p.getByRole('button', { name: 'Borrar', exact: true })).toHaveCount(0);
  await expect.poll(() => puts()).toEqual([{ provider: 'anthropic', model: 'claude-sonnet-5-5' }, { forgetKey: true }]);
});

test('ajustes: el buscador deja las secciones que tienen ese ajuste, dice cuando no hay ninguna, y Extras lleva a Modelo', async () => {
  h = await openView();
  h.reply('/settings/tuned-model', () => ({ body: { ...TUNED } }));
  const p = h.page;
  await p.locator('.bx-gear').click();
  const find = p.getByRole('searchbox', { name: 'Buscar un ajuste' });
  const tabs = p.locator('.settings-tab');
  await expect(tabs).toHaveCount(10);
  // by a word of one of its settings, not only by its name; capitals and spaces around are the person's
  await find.fill('  Overlay ');
  await expect(tabs).toHaveText(['Personalización']);
  await find.fill('silenciar');
  await expect(tabs).toHaveText(['Comportamiento', 'Voz']);
  await find.fill('zzz');
  await expect(tabs).toHaveCount(0);
  await expect(p.getByRole('status').filter({ hasText: 'Ningún ajuste' })).toHaveText('Ningún ajuste con esas palabras');
  await find.fill('ajustado');
  await expect(tabs).toHaveText(['Modelo', 'Extras no oficiales']);
  await tabs.filter({ hasText: 'Extras no oficiales' }).click();
  await p.getByRole('button', { name: 'Ir a Modelo' }).click();
  await expect(tabs.filter({ hasText: 'Modelo' })).toHaveAttribute('aria-selected', 'true');
  await expect(p.getByRole('radiogroup', { name: 'Dónde piensa BAXY' })).toBeVisible();
  await find.fill('');
  await expect(tabs).toHaveCount(10);
});

test('personalización: el tamaño de tus mensajes y los subtítulos se eligen y se ven, y «Volver a lo de siempre» lo deshace todo', async () => {
  h = await openView({ items: [{ who: 'you', id: 'y1', ts: '12:00', text: 'abre la calculadora' }] });
  const p = h.page;
  h.emit({ type: 'item', item: { who: 'baxy', id: 'b1', ts: '12:00', text: 'Listo, ya está abierta.', steps: [] } });
  await expect(p.locator('.bx-sub')).toContainText('Listo, ya está abierta.');
  const mine = () => p.locator('.bx-c4-you').evaluate((e) => parseFloat(getComputedStyle(e).fontSize));
  const before = await mine();
  await p.locator('.bx-gear').click();
  await p.locator('.settings-tab', { hasText: 'Personalización' }).click();
  await p.getByRole('group', { name: 'Tamaño de tus mensajes' }).getByRole('button', { name: 'Normal' }).click();
  await p.getByRole('switch', { name: 'Subtítulos bajo la cara' }).click();
  await p.getByRole('group', { name: 'Borde de color' }).getByRole('button', { name: 'Apagado' }).click();
  expect(await mine()).toBeGreaterThan(before + 1);
  await expect(p.locator('.bx-sub')).toHaveCount(0);
  expect(await p.evaluate(() => JSON.parse(localStorage.getItem('baxy.look') ?? '{}'))).toMatchObject({ you: 'm', captions: false, ring: 'off' });
  await p.getByRole('button', { name: 'Volver a lo de siempre' }).click();
  await expect(p.getByRole('switch', { name: 'Subtítulos bajo la cara' })).toHaveAttribute('aria-checked', 'true');
  await expect(p.getByRole('group', { name: 'Tamaño de tus mensajes' }).getByRole('button', { name: 'Pequeño' })).toHaveAttribute('aria-pressed', 'true');
  expect(await mine()).toBe(before);
  await expect(p.locator('.bx-sub')).toContainText('Listo, ya está abierta.');
  expect(await p.evaluate(() => JSON.parse(localStorage.getItem('baxy.look') ?? '{}'))).toMatchObject({ reply: 'm', you: 's', chat: 'n', steps: false, captions: true, gauges: true, ring: 'on', ringSpeed: 'normal' });
});

test('capacidades: el buscador deja las acciones que llevan esas letras y esconde los grupos sin ninguna; si no se pudo leer, se dice', async () => {
  h = await openView();
  let answer: Reply = { body: { total: 4, groups: [
    { name: 'Apps', items: [{ name: 'app.open', title: 'Abrir una app', confirm: 'never' }, { name: 'app.close', title: 'Cerrar una app', confirm: 'sometimes' }] },
    { name: 'Archivos', items: [{ name: 'files.delete', title: 'Borrar un archivo', confirm: 'always' }, { name: 'files.open', title: 'Abrir un archivo', confirm: 'never' }] }] } };
  h.reply('/catalog', () => answer);
  const p = h.page;
  await p.getByRole('button', { name: /Capacidades/ }).click();
  const panel = p.getByRole('dialog');
  const shown = panel.locator('.bx-tl > span');
  await expect(shown).toHaveCount(4);
  await expect(panel.locator('.bx-tnote')).toContainText('4 acciones del catálogo');
  // the one the kernel always confirms carries its mark
  await expect(panel.locator('.bx-tl > span.cf')).toHaveText('Borrar un archivo!');
  const find = panel.getByRole('textbox', { name: 'Buscar una acción' });
  await find.fill(' ABRIR ');
  await expect(shown).toHaveText(['Abrir una app', 'Abrir un archivo']);
  await find.fill('borr');
  await expect(shown).toHaveText(['Borrar un archivo!']);
  await expect(panel.locator('.panel-sec-head')).toHaveText(['Archivos2']);
  await find.fill('');
  await expect(shown).toHaveCount(4);
  await p.keyboard.press('Escape');
  answer = { status: 503, body: { error: 'catalog_unavailable' } };
  await p.getByRole('button', { name: /Capacidades/ }).click();
  await expect(p.getByRole('dialog').getByRole('status')).toHaveText('No se pudo leer el catálogo.');
  await expect(p.getByRole('dialog').locator('.bx-tnote')).toContainText('—');
});

test('propuestas: cada situación se apaga por separado, silenciar se elige y se quita con el mismo botón, y lo que no se guardó se dice', async () => {
  h = await openView();
  let host = { quietUntil: null as number | null, quiet: null as string | null, ctx: { game: true, call: true, video: true } };
  let refuse = false;
  h.reply('/proposals', (c) => {
    if (c.method !== 'PUT') return { body: host };
    if (refuse) return { status: 503, body: { error: 'Error: BAXY native request timed out: http' } };
    const body = c.body as { quiet?: string | null; ctx?: typeof host.ctx };
    host = { ...host, ...body, quietUntil: body.quiet === undefined ? host.quietUntil : body.quiet ? new Date(2026, 10, 9, 17, 5).getTime() : null };
    return { body: host };
  });
  const p = h.page;
  await p.locator('.bx-gear').click();
  await p.locator('.settings-tab', { hasText: 'Comportamiento' }).click();
  const puts = () => h.calls.filter((c) => c.method === 'PUT' && c.path === '/proposals').map((c) => c.body);
  const quietRow = p.locator('.bxs-row', { hasText: 'Silenciar todas las propuestas' });
  await expect(quietRow.locator('.h')).toHaveText('Activas');
  await p.getByRole('switch', { name: 'Llamadas' }).click();
  await expect(p.getByRole('switch', { name: 'Llamadas' })).toHaveAttribute('aria-checked', 'false');
  await expect(p.getByRole('switch', { name: 'Juegos' })).toHaveAttribute('aria-checked', 'true');
  await quietRow.getByRole('button', { name: '30 min' }).click();
  await expect(quietRow.locator('.h')).toHaveText(/^En silencio hasta las \d{1,2}:05/);
  await expect(quietRow.getByRole('button', { name: '30 min' })).toHaveAttribute('aria-pressed', 'true');
  // the same button again turns them back on
  await quietRow.getByRole('button', { name: '30 min' }).click();
  await expect(quietRow.locator('.h')).toHaveText('Activas');
  await expect.poll(() => puts()).toEqual([{ ctx: { game: true, call: false, video: true } }, { quiet: '30m' }, { quiet: null }]);
  refuse = true;
  await p.getByRole('switch', { name: 'Juegos' }).click();
  await expect(p.locator('.bx-notice')).toContainText('no se pudo guardar');
  await expect(p.getByRole('switch', { name: 'Juegos' })).toHaveAttribute('aria-checked', 'true');
});

test('sesiones: salir de la caja al renombrar guarda el nombre una vez, vacío no renombra, y lo que no se renombró se dice', async () => {
  h = await openView();
  let answer: Reply = { body: { ok: true } };
  h.reply('/sessions/rename', () => answer);
  const input = await renaming();
  const panel = h.page.locator('.panel', { hasText: 'Historial' });
  await panel.locator('.panel-title').click();
  await expect(input).toHaveCount(0);
  await expect.poll(renames).toEqual([{ id: 's2', title: 'Compras' }]);
  await panel.locator('.bx-mem-row', { hasText: 'Ayer' }).locator('.bx-lnk').click();
  await input.fill('   ');
  await panel.locator('.panel-title').click();
  await expect(input).toHaveCount(0);
  answer = { status: 409, body: { ok: false, error: 'session_not_found' } };
  await panel.locator('.bx-mem-row', { hasText: 'Ayer' }).locator('.bx-lnk').click();
  await input.fill('Viaje');
  await panel.locator('.panel-title').click();
  await expect(panel.getByRole('status')).toHaveText('No se pudo renombrar.');
  expect(renames()).toEqual([{ id: 's2', title: 'Compras' }, { id: 's2', title: 'Viaje' }]);
});

test('el botón de enviar manda lo escrito una vez, como Enter, y sólo aparece con algo escrito', async () => {
  h = await openView();
  const sendButton = h.page.getByRole('button', { name: 'Enviar' });
  await expect(sendButton).toHaveClass(/hide/);
  await box().fill('abre la calculadora');
  await expect(sendButton).not.toHaveClass(/hide/);
  await sendButton.click();
  await expect.poll(() => h.calls.filter((c) => c.path === '/turn').map((c) => c.body)).toEqual([{ text: 'abre la calculadora' }]);
  await expect(box()).toHaveValue('');
  await expect(sendButton).toHaveClass(/hide/);
});

// VIS1, tanda 5: what the person touches and no spec without the App ran (the chat's fold was only in controls.spec.ts,
// which needs the App).
const reply = (id: string, text: string) => ({ who: 'baxy', id, ts: '12:00', text, steps: [] });

test('conversación: se pliega y se abre con su botón; plegada, una respuesta nueva queda marcada sin leer hasta abrirla', async () => {
  h = await openView({ items: [reply('b1', 'Listo.')] });
  const p = h.page;
  const folded = p.locator('.bx2.chat-off');
  const show = p.locator('button[title="Mostrar conversación"]');
  await expect(show).toHaveCount(0);
  await p.locator('button[title="Ocultar conversación"]').click();
  await expect(folded).toHaveCount(1);
  // what was already there was seen: nothing is unread
  await expect(show).toHaveAttribute('aria-label', 'Mostrar conversación');
  await expect(show.locator('.dot')).toHaveCount(0);
  h.emit({ type: 'item', item: reply('b2', 'Son las cinco.') });
  await expect(show).toHaveAttribute('aria-label', 'Mostrar conversación · hay una respuesta sin leer');
  await expect(show.locator('.dot')).toHaveCount(1);
  await expect(folded).toHaveCount(1);
  await show.click();
  await expect(folded).toHaveCount(0);
  await expect(p.locator('.bx-chat4')).toContainText('Son las cinco.');
  // opened, it was read: folding again marks nothing
  await p.locator('button[title="Ocultar conversación"]').click();
  await expect(show).toHaveAttribute('aria-label', 'Mostrar conversación');
  await expect(show.locator('.dot')).toHaveCount(0);
});

test('conversación: plegada, una tarjeta que espera tu sí la abre sola; si la pliegas con ella, se queda plegada hasta la siguiente', async () => {
  h = await openView({ items: [reply('b1', 'Listo.')] });
  const p = h.page;
  const folded = p.locator('.bx2.chat-off');
  await p.locator('button[title="Ocultar conversación"]').click();
  await expect(folded).toHaveCount(1);
  h.emit({ type: 'item', item: card('c1') });
  await expect(folded).toHaveCount(0);
  await expect(p.locator('.bx-card.s-pending')).toHaveCount(1);
  await p.locator('button[title="Ocultar conversación"]').click();
  await expect(folded).toHaveCount(1);
  await p.waitForTimeout(300);
  await expect(folded).toHaveCount(1);
  h.emit({ type: 'item', item: card('c2', { title: 'Borrar fotos.zip' }) });
  await expect(folded).toHaveCount(0);
  await expect(p.locator('.bx-card.s-pending', { hasText: 'Borrar fotos.zip' })).toHaveCount(1);
});

test('modelo: «Usar» en cada fila de Modelos en este PC pone ese modelo, y sólo ese queda «En uso»', async () => {
  h = await openView();
  // like the host, one model at a time (FieldProductChannel, PUT /settings/tuned-model: KeepOneModel)
  let ext = { ...EXTERNAL, provider: 'local', model: 'llama3.2:3b', url: 'http://127.0.0.1:11434', enabled: true, active: true, activeModel: 'llama3.2:3b' as string | null, activeLocal: true, ceilingHolds: false };
  let tuned = { ...TUNED, installed: true };
  // the first one chosen is still being loaded by Ollama while the test looks: chosen, not yet the one answering
  let loading = true;
  h.reply('/settings/external-model', (c) => {
    if (c.method === 'PUT') {
      ext = { ...ext, ...(c.body as object) };
      ext = { ...ext, active: ext.enabled && !loading, activeModel: ext.enabled && !loading ? ext.model : null };
      if (ext.enabled) tuned = { ...tuned, use: false, active: false };
    }
    return { body: ext };
  });
  h.reply('/settings/tuned-model', (c) => {
    if (c.method === 'PUT') {
      tuned = { ...tuned, ...(c.body as object) };
      tuned = { ...tuned, active: tuned.use };
      if (tuned.use) ext = { ...ext, enabled: false, active: false, activeModel: null };
    }
    return { body: tuned };
  });
  const big = 'necesita unos 48 GB de memoria y este PC tiene 16';
  h.reply('/settings/external-model/models', () => ({ body: { models: [
    { id: 'llama3.2:3b', label: 'llama3.2:3b', fits: true, vision: false, bytes: 2_019_000_000 },
    { id: 'gpt-oss:20b', label: 'gpt-oss:20b', fits: true, vision: false, bytes: 11_600_000_000 },
    { id: 'enorme:70b', label: 'enorme:70b', fits: false, why: big, vision: false, bytes: 42_000_000_000 }] } }));
  const p = h.page;
  await p.locator('.bx-gear').click();
  await p.locator('.settings-tab', { hasText: 'Modelo' }).click();
  const row = (text: string) => p.locator('.bx-installed .bx-irow', { hasText: text });
  const use = (text: string) => row(text).getByRole('button', { name: 'Usar', exact: true });
  const inUse = p.locator('.bx-installed .bx-irow', { has: p.locator('.live') });
  const puts = (path: string) => h.calls.filter((c) => c.method === 'PUT' && c.path === path).map((c) => c.body);
  await expect(inUse).toHaveCount(1);
  await expect(inUse).toContainText('llama3.2:3b');
  await expect(use('llama3.2:3b')).toHaveCount(0);
  // what does not fit can't be put, and its row says why
  await expect(use('enorme:70b')).toBeDisabled();
  await expect(use('enorme:70b')).toHaveAttribute('title', big);
  await expect(row('enorme:70b')).toContainText(big);
  await use('gpt-oss:20b').click();
  await expect(inUse).toContainText('gpt-oss:20b');
  await expect(inUse).toHaveCount(1);
  await expect(use('llama3.2:3b')).toBeEnabled();
  await expect.poll(() => puts('/settings/external-model')).toEqual([{ provider: 'local', model: 'gpt-oss:20b', enabled: true }]);
  // the tuned one: the host turns the other off with it, and the rows say so
  await use('BAXY ajustado').click();
  await expect(inUse).toContainText('BAXY ajustado');
  await expect(inUse).toHaveCount(1);
  await expect(use('gpt-oss:20b')).toBeEnabled();
  await expect.poll(() => puts('/settings/tuned-model')).toEqual([{ use: true }]);
  await use('De serie').click();
  await expect(inUse).toContainText('De serie');
  await expect(inUse).toHaveCount(1);
  await expect.poll(() => puts('/settings/tuned-model')).toEqual([{ use: true }, { use: false }]);
  await expect.poll(() => puts('/settings/external-model')).toEqual([{ provider: 'local', model: 'gpt-oss:20b', enabled: true }]);
  // and from the stock one back to a model of Ollama's
  loading = false;
  await use('llama3.2:3b').click();
  await expect(inUse).toContainText('llama3.2:3b');
  await expect(inUse).toHaveCount(1);
  await expect.poll(() => puts('/settings/external-model')).toEqual([{ provider: 'local', model: 'gpt-oss:20b', enabled: true }, { provider: 'local', model: 'llama3.2:3b', enabled: true }]);
});

// VIS1 (revisión ciega de la tanda 5): «Usar» sent the model without saying it is a local one. The host keeps a model under
// the provider in force (ExternalModel.Apply), and the rows of Ollama are listed whenever Ollama runs, whatever is chosen.
for (const [keyed, button] of [[false, 'Usar'], [true, 'Usar'], [true, 'Usar con Esencial']] as const) {
  test(`modelo: con una API elegida${keyed ? ' y su clave guardada' : ''}, «${button}» en un modelo de Ollama lo pone como modelo local, no como modelo de la API`, async () => {
    h = await openView();
    // the host's own order: the provider first (another one turns the switch off), the model under the provider in force,
    // the switch last (an API without its key is refused, and nothing of the request is kept)
    let models: Record<string, string> = { anthropic: 'claude-opus-5-5' };
    let provider = 'anthropic';
    let enabled = false;
    const state = () => ({ ...EXTERNAL, provider, enabled, model: models[provider] ?? '', hasKey: provider === 'anthropic' && keyed,
      url: provider === 'local' ? 'http://127.0.0.1:11434' : '', active: enabled, activeModel: enabled ? models[provider] : null,
      activeLocal: enabled && provider === 'local', ceilingHolds: provider === 'anthropic', open: OPEN_IDLE,
      providers: EXTERNAL.providers.map((x) => ({ ...x, hasKey: x.id === 'anthropic' && keyed, model: models[x.id] ?? '' })) });
    h.reply('/settings/external-model', (c) => {
      if (c.method !== 'PUT') return { body: state() };
      const asked = c.body as { provider?: string; model?: string; enabled?: boolean };
      const next = asked.provider ?? provider;
      let on = next === provider ? enabled : false;
      const kept = typeof asked.model === 'string' ? { ...models, [next]: asked.model } : models;
      if (asked.enabled && next !== 'local' && !keyed) return { status: 409, body: { error: 'external_model_no_key' } };
      if (asked.enabled && !kept[next]) return { status: 409, body: { error: 'external_model_no_model' } };
      if (typeof asked.enabled === 'boolean') on = asked.enabled;
      provider = next; enabled = on; models = kept;
      return { body: state() };
    });
    h.reply('/settings/external-model/models', () => ({ body: { models: [
      { id: 'llama3.2:3b', label: 'llama3.2:3b', fits: true, vision: false, bytes: 2_019_000_000 },
      { id: 'mistral:latest', label: 'mistral:latest', fits: false, context: 32768, profile: 'esencial', vision: false, bytes: 4_113_000_000,
        why: 'admite 32.768 tokens de contexto y el perfil de herramientas elegido necesita unos 52.670' }] } }));
    h.reply('/settings/tools', () => ({ body: { profile: 'esencial', on: [] } }));
    const p = h.page;
    await p.locator('.bx-gear').click();
    await p.locator('.settings-tab', { hasText: 'Modelo' }).click();
    const name = button === 'Usar' ? 'llama3.2:3b' : 'mistral:latest';
    const row = p.locator('.bx-installed .bx-irow', { hasText: name });
    await row.getByRole('button', { name: button, exact: true }).click();
    await expect(row.locator('.live')).toHaveText('En uso');
    expect({ provider, enabled, models }).toEqual({ provider: 'local', enabled: true, models: { anthropic: 'claude-opus-5-5', local: name } });
    await expect(p.getByRole('radio', { name: /Local/ })).toHaveAttribute('aria-checked', 'true');
  });
}

// VIS1 (segunda revisión ciega): the host turns the tuned model off when another one is turned on (KeepOneModel), and
// «Usar» on a model of Ollama's never asked the tuned one's state again.
test('modelo: con el ajustado en uso, «Usar» en un modelo de Ollama deja de decir que el ajustado está en uso', async () => {
  h = await openView();
  let ext = { ...EXTERNAL, provider: 'local', model: '', url: 'http://127.0.0.1:11434', ceilingHolds: false, open: OPEN_IDLE, activeModel: null as string | null, lastError: null as string | null };
  let tuned = { ...TUNED, installed: true, use: true, active: true };
  h.reply('/settings/external-model', (c) => {
    if (c.method === 'PUT') {
      ext = { ...ext, ...(c.body as object) };
      // chosen, and Ollama does not answer: BAXY goes on with its own model
      ext = { ...ext, active: false, activeModel: null, lastError: ext.enabled ? 'no se pudo conectar con Ollama' : null };
      if (ext.enabled) tuned = { ...tuned, use: false, active: false };
    }
    return { body: ext };
  });
  h.reply('/settings/tuned-model', () => ({ body: tuned }));
  h.reply('/settings/external-model/models', () => ({ body: { models: [{ id: 'llama3.2:3b', label: 'llama3.2:3b', fits: true, vision: false, bytes: 2_019_000_000 }] } }));
  const p = h.page;
  await p.locator('.bx-gear').click();
  await p.locator('.settings-tab', { hasText: 'Modelo' }).click();
  const inUse = p.locator('.bx-installed .bx-irow', { has: p.locator('.live') });
  await expect(inUse).toContainText('BAXY ajustado');
  await p.locator('.bx-installed .bx-irow', { hasText: 'llama3.2:3b' }).getByRole('button', { name: 'Usar', exact: true }).click();
  await expect.poll(() => h.calls.filter((c) => c.method === 'PUT' && c.path === '/settings/external-model').length).toBe(1);
  // the host has no tuned model in use any more: its row offers «Usar» again, and Extras does not say «En uso»
  await expect(p.locator('.bx-installed .bx-irow', { hasText: 'BAXY ajustado' }).getByRole('button', { name: 'Usar', exact: true })).toBeVisible();
  await p.locator('.settings-tab', { hasText: 'Extras' }).click();
  await expect(p.getByRole('button', { name: /^Modelo ajustado a BAXY/ })).toContainText('Instalado');
});

// VIS1 (segunda revisión ciega): «Usar» never looked at its answer: not taken, the tab stayed on «Local» and said nothing.
// (Tercera:) with no answer to the reading either, nothing is known: it is not said failed; and a model not taken leaves
// the person on the place they had picked.
test('modelo: un «Usar» sin respuesta se mira en lo que BAXY tiene: si no lo tomó se dice y la pestaña vuelve; si lo tomó, queda en uso', async () => {
  h = await openView();
  let ext = { ...EXTERNAL, ceilingHolds: false, open: OPEN_IDLE, activeModel: null as string | null };
  let takes = false;
  let silent = false;
  // the host's answer does not come in time: what field-native-bridge.js gives the view then
  const late = { status: 503, body: { error: 'Error: BAXY native request timed out: http' } };
  // a «Usar» whose answer is held until the test gives it
  let hold = false;
  const held: { answer?: (r: Reply) => void } = {};
  h.reply('/settings/external-model', (c) => {
    if (c.method !== 'PUT') return silent ? late : { body: ext };
    if (hold) return new Promise<Reply>((r) => { held.answer = r; });
    if (takes) ext = { ...ext, ...(c.body as object), url: 'http://127.0.0.1:11434', active: true, activeLocal: true, activeModel: 'llama3.2:3b' };
    return late;
  });
  h.reply('/settings/external-model/models', () => ({ body: { models: [{ id: 'llama3.2:3b', label: 'llama3.2:3b', fits: true, vision: false, bytes: 2_019_000_000 }] } }));
  const p = h.page;
  await p.locator('.bx-gear').click();
  await p.locator('.settings-tab', { hasText: 'Modelo' }).click();
  const row = p.locator('.bx-installed .bx-irow', { hasText: 'llama3.2:3b' });
  const use = row.getByRole('button', { name: 'Usar', exact: true });
  const notTaken = p.getByRole('alert').filter({ hasText: 'No se pudo cambiar de modelo' });
  await expect(p.getByRole('radio', { name: /De serie/ })).toHaveAttribute('aria-checked', 'true');
  await use.click();
  await expect(notTaken).toBeVisible();
  await expect(p.getByRole('radio', { name: /De serie/ })).toHaveAttribute('aria-checked', 'true');
  await expect(use).toBeVisible();
  // the reading after it gets no answer either: unknown, said as unknown
  silent = true;
  await use.click();
  await expect(p.getByRole('alert')).toHaveText('BAXY no contestó: no se sabe si cambió de modelo.');
  await expect(notTaken).toHaveCount(0);
  await expect(p.getByRole('radio', { name: /De serie/ })).toHaveAttribute('aria-checked', 'true');
  silent = false;
  // «Local» picked first: not taken, the person stays there
  await p.getByRole('radio', { name: /Local/ }).click();
  await expect(p.getByRole('radio', { name: /Local/ })).toHaveAttribute('aria-checked', 'true');
  await use.click();
  await expect(notTaken).toBeVisible();
  await expect(p.getByRole('radio', { name: /Local/ })).toHaveAttribute('aria-checked', 'true');
  // another place picked while it waits: the person stays there when the answer comes
  hold = true;
  await use.click();
  await expect.poll(() => !!held.answer).toBe(true);
  hold = false;
  await p.getByRole('radio', { name: /De serie/ }).click();
  await expect(p.getByRole('radio', { name: /De serie/ })).toHaveAttribute('aria-checked', 'true');
  held.answer!(late);
  await expect(notTaken).toBeVisible();
  await expect(p.getByRole('radio', { name: /De serie/ })).toHaveAttribute('aria-checked', 'true');
  // taken, and only its answer was lost: it is the model in use, and nothing is said to have failed
  takes = true;
  await use.click();
  await expect(row.locator('.live')).toHaveText('En uso');
  await expect(notTaken).toHaveCount(0);
  await expect(p.getByRole('radio', { name: /Local/ })).toHaveAttribute('aria-checked', 'true');
});

test('otro modelo local: lo que se descarga avanza solo, sin pulsar nada, y al terminar el modelo nuevo está en la lista', async () => {
  h = await openView();
  const name = 'hf.co/a/b-GGUF:Q4_K_M';
  let open = { ...OPEN_IDLE, pulling: name as string | null, pullTotal: 2_000_000_000, pullDone: 200_000_000, pullBytesPerSecond: 10_000_000 as number | null, pullSecondsLeft: 180 as number | null };
  let models: { id: string; label: string; fits: boolean }[] = [];
  h.reply('/settings/external-model', () => ({ body: { ...EXTERNAL, provider: 'local', model: '', url: 'http://127.0.0.1:11434', ceilingHolds: false, open } }));
  h.reply('/settings/external-model/models', () => ({ body: { models } }));
  const p = h.page;
  await p.locator('.bx-gear').click();
  await p.locator('.settings-tab', { hasText: 'Modelo' }).click();
  await pickWhere(p, /Local/);
  const bar = p.getByRole('group', { name: 'Descarga de a/b-GGUF:Q4_K_M' });
  await expect(bar.getByRole('progressbar')).toHaveAttribute('aria-valuenow', '10');
  open = { ...open, pullDone: 1_500_000_000, pullSecondsLeft: 50 };
  await expect(bar.getByRole('progressbar')).toHaveAttribute('aria-valuenow', '75');
  await expect(bar).toContainText('quedan 50 s');
  models = [{ id: name, label: 'a/b-GGUF:Q4_K_M · 2 GB', fits: true }];
  open = { ...open, pulling: null, pullDone: 0, pullTotal: 0, pullBytesPerSecond: null, pullSecondsLeft: null };
  await expect(bar).toHaveCount(0);
  await expect(p.getByRole('combobox', { name: 'Modelo', exact: true }).locator('option')).toHaveText(['Elige un modelo', 'a/b-GGUF:Q4_K_M · 2 GB']);
  // with nothing downloading, the host is no longer asked every second (the window itself asks every three, App.tsx)
  await p.waitForTimeout(700);
  const asked = () => h.calls.filter((c) => c.method === 'GET' && c.path === '/settings/external-model').length;
  const before = asked();
  await p.waitForTimeout(3200);
  expect(asked() - before).toBeLessThanOrEqual(2);
});

test('otro modelo local: el botón «Buscar» busca lo escrito una vez; sin nada escrito no se puede, y lo que no se pudo buscar se dice', async () => {
  h = await openView();
  h.reply('/settings/external-model', () => ({ body: { ...EXTERNAL, provider: 'local', model: '', url: 'http://127.0.0.1:11434', ceilingHolds: false, open: OPEN_IDLE } }));
  h.reply('/settings/external-model/models', () => ({ body: { models: [] } }));
  let answer: (r: Reply) => void = () => undefined;
  h.reply('/settings/external-model/search', () => new Promise<Reply>((r) => { answer = r; }));
  const p = h.page;
  await p.locator('.bx-gear').click();
  await p.locator('.settings-tab', { hasText: 'Modelo' }).click();
  await pickWhere(p, /Local/);
  const box = p.getByRole('textbox', { name: 'Nombre del modelo a buscar' });
  const button = p.getByRole('button', { name: 'Buscar', exact: true });
  const searches = () => h.calls.filter((c) => c.path === '/settings/external-model/search').map((c) => c.body);
  await expect(button).toBeDisabled();
  await box.fill('   ');
  await expect(button).toBeDisabled();
  await box.fill('gemma 4');
  await button.click();
  // while it searches the button says so and takes no second press
  await expect(p.getByRole('button', { name: 'Buscando…' })).toBeDisabled();
  await expect.poll(() => searches().length).toBe(1);
  // the host says why it could not (OpenModels.SearchAsync: «limite» when Hugging Face answers 429, else «sin_red»)
  answer({ body: { error: 'limite' } });
  await expect(p.getByRole('alert').filter({ hasText: 'Hugging Face pidió esperar unos minutos antes de buscar otra vez' })).toHaveCount(1);
  await button.click();
  // a new search takes the old reason away
  await expect(p.getByRole('alert').filter({ hasText: 'Hugging Face' })).toHaveCount(0);
  await expect.poll(() => searches().length).toBe(2);
  answer({ body: { error: 'sin_red' } });
  await expect(p.getByRole('alert').filter({ hasText: 'No pude buscar: revisa tu conexión' })).toHaveCount(1);
  await button.click();
  await expect.poll(() => searches().length).toBe(3);
  answer({ body: { results: [{ repo: 'unsloth/gemma-4-GGUF', file: 'gemma-4-Q4_K_M.gguf', quant: 'Q4_K_M', name: 'unsloth/gemma-4-GGUF:Q4_K_M', visionName: null,
    sha256: 'c'.repeat(64), bytes: 2_500_000_000, projectorBytes: 0, license: 'gemma', context: 131072, tools: true, vramBytes: 4_200_000_000, vramContext: 78000, fit: 'cabe', why: null }] } });
  await expect(p.locator('ul[aria-label="Modelos encontrados"] li')).toHaveCount(1);
  await expect(p.getByRole('alert').filter({ hasText: 'No pude buscar' })).toHaveCount(0);
  await expect(button).toBeEnabled();
  await expect.poll(() => searches()).toEqual([{ q: 'gemma 4' }, { q: 'gemma 4' }, { q: 'gemma 4' }]);
});

// An Ollama of the person's older than the one BAXY installs: said with its version, and BAXY's is offered. The versions
// compare as numbers (0.9.6 is older than 0.40.15; 0.100.0 is not).
for (const [running, own, said] of [['0.9.6', false, true], ['0.40.15', false, false], ['0.100.0', false, false], ['0.9.6', true, false]] as const) {
  test(`otro modelo local: con Ollama ${running}${own ? ' de BAXY' : ' tuyo'} ${said ? 'se dice que es viejo y se ofrece el de BAXY' : 'no se ofrece instalar otro'}`, async () => {
    h = await openView();
    h.reply('/settings/external-model', () => ({ body: { ...EXTERNAL, provider: 'local', model: '', url: 'http://127.0.0.1:11434', ceilingHolds: false,
      open: { ...OPEN_IDLE, ollamaOwn: own, ollamaRunning: running } } }));
    h.reply('/settings/external-model/models', () => ({ body: { models: [] } }));
    const p = h.page;
    await p.locator('.bx-gear').click();
    await p.locator('.settings-tab', { hasText: 'Modelo' }).click();
    await pickWhere(p, /Local/);
    await expect(p.getByRole('textbox', { name: 'Nombre del modelo a buscar' })).toBeVisible();
    const old = p.getByText(`Tienes Ollama ${running}, y los modelos nuevos pueden no cargar en él.`, { exact: false });
    await expect(old).toHaveCount(said ? 1 : 0);
    await expect(p.getByRole('button', { name: 'Instalar Ollama' })).toHaveCount(said ? 1 : 0);
  });
}

test('privacidad: lo que salió a internet en la sesión se lista con su hora y se cuenta; sin nada, se dice', async () => {
  h = await openView();
  const p = h.page;
  await p.locator('.bx-gear').click();
  await p.locator('.settings-tab', { hasText: 'Privacidad' }).click();
  const fold = p.getByRole('button', { name: /^Salidas a internet de esta sesión/ });
  const rows = p.locator('.bxs-log');
  await expect(fold).toContainText('0');
  await expect(rows).toHaveText(['Ninguna. Todo se ha quedado en este PC.']);
  h.emit({ type: 'net', what: 'búsqueda «farmacias cerca»', ts: '12:01' });
  h.emit({ type: 'net', what: 'clima · Querétaro', ts: '12:02' });
  await expect(rows).toHaveCount(2);
  await expect(rows.nth(0)).toContainText('búsqueda «farmacias cerca»');
  await expect(rows.nth(0).locator('.ts')).toHaveText('12:01');
  await expect(rows.nth(1)).toContainText('clima · Querétaro');
  await expect(rows.nth(1).locator('.ts')).toHaveText('12:02');
  await expect(fold).toContainText('2');
  await expect(p.getByText('Ninguna. Todo se ha quedado en este PC.')).toHaveCount(0);
});

test('ajustes: «Avisar de versiones nuevas» envía su ajuste, y sólo ese', async () => {
  h = await openView();
  let host: Record<string, unknown> = { language: 'es', languageInUse: 'es', autostart: false, closeToTray: true, minimizeToTray: false, updateNotice: true };
  h.reply('/settings/general', (c) => { if (c.method === 'PUT') host = { ...host, ...(c.body as object) }; return { body: host }; });
  const p = h.page;
  await p.locator('.bx-gear').click();
  const toggle = p.getByRole('switch', { name: 'Avisar de versiones nuevas', exact: true });
  await expect(toggle).toHaveAttribute('aria-checked', 'true');
  await toggle.click();
  await expect(toggle).toHaveAttribute('aria-checked', 'false');
  await toggle.click();
  await expect(toggle).toHaveAttribute('aria-checked', 'true');
  await expect.poll(() => h.calls.filter((c) => c.method === 'PUT' && c.path === '/settings/general').map((c) => c.body)).toEqual([{ updateNotice: false }, { updateNotice: true }]);
});

test('micrófono: su botón abre y cierra el menú de modos; en mantener para hablar no lo abre: abre el oído mientras se mantiene', async () => {
  h = await openView({ mic: 'off' });
  const p = h.page;
  const mic = p.locator('.bx-mic');
  const menu = p.locator('.bx-micmenu');
  await mic.click();
  await expect(menu).toHaveCount(1);
  await mic.click();
  await expect(menu).toHaveCount(0);
  expect(voice()).toEqual([]);
  await mic.click();
  await menu.locator('button', { hasText: 'Mantener para hablar' }).click();
  await expect(menu).toHaveCount(0);
  await expect(mic).toHaveAttribute('title', 'Mantén para hablar');
  await expect(p.locator('.bx-notice')).toContainText('mantén el botón o espacio para hablar');
  await mic.hover();
  await p.mouse.down();
  await expect.poll(voice).toEqual(['/voice/trigger']);
  await p.waitForTimeout(300);
  expect(voice()).toEqual(['/voice/trigger']);
  await p.mouse.up();
  await expect.poll(voice).toEqual(['/voice/trigger', '/voice/release']);
  await expect(menu).toHaveCount(0);
});

test('personalización: la opacidad del overlay se guarda al soltar el ratón, una vez, con lo que quedó puesto', async () => {
  h = await openView();
  let host = { on: true, corner: 'br', size: 'm', opacity: 90, hideSeconds: 8, notFullscreen: true, answer: false };
  h.reply('/settings/overlay', (c) => { if (c.method === 'PUT') host = { ...host, ...(c.body as object) }; return { body: host }; });
  const p = h.page;
  await p.locator('.bx-gear').click();
  await p.locator('.settings-tab', { hasText: 'Personalización' }).click();
  await p.getByRole('button', { name: /^Overlay mientras trabaja/ }).click();
  const slider = p.getByRole('slider', { name: 'Opacidad del overlay' });
  await slider.scrollIntoViewIfNeeded();
  const box = (await slider.boundingBox())!;
  await p.mouse.move(box.x + box.width * 0.25, box.y + box.height / 2);
  await p.mouse.down();
  await p.mouse.move(box.x + box.width * 0.5, box.y + box.height / 2, { steps: 4 });
  // dragged, nothing is saved yet: the value follows the pointer
  const dragged = Number(await slider.inputValue());
  expect(dragged).toBeGreaterThan(60);
  expect(dragged).toBeLessThan(80);
  expect(h.calls.filter((c) => c.method === 'PUT' && c.path === '/settings/overlay')).toEqual([]);
  await p.mouse.up();
  await expect.poll(() => h.calls.filter((c) => c.method === 'PUT' && c.path === '/settings/overlay').map((c) => c.body)).toEqual([{ opacity: dragged }]);
  await expect(slider).toHaveValue(String(dragged));
  await expect(p.locator('.bxs-row', { hasText: 'Opacidad' })).toContainText(dragged + ' %');
});

test('si la conexión con BAXY se cae, la vista se vuelve a conectar sola y muestra lo que pasó mientras', async () => {
  h = await openView({ items: [reply('b1', 'Listo.')] });
  const p = h.page;
  const chat = p.locator('.bx-chat4');
  await expect(chat).toContainText('Listo.');
  h.drop();
  h.emit({ type: 'item', item: reply('b2', 'Son las cinco.') });
  await expect(chat).toContainText('Son las cinco.');
  // this stand-in says again all it said (the App sends its transcript whole): what the view already had is not shown
  // twice, and what comes next arrives by the new connection
  await expect(chat.getByText('Listo.', { exact: true })).toHaveCount(1);
  h.emit({ type: 'item', item: reply('b3', 'Ya puse la alarma.') });
  await expect(chat).toContainText('Ya puse la alarma.');
  h.drop();
  h.emit({ type: 'state', value: 'thinking' });
  h.emit({ type: 'item', item: reply('b4', 'Sigo aquí.') });
  await expect(chat).toContainText('Sigo aquí.');
});

// APP1 (UPD-f, review of the App 2026-11-09): the installer's download outlives a request (the bridge gives one 30 s), so
// the view said «No pude buscar ahora» and offered the button again while the host went on, started the installer and
// BAXY closed. The install is a long operation the view reads (GET /update/install), as a model's download: its
// percentage, the check, and its end as the host says it; while it runs no button asks for another.
const NEWER = { ok: true, channel: 'github', installed: '1.3.2', latest: '1.4.0', newer: true, downloadBytes: 81_450_121 };
const DOWNLOADING = { installing: true, phase: 'downloading', latest: '1.4.0', downloadBytes: 81_450_121, downloadedBytes: null as number | null };

test('versión: una instalación larga se ve bajando con su porcentaje y comprobando, sin botón que pida otra, hasta su final', async () => {
  h = await openView();
  let state: Record<string, unknown> = { installing: false };
  h.reply('/update', () => ({ body: NEWER }));
  h.reply('/update/install', (c) => {
    if (c.method === 'POST') state = DOWNLOADING;
    return { body: state };
  });
  const p = h.page;
  await p.locator('.bx-gear').click();
  await p.getByRole('button', { name: 'Buscar actualizaciones' }).click();
  await p.getByRole('button', { name: 'Actualizar a 1.4.0' }).click();
  await expect(p.getByText('Bajando el instalador de BAXY 1.4.0…')).toBeVisible();
  await expect(p.getByRole('button', { name: 'Actualizando a 1.4.0…' })).toBeDisabled();
  state = { ...DOWNLOADING, downloadedBytes: 30_136_545 };
  await expect(p.getByText('Bajando el instalador de BAXY 1.4.0: 37 % (29 de 78 MB)')).toBeVisible();
  // every byte here is not the end: the check and the installer's start are still to come
  state = { ...DOWNLOADING, phase: 'checking', downloadedBytes: 81_450_121 };
  await expect(p.getByText('Comprobando el instalador de BAXY 1.4.0…')).toBeVisible();
  await expect(p.getByText('BAXY se cierra y el instalador la reemplaza; tus datos se quedan')).toHaveCount(0);
  await expect(p.getByText(/No pude/)).toHaveCount(0);
  state = { installing: false, ok: true, channel: 'github', installed: '1.3.2', latest: '1.4.0', installerStarted: true };
  await expect(p.getByText('BAXY se cierra y el instalador la reemplaza; tus datos se quedan')).toBeVisible();
  expect(h.calls.filter((c) => c.method === 'POST' && c.path === '/update/install')).toHaveLength(1);
});

test('versión: un pedido de instalar sin respuesta (plazo del puente) no se dice «no pude»: se lee qué hace el host', async () => {
  h = await openView();
  let state: Record<string, unknown> = { installing: false };
  h.reply('/update', () => ({ body: NEWER }));
  h.reply('/update/install', (c) => {
    if (c.method === 'GET') return { body: state };
    state = { ...DOWNLOADING, downloadedBytes: 30_136_545 };
    // field-native-bridge.js: a request that timed out or failed in the bridge answers 503; the host may have taken it
    return { status: 503, body: { error: 'Error: BAXY native request timed out: http' } };
  });
  const p = h.page;
  await p.locator('.bx-gear').click();
  await p.getByRole('button', { name: 'Buscar actualizaciones' }).click();
  await p.getByRole('button', { name: 'Actualizar a 1.4.0' }).click();
  await expect(p.getByText('Bajando el instalador de BAXY 1.4.0: 37 % (29 de 78 MB)')).toBeVisible();
  await expect(p.getByText(/No pude/)).toHaveCount(0);
  // the host's own failure, with its cause
  state = { installing: false, ok: false, error: 'baxy_update_download_failed', channel: 'github', installed: '1.3.2', latest: '1.4.0' };
  await expect(p.getByText('La descarga del instalador se cortó; BAXY sigue como estaba')).toBeVisible();
  await expect(p.getByRole('button', { name: 'Buscar actualizaciones' })).toBeEnabled();
});

test('versión: si el host no contesta ni al pedido ni al estado, se dice que no contestó, no que no pudo buscar', async () => {
  h = await openView();
  h.reply('/update', () => ({ body: NEWER }));
  h.reply('/update/install', (c) => c.method === 'GET' && h.calls.every((x) => x.method !== 'POST')
    ? { body: { installing: false } }
    : { status: 503, body: { error: 'Error: BAXY native request timed out: http' } });
  const p = h.page;
  await p.locator('.bx-gear').click();
  await p.getByRole('button', { name: 'Buscar actualizaciones' }).click();
  await p.getByRole('button', { name: 'Actualizar a 1.4.0' }).click();
  await expect(p.getByText('BAXY no contestó: no sé si la actualización empezó')).toBeVisible();
  await expect(p.getByText('No pude buscar ahora')).toHaveCount(0);
});

test('versión: al abrir Ajustes con una instalación en marcha se ve su avance y no hay botón que pida otra', async () => {
  h = await openView();
  h.reply('/update/install', () => ({ body: { ...DOWNLOADING, downloadedBytes: 61_087_591 } }));
  const p = h.page;
  await p.locator('.bx-gear').click();
  await expect(p.getByText('Bajando el instalador de BAXY 1.4.0: 75 % (58 de 78 MB)')).toBeVisible();
  await expect(p.getByRole('button', { name: 'Actualizando a 1.4.0…' })).toBeDisabled();
  await expect(p.getByRole('button', { name: 'Buscar actualizaciones' })).toHaveCount(0);
  expect(h.calls.filter((c) => c.method === 'POST' && c.path === '/update/install')).toHaveLength(0);
});

test('versión: cada final de una instalación se dice con su causa', async () => {
  h = await openView();
  let error = 'update_outcome_unknown';
  h.reply('/update', () => ({ body: NEWER }));
  h.reply('/update/install', (c) => c.method === 'GET' ? { body: { installing: false } }
    : { body: { installing: false, ok: false, error, channel: 'github', installed: '1.3.2', latest: '1.4.0' } });
  const p = h.page;
  await p.locator('.bx-gear').click();
  for (const [code, said] of [
    ['update_outcome_unknown', 'El motor de BAXY dejó de contestar: no sé si el instalador llegó a abrirse'],
    ['baxy_update_installer_not_started', 'Bajé el instalador y Windows no lo abrió; BAXY sigue como estaba'],
    ['engine_not_ready', 'El motor de BAXY todavía no está listo'],
    ['baxy_update_hash_mismatch', 'El instalador bajado no era el publicado: lo borré y no lo abrí'],
  ]) {
    error = code;
    await p.getByRole('button', { name: 'Buscar actualizaciones' }).click();
    await p.getByRole('button', { name: 'Actualizar a 1.4.0' }).click();
    await expect(p.getByText(said)).toBeVisible();
  }
});
