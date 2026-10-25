import { chromium, type Browser, type Page, type WebSocketRoute } from '@playwright/test';
import { createServer, type ViteDevServer } from 'vite';
import { fileURLToPath } from 'node:url';

/* A stand-in for Baxy.App, for the view's logic without the real app: Vite serves the view's own sources, a headless
   browser opens it (Edge by default; BAXY_TEST_BROWSER names another executable), and the host's routes and its
   `/events` socket are answered here. Nothing opens a window and nothing leaves the PC. */

const ROOT = fileURLToPath(new URL('..', import.meta.url));
const ROUTES = /^\/(turn|confirmation|accessibility|settings|proposals|metrics|triggers|surfaces|sessions|voice|power|memory|catalog|agent)(\/|$)/;

export interface Call { method: string; path: string; body: unknown }

export interface Host {
  page: Page;
  /** every call the view made to the host's routes, in order. */
  calls: Call[];
  /** sends one host event over `/events`. */
  emit: (ev: Record<string, unknown>) => void;
  /** the reply to a route: a JSON body, or a status for a refusal; default {}. */
  reply: (path: string, fn: (c: Call) => { status?: number; body?: unknown }) => void;
  close: () => Promise<void>;
}

let server: ViteDevServer | null = null;
let browser: Browser | null = null;

async function base(): Promise<string> {
  if (!server) {
    server = await createServer({ root: ROOT, configFile: `${ROOT}/vite.config.ts`, logLevel: 'silent', server: { host: '127.0.0.1', port: 0, hmr: false } });
    await server.listen();
  }
  return server.resolvedUrls!.local[0];
}

export async function stopHost(): Promise<void> {
  await browser?.close(); browser = null;
  await server?.close(); server = null;
}

/** opens the view against a host that is up, powered and idle with the given transcript. */
export async function openView(opts: { items?: unknown[]; mic?: string } = {}): Promise<Host> {
  const url = await base();
  browser ??= process.env.BAXY_TEST_BROWSER
    ? await chromium.launch({ executablePath: process.env.BAXY_TEST_BROWSER })
    : await chromium.launch({ channel: 'msedge' });
  const ctx = await browser.newContext({ viewport: { width: 1400, height: 860 } });
  const page = await ctx.newPage();
  const calls: Call[] = [];
  const replies = new Map<string, (c: Call) => { status?: number; body?: unknown }>();
  let socket: WebSocketRoute | null = null;
  // like the host, a socket that connects gets the state so far (StrictMode connects twice)
  const history: string[] = [];
  const emit = (ev: Record<string, unknown>) => { const m = JSON.stringify(ev); history.push(m); socket?.send(m); };

  await page.route((u) => ROUTES.test(u.pathname), async (route) => {
    const req = route.request();
    const path = new URL(req.url()).pathname;
    let body: unknown;
    try { body = req.postDataJSON(); } catch { body = req.postData(); }
    const call = { method: req.method(), path, body };
    calls.push(call);
    const r = replies.get(path)?.(call) ?? {};
    await route.fulfill({ status: r.status ?? 200, contentType: 'application/json', body: JSON.stringify(r.body ?? {}) });
  });
  await page.routeWebSocket(/\/events$/, (ws) => {
    socket = ws;
    for (const m of history) ws.send(m);
  });
  await page.addInitScript((mic) => { try { localStorage.setItem('bx-avatar', 'live'); if (mic) localStorage.setItem('baxy.mic', mic); } catch { /* none */ } }, opts.mic ?? 'off');

  emit({ type: 'agent', built: true, ready: true, powered: true });
  emit({ type: 'boot', stt: true, wake: true, tts: true, model: true, startedAt: 1, readyAt: 2 });
  emit({ type: 'voice', available: true, mode: 'off', speaking: false });
  emit({ type: 'state', value: 'idle' });
  emit({ type: 'transcript', items: opts.items ?? [] });
  await page.goto(url);
  await page.waitForSelector('.bx-statel');
  return {
    page, calls, emit,
    reply: (path, fn) => { replies.set(path, fn); },
    close: () => ctx.close(),
  };
}

/** a card waiting for the person's Sí or No. */
export function card(id: string, over: Record<string, unknown> = {}) {
  return { who: 'card', id, ts: '12:00', kind: 'confirm', title: 'Borrar notas.txt', target: 'Escritorio', expires: Date.now() + 120_000, status: 'pending', ...over };
}
