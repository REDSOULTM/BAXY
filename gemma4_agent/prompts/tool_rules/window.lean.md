window(...): ventanas OS top-level. Actions: list, active, focus, close, minimize, maximize, restore, move_resize.
USAR para ops window-level de CUALQUIER app, incl browser (cerrar/minimizar ventana browser=window, NO browser). browser=tabs+contenido; window=el chrome.
close(query|title): substring de título VISIBLE, case-insensitive.
"¿qué juego/app/ventana está abierta/en foco AHORA?" -> window(action='active') (sin target; el verbo 'jugando'/'playing' NO es un nombre). NUNCA app.search para esto.
window.close != app.close: app.close MATA el proceso; window.close solo descarta la ventana.
