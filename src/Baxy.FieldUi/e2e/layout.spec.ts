import { test } from '@playwright/test';
import { attach, ready, spanish } from './app';
import { layoutChecks } from './layoutChecks';

/* «Baxy pruebas.html» against the real app: the checks of layoutChecks.ts on BAXY's own window. */

let restoreLang: () => Promise<void>;
test.describe('ventana real', () => layoutChecks(
  async () => { const app = await attach(); await ready(app.page); restoreLang = await spanish(app.page); return app; },
  async (app) => { await restoreLang?.(); await app.browser.close(); }));
