import { toastError } from './useToast';

/** POST /sessions/new — the host clears the transcript, the model's session and anything pending, then publishes
 *  log_clear and session. A refusal (turn_in_progress) is shown with its own code; nothing is reset here. */
export async function startNewSession(): Promise<boolean> {
  try {
    const r = await fetch('/sessions/new', { method: 'POST' });
    if (r.ok) return true;
    const data = (await r.json().catch(() => ({}))) as { error?: string };
    toastError(`new session · ${data.error ?? `status ${r.status}`}`);
  } catch (e) {
    toastError(`new session · ${String(e).replace(/^Error: /, '')}`);
  }
  return false;
}
