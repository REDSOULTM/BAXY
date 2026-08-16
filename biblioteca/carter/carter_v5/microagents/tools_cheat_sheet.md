---
name: tools_cheat_sheet
triggers: ["que puedes", "qué puedes", "que sabes hacer", "qué sabes hacer", "tus herramientas", "tools disponibles", "lista de herramientas"]
priority: medium
---

# Carter v5 — Tools cheat sheet

## Composite tools (16, consolidated catalog)

| Tool | What it does | Example trigger |
|---|---|---|
| `system_info` | hora, cpu, ram, gpu, disco, batería, volumen | "qué hora es", "cuánto cpu uso" |
| `system_control` | set_volume, mute, shutdown, reboot | "subí volumen", "muteá" |
| `app` | open, close, uninstall apps | "abre Notepad" |
| `gui` | screenshot, click, type, keypress, locate, describe | "mostrame qué hay" |
| `gui_deeplink` | URI handler para Steam, Spotify, Discord, VSCode, etc. | "abre Steam" |
| `window` | list, manage, arrange windows | "qué ventanas" |
| `process` | list_processes | "qué corre" |
| `filesystem` | list/read/write/delete/rename/copy/move/search | "leé archivo X" |
| `web` | open_url, search, fetch | "buscá Python docs" |
| `terminal_run` | ejecuta binario en terminal | "ejecuta python --version" |
| `memory` | save/recall/delete/list facts | "recordá que X" |
| `media` | play_pause, next, prev | "pausa la música" |
| `clipboard` | read/write portapapeles | "copia esto" |
| `office` | crear docx/pptx/xlsx | "armá un doc" |
| `registry` | leer Windows registry | "leé HKLM\..." |
| `skill_load` | cargar skill curado externo | (avanzado) |

## Cómo elegir

- "abre X" → `app` o `gui_deeplink` (preferí deeplink si X es Steam/Spotify/Discord/VSCode).
- "buscá X" → `web` para web search, `filesystem` para local.
- "leé/escribí archivo" → `filesystem`.
- "ejecutá comando" → `terminal_run`.
- "qué hora/cpu/ram" → `system_info`.
- "mostrame pantalla" → `gui` (screenshot + describe).

## Negación importante

- "no abrir X / solo dime si está / sin ejecutar" → SOLO read-only tools (`process`, `filesystem.list`, etc.), NUNCA `app.open`.
