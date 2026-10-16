/* Tiny global bus for failure toasts. Any module calls `toastError(msg)`
 * without a hook or context; the `<ToastHost />` component subscribes and
 * renders. A plain EventTarget, so callers don't pay the React tree cost —
 * they dispatch a CustomEvent and the host picks it up. Every toast is a
 * failure and goes away after 4 s or when the person closes it. */

import { useEffect, useState } from 'react';

const TTL_MS = 4000;

export interface Toast {
  id: string;
  msg: string;
  // wall-clock ts so the host can drop expired entries.
  bornAt: number;
}

const BUS = new EventTarget();
const EV = 'baxy:toast';

let _seq = 0;
function nextId(): string {
  _seq = (_seq + 1) & 0xffff;
  return `t${Date.now().toString(36)}${_seq.toString(36)}`;
}

/** A failure the person should see (a request that did not go through). */
export function toastError(msg: string): void {
  const t: Toast = { id: nextId(), msg, bornAt: Date.now() };
  BUS.dispatchEvent(new CustomEvent<Toast>(EV, { detail: t }));
}

export function useToasts(): { toasts: Toast[]; dismiss: (id: string) => void } {
  const [toasts, setToasts] = useState<Toast[]>([]);

  useEffect(() => {
    const onPush = (e: Event) => {
      const detail = (e as CustomEvent<Toast>).detail;
      setToasts((prev) => [...prev, detail]);
    };
    BUS.addEventListener(EV, onPush);
    return () => BUS.removeEventListener(EV, onPush);
  }, []);

  // GC expired toasts on a 500ms tick. Cheap and bounded — the toast list
  // is never more than a handful of entries.
  useEffect(() => {
    const id = window.setInterval(() => {
      const now = Date.now();
      setToasts((prev) =>
        prev.filter((t) => now - t.bornAt < TTL_MS)
      );
    }, 500);
    return () => window.clearInterval(id);
  }, []);

  const dismiss = (id: string) => setToasts((p) => p.filter((t) => t.id !== id));

  return { toasts, dismiss };
}
