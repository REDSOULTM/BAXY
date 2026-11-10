import { expect, test } from '@playwright/test';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { headless, ROOT } from './headless';

/* The App's bridge (src/Baxy.App/Assets/field-native-bridge.js), which turns each fetch of the view into a message to the
   host and gives a request up with a 503 at its limit. Loaded here as the App loads it, over a stand-in for WebView2's
   channel that never answers, with the page's clock moved by hand: what is tested is when the bridge stops waiting. */
const BRIDGE = readFileSync(join(ROOT, '..', 'Baxy.App', 'Assets', 'field-native-bridge.js'), 'utf8');

// REV_APP EST-a (2026-11-09): the App measures a model of Ollama's for up to 6 minutes (ExternalModel.MeasuredAsync) and lists
// them for up to 45 s after opening Ollama (another 45 s), and the bridge gave every GET up at 30 s: Settings said «No se pudo
// calcular: Ollama no respondió» while Ollama was still loading it, and the context could not be chosen until another model
// was. A request the App itself waits longer for is waited for as long; every other one keeps its 30 s.
test('puente: lo que la App tarda más de 30 s en responder no se da por perdido antes', async () => {
  const browser = await headless();
  try {
    const page = await browser.newPage();
    await page.route('http://baxy.test/', (r) => r.fulfill({ contentType: 'text/html', body: '<!doctype html><title>puente</title>' }));
    await page.clock.install();
    await page.addInitScript(() => {
      const w = window as unknown as { chrome?: { webview?: unknown } };
      w.chrome = { ...(w.chrome ?? {}), webview: { postMessage: () => undefined, addEventListener: () => undefined } };
    });
    await page.goto('http://baxy.test/');
    await page.addScriptTag({ content: BRIDGE });
    await page.evaluate(() => {
      const w = window as unknown as { given: Record<string, number> };
      w.given = {};
      const ask = (name: string, path: string, method = 'GET') => void fetch(path, { method, body: method === 'GET' ? undefined : '{}' }).then((r) => { w.given[name] = r.status; });
      ask('estimate', '/settings/external-model/estimate');
      ask('models', '/settings/external-model/models?provider=local');
      ask('search', '/settings/external-model/search', 'POST');
      ask('remove', '/settings/external-model/remove', 'POST');
      ask('state', '/settings/external-model');
      ask('put', '/settings/external-model', 'PUT');
    });
    const given = () => page.evaluate(() => (window as unknown as { given: Record<string, number> }).given);
    await page.clock.runFor(31_000);
    // control: a request the App answers at once is still given up at 30 s
    expect(await given()).toEqual({ state: 503, put: 503 });
    // the list: Ollama's start and the translator's answer, 45 s each
    await page.clock.runFor(60_000);
    expect(Object.keys(await given()).sort()).toEqual(['put', 'state']);
    await page.clock.runFor(30_000);
    expect((await given()).models).toBe(503);
    // the measure: 6 minutes, after Ollama's start
    await page.clock.runFor(285_000);
    expect((await given()).estimate).toBeUndefined();
    await page.clock.runFor(60_000);
    expect(await given()).toEqual({ state: 503, put: 503, models: 503, search: 503, remove: 503, estimate: 503 });
  } finally {
    await browser.close();
  }
});
