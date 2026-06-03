window(...): ventanas OS top-level. Actions: list, active, focus, close, minimize, maximize, restore, move_resize.
USAR para ops window-level de CUALQUIER app, incl browser (cerrar/minimizar ventana browser=window, NO browser). browser=tabs+contenido; window=el chrome.
close(query|title): substring de título VISIBLE, case-insensitive. App en foco -> action='active'.
window.close != app.close: app.close MATA el proceso; window.close solo descarta la ventana.
