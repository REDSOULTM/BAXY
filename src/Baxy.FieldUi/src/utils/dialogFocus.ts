import { useCallback, useEffect, useRef } from 'react';

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
    // its «Cancelar» first when it has one (data-cancel: a question asked in a panel), else the panel itself
    (el?.querySelector<HTMLElement>('[data-cancel]') ?? el)?.focus({ preventScroll: true });
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

/** An ask inside a panel (role=dialog or alertdialog: uninstall, remove, change the context, Sin frenos). REV_VISTA V-12
 *  (2026-11-09): it took no Escape (Escape closed all of Settings) and Tab walked out of it. Following WAI-ARIA APG's dialog
 *  (https://www.w3.org/WAI/ARIA/apg/patterns/dialog-modal/): Escape is its «Cancelar», Tab goes round inside it, its first
 *  focus is its own (its «Cancelar», marked data-cancel, else its first control) and the focus goes back to what had it when it closes.
 *  A callback ref (React 19 runs its cleanup on unmount); its listener is the element's own, ahead of the panel's and the
 *  window's, which never see these keys. */
export function useInnerDialog<T extends HTMLElement>(onCancel: () => void) {
  const cancel = useRef(onCancel);
  useEffect(() => { cancel.current = onCancel; });
  return useCallback((el: T | null) => {
    if (!el) return undefined;
    const back = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    const home = el.parentElement?.closest<HTMLElement>('[role="dialog"], [role="alertdialog"]') ?? null;
    // its «Cancelar» (data-cancel), not React's autoFocus: that one runs before this ref, and what had the focus is lost
    (el.querySelector<HTMLElement>('[data-cancel]') ?? el.querySelector<HTMLElement>(FOCUSABLE))?.focus({ preventScroll: true });
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') { e.preventDefault(); e.stopPropagation(); cancel.current(); return; }
      if (e.key !== 'Tab') return;
      e.stopPropagation();
      const to = wrapTab([...el.querySelectorAll<HTMLElement>(FOCUSABLE)], document.activeElement, e.shiftKey, el);
      if (to) { e.preventDefault(); to.focus(); }
    };
    el.addEventListener('keydown', onKey);
    return () => {
      el.removeEventListener('keydown', onKey);
      if (back?.isConnected) back.focus({ preventScroll: true });
      else home?.focus({ preventScroll: true });
    };
  }, []);
}
