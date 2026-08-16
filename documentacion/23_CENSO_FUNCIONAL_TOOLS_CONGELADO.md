# Censo funcional de tools (congelado)

Congelado: 2026-07-16, después de inspeccionar todas las referencias Git locales, el snapshot `legacy/`, el corpus de 2.084 misiones/14.836 mensajes y el catálogo ejecutable. Congelar significa que las 43 filas no crecerán; los cortes solo pueden cambiar su estado y evidencia.

| Operación/familia | Alias históricos | Misiones / mensajes | Implementación al congelar | Brecha comprobada | Estrategia/provider/verificador | Riesgo | Estado tras corte ventana |
|---|---|---:|---|---|---|---|---|
| `app.open` | apps launch | 38 / 307 | Notepad+Calculadora; apps especializadas separadas | ninguna del censo | adapters de identidad por app + postlectura | baja reversible | `cubierta-y-verificada` |
| `app.close` | close_targets | 6 / 62 | `app.close` portado | falta gate físico mutante | windowId + WM_CLOSE + ausencia verificada | pérdida de trabajo | `cubierta-y-verificada` |
| `window.manage` | resolve/focus/min/max/restore/move/resize | 29 / 178 | 7 tools nuevas | ninguna; close vive en `app.close` | provider Win32 + identidad efímera + verifier separado | baja reversible | `cubierta-y-verificada` |
| `audio.volume` | set/up/down | 21 / 277 | ejecutable | relativo componible con status+absolute | conservar Core Audio | baja reversible | `cubierta-y-verificada` |
| `audio.mute` | set_mute | 8 / 108 | ejecutable | ninguna | conservar Core Audio | baja reversible | `cubierta-y-verificada` |
| `audio.status` | now volume | 1 / 16 | ejecutable | ninguna | conservar lectura endpoint | solo lectura | `cubierta-y-verificada` |
| `media.play` | spotify exact | 49 / 524 | contrato+seam+probe | falta sesión Spotify autenticada | adapter oficial + now-playing verifier | externa | `bloqueada-por-dependencia-externa` |
| `media.control` | pause/next/previous/stop | 22 / 199 | contrato+seam SMTC | no hay sesión SMTC seleccionable en gate | adapter SMTC + postlectura | baja reversible | `bloqueada-por-entorno` |
| `streaming.navigate` | streaming apps | 35 / 230 | contrato+seam | falta sesión autenticada por servicio | resourceUri exacta + postlectura | externa | `bloqueada-por-dependencia-externa` |
| `web.search` | web.search | 45 / 321 | contrato+seam | proveedor web no configurado | provider oficial + resultados acotados | solo lectura remota | `bloqueada-por-dependencia-externa` |
| `browser.navigate` | browser v2 | 24 / 164 | contrato+seam CDP | no hay sesión CDP autenticada | URL exacta + postlectura | externa | `bloqueada-por-dependencia-externa` |
| `reminder.create` | reminder/timer | 6 / 79 | 5 tools portadas | ninguna del lifecycle durable | store separado + reloj UTC + postlectura | baja reversible | `cubierta-y-verificada` |
| `calendar.manage` | calendar.local_* | 15 / 194 | create/list con seam | cuenta no autorizada | adapter de cuenta + identidad remota | externa | `bloqueada-por-dependencia-externa` |
| `note.manage` | note CRUD/search | 9 / 65 | 7 tools v3 | ninguna; delete se modela como trash reversible | LocalNoteStore + relectura | reversible | `cubierta-y-verificada` |
| `task.manage` | task lifecycle | 63 / 681 | 9 tools portadas | ninguna del ciclo CRUD/CAS histórico | LocalTaskStore sobre documentos íntegros + postlectura | reversible | `cubierta-y-verificada` |
| `filesystem.search` | list/stat/hash/search | 4 / 20 | list/search/hash portadas | ninguna dentro del sandbox explícito | LocalFilesystemProvider + IDs opacos | solo lectura | `cubierta-y-verificada` |
| `filesystem.read` | read_text | 5 / 28 | read.text portado | ninguna dentro del sandbox explícito | UTF-8 acotado + SHA-256 | solo lectura | `cubierta-y-verificada` |
| `filesystem.write` | mkdir/write | 8 / 77 | create.directory/write.text nuevas | ninguna; reemplazo exige CAS por hash | escritura temporal + rename + posthash | reversible | `cubierta-y-verificada` |
| `filesystem.transfer` | copy/move/archive | 3 / 15 | copy/move portadas | archive queda en backup, no es primitiva necesaria aquí | identidad revalidada + hash/ausencia | reversible | `cubierta-y-verificada` |
| `filesystem.trash` | prepare/commit/restore | 4 / 42 | tres tools portadas | ninguna | handle de un uso + papelera privada + verifier | borrado recuperable | `cubierta-y-verificada` |
| `office.document` | office v2 | 23 / 120 | create/read con seam | adapter Office no autenticado | documentId + postlectura | externa | `bloqueada-por-dependencia-externa` |
| `message.send` | WhatsApp/Discord | 12 / 98 | resolve/send con seam | sesión de mensajería no autorizada | recipientId + recibo | comunicación externa | `bloqueada-por-dependencia-externa` |
| `system.status` | CPU/RAM/disk/battery/GPU | 25 / 294 | ejecutable | temperatura fuera de fuentes seguras | conservar DXGI/PDH | solo lectura | `cubierta-y-verificada` |
| `system.settings` | device settings | 14 / 89 | contrato setting/value + seam | hardware brightness/night-light no gateado | API oficial + postlectura | sensible | `bloqueada-por-entorno` |
| `system.power` | shutdown/restart/sleep/lock | 8 / 157 | contrato action + seam | gate destructivo no ejecutado | confirmación work-loss + receipt durable | irreversible | `bloqueada-por-entorno` |
| `wifi.manage` | wifi/network.status | 5 / 61 | status+connect/disconnect contracts | perfil/hardware WLAN no gateado | profileId + WLAN postread | sensible | `bloqueada-por-entorno` |
| `bluetooth.manage` | pair/connect | 4 / 28 | list/pair contracts+seam | permisos/hardware sin gate | deviceId + postread | sensible | `bloqueada-por-entorno` |
| `package.install` | install/update/uninstall | 1 / 5 | prepare/commit winget seam | winget authority no gateada | selección exacta + receipt | instalación | `bloqueada-por-entorno` |
| `game.install` | Steam install dialog | 5 / 74 | prepare/commit contracts+seam | cuenta/cliente no autorizados | confirmationId + job verifier | instalación | `bloqueada-por-dependencia-externa` |
| `game.manage` | Steam catalog | 6 / 160 | catalog.list contract+seam | sesión Steam no autorizada | snapshot acotado | externa read-only | `bloqueada-por-dependencia-externa` |
| `game.purchase` | purchase | 2 / 6 | prepare/commit contracts+seam | cuenta/dinero real no autorizados | precio exacto + receipt; solo doble | monetario | `bloqueada-por-dependencia-externa` |
| `game.launch` | launcher/AppID | 2 / 46 | contract+Steam seam | sesión/propiedad no autorizadas | AppID + process verifier | baja reversible | `bloqueada-por-dependencia-externa` |
| `vision.describe` | describe/identify | 48 / 318 | contract+VLM seam | endpoint VLM no configurado | captureId ligado + respuesta verificada | privacidad | `bloqueada-por-dependencia-externa` |
| `ocr.read` | vision.ocr | 7 / 15 | contract+Windows OCR seam | language pack/adapter no gateado | captureId ligado + OCR local | privacidad | `bloqueada-por-entorno` |
| `capture.screenshot` | vision.capture | 14 / 95 | GDI/BMP portado | ninguna | captureId privado + dimensiones + SHA-256 | privacidad | `cubierta-y-verificada` |
| `memory.save` | save/correct/sensitive | 9 / 102 | ejecutable | ninguna del censo | conservar DPAPI+verifier | privacidad | `cubierta-y-verificada` |
| `memory.recall` | recall/list/export/status | 9 / 44 | ejecutable | ninguna del censo | conservar envelope privado | privacidad | `cubierta-y-verificada` |
| `memory.forget` | forget/clear/disable | 9 / 36 | ejecutable | ninguna del censo | conservar confirmación+ausencia | pérdida de datos | `cubierta-y-verificada` |
| `clipboard.manage` | read/write | 6 / 36 | 2 tools portadas | gate físico omitido para no leer/sobrescribir estado real | Win32 confinado + snapshots dobles | privacidad | `cubierta-y-verificada` |
| `notification.manage` | reminder/timer/alarm | 29 / 525 | list.due/dismiss ejecutables | no existe canal visual del shell actual | cola durable verificable; gate requiere superficie BAXY | baja reversible | `bloqueada-por-entorno` |
| `routine.manage` | routine lifecycle | 4 / 19 | 6 tools portadas | ninguna del lifecycle histórico | LocalRoutineStore + CAS; sin creation/runner por frontera | reversible | `cubierta-y-verificada` |
| `backup.manage` | backup/sync/restore | 9 / 37 | create/verify/restore ejecutables | ninguna dentro del sandbox | copia privada + SHA-256 + destino libre | pérdida de datos | `cubierta-y-verificada` |
| `peripheral.manage` | printer/scanner | 6 / 26 | list/print/scan contracts+seam | hardware/driver sin gate | deviceId + job/capture verifier | sensible | `bloqueada-por-entorno` |

## Catálogo ejecutable final

- 106 operaciones totales, 105 públicas en `hello`; `app.status` sigue interna.
- El catálogo final contiene primitivas de app/window, audio/media, backup/filesystem, captura/visión, memoria/notas/tareas/recordatorios/rutinas y contratos gateados para browser/web, cuentas, juegos, hardware, paquetes, red y energía.
- Las 43 familias del censo son capacidades; no se cuentan dos veces primitivas, aliases o cambios de nombre.
- Ninguna fila `crear` se autorizó sin búsqueda histórica: significa que no existe una base segura reutilizable, no que no haya prototipos.

`network.status` es una primitiva pública auxiliar recuperada del v2 y justificada por `wifi.manage`: devuelve solo conectividad, conteo y tipos de interfaz; omite SSID, nombres y direcciones. Dos lecturas independientes deben coincidir.

`system.time` es una primitiva histórica v2 auxiliar para recordatorios, calendario y rutinas: devuelve UTC y desfase local estructurados y exige una segunda lectura monotónica coherente.

`note.search` busca de forma acotada en título y contenido, excluye la papelera salvo petición expresa y reabre cada resultado antes de responder. Junto con `note.update`, `note.trash` y `note.restore`, cierra la familia histórica de notas sin introducir borrado físico.

`task.manage` recupera las nueve operaciones v2 como `task.create`, `task.list`, `task.search`, `task.resolve.exact` (alias histórico `task.resolve_exact`), `task.update`, `task.complete`, `task.reopen`, `task.delete` y `task.restore`. El due date es metadato UTC y nunca agenda una notificación implícita; cada mutación usa versión CAS y postlectura.

`clipboard.manage` recupera `clipboard.read_text` y `clipboard.write_text` como nombres canónicos con puntos. La lectura exige dos snapshots de contenido y número de secuencia idénticos; la escritura reabre dos veces y compara el texto exacto. Se clasifica como privacidad sensible y las pruebas usan un seam controlado.

`window.move` y `window.resize` completan la familia conservando respectivamente tamaño o posición. Ambos consumen el `windowId` de un solo uso, revalidan HWND+PID+creation-time antes del efecto y solo renuevan autoridad cuando la geometría observada coincide exactamente.

Las once primitivas `filesystem.*` recuperan búsqueda, lectura, transferencia y papelera, y reemplazan la escritura v2 en cuarentena. Toda autoridad queda confinada a `filesystem-sandbox`, las lecturas producen IDs opacos y SHA-256, y una sobrescritura requiere el hash exacto de la versión observada.

Los recordatorios usan un store durable separado con due UTC obligatorio y futuro. `notification.list.due` ofrece al shell una cola estructurada y `notification.dismiss` confirma por CAS; no se afirma entrega visual porque el protocolo actual carece de un canal de eventos salientes hacia la superficie BAXY.

`routine.delete/list/read/resolve.exact/restore/set.enabled` porta exactamente el lifecycle v2. El store solo acepta creación desde un controlador confiable interno; no se publica creación ni ejecución porque el histórico las separaba de las tools y un runner sería planner.
