# Inventario arqueológico Carter → BAXY

Estado: inventario cerrado sobre el cutoff histórico `2026-07-14T10:51:49.161254Z`.

## Fuentes inspeccionadas

- Git completo: `master`, `Gemma4`, `codex/tool-ecosystem-v2`, tag `backup-pre-export-voz-jarvis`, commits `4a83f2d`, `6dd84f9`, `f1c76b4`, `ba6bf11`, `ee06786` y el linaje v3 hasta el baseline `c5a1295`.
- Snapshot local de solo lectura `legacy/`, incluyendo `tooling/`, `tools/`, `legacy_export/tools_full/`, providers, workflows y pruebas.
- Manifest y reporte del cutoff; los tres JSONL históricos; ledgers 07/09; ADR-0005; `GATES_MENTE.md`; frontera vigente; README de `baxy_mind`; catálogo y `hello` actuales.
- Código eliminado localizado con `git log --all --diff-filter=D`: ecosistema v2, providers, oráculos, workflows y más de cien pruebas fueron retirados del árbol v3 en `d3b92a3`, no inexistentes.

## Activos encontrados

El activo histórico más completo es Tool Ecosystem v2 (`6dd84f9`→`ba6bf11`): registro congelable, 94 contratos (91 públicos y 3 en cuarentena), schemas cerrados, riesgo, confirmaciones, invoker, verificadores, journal, replay, providers Windows y pruebas. La corrida arqueológica actual aprobó 529 pruebas seleccionadas. Se reutiliza por cortes; no se porta su gateway conversacional, router, workflows multipaso ni planner.

| Familia canónica | Alias/operaciones históricas principales | Misiones / mensajes | Procedencia primaria | Implementación histórica | Equivalente v3 al baseline | Decisión |
|---|---|---:|---|---|---|---|
| `app.open` | `app.open`, apps launcher | 38 / 307 | `tooling/providers/desktop.py`, `tools/apps.py`, `9c67495` | provider Windows + verificador | `app.open` allowlist Notepad | conservar-actual |
| `app.close` | `app.resolve_close_targets`, `app.close_targets` | 6 / 62 | v2 `desktop.py`, workflows `desktop_close_safely` | handle + cierre verificado | no | adaptar-al-contrato-actual |
| `window.manage` | `window.resolve/focus/minimize/maximize/restore` | 29 / 178 | v2 `windows_control.py` | IDs efímeros, revalidación y verifier | no | adaptar-al-contrato-actual |
| `audio.volume` | `audio.set_volume`, `volume_up/down` | 21 / 277 | v2 `desktop.py`; v3 `33b62bc`, `17d85bd` | Core Audio y postlectura | `audio.volume` | conservar-actual |
| `audio.mute` | `audio.set_mute` | 8 / 108 | mismas fuentes de audio | Core Audio y postlectura | `audio.mute` | conservar-actual |
| `audio.status` | `audio.status`, now volume | 1 / 16 | mismas fuentes; enmienda corpus v3 | lectura Core Audio | `audio.status` | conservar-actual |
| `media.play` | `media.play`, `spotify.play_exact` | 49 / 524 | v2 `desktop.py`, `spotify_play*.py`; D20/D21 | SMTC/Spotify, gates parciales | no | adaptar-al-contrato-actual |
| `media.control` | `media.pause/next/previous/stop`, `now_playing` | 22 / 199 | v2 `desktop.py`, `tools/media.py` | SMTC + verificación | no | portar-sin-cambios-funcionales |
| `streaming.navigate` | streaming/media apps | 35 / 230 | `tools/streaming*`, `legacy_export/.../media_apps.py` | adapters de apps/web | no | adaptar-al-contrato-actual |
| `web.search` | `web.search` | 45 / 321 | v2 `services.py`, `tools/web_search.py` | provider remoto read-only | no | adaptar-al-contrato-actual |
| `browser.navigate` | browser v2 open/navigate/read | 24 / 164 | `tooling/providers/browser_v2.py`, `browser_v2_identity.py` | CDP con identidad y lifecycle | no | completar-implementacion-parcial |
| `reminder.create` | reminder create/list/resolve/delete, timer | 6 / 79 | v2 `reminders.py`, `services.py`, D33 | store durable + scheduler | no | portar-sin-cambios-funcionales |
| `calendar.manage` | `calendar.local_*` | 15 / 194 | v2 `local_calendar_v2.py`, Windows binding | contrato y provider opt-in | no | adaptar-al-contrato-actual |
| `note.manage` | note create/list/read/search/update/delete/restore | 9 / 65 | v2 `notes.py`; v3 `c1c07ff`, `fa08653` | ambos completos en sus contratos | 5 primitivas, sin update/search | fusionar-con-implementacion-actual |
| `task.manage` | task create/list/search/update/complete/reopen/delete/restore | 63 / 681 | v2 `tasks.py` | store durable + verificadores | no | portar-sin-cambios-funcionales |
| `filesystem.search` | search/list/stat/hash | 4 / 20 | v2 `filesystem.py` | sandbox de rutas | no | adaptar-al-contrato-actual |
| `filesystem.read` | read_text/stat/hash | 5 / 28 | misma fuente | lectura acotada | no | adaptar-al-contrato-actual |
| `filesystem.write` | create_directory/write_text | 8 / 77 | v2 `filesystem.py` | write transaccional; write quedó cuarentena | no | reemplazar-con-motivo |
| `filesystem.transfer` | copy/move/archive | 3 / 15 | v2 `filesystem_transfer.py` | copy/move verificados | no | adaptar-al-contrato-actual |
| `filesystem.trash` | prepare/commit/restore | 4 / 42 | v2 filesystem + workflow exacto | handle, confirmación y compensación | no | portar-sin-cambios-funcionales |
| `office.document` | office document v2 | 23 / 120 | `office_document_v2.py` | seam + dobles; dependencia Office | no | adaptar-al-contrato-actual |
| `message.send` | WhatsApp resolve/send; Discord v2 | 12 / 98 | v2 `services.py`, `discord_message_v2.py`, D33 | recipient handle + verifier | no | adaptar-al-contrato-actual |
| `system.status` | status/battery/disks/GPU | 25 / 294 | v2 `desktop.py`; v3 `88cb456`, `cf44b89` | v3 superior, DXGI+PDH | `system.status` | conservar-actual |
| `system.settings` | device settings, brightness, display | 14 / 89 | `legacy_export/domain_tools/device_settings.py` | implementación monolítica insegura | no | reemplazar-con-motivo |
| `system.power` | shutdown/restart/sleep/lock | 8 / 157 | legacy system tools | efecto real sin frontera actual | no | reemplazar-con-motivo |
| `wifi.manage` | wifi/network | 5 / 61 | `domain_tools/wifi.py`, v2 network read-only | lectura segura; mutación legacy débil | no | completar-implementacion-parcial |
| `bluetooth.manage` | bluetooth/device | 4 / 28 | `domain_tools/bluetooth.py` | prototipo histórico | no | reemplazar-con-motivo |
| `package.install` | install/update/uninstall | 1 / 5 | legacy package tools; setup v3 | setup v3 solo BAXY | no | reemplazar-con-motivo |
| `game.install` | Steam install prepare/commit/dialog | 5 / 74 | v2 `steam_install*.py` | provider opt-in y gates con doble | no | adaptar-al-contrato-actual |
| `game.manage` | Steam catalog/status/navigation | 6 / 160 | v2 `steam.py`, `steam_catalog_snapshot.py` | consulta local parcial | no | completar-implementacion-parcial |
| `game.purchase` | purchase | 2 / 6 | corpus + reglas legacy | no hay provider seguro reutilizable | no | reemplazar-con-motivo |
| `game.launch` | game launcher/Steam | 2 / 46 | `domain_tools/game_launcher.py`, `tools/apps_engine/steam_store.py` | launch por AppID parcial | no | adaptar-al-contrato-actual |
| `vision.describe` | describe/identify | 48 / 318 | v2 `vision_attachment.py`, legacy vision | captura ligada + VLM externo | no | adaptar-al-contrato-actual |
| `ocr.read` | `vision.ocr` | 7 / 15 | mismas fuentes | OCR provider con captura | no | portar-sin-cambios-funcionales |
| `capture.screenshot` | `vision.capture` | 14 / 95 | mismas fuentes | captura local tipada | no | adaptar-al-contrato-actual |
| `memory.save` | save/sensitive.save/correct | 9 / 102 | v3 `2a4ad21`→`478a19a` | DPAPI, envelope y postlectura | `memory.*` | conservar-actual |
| `memory.recall` | recall/list/status/export | 9 / 44 | mismas fuentes | provider privado | `memory.*` | conservar-actual |
| `memory.forget` | forget/session.clear/disable | 9 / 36 | mismas fuentes | confirmación y ausencia | `memory.*` | conservar-actual |
| `clipboard.manage` | read/write text | 6 / 36 | v2 `clipboard.py` | provider y verifier | no | adaptar-al-contrato-actual |
| `notification.manage` | timer/reminder/notification | 29 / 525 | v2 reminders + legacy notifications | recordatorios/timer útiles | no | fusionar-con-implementacion-actual |
| `routine.manage` | routine list/read/enable/delete/restore | 4 / 19 | v2 `routines.py`, `routines_v2.py` | store y verificadores | no | portar-sin-cambios-funcionales |
| `backup.manage` | backup/sync/restore | 9 / 37 | `domain_tools/backup_sync.py`; filesystem backup handle | implementación fragmentaria | no | completar-implementacion-parcial |
| `peripheral.manage` | printer/scanner/peripheral | 6 / 26 | `peripheral.py`, `printer_scanner.py` | prototipos dependientes de hardware | no | reemplazar-con-motivo |

## Descartes explícitos

- Se descartan parsers de frases, regex de intención, routers, gateway conversacional, compound mission y workflows como runtime de producción: son mente/planner o mezclan una misión completa.
- Las tres operaciones v2 en cuarentena (`filesystem.archive_extract`, `filesystem.restore_backup`, `filesystem.write_text`) no se publican sin corregir la carrera check/use y el cierre transaccional descritos por el propio historial.
- No se portan credenciales, rutas personales, UI automation sin handles, éxitos sin verifier ni acciones monetarias reales.
