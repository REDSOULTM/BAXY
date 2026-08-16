import { useCallback, useEffect, useState } from 'react';
import { Icon } from './Icon';

/** pywebview exposes the controller passed as `js_api=` under
 *  window.pywebview.api. The launcher wires minimize/toggle_maximize/close +
 *  is_maximized (see launcher.py _WindowControls). In a plain browser / vite
 *  dev there is no pywebview object — the buttons degrade gracefully (close
 *  falls back to window.close(), min/max no-op). */
interface PyWebviewApi {
  win_minimize?: () => Promise<unknown>;
  win_toggle_maximize?: () => Promise<boolean>;
  win_close?: () => Promise<unknown>;
  win_is_maximized?: () => Promise<boolean>;
}
declare global {
  interface Window {
    pywebview?: { api?: PyWebviewApi };
  }
}

function api(): PyWebviewApi | null {
  return (typeof window !== 'undefined' && window.pywebview?.api) || null;
}

/** A thin custom title bar that sits above the red instrument frame. The
 *  window is created frameless (launcher.py) so without this the user has no
 *  way to move/minimise/close the window. The `.pywebview-drag-region` span is
 *  the native drag handle; the buttons live OUTSIDE it so a click on a control
 *  isn't swallowed by the drag (pywebview starts a drag when the mousedown
 *  target — or any ancestor — is the drag region). */
export function TitleBar() {
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
    const a = api();
    if (!a?.win_is_maximized) return;
    let cancelled = false;
    const sync = () => {
      a.win_is_maximized!()
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
    api()?.win_minimize?.().catch(() => { /* ignore */ });
  }, []);

  const onToggleMax = useCallback(() => {
    const a = api();
    if (!a?.win_toggle_maximize) { setMaximized((m) => !m); return; }
    a.win_toggle_maximize()
      .then((isMax) => setMaximized(!!isMax))
      .catch(() => { /* ignore */ });
  }, []);

  const onClose = useCallback(() => {
    const a = api();
    if (a?.win_close) { a.win_close().catch(() => { /* ignore */ }); return; }
    // browser / dev fallback
    window.close();
  }, []);

  return (
    <div className="titlebar">
      {/* drag handle: title text + flexible spacer. NOT an ancestor of the
          buttons, so clicking a control never starts a window drag. */}
      <div className="titlebar-drag pywebview-drag-region">
        <span className="titlebar-title">
          gemma <span className="accent">4</span> <span className="dim">· field</span>
        </span>
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
