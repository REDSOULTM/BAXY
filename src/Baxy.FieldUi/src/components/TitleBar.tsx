import { useCallback, useEffect, useState } from 'react';
import { Icon } from './Icon';

/** The window controls. The native bridge (Baxy.App's field-native-bridge.js,
 *  injected before the page loads) defines them under window.pywebview.api,
 *  the name the historical export used, and the host runs each as a
 *  window_command. */
interface WindowApi {
  win_minimize: () => Promise<unknown>;
  win_toggle_maximize: () => Promise<boolean>;
  win_close: () => Promise<unknown>;
  win_is_maximized: () => Promise<boolean>;
}
declare global {
  interface Window {
    pywebview: { api: WindowApi };
  }
}

/** A thin custom title bar that sits above the red instrument frame. The
 *  window has no native frame, so without this the user has no way to
 *  move/minimise/close it. The `.pywebview-drag-region` span is the drag
 *  handle (the bridge starts a native window drag on a primary press inside
 *  it); the buttons live OUTSIDE it so a click on a control isn't swallowed
 *  by the drag. */
export function TitleBar({ bypass }: { bypass: boolean }) {
  const [maximized, setMaximized] = useState(false);

  // Reflect the maximized state on <html> so the CSS can release the compact
  // size cap and let the instrument fill the whole window (like any normal app
  // when maximized); at rest it stays the centered compact instrument.
  useEffect(() => {
    const el = document.documentElement;
    if (maximized) el.setAttribute('data-maximized', 'true');
    else el.removeAttribute('data-maximized');
  }, [maximized]);

  // Reconcile the max/restore icon with the real window state on mount + when
  // the window regains focus (the OS can maximise via Win+Up / double-click the
  // drag region / aero-snap without going through our button).
  useEffect(() => {
    let cancelled = false;
    const sync = () => {
      window.pywebview.api.win_is_maximized()
        .then((m) => { if (!cancelled) setMaximized(!!m); })
        .catch(() => { /* ignore */ });
    };
    sync();
    // re-check on focus AND resize: the OS can maximize/restore via double-click
    // the drag region, Win+Up or aero-snap (no button), which fires a resize on
    // the webview content — keeps the expand/compact CSS in step every path.
    window.addEventListener('focus', sync);
    window.addEventListener('resize', sync);
    return () => {
      cancelled = true;
      window.removeEventListener('focus', sync);
      window.removeEventListener('resize', sync);
    };
  }, []);

  const onMinimize = useCallback(() => {
    window.pywebview.api.win_minimize().catch(() => { /* ignore */ });
  }, []);

  const onToggleMax = useCallback(() => {
    window.pywebview.api.win_toggle_maximize()
      .then((isMax) => setMaximized(!!isMax))
      .catch(() => { /* ignore */ });
  }, []);

  const onClose = useCallback(() => {
    window.pywebview.api.win_close().catch(() => { /* ignore */ });
  }, []);

  return (
    <div className="titlebar">
      {/* drag handle: title text + flexible spacer. NOT an ancestor of the
          buttons, so clicking a control never starts a window drag. */}
      <div className="titlebar-drag pywebview-drag-region">
        <span className="titlebar-title">
          <span className="accent">BAXY</span><span className="dim"> · desktop</span>
        </span>
        {/* Bypass is seen on at every moment while it is on (identity: a conscious
            setting that stays on until it is switched off). */}
        {bypass && (
          <span className="titlebar-bypass" role="status">
            bypass · sin confirmaciones
          </span>
        )}
      </div>
      <div className="titlebar-controls">
        <button
          type="button"
          className="winbtn"
          onClick={onMinimize}
          aria-label="minimizar"
          title="minimizar"
        >
          <Icon name="win-min" size={14} strokeWidth={1.4} />
        </button>
        <button
          type="button"
          className="winbtn"
          onClick={onToggleMax}
          aria-label={maximized ? 'restaurar' : 'maximizar'}
          title={maximized ? 'restaurar' : 'maximizar'}
        >
          <Icon name={maximized ? 'win-restore' : 'win-max'} size={14} strokeWidth={1.4} />
        </button>
        <button
          type="button"
          className="winbtn winbtn-close"
          onClick={onClose}
          aria-label="cerrar"
          title="cerrar"
        >
          <Icon name="x" size={14} strokeWidth={1.4} />
        </button>
      </div>
    </div>
  );
}
