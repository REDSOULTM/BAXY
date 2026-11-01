# Auditoría (solo lectura): capa de presentación de resultados al modelo

Repo `%USERPROFILE%\BAXY-Renew`, rama `renew-nb` @ `9a27765a2`. Las rutas son relativas a `src/`. No se editó, compiló ni ejecutó nada del proyecto. Lo único que se leyó fuera del código fueron los conteos `prompt_n` del trace del mind (`%LOCALAPPDATA%\BAXY\renew\turns.jsonl`, con fecha 2026-10-15 13:32, así que puede ser anterior a parte de este código), solo para medir tokens.

Totales: **26 hallazgos**, de los cuales 5 son de severidad alta, 9 media y 12 baja.

---

## 1. Traza completa de un resultado: del recibo del proveedor al texto que lee el modelo

### 1.A Operación normal (ejemplo `file.find`)

| # | Etapa | Archivo:líneas | Qué se pierde, cambia o se agrega | Quién decide |
|---|---|---|---|---|
| 1 | Recibo del proveedor | `Baxy.Providers.Windows/External/WindowsKnownFileAdapter.cs:208-262`, contrato `External/ExternalCapabilityContracts.cs:5-31` | `ExternalCapabilityReceipt(Operation, EffectObserved, Verified, Result, ErrorCode)` más `EffectMayHaveOccurred`, `StateAlreadyReached` y `AssistantPlaybackPauses`. `Result` es el JSON del proveedor (`version`, `mode`, `count`, `matchCount`, `files[]`, `searchScope{…}`, `authority`). | Proveedor |
| 2 | Recibo → `OperationOutcome` | `Baxy.Core/Operations/ExternalCapabilityHandlers.cs:276-335` | **Si tiene éxito**, `Success(Result)`: **se descartan** `EffectObserved`, `StateAlreadyReached` y `AssistantPlaybackPauses`. **Si falla**, `Failure(ErrorCode ?? "external_verification_failed", result: Verified ? null : Result, effectMayHaveOccurred = EffectObserved‖EffectMayHaveOccurred, cause "external_effect_ambiguous")`. Si la operación exige efecto observado y no lo hubo, devuelve `external_verification_failed` con causa `external_effect_unobserved`/`ambiguous`. Si el proveedor lanza una excepción, `external_provider_failed`. | Core |
| 3 | `OperationOutcome` → `OperationResponse` | `Baxy.Kernel/Mission/MissionEngine.cs:216-241` | `Status` se deriva así: Pending si es reintentable, Completed si hay éxito y verificación, Failed en otro caso. `ErrorCode` por defecto es `verification_failed` u `operation_failed`. `Message = OperationVisibleFacts.FromOutcome(...)`. `Result` viaja **crudo** junto al mensaje. Se asienta en el journal. | Kernel |
| 4 | `FromOutcome`: el JSON que verá el modelo | `Baxy.Kernel/Operations/OperationVisibleFacts.cs:52-152` | **Se agrega** `{"kind":"operation","operation","polarity","verified","succeeded"}`, más `error`, `cause`, `pending` y `effectUncertain` (solo cuando son verdaderos o existen). **No incluye `status`.** `observed` sale de `Sanitize` (365-426): **se eliminan** `hwnd`, `handle`, `pid`, `processId` (salvo en process.list, ocr y capture), `fingerprint`, `invocationId`, `requestId`, `missionId` y `token`; **se eliminan** los valores `null` (421-422) y todo lo que pasa de profundidad 4 (369-373). **Se recortan** las listas a 20 elementos (50 para procesos, sin límite en OCR) y se agregan `<k>Shown`/`<k>Count` (397-407) y `truncated:true` en la raíz (110-113). **Presupuesto de tamaño**: 8 192 caracteres (`MaximumMessageChars`, 22), o 48 000 para process.list, ocr y shell (65). Si se supera, se aplica `WithProjectedObservation` (256-284) por pasos (2000/20 → 600/10 → 280/5 → 120/3): los textos que no son de identidad se cortan con `…` (329-351), se marca `observedLimit:"projected"` y `truncated:true`; si ni así cabe, `observed` se borra y se marca `observedLimit:"omitted"`. Al final queda un corte duro `json[..messageLimit]` (149-151), sin marca y con JSON inválido. Encoder `UnsafeRelaxedJsonEscaping`. | Kernel |
| 5 | Core → App (JSONL) | `Baxy.App/CoreProcessClient.cs:15,315,347` | Una línea de más de 1 MiB rompe el canal (InvalidDataException → core desconectado). | Protocolo |
| 6 | Bucle de herramientas | `Baxy.App/NativeTurnLoop.cs:399-452` | Si hay desafío del kernel, el App **reemplaza** el mensaje por el suyo (`needs_confirmation`, 430-438). Si es memoria, va por `MemoryObservation` (455-482). En los demás casos, `OperationResponseProjection.Create(...)`. | App |
| 7 | `OperationResponseProjection` | `Baxy.App/OperationResponseProjection.cs:12-68` | `input.visible.controls` sale por `ScreenViewProjection` (19-24). `ocr.read` tiene una rama propia (26-50). El resto pasa por `TruncateMessage` con 16 384 caracteres, o 48 000 para process y shell (57-59), con el sufijo `… [respuesta truncada]`. En la práctica es un no-op porque el kernel ya acotó a 8 192/48 000 (ver H15). | App |
| 8 | Registro | `NativeTurnLoop.cs:521-541` | El trace `loop.step` guarda `op.status.verified.ms`. `StepCompleted` lleva la **observación completa** al conductor (`ProductConductorHost.cs:99-111` → stdout y `events.jsonl`). | App |
| 9 | App → mind | `Baxy.App/MindSidecarClient.cs:350-360` | `{"type":"turn.continue","observation":<texto>,"final":bool,"beat":bool}`. **No se dice por qué** `final` es verdadero. | App |
| 10 | Mind | `baxy_mind/mind.py:410-435` | **Se agrega** al final: `"\n[En este turno: <op con puntos> → <_outcome>; …]"`, una lista acumulativa con todas las llamadas del turno (421-424). `_outcome` (95-113) **interpreta** `status`/`succeeded`/`verified`/`polarity`/`effectUncertain`/`error` y lo convierte en prosa («completado y verificado», «falló (x)»…). Si `final`, **se agrega** `"\n[Límite de pasos alcanzado: no llames más herramientas; …]"` (426-429). El texto entra como mensaje `role: tool` y la plantilla de Qwen lo envuelve. Se recorta el historial solo al inicio de un turno (397-404), sin marca. | Mind |

Texto final, por ejemplo:
```
{"kind":"operation","operation":"file.find","polarity":"success","verified":true,"succeeded":true,"observed":{"version":1,"mode":"name","query":"informe","count":20,"matchCount":20,"files":[{"name":"…","folder":"Documentos","relativePath":"…","size":48213,"modifiedUtc":"2026-10-14T18:22:31.1234567Z"},…],"order":"name","searchScope":{"folders":[…],"maxRecursionDepth":12,"timeLimitSeconds":8,"timeLimitReached":false,"ignoreInaccessible":true,"skipReparsePoints":true,"resultLimit":20,"resultsMayBeTruncated":false,"exhaustive":false},"authority":"windows_known_folders_name_search_postread"}}
[En este turno: file.find → completado y verificado]
```

### 1.B `input.visible.controls`

Los pasos 1 a 5 son los mismos: el kernel arma y sanea `observed` igual que en 1.A, aunque luego se descarte. Desde el paso 6:

| Etapa | Archivo:líneas | Transformación |
|---|---|---|
| Recibo | `WindowsVisibleControlAdapter.cs:1965-2258` | Entrega `version, ok, error, identityOnly?, applicationElevated?, windowsActivations*?, window{title, process, processId, hwnd, requested, root?, modal?, owner?, born?, personNearAgoMs?, others[]?, personInputAgoMs?/personInputUnknownAgoMs?, protected?, family[]?, surface{…}?, frontReturned?, foreground, elevated?, reopensUnraised?, rect, coveredBy{title,process}?, focused}`, `controls[]{i, kind, name, nameSource?, id, state, value (null o ""), itemType?, shortcut?, rect, zone, color, repeated?, systemMenu?, body?, reserved?}`, `disabled[]?`, `controlCount`, `clientProviders?`, `clientFrom?`, `frameOnly?`, `partial?`, `uiaFailed?`, `text{TL..BR:[líneas]}`, `textAuthority`, `textLines[]?`, `textMarks[]?`, `surface` (sha), `elapsedMs{}`, `authority`. |
| Selección | `OperationResponseProjection.cs:19-24` | Se usa `response.Result` **crudo** (sin el Sanitize del kernel, con `hwnd`) y `response.Message` (los hechos del kernel). |
| Proyección | `ScreenViewProjection.cs:26-167` | **Se conservan los hechos** del kernel salvo `observed` (128-135), también `observedLimit` si existe (ver H14). **Se agrega** `"view"` con este texto en español: `Ventana «title» (process, window <hwnd>)`, luego `, al frente`/`, no está al frente`, luego `, tapada por «title»` (49-63); `Foco: …` (65-68); `Controles:` con una línea `[i] kind «name» = value (state) ×repeated` por control (71-78, 145-166); `(ninguno)` (80-83); `(+N más fuera de la vista)` (85-89); `Texto arriba/centro/abajo: l1 | l2 …` (91-119), con **reagrupado** por bandas y **deduplicado global** de líneas; `Error: …` (121-124). **Se descartan** todos los demás campos del recibo listados arriba; en especial `partial`, `frameOnly`, `uiaFailed`, `textAuthority`, `disabled[]`, `modal`, `protected`, `elevated`, `identityOnly`, `itemType`, `shortcut` y la diferencia entre `value` null y `""`. No hay **ningún límite de tamaño** en esta ruta. |
| Mind | `mind.py:421-429` | Igual que en 1.A: sufijo `[En este turno: …]` y, si corresponde, `[Límite de pasos…]`. |

Ejemplo de lo que lee el modelo:
```
{"kind":"operation","operation":"input.visible.controls","polarity":"success","verified":true,"succeeded":true,"view":"Ventana «Steam» (steamwebhelper, window 1312456), al frente\nFoco: [3] Edit «Buscar»\nControles:\n[0] Button «TIENDA»\n[1] Button «BIBLIOTECA» (selected)\n…\n(+14 más fuera de la vista)\nTexto arriba: …"}
[En este turno: input.visible.controls → completado y verificado]
```

### 1.C Ruta de memoria
`NativeTurnLoop.cs:455-482`. El resultado del kernel viaja sellado (`ProtectedPrivateResult`, sin `observed`, `OperationVisibleFacts.cs:96`). El App lo abre y lo proyecta con `MemoryOperationResponseProjection` (`:26-104`):
- `recall`/`list` devuelven `records[{label (≤160 car.), value (≤512, o "[REDACTED]" si es sensible o secreto)}]`, `shown` y `total`; como máximo 20.
- `save` devuelve `remembered` y `selector` (177-180).
- `export` devuelve `fullPath`.
- Los fallos usan `TurnVisibleFacts` (`kind:"failure"`, `cause`).
- Si la proyección no sale o supera 16 384 caracteres, el App arma `Observation(op,"completed",false,"result_unreadable")`.

---

## 2. ¿Se pierde algo que el modelo necesita para ser honesto? Muestra de proveedores

| Campo | ¿Llega al modelo? | Evidencia |
|---|---|---|
| `verified` / `succeeded` | Sí, en las observaciones del kernel y del App. No aparece en `FromStatus` (rechazos y pendientes, `OperationVisibleFacts.cs:154-172`) ni en `needs_confirmation`. | |
| `effectObserved` (recibo) | No como campo. En caso de éxito queda implícito; en caso de fallo se convierte en `effectUncertain`/`cause` (`ExternalCapabilityHandlers.cs:310-317`). | |
| `effectMayHaveOccurred` | Sí, como `effectUncertain:true` (`OperationVisibleFacts.cs:90-93`). El App lo pone **siempre**, también como `false` (`NativeTurnLoop.cs:571`). | |
| `StateAlreadyReached` | No, salvo que el proveedor escriba `changed:false` (lo hacen 6 sitios). | `ExternalCapabilityContracts.cs:24` |
| `AssistantPlaybackPauses` | **No** cuando hay éxito: nadie lee esa propiedad. | H18 |
| `errorCode` / `cause` | Sí (`error`, `cause`). | |
| `candidates` | Sí: los recibos con `Verified=false` conservan `Result` (winget `WingetPackageAdapter.cs:181-200`, clima `OpenMeteoWeatherAdapter.cs:234-251`, archivo `WindowsKnownFileAdapter.cs:785-797`). | `ExternalCapabilityHandlers.cs:316` |
| `truncated` (proveedor) | Sí (shell `ShellCommandAdapter.cs:149`). El `truncated:true` del kernel lo pisa con el mismo nombre: colisión semántica menor. | |
| `fullPath` (export) | Sí (`MemoryOperationResponseProjection.cs:317`). | |
| `alreadyInstalled` | Sí (`WingetPackageAdapter.cs:173`). | |
| `timeLimitReached`, `scanLimitReached`, `resultsMayBeTruncated` | Sí (profundidad 2 dentro de `searchScope`). | `WindowsKnownFileAdapter.cs:242-257` |
| `inRecycleBin` | Sí (`WindowsKnownFileAdapter.cs:432`). | |
| `lines` / `totalLines` / `returnedCharacters` / `hasMore` / `nextOffset` | Llegan, **pero dejan de ser ciertos** cuando el kernel acorta `text`. | **H1** |
| `partial` / `frameOnly` / `uiaFailed` / `textAuthority` / `disabled` / `modal` / `protected` (la mirada) | **No.** | **H3** |
| `value` null frente a `""` (la mirada) | **No**: ambos se muestran igual. | H5 |
| `null` en general | Se elimina (`OperationVisibleFacts.cs:421-422`): «desconocido» y «ausente» se confunden. | H26 |

---

## 3. Truncado: dónde se corta, si se marca y si el JSON sigue válido

| Dónde | Límite | ¿Se marca donde lee el modelo? | ¿JSON válido? |
|---|---|---|---|
| Proveedor `file.read` | `maximumCharacters` 4 000 por defecto, hasta 200 000 (`ProductCatalog.cs:460`) | `hasMore`, `nextOffset`, `totalLines` | Sí |
| Proveedor `web.fetch` | 4 000, hasta 20 000 (`ProductCatalog.cs:1609`); body hasta 1,5 MB | `hasMore`, `nextOffset`, `bodyTruncated` | Sí |
| Proveedor shell | 8 KiB de stdout/stderr (`ShellCommandAdapter.cs:17,163-169`) | `truncated` | Sí |
| Proveedor UIA | valores ≤120 car. (`DesktopUiaWorker.ps1:1279`), `limit` de controles y `controlCount` | El conteo se dice como «fuera de la vista» (H4); `partial` se pierde (H3) | n/a |
| Kernel Sanitize | profundidad >4 → null; listas a 20/50 | `truncated:true`, `<k>Shown`, `<k>Count` | Sí |
| Kernel presupuesto | 8 192, o 48 000 en process/ocr/shell | `…` en el texto, `truncated:true`, `observedLimit:"projected"/"omitted"`. **Pero `<k>Shown` queda viejo (H13) y los cursores de paginación mienten (H1)** | Sí |
| Kernel corte final | `json[..messageLimit]` (`OperationVisibleFacts.cs:149-151`) | **No** | **No**. En la práctica no se alcanza (H16) |
| App `TruncateMessage` | 16 384 / 48 000 (`OperationResponseProjection.cs:57-59,70-90`) | `… [respuesta truncada]` | **No** (corta JSON). Código muerto (H15) |
| App memoria | 20 registros, label 160, value 512, total 16 384 | `shown`/`total` sí; los `…` de label y value **no llevan bandera**; si pasa de 16 384 se dice `result_unreadable` (H23) | Sí |
| App ScreenView | **sin límite**, deduplica líneas | No (H6) | Sí |
| Mind | ningún corte de observaciones. Historial: 8 turnos / 24 000 car., recortado por turnos enteros (`mind.py:151-152,397-404`) | No (H24) | Sí |

---

## 4. Rutas de error: el texto exacto que llega al modelo

Todas terminan con `\n[En este turno: … → <_outcome>]`.

- **unknown_operation (App)**, `NativeTurnLoop.cs:218-221`: `{"kind":"operation","operation":"foo","status":"rejected","verified":false,"succeeded":false,"error":"unknown_operation","effectUncertain":false}`. Una herramienta inventada cuyo nombre lleva `_` **nunca llega aquí**: `ParseStep` exige `[A-Za-z0-9.]` (`MindSidecarClient.cs:411-412`), así que el paso queda nulo, se dispara `Fail("decision_unavailable")` (`NativeTurnLoop.cs:172-174`) y en el turno siguiente el modelo lee `{"status":"not_run","reason":"the turn ended before this call ran"}` (`mind.py:154,387-395`). Ver H9.
- **unknown_operation (kernel)**, `MissionEngine.cs:146-152` y `FromStatus`: `{"kind":"operation","operation":"x","polarity":"failure","status":"rejected","error":"unknown_operation"}`. Es otra forma JSON para el mismo error.
- **arguments_invalid (App)**, `NativeTurnLoop.cs:243-250`: `{…,"status":"rejected",…,"error":"arguments_invalid","effectUncertain":false,"argumentsGiven":{…}}`. **No dice qué argumento ni por qué.** En memoria ni siquiera trae `argumentsGiven`. Además se dispara ante `InvalidOperationException("outbox_unavailable"/"memory_protection_unavailable")`, que son fallos de infraestructura (H7).
- **invalid_arguments (kernel)**, que es la ruta real de validación de esquema: `MissionEngine.cs:390-404` devuelve `{"kind":"operation","operation":"x","polarity":"failure","status":"failed","error":"invalid_arguments"}`. **Sin argumento, sin motivo y sin argumentos dados**: `OperationArgumentValidator.IsValid` devuelve solo `bool` (`ProductOperationSchema.cs:485`). Ver H8.
- **engine_unavailable**, `NativeTurnLoop.cs:213-216`: `{…,"status":"failed",…,"error":"engine_unavailable","effectUncertain":false}`, y como `final=true` (196) se agrega **«[Límite de pasos alcanzado…]»** aunque la causa no sea esa (H11).
- **needs_confirmation (desafío del kernel)**, `NativeTurnLoop.cs:430-438`: `{"kind":"operation","operation":"x","status":"needs_confirmation","next":"ask the person whether to do it; when they answer, call confirm_pending with their answer","arguments":{…},"effectStarted":false}`, con `[En este turno: x → espera el sí de la persona]` y **también** «[Límite de pasos alcanzado…]», porque `HasPendingConfirmation` provoca `final`. La propuesta del latido (`:259-265`) usa la misma forma sin `effectStarted`. `only_the_person_answers` (`:318-325`), `nothing_pending` y `declined_by_person` (status `cancelled`) siguen formas parecidas.
- **Timeout del motor (30 s)**, `NativeTurnLoop.cs:415-421`: `{…,"status":"failed",…,"error":"engine_no_answer","effectUncertain":true}`, que se resume como «sin confirmar: pudo o no ocurrir». Correcto.
- **Timeout del proveedor** (shell): `{"kind":"operation","operation":"shell.command.run","polarity":"failure","verified":false,"succeeded":false,"error":"shell_command_timeout","cause":"external_effect_ambiguous","effectUncertain":true}`. Correcto, aunque se pierde la salida parcial.
- **Mind caído o cancelación después de ejecutar**: el resultado nunca entra en la conversación y en el turno siguiente el modelo lee `not_run … before this call ran`, que **es falso** (H10).

---

## 5 y 6. Duplicados, código muerto y costo en tokens

**Medido** en el trace (`prompt_n` de `turn.continue` agrupado por la llamada anterior, n=262; incluye fallos de caché):
- `input.visible.controls`: mediana **≈880 tokens**, máximo 6 593 (n=16).
- `web.fetch`: 1 400.
- `web.search`: ≈515.
- `file.find`: mediana 192, máximo 1 506 (n=4).
- La mayoría de operaciones simples: 40 a 220.

**Estimado**:
- `input.visible.controls` con 60 controles: unos 130 car. de hechos, 70 del encabezado de ventana, 60 líneas de unos 32 car. (≈1 900) y 1,2 a 2,5 k de texto OCR. Total ≈3,5 a 4,7 k car., es decir **≈1,1 a 1,6 k tokens**. La vista ya es compacta; lo único que es puro overhead son los hechos `kind`, `polarity` y, si aparece, `observedLimit`.
- `file.find` con 20 archivos: unos 105 car. de encabezado, 80 de cabecera de `observed`, 20 entradas de unos 165 car. (3 300), unos 330 de `searchScope`+`authority` y 55 del sufijo del mind. Total ≈3,9 k car., es decir **≈1,2 a 1,3 k tokens**. Overhead quitable sin perder honestidad: unos 900 car. (≈25 %):
  - `"kind":"operation"`
  - `polarity`, que se deriva de `verified`+`succeeded` (`OperationVisibleFacts.cs:71`)
  - `"version":1`
  - `"authority":"…"` (unos 55 car.)
  - las constantes de `searchScope` (`maxRecursionDepth`, `timeLimitSeconds`, `ignoreInaccessible`, `skipReparsePoints`, `exhaustive:false`, `resultLimit`, `maximumFilesScanned`, `maximumFileBytes`); se mantienen `folders`, `timeLimitReached`, `scanLimitReached`, `resultsMayBeTruncated` y `skipped*`
  - los 7 decimales de `modifiedUtc` (8 car. × 20)
  - `effectUncertain:false` en las observaciones del App
- Sufijo `[En este turno: …]`: crece de forma cuadrática, unos 45 car. por llamada previa repetidos en cada resultado. Con 15 llamadas son ≈5 k car. por turno.
- Riesgo de contexto: observaciones de hasta 48 000 car. (process, shell, ocr), ≈13 a 15 k tokens, contra `-c 32768` (`llm_server.py:20`) con un prefijo de herramientas grande (`tool_descriptions.en.v1.json` pesa 81 KB) y sin acotar dentro del turno (H21). No está medido.

---

## Tabla de hallazgos

| # | archivo:líneas | regla | qué | severidad | arreglo mínimo |
|---|---|---|---|---|---|
| 1 | `Baxy.Kernel/Operations/OperationVisibleFacts.cs:38-39,256-325`; `Baxy.Providers.Windows/External/WindowsKnownFileAdapter.cs:592-600`; `External/WebBrowserAdapter.cs:283-293`; `Baxy.Kernel/Operations/ProductCatalog.cs:221,460,1609` | R2 | Cuando el mensaje pasa de 8 KiB, el kernel acorta `text` a 2000/600/280/120 car. con «…», pero `hasMore`, `nextOffset`, `returnedCharacters` y `lines` siguen describiendo la página sin cortar. El modelo pagina desde `nextOffset` y **se salta para siempre** el texto que no vio (file.read con `maximumCharacters` de hasta 200 000, web.fetch de hasta 20 000, browser.page.read de hasta 32 768; incluso los 4 000 por defecto con escapes pueden superar 8 KiB). | Alta | Bajar los máximos de esquema de `maximumCharacters` (catálogo 221/460/1609) a un valor que quepa en el presupuesto (≈3 000), para que el kernel nunca necesite cortar `text` de una operación paginada. |
| 2 | `Baxy.App/NativeTurnLoop.cs:301,529-539`; `Baxy.App/ProductConductorHost.cs:99-111`; `Baxy.App/MemoryOperationResponseProjection.cs:177-180,512-535` | R3 | La observación de memoria (`records[].label/value`, `remembered`, `selector`) llega tal cual a `NativeTurnStep.Observation`, y de ahí a los eventos del conductor (stdout y `events.jsonl`). El comentario de la línea 301 afirma lo contrario. | Alta | En `Record`, para las operaciones `memory.*` guardar en el paso solo `status/verified/error` (por ejemplo, `observation` sin `observed`). El modelo sigue recibiendo la observación completa. |
| 3 | `Baxy.App/ScreenViewProjection.cs:13,26-137`; `External/WindowsVisibleControlAdapter.cs:1868,2001,2039,2071,2144,2178,2186,2191,2208` | R2 | La vista descarta `partial` («lo que no lista puede estar»), `frameOnly`, `uiaFailed`, `textAuthority:"unavailable"`, `disabled[]` (el adaptador dice que «la mente sabe que existen»), `modal`, `protected`, `elevated`/`reopensUnraised` e `identityOnly`. Un corte o un fallo de lectura se presenta como observación completa, y el doc de la línea 13 dice «todo se conserva». | Alta | Agregar a `view` una línea con esos mismos campos tal como vienen (por ejemplo `Lectura: partial, frameOnly, uiaFailed=…, texto=unavailable, modal, protegida, elevada`) y `Desactivados: kind «name»…`. Sin interpretar. |
| 4 | `Baxy.App/ScreenViewProjection.cs:85-89`; `External/WindowsVisibleControlAdapter.cs:2182-2185` | R2 | `(+N más fuera de la vista)`: `controlCount` cuenta controles recorridos que no se listaron por el tope, no controles fuera de la vista. El App les agrega una causa que no se observó. | Media | Escribir `(+N más sin listar)`. |
| 5 | `Baxy.App/ScreenViewProjection.cs:150-153`; `Baxy.Providers.Windows/External/DesktopUiaWorker.ps1:1278` | R2 | `value ""` (vacío confirmado) y `value null` (desconocido) se muestran igual. Después de `input.text.type`, el modelo no puede distinguir «el campo quedó vacío» de «no se puede leer». | Media | Si `value == ""`, escribir ` = ""`; si es null, nada (como ahora). |
| 6 | `Baxy.App/ScreenViewProjection.cs:91-119` (`seen` en 93,107) | R2/R1 | El deduplicado **global** elimina líneas repetidas reales (mensajes iguales de un chat) sin marca, y el agrupado L/C/R por banda reordena la conversación, perdiendo quién dijo qué y en qué orden. | Media | Quitar el `HashSet` global (o deduplicar solo dentro de la misma zona con `×n`) y mantener el orden de zonas. |
| 7 | `Baxy.App/NativeTurnLoop.cs:226-230,243-250` | R2 | `InvalidOperationException("outbox_unavailable")` y `("memory_protection_unavailable")` (fallos de infraestructura) caen en el `catch` y se presentan como `arguments_invalid` con `argumentsGiven`: el modelo culpa a sus argumentos. | Alta | Comprobar `Registry()`/`MemoryProtector()` antes del `try` y devolver `Observation(op,"failed",false,"outbox_unavailable"/"memory_protection_unavailable")`. |
| 8 | `Baxy.Kernel/Mission/MissionEngine.cs:390-404`; `Baxy.Kernel/Operations/ProductOperationSchema.cs:485`; `baxy_mind/mind.py:480-482` | R2/R4 | La validación real (kernel) responde `invalid_arguments` sin decir qué argumento, por qué ni qué se dio; el comentario del mind («the rejection says what the model gave») es falso en esta ruta. Hay dos códigos para lo mismo (`arguments_invalid` en el App y `invalid_arguments` en el kernel). | Media | Hacer que el validador devuelva el primer camino y motivo (por ejemplo `cause:"fileName: required"`) en `CauseCode`. Unificar el código. |
| 9 | `Baxy.App/MindSidecarClient.cs:411-412`; `NativeTurnLoop.cs:172-174`; `mind.py:507` | R2 | Un nombre de herramienta desconocido con `_` (los nombres wire siempre lo llevan) se rechaza en `ParseStep`, el turno falla con `decision_unavailable` y el modelo **nunca** ve `unknown_operation`; luego lee `not_run`. | Media | Aceptar `_` en `ParseStep`; el App ya responde `unknown_operation` en la línea 218. |
| 10 | `Baxy.App/NativeTurnLoop.cs:191-197`; `baxy_mind/mind.py:154,387-395` | R2 | Si `ContinueAsync` falla (mind lento o caído) o hay cancelación después de que el core ejecutó la llamada, el resultado se pierde, y en el turno siguiente se escribe `"the turn ended before this call ran"`, que es **falso** porque sí corrió. | Alta | Para `awaiting` (la llamada enviada al App) usar otro texto: `{"status":"result_missing","reason":"no result reached you; it may have run"}`; dejar `not_run` solo para la `queue`. |
| 11 | `Baxy.App/NativeTurnLoop.cs:196`; `MindSidecarClient.cs:358`; `mind.py:426-429` | R2 | `final` se activa también con el motor caído o con una confirmación pendiente, pero el mind siempre escribe «[Límite de pasos alcanzado…]»: la causa queda mal atribuida justo después de un `needs_confirmation`. | Media | Mandar el motivo (`final:"budget"/"engine"/"awaiting_person"`), o un texto neutro («no llames más herramientas en este turno»). |
| 12 | `baxy_mind/mind.py:95-113`; `NativeTurnLoop.cs:475,480` | R1/R2 | `_outcome` interpreta resultados: si `status:"completed"` y `error:"result_unreadable"`, dice «completado sin verificar» y oculta el error; ignora `pending:true` del kernel y `effectStarted:true`. | Media | Si hay `error`, incluirlo siempre (`completado; error result_unreadable`), y evaluar `error` antes de `status == completed`. |
| 13 | `Baxy.Kernel/Operations/OperationVisibleFacts.cs:397-407` frente a `286-303` | R2 | `Project` recorta listas otra vez (20→10→5→3) pero deja el `<k>Shown` viejo que escribió `Sanitize`: el modelo lee `filesShown:20` y ve 10. | Media | En `Project`, al cortar `name`, actualizar `projected[name+"Shown"]` si existe. |
| 14 | `Baxy.App/ScreenViewProjection.cs:128-135` | R2 | Se copian los hechos del kernel salvo `observed`, así que `observedLimit:"projected"/"omitted"` (que se refiere al `observed` descartado) aparece junto a una vista entera: una señal de corte falsa. | Baja | Excluir también `observedLimit`. |
| 15 | `Baxy.App/OperationResponseProjection.cs:10,26-50,57-67,70-90` | R4 | `TruncateMessage` (16 384/48 000), la rama de `ocr.read` (duplica `OcrSizeLimit`, `OperationVisibleFacts.cs:123-142,245-249`) y el fallback `FromStatus` (el mensaje nunca llega vacío, `Baxy.Contracts/ContractValidator.cs:270,396`) no se ejecutan nunca: el kernel ya acota a 8 192/48 000. Si se ejecutaran, romperían el JSON. | Baja | Borrarlos y devolver `response.Message` (salvo la mirada). |
| 16 | `Baxy.Kernel/Operations/OperationVisibleFacts.cs:149-151` | R4/R2 | Corte final `json[..messageLimit]`: inalcanzable una vez quitado `observed`; si se alcanzara, emitiría JSON inválido sin marca. | Baja | Borrarlo. |
| 17 | `NativeTurnLoop.cs:259-265,318-325,430-437,555-579`; `OperationVisibleFacts.cs:52-172`; `Baxy.App/TurnVisibleFacts.cs:17-33`; `MemoryOperationResponseProjection.cs:543-555,860-875`; `OperationResponseProjection.cs:33-49,70-90` | R4 | Hay unas 7 formas de observación (con o sin `status`, con o sin `polarity`, `kind` operation/failure/status, `cause` como error o como éxito) y `needs_confirmation` se arma dos veces. Hay tres helpers de corte (`TruncateMessage`, `TruncateText`, `Shortened`). `_outcome` tiene que adivinar entre todas. | Baja | Un único helper de confirmación; `Observation(...)` para todo lo que arma el App; un solo `Shortened`. |
| 18 | `External/ExternalCapabilityContracts.cs:30`; `External/WindowsExternalCapabilityProvider.cs:335-338` | R4/R2 | `AssistantPlaybackPauses` no lo lee nadie. Cuando hay éxito, la pausa de la reproducción previa de BAXY (un efecto del turno) no llega al modelo. | Baja | Escribir `pausedAssistantPlayback` en `Result` también cuando hay éxito, o eliminar la propiedad. |
| 19 | `OperationVisibleFacts.cs:353-360`; `External/WebBrowserAdapter.cs:264`; `ScreenViewProjection.cs:13` | R4 | Comentarios obsoletos o falsos: «hwnd… which no public operation takes» (los `input.visible.*` sí toman `window` = hwnd, que es lo que muestra la vista); «the mind cuts at 6 000» (el mind de Renew no corta); «every control and every line… is kept». | Baja | Corregir o borrar esos comentarios. |
| 20 | `baxy_mind/mind.py:132-135,357,361` | R3 | El trace del mind (`turns.jsonl`) guarda `content` con la decisión JSON del latido, cuyo campo `preferencia` reescribe valores de la memoria del autor que recibió en `beat_message`. | Baja | En `turn.beat.decide`, registrar solo `intervene` y la longitud de `content`. |
| 21 | `Baxy.Kernel/Operations/OperationVisibleFacts.cs:65`; `baxy_mind/llm_server.py:20`; `baxy_mind/mind.py:397-404` | tokens | Observaciones de 48 000 car. (process, shell, ocr), ≈13 a 15 k tokens, sin acotar dentro del turno, contra un contexto de 32 768 con un prefijo de herramientas grande: riesgo de desborde, que termina en fallo del turno. No medido. | Media | Usar para esas operaciones el mismo presupuesto que el resto (8 a 16 KiB), que ya se proyecta y se marca. |
| 22 | `OperationVisibleFacts.cs:69-73`; `NativeTurnLoop.cs:571`; `WindowsKnownFileAdapter.cs:210,225,236-261`; `mind.py:421-424` | tokens | Overhead sin valor para el modelo: `kind`, `polarity` (redundante), `effectUncertain:false`, `version`, `authority`, constantes de `searchScope`, 7 decimales de `modifiedUtc`, y el sufijo «En este turno» que crece de forma cuadrática. ≈25 % de un `file.find`. | Baja | Quitar esos campos (agregar `version` y `authority` a las claves de contabilidad de `Sanitize`, omitir `effectUncertain` cuando es false, quitar las constantes de `searchScope`). Para `_outcome`, basta con `status`. |
| 23 | `MemoryOperationResponseProjection.cs:98-104,515-516` | R2 | Label y value se cortan con «…» sin bandera; si la proyección pasa de 16 384 car. se informa `result_unreadable` en lugar de «demasiado grande». | Baja | Agregar `truncated:true` cuando `TruncateText` corta. |
| 24 | `baxy_mind/mind.py:30-34,397-404` | R2 | El historial se recorta sin marca, y la regla 2 dice «sin una herramienta que lo hiciera, no lo hiciste»: tras un recorte, el modelo puede negar acciones reales. | Baja | Al recortar, dejar un primer mensaje `[turnos anteriores omitidos por espacio]`. |
| 25 | `baxy_mind/mind.py:510`; `NativeTurnLoop.cs:249` | R2 | `argumentsGiven` incluye constantes que inyectó el mind y que el modelo no escribió, presentadas como «dadas». | Baja | Usar como clave `argumentsSent`, o quitar las constantes de `argumentsGiven`. |
| 26 | `OperationVisibleFacts.cs:391-395,421-422` | R2 | `Sanitize` elimina los valores `null`: en las operaciones que no son la mirada, «desconocido» (null) y «ausente» quedan indistinguibles. | Baja | Conservar `null` (son pocos bytes). |

---

## Notas

- La ruta de memoria **no** filtra argumentos al trace del App (`NativeTurnLoop.cs:531`) ni al del mind (`mind.py:516`). La filtración R3 está en los **resultados** (H2).
- El registro `RetryableOperationRegistry` (`Baxy.App/PreparedOperation.cs:161-187`) casi nunca deduplica, porque `DropPending` y `Resolve` se ejecutan antes y después de cada envío. Está fuera del alcance estricto; sospecha de R4.
