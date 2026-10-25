import { useEffect, useRef } from 'react';

/** A panel takes the keyboard's focus when it opens (Tab then walks the panel, not the view under its veil) and gives
 *  it back to what had it, the button that opened it, when it closes. The ref goes on the dialog (tabIndex -1). */
export function useDialogFocus<T extends HTMLElement>() {
  const ref = useRef<T>(null);
  useEffect(() => {
    const back = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    ref.current?.focus({ preventScroll: true });
    return () => { if (back?.isConnected) back.focus({ preventScroll: true }); };
  }, []);
  return ref;
}
