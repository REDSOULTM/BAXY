import { useEffect, useRef } from 'react';

const FOCUSABLE = 'button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), a[href], [tabindex]:not([tabindex="-1"])';

/** Where Tab goes inside a dialog: from its last control (or the dialog itself, going back) round to the other end, so
 *  the focus never walks out to the view under the veil (final 4, accesibilidad: aria-modal said so, Tab did not).
 *  null leaves Tab to the browser. */
export function wrapTab(focusables: readonly HTMLElement[], active: Element | null, back: boolean, dialog: Element | null): HTMLElement | null {
  if (!focusables.length) return null;
  const first = focusables[0], last = focusables[focusables.length - 1];
  if (back && (active === first || active === dialog)) return last;
  if (!back && active === last) return first;
  return null;
}

/** A panel takes the keyboard's focus when it opens (Tab then walks the panel, not the view under its veil) and gives
 *  it back to what had it, the button that opened it, when it closes. The ref goes on the dialog (tabIndex -1). */
export function useDialogFocus<T extends HTMLElement>() {
  const ref = useRef<T>(null);
  useEffect(() => {
    const back = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    const el = ref.current;
    el?.focus({ preventScroll: true });
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== 'Tab' || !el) return;
      const to = wrapTab([...el.querySelectorAll<HTMLElement>(FOCUSABLE)], document.activeElement, e.shiftKey, el);
      if (to) { e.preventDefault(); to.focus(); }
    };
    el?.addEventListener('keydown', onKey);
    return () => {
      el?.removeEventListener('keydown', onKey);
      if (back?.isConnected) back.focus({ preventScroll: true });
    };
  }, []);
  return ref;
}
