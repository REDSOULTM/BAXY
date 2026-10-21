import { expect, test } from '@playwright/test';
import { seededRng } from '../src/utils/seededRng';
import { BXM, HUBS, bxMouth, bxRoute } from '../src/components/face/geometry';
import { LIB, NEXT, groupFor } from '../src/components/avatarClips';

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

test('design v5: al hablar la boca es una onda de voz salvo contenta; seria en zigzag; en reposo sonrisa abierta', () => {
  const [wave, wc] = bxMouth('neutral', 0.6);
  expect(wc, 'la onda es abierta').toBe(0);
  expect(wave.length).toBe(15);
  const [open, oc] = bxMouth('happy', 0.6);
  expect(oc, 'contenta habla con la boca abierta').toBe(1);
  expect(open.length).toBeGreaterThan(15);
  const [zig, zc] = bxMouth('serious', -1);
  expect(zc).toBe(0);
  expect(zig.every(([, y], i) => Math.abs(y - (0.46 + (i % 2 ? -0.035 : 0.035))) < 1e-9), 'zigzag').toBe(true);
  const [smile, sc] = bxMouth('neutral', -1);
  expect(sc, 'sonrisa abierta').toBe(1);
  expect(smile[0]).toEqual([-0.23, 0.33]);
});

test('design v5: cada estado tiene su grupo de clips y cada grupo existe en la biblioteca', () => {
  const states = ['booting', 'standby', 'idle', 'listening', 'thinking', 'speaking', 'error', 'confirm'] as const;
  const want: Record<string, string> = { booting: 'reposo', standby: 'dormido', idle: 'reposo', listening: 'escuchando', thinking: 'pensando', speaking: 'hablando', error: 'error', confirm: 'reposo' };
  for (const st of states) expect(groupFor(st, 'neutral'), st).toBe(want[st]);
  expect(groupFor('idle', 'happy')).toBe('contento');
  for (const [g, next] of Object.entries(NEXT)) {
    expect(LIB[g as keyof typeof LIB], g).toBeGreaterThan(0);
    for (const n of next) expect(LIB[n], g + '→' + n).toBeGreaterThan(0);
  }
});

test('design v5: cada variante de la biblioteca tiene su clip en public/clips', async () => {
  const { existsSync } = await import('node:fs');
  const missing = Object.entries(LIB).flatMap(([g, n]) => Array.from({ length: n }, (_, i) => `public/clips/${g}-${i + 1}.mp4`)).filter((f) => !existsSync(f));
  expect(missing).toEqual([]);
});
