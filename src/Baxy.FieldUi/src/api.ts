/* The host's routes (FieldProductChannel). field-native-bridge.js turns each fetch into a typed WebView2 message:
   there is no HTTP server and no network. A failed request resolves to null; the caller keeps what it shows. */

export async function getJson<T>(path: string): Promise<T | null> {
  try {
    const r = await fetch(path);
    if (!r.ok) return null;
    return (await r.json()) as T;
  } catch {
    return null;
  }
}

/** sends a JSON body; returns the reply's JSON (or {} for an empty reply), or null when the host refused it. */
export async function send<T = Record<string, unknown>>(
  method: 'POST' | 'PUT' | 'DELETE',
  path: string,
  body?: unknown,
): Promise<T | null> {
  try {
    const r = await fetch(path, {
      method,
      headers: { 'Content-Type': 'application/json' },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
    if (!r.ok) return null;
    const text = await r.text();
    return (text ? JSON.parse(text) : {}) as T;
  } catch {
    return null;
  }
}

/** like send, telling apart a request the host refused (a 4xx with its error code: it took nothing) from one that got
 *  no answer (the bridge's 503 for a request that timed out or failed on the way: the host may have taken it). «code» is the
 *  host's own word for the refusal, for the caller to say its real cause. */
export async function sendTold<T = Record<string, unknown>>(
  method: 'POST' | 'PUT' | 'DELETE',
  path: string,
  body?: unknown,
): Promise<{ value: T | null; refused: boolean; code: string | null }> {
  try {
    const r = await fetch(path, {
      method,
      headers: { 'Content-Type': 'application/json' },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
    const text = await r.text();
    if (r.ok) return { value: (text ? JSON.parse(text) : {}) as T, refused: false, code: null };
    let code: unknown = null;
    try { code = (JSON.parse(text) as { error?: unknown }).error; } catch { /* no code */ }
    const said = r.status >= 400 && r.status < 500 && typeof code === 'string' ? code : null;
    return { value: null, refused: said !== null, code: said };
  } catch {
    return { value: null, refused: false, code: null };
  }
}
