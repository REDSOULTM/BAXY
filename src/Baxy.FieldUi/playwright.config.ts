import { defineConfig } from '@playwright/test';

/* The view's acceptance tests (design_handoff_baxy «Baxy pruebas.html», ported). They run against the real app: BAXY is
   started with WebView2's remote debugging port (scripts/test_field_ui.ps1) and the tests attach to it over CDP;
   no browser is downloaded and nothing is served. The pure-logic tests import the view's own modules. */
export default defineConfig({
  testDir: './e2e',
  fullyParallel: false,
  workers: 1,
  retries: 0,
  timeout: 120_000,
  reporter: [['list']],
});
