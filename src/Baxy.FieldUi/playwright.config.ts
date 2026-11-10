import { defineConfig } from '@playwright/test';
import { readdirSync, readFileSync } from 'node:fs';

/* The view's acceptance tests (design_handoff_baxy «Baxy pruebas.html», ported), in two projects:
   - «app»: the specs that attach to BAXY's own window (e2e/app.ts). BAXY is started with WebView2's remote debugging
     port (scripts/test_field_ui.ps1) and the tests attach to it over CDP; no browser is downloaded and nothing is served.
   - «vista»: every other spec. They import the view's own modules, or open it in a headless browser, alone or against
     the stand-in host (e2e/host.ts): no app, no model. `pnpm test` runs them all.
   Which is which is read from the specs themselves (the ones that import `attach` from e2e/app.ts), so a new one is
   never left out of both. */
const e2e = new URL('./e2e/', import.meta.url);
const attaches = /^import\s*\{[^}]*\battach\b[^}]*\}\s*from\s*'\.\/app';/m;
const app = readdirSync(e2e).filter((f) => f.endsWith('.spec.ts') && attaches.test(readFileSync(new URL(f, e2e), 'utf8'))).map((f) => '**/' + f);

export default defineConfig({
  testDir: './e2e',
  fullyParallel: false,
  workers: 1,
  retries: 0,
  timeout: 120_000,
  reporter: [['list']],
  projects: [
    { name: 'vista', testIgnore: app },
    { name: 'app', testMatch: app },
  ],
});
