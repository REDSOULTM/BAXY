import { chromium, type Browser } from '@playwright/test';
import { existsSync, readdirSync } from 'node:fs';
import { homedir } from 'node:os';
import { join } from 'node:path';

/* A headless browser for the tests that need a page but not the app (styles, components on their own): Playwright's
   own headless Chromium, or, when this Playwright's build is not downloaded (nothing is downloaded here), the newest
   headless shell already in the Playwright cache. No window is ever shown. */

export async function headless(): Promise<Browser> {
  try {
    return await chromium.launch({ headless: true });
  } catch (e) {
    const cache = process.env.PLAYWRIGHT_BROWSERS_PATH ?? join(homedir(), 'AppData', 'Local', 'ms-playwright');
    const shells = existsSync(cache) ? readdirSync(cache).filter((d) => /^chromium_headless_shell-\d+$/.test(d)).sort((a, b) => +b.split('-')[1] - +a.split('-')[1]) : [];
    for (const d of shells) {
      const exe = join(cache, d, 'chrome-win', 'headless_shell.exe');
      if (existsSync(exe)) return chromium.launch({ headless: true, executablePath: exe });
    }
    throw e;
  }
}
