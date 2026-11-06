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
  await h.page.locator('.bx-line > input').focus();
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

test('siempre activo: un clic en la ventana no abre el oído como mantener para hablar', async () => {
  // Uso real 03-11: the owner clicked the window to focus it and BAXY took it as the held space, transcribing all he
  // said. Only the wake word, the held space or the microphone button open the ear.
  h = await openView({ mic: 'always' });
  h.emit({ type: 'voice', available: true, mode: 'wake', speaking: false });
  await h.page.locator('.bx-graph').click();
  await h.page.waitForTimeout(300);
  expect(voice()).toEqual([]);
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
  await h.page.locator('button', { hasText: 'Sesiones' }).first().click();
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
  const list = p.getByLabel('Modelo', { exact: true });
  await expect(list.locator('option')).toHaveText(['Elige un modelo', 'grande:4b · 5.2 GB', 'visual · 5.2 GB · no sabe usar herramientas']);
  await expect(list.locator('option', { hasText: 'visual' })).toBeDisabled();
  await list.selectOption('grande:4b');
  await expect.poll(() => h.calls.filter((c) => c.method === 'PUT').map((c) => c.body)).toContainEqual({ model: 'grande:4b', enabled: true });
  await expect(p.locator('button.toggle[aria-label="Usar otro modelo"]')).toHaveAttribute('aria-checked', 'true');
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
  const context = p.getByLabel('Contexto', { exact: true });
  await expect(context.locator('option')).toHaveText(['64.000 tokens · unos 4,4 GB de VRAM', '78.000 tokens · unos 4,7 GB de VRAM · recomendado', '200.000 tokens · unos 7,0 GB de VRAM']);
  await expect(context).toHaveValue('78000');
  await expect(p.getByText('Deja unos 29.000 tokens para la conversación. Tu tarjeta tiene 8,0 GB y hay 5,6 GB libres')).toBeVisible();
  await context.selectOption('200000');
  await expect.poll(() => h.calls.filter((c) => c.method === 'PUT').map((c) => c.body)).toContainEqual({ context: 200000 });
  await expect(p.getByText('No cabe entero: lo demás irá a la RAM')).toBeVisible();
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
  await expect(p.getByLabel('Contexto', { exact: true }).locator('option')).toHaveText(['78.000 tokens · unos 2,0 GB de VRAM · recomendado', '200.000 tokens · unos 8,0 GB de VRAM · sin memoria']);
  await expect(p.getByText('Este PC tiene 8,0 GB de memoria libre: no se conectará con este contexto')).toBeVisible();
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
  await expect(p.getByText('No cabe: elige menos contexto. El modelo declara 40.960: BAXY le amplía el límite')).toBeVisible();
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
  await expect(p.getByText('No encontré Ollama en este PC')).toBeVisible();
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
  await expect(p.locator('.bxs-fixed', { hasText: 'qwen en este PC' }).first()).toBeVisible();
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
  await expect(h.page.getByText('Otro modelo', { exact: true })).toHaveCount(0);
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
  const toggle = p.locator('button.toggle[aria-label="Usar otro modelo"]');
  await expect(p.getByText('también la conversación que ya tuviste')).toBeVisible();
  await toggle.click();
  await expect(p.getByRole('alert')).toHaveText('Primero guarda la clave');
  await expect(toggle).toHaveAttribute('aria-checked', 'false');

  const key = p.getByLabel('Clave de la API');
  await expect(key).toHaveAttribute('type', 'password');
  await key.fill('sk-secreta');
  await p.getByRole('button', { name: 'Guardar' }).click();
  await expect(key).toHaveValue('');
  await expect(p.getByText('Guardada y protegida en este PC')).toBeVisible();
  expect(h.calls.filter((c) => c.method === 'PUT' && (c.body as { key?: string }).key === 'sk-secreta')).toHaveLength(1);

  await toggle.click();
  await expect(toggle).toHaveAttribute('aria-checked', 'true');
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
  await expect(p.locator('.bxs-fixed', { hasText: 'claude-opus-5-5 por API' }).first()).toBeVisible();
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
  await expect(p.getByText('Esta sesión usó un modelo por API')).toBeVisible();
  await expect(p.getByText('Ninguna. Todo se ha quedado en este PC.')).toHaveCount(0);
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
  await p.getByLabel('Dirección de la API').fill('http://no-vale.com/v1');
  const toggle = p.locator('button.toggle[aria-label="Usar otro modelo"]');
  await toggle.click();
  await expect(toggle).toHaveAttribute('aria-checked', 'false');
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
  await p.waitForTimeout(150); // the keys follow the card once the view's effects ran
  await p.keyboard.press('Enter');
  await expect.poll(answers).toEqual([{ approve: true, card: 'c1' }]);
  await expect(p.locator('.settings-panel')).toHaveCount(0);
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
      .filter((b) => /Sesiones|Memoria|Triggers|Capacidades|Propuestas|puedo/.test(b.innerText))
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
