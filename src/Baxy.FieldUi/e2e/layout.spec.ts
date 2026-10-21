import { expect, test, type Page } from '@playwright/test';
import { attach, ready, size, unsize, type App } from './app';

/* «Baxy pruebas.html» against the real app: the 11 sizes from 720p to 8K, small windows, live resizing and the start
   with a 0×0 window. The view is laid out at each size with the DevTools protocol (as a window of that size would). */

const SIZES: [string, number, number][] = [
  ['720p', 1280, 720], ['1366×768', 1366, 768], ['1080p', 1920, 1080], ['1440p', 2560, 1440],
  ['Ultrawide 3440×1440', 3440, 1440], ['4K', 3840, 2160], ['8K', 7680, 4320],
  ['Ventana pequeña 900×560', 900, 560], ['Ventana mínima 640×400', 640, 400], ['Alta y estrecha 760×1000', 760, 1000],
  ['Ancha y baja 1920×420', 1920, 420],
];
const FACE_MAXPX = 4.5e6, COSMOS_MAXPX = 4e6;

let app: App;
test.beforeAll(async () => { app = await attach(); await ready(app.page); });
test.afterAll(async () => { await unsize(app); await app.browser.close(); });

interface Audit { issues: string[]; cut: string[]; minFont: number; minEl: string; fr: { left: number; top: number; right: number; bottom: number; width: number; height: number }; vw: number; vh: number }

// layoutAudit of the design's test page: nothing outside the frame, no text cut without an ellipsis, the smallest text.
function audit(page: Page): Promise<Audit> {
  return page.evaluate(() => {
    const ui = parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--ui')) || 1;
    const frame = document.querySelector('.app-frame')!;
    const fr = frame.getBoundingClientRect();
    const issues: string[] = [], cut: string[] = [];
    let minFont = 99, minEl = '';
    const visible = (el: Element) => {
      const r = el.getBoundingClientRect(), cs = getComputedStyle(el);
      return r.width > 0 && r.height > 0 && cs.visibility !== 'hidden' && cs.display !== 'none' && +cs.opacity > 0.05;
    };
    const clipped = (el: Element) => {
      let p = el.parentElement;
      while (p && !p.classList.contains('bx2')) {
        const cs = getComputedStyle(p);
        if (cs.overflowX !== 'visible' || cs.overflowY !== 'visible') {
          const pr = p.getBoundingClientRect(), r = el.getBoundingClientRect();
          if (r.right <= pr.left || r.left >= pr.right || r.bottom <= pr.top || r.top >= pr.bottom) return true;
        }
        if (cs.visibility === 'hidden') return true;
        p = p.parentElement;
      }
      return false;
    };
    // design v5 clipRect: the rect left visible after clipping by overflow / clip-path ancestors
    const clipRect = (el: Element) => {
      const b = el.getBoundingClientRect();
      let L = b.left, T = b.top, R = b.right, B = b.bottom, p = el.parentElement;
      while (p && !p.classList.contains('app-frame')) {
        const cs = getComputedStyle(p);
        if (cs.overflowX !== 'visible' || cs.overflowY !== 'visible' || cs.clipPath !== 'none') {
          const pr = p.getBoundingClientRect();
          L = Math.max(L, pr.left); T = Math.max(T, pr.top); R = Math.min(R, pr.right); B = Math.min(B, pr.bottom);
        }
        p = p.parentElement;
      }
      return { left: L, top: T, right: R, bottom: B };
    };
    for (const el of document.querySelectorAll('.bx2 *')) {
      if (el.closest('.bx-c4-list') || el.tagName.toLowerCase() === 'svg' || el.closest('svg') || el.tagName === 'CANVAS') continue;
      if (!visible(el) || clipped(el)) continue;
      const r = clipRect(el), tol = 0.75 * ui + 0.5;
      if (r.right > fr.right + tol || r.left < fr.left - tol || r.bottom > fr.bottom + tol || r.top < fr.top - tol) {
        issues.push((typeof el.className === 'string' ? el.className : el.tagName) + ' sale del marco');
      }
      if ([...el.childNodes].some((n) => n.nodeType === 3 && n.textContent!.trim())) {
        const cs = getComputedStyle(el), fs = parseFloat(cs.fontSize) * ui;
        if (fs < minFont) { minFont = fs; minEl = el.textContent!.trim().slice(0, 24); }
        if (el.scrollWidth > el.clientWidth + 1 && cs.overflowX !== 'visible' && cs.textOverflow !== 'ellipsis') {
          cut.push('«' + el.textContent!.trim().slice(0, 28) + '» cortado');
        }
      }
    }
    return {
      issues: [...new Set(issues)], cut: [...new Set(cut)], minFont, minEl,
      fr: { left: fr.left, top: fr.top, right: fr.right, bottom: fr.bottom, width: fr.width, height: fr.height },
      vw: innerWidth, vh: innerHeight,
    };
  });
}

// edgeLine: bright dots piled on a canvas' border (the «line of dots» bug of a canvas narrower than its column).
function edgeLine(page: Page, selector: string): Promise<{ bad: boolean; n: number }> {
  return page.evaluate((sel) => {
    const cv = document.querySelector<HTMLCanvasElement>(sel);
    if (!cv) return { bad: true, n: -1 };
    const g = cv.getContext('2d')!, W = cv.width, H = cv.height;
    if (W < 40 || H < 40) return { bad: false, n: 0 };
    const d = g.getImageData(0, 0, W, H).data;
    const col = (x: number) => { let n = 0; for (let y = 0; y < H; y += 2) { const i = (y * W + x) * 4; if (d[i + 3] > 60 && d[i] + d[i + 1] + d[i + 2] > 220) n++; } return n; };
    const e = Math.max(...[0, 1, 2, W - 3, W - 2, W - 1].map(col));
    const m = [12, 16, 20, W - 21, W - 17, W - 13].map(col).reduce((a, b) => a + b, 0) / 6;
    return { bad: e > 12 && e > (m + 2) * 3, n: e };
  }, selector);
}

const uiOf = (page: Page) => page.evaluate(() => parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--ui')));
const scaleFor = (page: Page, w: number, h: number) => page.evaluate(([a, b]) => (window as unknown as { bxScale: (w: number, h: number) => number }).bxScale(a, b), [w, h]);

test('escala de interfaz: 720p 1× · 1080p 1.5× · 1440p 2× · 4K 3× · 8K 6× · mínimo 0.8×', async () => {
  const expected: [number, number, number][] = [[1280, 720, 1], [1920, 1080, 1.5], [2560, 1440, 2], [3840, 2160, 3], [7680, 4320, 6], [3440, 1440, 2], [1366, 768, 1.067], [640, 400, 0.8], [15360, 8640, 6]];
  for (const [w, h, u] of expected) expect(Math.abs((await scaleFor(app.page, w, h)) - u), `${w}×${h}`).toBeLessThan(0.002);
});

for (const [label, w, h] of SIZES) {
  test(`humo · ${label} · ${w}×${h}`, async () => {
    const { page } = app;
    const errors = app.errors.length;
    await size(app, w, h);
    await page.waitForTimeout(900);
    expect(Math.abs((await uiOf(page)) - (await scaleFor(page, w, h))), 'escala aplicada').toBeLessThan(0.002);
    let A = await audit(page);
    const fill = (A.fr.width * A.fr.height) / (A.vw * A.vh);
    expect(fill, 'la app llena la ventana').toBeGreaterThan(0.9);
    expect(A.fr.left >= -1 && A.fr.top >= -1 && A.fr.right <= A.vw + 1 && A.fr.bottom <= A.vh + 1, 'sin salirse de la ventana').toBe(true);
    expect(A.issues, 'nada se sale del marco').toEqual([]);
    expect(A.cut, 'ningún texto cortado sin puntos suspensivos').toEqual([]);
    expect(A.minFont, `texto legible («${A.minEl}»)`).toBeGreaterThanOrEqual(7);
    const canvases = await page.evaluate(() => [...document.querySelectorAll('canvas')].map((c) => ({ cls: c.className, w: c.width, h: c.height })));
    expect(canvases.length).toBeGreaterThanOrEqual(2);
    for (const c of canvases) {
      expect(c.w * c.h, c.cls).toBeGreaterThan(0);
      const cap = c.cls === 'bx-face' ? FACE_MAXPX : c.cls === 'bx-cosmos' ? COSMOS_MAXPX : Infinity;
      expect(c.w * c.h, c.cls + ' dentro del tope de píxeles').toBeLessThanOrEqual(cap * 1.02);
    }
    const centred = await page.evaluate(() => {
      const f = document.querySelector('.bx-face')!.getBoundingClientRect(), m = document.querySelector('.bx-center')!.getBoundingClientRect();
      return f.width > 0 && Math.abs((f.left + f.right) / 2 - (m.left + m.right) / 2) < 2;
    });
    expect(centred, 'la cara está centrada en su columna').toBe(true);
    // fold and open the chat 12 times, some mid-transition: no dots piled on the canvases' borders, nothing outside
    for (let i = 0; i < 12; i++) {
      await page.evaluate(() => {
        const hide = [...document.querySelectorAll<HTMLButtonElement>('button')].find((b) => /ocultar conversación/i.test(b.title));
        if (hide) hide.click(); else document.querySelector<HTMLButtonElement>('.bx-ctr .bx-ib:not(.plain)')?.click();
      });
      await page.waitForTimeout(i % 3 === 0 ? 120 : 520);
    }
    await page.waitForTimeout(700);
    expect((await edgeLine(page, '.bx-face')).bad, 'sin línea de puntos en el borde de la cara').toBe(false);
    expect((await edgeLine(page, '.bx-cosmos')).bad, 'sin línea de puntos en el borde del cielo').toBe(false);
    A = await audit(page);
    for (const t1 = Date.now(); A.issues.length && Date.now() - t1 < 4000;) { await page.waitForTimeout(250); A = await audit(page); }
    expect(A.issues, 'tras plegar el chat nada se sale del marco').toEqual([]);
    // Settings fits the window
    await page.click('.bx-gear');
    await page.waitForTimeout(400);
    const panel = await page.evaluate(() => { const r = document.querySelector('.settings-panel')!.getBoundingClientRect(); return { l: r.left, t: r.top, r: r.right, b: r.bottom }; });
    expect(panel.l >= -1 && panel.t >= -1 && panel.r <= A.vw + 1 && panel.b <= A.vh + 1, 'Ajustes cabe en la ventana').toBe(true);
    await page.click('.panel-shroud', { position: { x: 2, y: 2 } });
    expect(app.errors.slice(errors), 'sin errores de consola').toEqual([]);
  });
}

test('arranque oculto: con la ventana a 0×0 no se aplica nada y al aparecer la escala se corrige sola', async () => {
  const { page } = app;
  await size(app, 1280, 720);
  await page.waitForTimeout(600);
  const before = await uiOf(page);
  // The host collapses the view while the window is hidden in the tray: innerWidth and innerHeight read 0.
  const kept = await page.evaluate(() => {
    const d = document.documentElement, w = Object.getOwnPropertyDescriptor(window, 'innerWidth')!, h = Object.getOwnPropertyDescriptor(window, 'innerHeight')!;
    const cw = Object.getOwnPropertyDescriptor(Element.prototype, 'clientWidth')!, ch = Object.getOwnPropertyDescriptor(Element.prototype, 'clientHeight')!;
    Object.defineProperty(window, 'innerWidth', { configurable: true, get: () => 0 });
    Object.defineProperty(window, 'innerHeight', { configurable: true, get: () => 0 });
    Object.defineProperty(d, 'clientWidth', { configurable: true, get: () => 0 });
    Object.defineProperty(d, 'clientHeight', { configurable: true, get: () => 0 });
    (window as unknown as { bxApplyScale: () => void }).bxApplyScale();
    const ui = getComputedStyle(d).getPropertyValue('--ui');
    Object.defineProperty(window, 'innerWidth', w); Object.defineProperty(window, 'innerHeight', h);
    delete (d as unknown as Record<string, unknown>).clientWidth; delete (d as unknown as Record<string, unknown>).clientHeight;
    void cw; void ch;
    return ui;
  });
  expect(parseFloat(kept), 'a 0×0 la escala no cambia').toBeCloseTo(before, 3);
  await size(app, 1920, 1080);
  await page.waitForTimeout(900);
  expect(Math.abs((await uiOf(page)) - 1.5), 'al aparecer la ventana la escala se corrige sola').toBeLessThan(0.002);
  const canvases = await page.evaluate(() => [...document.querySelectorAll('canvas')].map((c) => [c.width, c.height]));
  expect(canvases.every(([w, h]) => !(w === 300 && h === 150) && w > 0 && h > 0), 'los lienzos toman su tamaño real').toBe(true);
});

test('cambio de tamaño en vivo: vuelve a la escala correcta sin restos', async () => {
  const { page } = app;
  const errors = app.errors.length;
  const seq: [number, number][] = [[640, 400], [1920, 1080], [900, 900], [2560, 1080], [700, 1200], [1366, 768], [500, 380], [3840, 2160], [1280, 720]];
  for (const [w, h] of seq) { await size(app, w, h); await page.waitForTimeout(260); }
  for (const [w, h] of [[1000, 640], [1440, 900], [1100, 700]] as const) { await size(app, w, h); await page.waitForTimeout(60); }
  await size(app, 1280, 720);
  await page.waitForTimeout(900);
  expect(Math.abs((await uiOf(page)) - 1), 'vuelve a la escala 1×').toBeLessThan(0.002);
  const A = await audit(page);
  expect([...A.issues, ...A.cut], 'la disposición se recupera sin restos').toEqual([]);
  const face = await page.evaluate(() => { const c = document.querySelector<HTMLCanvasElement>('.bx-face')!; return { w: c.width, cw: c.clientWidth }; });
  expect(face.w, 'el lienzo se ajusta al nuevo tamaño').toBeGreaterThan(0);
  expect((await edgeLine(page, '.bx-face')).bad, 'sin líneas de puntos en los bordes').toBe(false);
  expect(app.errors.slice(errors), 'sin errores de consola').toEqual([]);
});
