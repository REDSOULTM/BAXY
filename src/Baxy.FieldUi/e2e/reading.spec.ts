import { expect, test } from '@playwright/test';
import { readingText, type ModelReading } from '../src/causes';
import { translator } from '../src/i18n';
import { heldReading } from '../src/reading';
import { openView, stopHost, type Host } from './host';

/* VUL1: what the window says is left of the model's read («Preparando el modelo · N % · quedan unos X min») never goes
   up while the person waits. The first test is the read of an RX 7600 on Vulkan as its window showed it every 30 s
   (INFORME_AMD3.md §1): at 4 min of waiting it said «5 min», more than it had said at 2. */

const es = translator('es'), en = translator('en');
const TOTAL = 46822;
// [percent, the minutes the host's count gave; 0 = under a minute]
const SEEN: [number, number][] = [[8, 8], [24, 3], [37, 3], [48, 3], [52, 2], [56, 2], [61, 2], [65, 4], [69, 5], [72, 5], [76, 4],
  [78, 4], [83, 3], [85, 3], [87, 3], [91, 2], [98, 0]];
const reading = (percent: number, minutes: number): ModelReading => ({ done: Math.round((TOTAL * (percent + 0.5)) / 100), total: TOTAL, seconds_left: minutes ? minutes * 60 - 10 : 30 });

function said(readings: ModelReading[], t = es): string[] {
  let held: ModelReading | null = null;
  return readings.map((r) => { held = heldReading(r, held); return readingText(held!, t).split(' · ').slice(2).join(' · '); });
}

test('el plazo que se dice no sube mientras la persona espera: cuando la cuenta sube, se dice que tarda más, sin minutos', () => {
  const texts = said(SEEN.map(([p, m]) => reading(p, m)));
  expect(texts.slice(0, 7)).toEqual(['quedan unos 8 min', 'quedan unos 3 min', 'quedan unos 3 min', 'quedan unos 3 min', 'quedan unos 2 min', 'quedan unos 2 min', 'quedan unos 2 min']);
  // the count went up to 4 and 5 min and came down to 3: more than the 2 already said
  expect(texts.slice(7, 15)).toEqual(Array(8).fill('tarda más de lo previsto'));
  expect(texts.slice(15)).toEqual(['quedan unos 2 min', 'queda menos de 1 min']);
  // and the minutes said are never more than the ones said before
  const minutes = texts.map((x) => (x.startsWith('quedan unos ') ? +x.split(' ')[2] : x.startsWith('queda menos') ? 0 : null)).filter((m) => m !== null);
  expect(minutes).toEqual([...minutes].sort((a, b) => b! - a!));
});

test('el porcentaje se sigue diciendo siempre, y en inglés se dice lo mismo', () => {
  let held: ModelReading | null = null;
  const lines = SEEN.map(([p, m]) => { held = heldReading(reading(p, m), held); return readingText(held!, en); });
  expect(lines[6]).toBe('Getting the model ready · 61 % · about 2 min left');
  expect(lines[8]).toBe('Getting the model ready · 69 % · taking longer than expected');
  expect(lines[16]).toBe('Getting the model ready · 98 % · less than 1 min left');
});

test('una lectura nueva (otro prefijo, o el arranque que empieza otra vez) no hereda lo que se dijo de la anterior', () => {
  expect(said([reading(50, 2), { done: 2048, total: TOTAL, seconds_left: 400 }])).toEqual(['quedan unos 2 min', 'quedan unos 7 min']);
  expect(said([reading(50, 2), { done: 30000, total: 32065, seconds_left: 400 }])).toEqual(['quedan unos 2 min', 'quedan unos 7 min']);
});

test('sin cuenta del host no se dice plazo ni que tarda más; y la cuenta que vuelve sin subir se dice', () => {
  expect(said([reading(10, 3), { done: 9000, total: TOTAL }, reading(30, 3), reading(40, 2)]))
    .toEqual(['quedan unos 3 min', '', 'quedan unos 3 min', 'quedan unos 2 min']);
  expect(said([{ done: 1024, total: TOTAL }, { done: 2048, total: TOTAL, seconds_left: null }])).toEqual(['', '']);
  expect(heldReading(null, reading(10, 3))).toBeNull();
});

let h: Host;
test.afterEach(async () => { await h?.close(); });
test.afterAll(async () => { await stopHost(); });

test('en la ventana: el plazo que sube se cambia por «tarda más de lo previsto» y vuelve cuando baja de lo dicho', async () => {
  h = await openView();
  const boot = { type: 'boot', stt: true, wake: true, tts: true, model: false, startedAt: Date.now(), readyAt: null };
  h.emit({ type: 'agent', built: true, ready: false, powered: true });
  const panel = h.page.locator('.bx-boot');
  h.emit({ ...boot, reading: reading(61, 2) });
  await expect(panel).toContainText('Preparando el modelo · 61 % · quedan unos 2 min');
  h.emit({ ...boot, reading: reading(69, 5) });
  await expect(panel).toContainText('Preparando el modelo · 69 % · tarda más de lo previsto');
  await expect(panel).not.toContainText('quedan unos');
  h.emit({ ...boot, reading: reading(91, 2) });
  await expect(panel).toContainText('Preparando el modelo · 91 % · quedan unos 2 min');
  h.emit({ ...boot, reading: reading(98, 0) });
  await expect(panel).toContainText('Preparando el modelo · 98 % · queda menos de 1 min');
});
