import { expect, test } from '@playwright/test';
import { seededRng } from '../src/utils/seededRng';
import { BXM, HUBS, bxMouth, bxRoute } from '../src/components/face/geometry';

/* «Unitarias · lógica del diseño» of Baxy pruebas.html, against the view's own modules. */

test('el cielo es el mismo en cada redibujado y sus valores están entre 0 y 1', () => {
  const a = seededRng(707), b = seededRng(707);
  let same = true, inRange = true;
  for (let i = 0; i < 20_000; i++) {
    const x = a(), y = b();
    if (x !== y) same = false;
    if (x < 0 || x > 1) inRange = false;
  }
  expect(same, 'mismo cielo').toBe(true);
  expect(inRange, 'valores entre 0 y 1').toBe(true);
});

test('hay un camino continuo de la mente a cada familia de la red', () => {
  const broken: string[] = [];
  for (const k of Object.keys(HUBS).filter((h) => h !== 'web' && h !== 'mente')) {
    const r = bxRoute(k === 'voz' ? ['mente', 'verificar', 'voz'] : ['mente', k]);
    const contiguous = r.every((n, i) => i === 0 || BXM.adj[r[i - 1]].includes(n));
    if (r[0] !== BXM.hub.mente || r[r.length - 1] !== BXM.hub[k] || !contiguous) broken.push(k);
  }
  expect(broken).toEqual([]);
});

test('cada expresión produce una boca válida', () => {
  const exprs = ['neutral', 'happy', 'sad', 'serious', 'curious', 'think', 'listen', 'sleep', 'wink', 'hum'];
  for (const e of exprs) {
    const [pts] = bxMouth(e, -1);
    expect(pts.length, e).toBeGreaterThan(0);
    expect(pts.every(([x, y]) => Number.isFinite(x) && Number.isFinite(y)), e).toBe(true);
  }
});
