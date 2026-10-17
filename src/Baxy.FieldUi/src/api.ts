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
