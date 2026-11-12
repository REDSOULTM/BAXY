import { chromium, type Browser, type CDPSession, type Page } from '@playwright/test';

/* Attaches to the real BAXY window: Baxy.App started with WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS=--remote-debugging-port
   (scripts/test_field_ui.ps1 does it). The page is the Field view on its local virtual host. */

/** the engine's Sí / No card as the view draws it (Chat.tsx, kind «confirm»): the specs against the real app look for it
 *  by this, and view.spec checks the view really draws it */
export const CONFIRM_CARD = '.bx-card.k-confirm';
export const CDP_URL = process.env.BAXY_CDP_URL ?? 'http://127.0.0.1:9333';

export interface App {
  browser: Browser;
  page: Page;
  cdp: CDPSession;
  errors: string[];
}

export async function attach(): Promise<App> {
  const browser = await chromium.connectOverCDP(CDP_URL);
  const deadline = Date.now() + 60_000;
  let page: Page | undefined;
  while (!page && Date.now() < deadline) {
    page = browser.contexts().flatMap((c) => c.pages()).find((p) => /^https?:\/\/[^/]*baxy/i.test(p.url()) && !p.url().includes('about:blank'));
    if (!page) await new Promise((r) => setTimeout(r, 500));
  }
  if (!page) throw new Error('No BAXY page on ' + CDP_URL + ': ' + browser.contexts().flatMap((c) => c.pages()).map((p) => p.url()).join(', '));
  const errors: string[] = [];
  page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text().slice(0, 300)); });
  page.on('pageerror', (e) => errors.push(String(e).slice(0, 300)));
  const cdp = await page.context().newCDPSession(page);
  return { browser, page, cdp, errors };
}

/** The specs read the view's Spanish words: the real host's language is set to Spanish (whatever Windows' is) until the
 *  returned function puts the person's choice back. */
export async function spanish(page: Page): Promise<() => Promise<void>> {
  const put = (lang: string) => page.evaluate(async (l) => {
    await fetch('/settings/language', { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ lang: l }) });
  }, lang);
  const was = await page.evaluate(async () => { const r = await fetch('/settings/general'); return r.ok ? ((await r.json()).language ?? 'auto') : 'auto'; });
  await put('es');
  await page.waitForFunction(() => document.documentElement.lang === 'es', undefined, { timeout: 15_000 });
  return () => put(was);
}

/** Lays the view out at w×h CSS pixels (device scale 1), as a window of that size would. */
export async function size(app: App, w: number, h: number): Promise<void> {
  await app.cdp.send('Emulation.setDeviceMetricsOverride', { width: w, height: h, deviceScaleFactor: 1, mobile: false });
}

export async function unsize(app: App): Promise<void> {
  await app.cdp.send('Emulation.clearDeviceMetricsOverride');
}

/** Waits until the view shows its state and the face (the layout does not need the model loaded). */
export async function ready(page: Page, timeout = 90_000): Promise<void> {
  await page.waitForFunction(() => {
    const s = document.querySelector('.bx-statel');
    return !!s && !!document.querySelector('.bx-face');
  }, undefined, { timeout });
}
