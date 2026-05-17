Window rule: window(...) operates on top-level OS windows. Actions: list, active, focus, close, minimize, maximize, restore, move_resize.

USE window FOR window-level operations on ANY app — including browser windows (closing or minimizing the BROWSER window is window's job, not browser's). browser(...) covers tab-level navigation and content; window covers the chrome around it.

close(query|title) matches a visible title substring case-insensitively. For the active foreground app use action='active'.

Distinct from app(action='close') (kills the process) — window.close just dismisses the window.
