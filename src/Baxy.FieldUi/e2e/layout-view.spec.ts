import { test } from '@playwright/test';
import { openView, stopHost, type Host } from './host';
import { layoutChecks } from './layoutChecks';

/* «Baxy pruebas.html» with no app and no model: the checks of layoutChecks.ts on the view the stand-in host opens, so
   a layout that breaks is seen wherever the specs without the app run. BAXY's own window is layout.spec.ts. */

let h: Host;
test.describe('vista sin app', () => layoutChecks(
  async () => {
    h = await openView();
    const errors: string[] = [];
    h.page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text().slice(0, 300)); });
    h.page.on('pageerror', (e) => errors.push(String(e).slice(0, 300)));
    return { browser: h.page.context().browser()!, page: h.page, cdp: await h.page.context().newCDPSession(h.page), errors };
  },
  async () => { await h.close(); await stopHost(); }));
