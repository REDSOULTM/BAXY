Window rule: window(...) operates on top-level OS windows. Actions: list, active, focus, close, minimize, maximize, restore, move_resize.

USE window FOR window-level operations on ANY app — including browser windows (closing or minimizing the BROWSER window is window's job, not browser's). browser(...) covers tab-level navigation and content; window covers the chrome around it.

close(query|title) matches a visible title substring case-insensitively.

active() answers "what app/game/window is in the FOREGROUND right now" — the foreground window IS the active game/app. Use it for state QUESTIONS like "¿qué juego estoy jugando?" / "what app is open" / "che gioco sto giocando?". It takes NO target; never pass the question's verb ('jugando'/'playing') as a name. Do NOT use app.search for this — that searches INSTALLED apps by name, not what's running.

Distinct from app(action='close') (kills the process) — window.close just dismisses the window.
