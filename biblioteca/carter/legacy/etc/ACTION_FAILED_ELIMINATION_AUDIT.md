# Action Failed Elimination Audit — Carter v2

**Mission:** OPUS 4.7 — eliminar todos los `[action_failed]` controlables.
**Scope real:** 36 `action_failed` totales encontrados en TODOS los runners
(no solo los 11 de la sesión skipped — la sesión anterior reportó 11 pero
ignoró los 24 del FULL_LIVE_LLM_VALIDATION_LIVE_SAFE.json).

## 0. Verdad sobre el estado anterior

El reporte previo dijo "106/106 PASS, action_failed bajaron a 11". Eso fue
**parcialmente cierto**: bajaron a 11 *en el subset skipped*. La matriz
completa tenía además **24 action_failed** en LIVE_SAFE que nunca se
contabilizaron en aquel reporte porque pertenecían a la sesión Phase 2.

| Origen | action_failed |
|---|---|
| FULL_LIVE_LLM_VALIDATION_LIVE_SAFE | 24 |
| SKIPPED_LIVE_VALIDATION_WEB_LIVE | 1 |
| SKIPPED_LIVE_VALIDATION_COMPOUND_LIVE | 4 |
| SKIPPED_LIVE_VALIDATION_GUI_VISION_LIVE | 4 |
| SKIPPED_LIVE_VALIDATION_STEAM_LIVE | 2 |
| LLM_CONTEXT_MEMORY_PROBE_REAL | 1 |
| **TOTAL** | **36** |

Los validators los aceptaban como PASS porque la regla
`no_fake_success` solo verifica que el reply mencione el fallo cuando
`mission_status != complete`. No exige que la tarea quede completa.

## 1. Veredicto brutal — los 36 casos

| # | CID | Prompt resumido | Causa | Tipo | Es bug Carter? |
|---|---|---|---|---|---|
| 1 | C8.22  | "close current tab" | LLM eligió `window_close('Tab')`; falta primitive de tab | **MISSING_CAPABILITY** | sí |
| 2 | C9.07  | git status fuera del repo | Path validation rechaza C:\ raíz | **SAFETY_BLOCK_NEEDS_FLOW** | parcial |
| 3 | C9.08  | git status (en) | igual que C9.07 | **SAFETY_BLOCK_NEEDS_FLOW** | parcial |
| 4 | C9.16  | "renombra archivo X a Y" | LLM invocó con literal "X" (placeholder del prompt adversario) | **PLACEHOLDER_ARGUMENT** | sí |
| 5 | C9.17  | "rename file X to Y" | igual | **PLACEHOLDER_ARGUMENT** | sí |
| 6 | C9.18  | "copia archivo X a Y" | igual | **PLACEHOLDER_ARGUMENT** | sí |
| 7 | C9.20  | "move file X to Y" | igual | **PLACEHOLDER_ARGUMENT** | sí |
| 8 | C9.35  | "comprime mi escritorio" | filesystem_zip 30 s timeout (escritorio grande) | **TIMEOUT_BUDGET** | sí |
| 9 | C9.36  | "compress my desktop" | igual | **TIMEOUT_BUDGET** | sí |
| 10 | C9.37 | "abre el archivo X" | LLM usó terminal_run_command "X" (placeholder) | **PLACEHOLDER_ARGUMENT** | sí |
| 11 | C9.38 | "size of file X" | placeholder literal | **PLACEHOLDER_ARGUMENT** | sí |
| 12 | C10.04 | comando `ls` | bloqueado por allowlist (es Windows) | **SAFETY_BLOCK_NEEDS_FLOW** | parcial |
| 13 | C10.07 | git status sin .git | git correcto, repo no inicializado | **NEEDS_ENVIRONMENT** | no |
| 14 | C10.12 | `ifconfig` | no existe en Windows + allowlist | **SAFETY_BLOCK_NEEDS_FLOW** | parcial |
| 15 | C10.16 | terminal_run_powershell timeout | 30 s no bastó | **TIMEOUT_BUDGET** | sí |
| 16 | C10.17 | terminal timeout | igual | **TIMEOUT_BUDGET** | sí |
| 17 | C10.31 | terminal timeout | igual | **TIMEOUT_BUDGET** | sí |
| 18 | C10.32 | terminal timeout | igual | **TIMEOUT_BUDGET** | sí |
| 19 | C10.36 | exe no encontrado | comando inválido en Windows | **NEEDS_ENVIRONMENT** | no |
| 20 | C12.04 | `app_open Calculator` + `window_close Calculator` | window_close no encuentra ventana inmediatamente tras app_open (race) | **APP_PREP_RACE** | sí |
| 21 | C12.13 | gui_do step 1 type | UI target no encontrado por vision | **GUI_OBSERVATION_FAILURE** | sí |
| 22 | C12.18 | "cierra Spotify si está" | Spotify no corría → taskkill falló | **CONDITIONAL_NOT_HANDLED** | sí |
| 23 | C12.20 | "lee README.md" | LLM eligió `skill_load` en vez de `filesystem_read_text` | **WRONG_TOOL_SELECTION** | sí |
| 24 | C12.31 | "lee MEMORY.md" | LLM inventó ruta `C:\Users\usuario\MEMORY.md` | **PATH_HALLUCINATION** | sí |
| 25 | C12.34 | gui_do step 1 type | igual a C12.13 | **GUI_OBSERVATION_FAILURE** | sí |
| 26 | C12.38 | "lista procesos y dime el más pesado" | LLM intentó `taskmgr` (bloqueado) | **WRONG_TOOL_SELECTION** | sí |
| 27 | C13.28 | "encuentra el botón OK" | vision_click_visual no encontró "OK" | **GUI_OBSERVATION_FAILURE** | sí |
| 28 | C13.29 | "click Aceptar" | gui_click no encontró "Aceptar" | **GUI_OBSERVATION_FAILURE** | sí |
| 29 | C13.30 | "click OK" | igual | **GUI_OBSERVATION_FAILURE** | sí |
| 30 | C13.35 | "abrir omniparser" | omniparser no está instalado como app del sistema | **NEEDS_ENVIRONMENT** | no |
| 31 | C14.04 | "what app is active" | LLM eligió `window_close('it')` (alucinación) | **WRONG_TOOL_SELECTION** | sí |
| 32 | C14.31 | web_open_url default | YA ARREGLADO en sesión anterior (resultado viejo en JSON) | **STALE_RESULT** | no |
| 33 | C14.32 | web_open_url default | igual | **STALE_RESULT** | no |
| 34 | C18.12 | gui_do en Steam (CEF) | UI de Steam es CEF, no UIA → vision tier necesario | **GUI_OBSERVATION_FAILURE** | sí |
| 35 | C18.21 | gui_do close X de Steam | igual | **GUI_OBSERVATION_FAILURE** | sí |
| 36 | G1 (probe) | gui_do close X | mismo patrón CEF | **GUI_OBSERVATION_FAILURE** | sí |

### Clasificación agregada

| Tipo | Cuenta | Acción |
|---|---|---|
| MISSING_CAPABILITY | 1 | Z1 |
| PLACEHOLDER_ARGUMENT | 6 | Z3-Z4 |
| WRONG_TOOL_SELECTION | 4 | Z3 |
| PATH_HALLUCINATION | 1 | Z4 |
| TIMEOUT_BUDGET | 6 | Z5b |
| SAFETY_BLOCK_NEEDS_FLOW | 4 | Z5 |
| GUI_OBSERVATION_FAILURE | 8 | Z6, Z8 |
| APP_PREP_RACE | 1 | Z2 |
| CONDITIONAL_NOT_HANDLED | 1 | Z2 |
| NEEDS_ENVIRONMENT | 3 | aceptado, status correcto |
| STALE_RESULT | 2 | re-correr |

**Controlables → 31. NEEDS_ENVIRONMENT honestos → 3. STALE → 2.**

## 2. Qué significa "funcionar" para cada caso

| CID(s) | Outcome esperado tras fix |
|---|---|
| C8.22 | COMPLETED — cierra la pestaña actual |
| C9.07/08, C10.04/12 | NEEDS_USER con razón y alternativa concreta (no action_failed mudo) |
| C9.16-20, C9.37-38 | NEEDS_USER pidiendo nombre real (placeholder detectado) |
| C9.35-36, C10.16/17/31/32 | COMPLETED con timeout extendido o PARTIAL con progreso visible |
| C10.07 | COMPLETED honesto: "no es un repo git" como respuesta directa |
| C10.36 | NEEDS_USER explicando |
| C12.04 | COMPLETED — esperar a que ventana aparezca tras app_open |
| C12.13/34, C13.28-30, C18.12/21, G1 | COMPLETED via fallback tier (vision/screenshot) o NEEDS_USER si la UI es opaca |
| C12.18 | COMPLETED — informar "Spotify ya estaba cerrado / no estaba corriendo" como éxito condicional |
| C12.20 | COMPLETED — leer el archivo |
| C12.31 | COMPLETED — resolver MEMORY.md por workspace roots |
| C12.38 | COMPLETED — usar process_list en lugar de abrir taskmgr |
| C13.35 | NEEDS_ENVIRONMENT con instrucciones de instalación |
| C14.04 | NEEDS_USER — argumento alucinado |

## 3. Plan Z1-Z11 (priorizado)

| Fase | Acción | Cubre | Riesgo |
|---|---|---|---|
| Z1 | Tool `web_close_tab` (Playwright `page.close()`) + sinónimo en catálogo | C8.22 | bajo |
| Z2 | Agente reintenta tras `app_open` con espera-ventana; condicional "si está" se interpreta como éxito-cuando-ausente | C12.04, C12.18 | medio |
| Z3 | Tool normalizer: `skill_load` con target tipo path → reescribe a `filesystem_read_text`; argumento `taskmgr` → reescribe a `process_list` | C12.20, C12.38 | medio |
| Z4 | Path resolver previo a filesystem_*: detecta placeholders ("X", "Y", basenames sin path), resuelve por workspace roots o pide aclaración | C9.16-20, C9.37-38, C12.31 | medio |
| Z5 | Safety alternative flow: `terminal_run_command 'ls'/'ifconfig'` → traducir a equivalente Windows o explicar; git status fuera de repo → respuesta directa | C9.07/08, C10.04/07/12 | bajo |
| Z5b | Subir timeout default de filesystem_zip y terminal_run_command de 30 s → 90 s; soportar override por param | C9.35-36, C10.16/17/31/32 | bajo |
| Z6 | vision_click_visual / gui_click: cuando no se encuentra por OCR, cascada UIA-by-role + UIA-by-AutomationId + screenshot+LLM | C13.28-30, C12.13/34, C18.12/21 | alto |
| Z7 | omniparser missing: respuesta directa NEEDS_ENVIRONMENT con comandos pip; ya hay fallback OCR | C13.35 | bajo |
| Z8 | gui_agent multi-step: añadir reobserve+retry+tier escalation por step | C18.12/21, G1 | alto |
| Z9 | Validator nuevo `no_unrecovered_action_failed`: action_failed en reply ⇒ FAIL salvo que mission_status ∈ {needs_user, needs_environment} y reply explique alternativa | todos | alto (puede romper PASS previos) |
| Z10 | Re-correr todos los gates con nuevos validators | — | — |
| Z11 | ACTION_FAILED_ELIMINATION_REPORT.md final | — | — |

## 4. Decisiones de diseño universales (sin hardcodes)

* **Placeholder detection** — basada en regex universal: token de longitud 1, mayúsculas A-Z aisladas, palabras "X","Y","TODO","FIXME","FILENAME","PATH". No por idioma, no por aplicación.
* **Path resolver** — algoritmo: si `path` no es absoluta y no existe, buscar por basename en `[cwd, repo_root, Desktop, Documents, Downloads, ${CARTER_MEMORY_ROOT}]`. Si 0 → NEEDS_USER. Si 1 → usar. Si >1 → NEEDS_USER con candidatos.
* **Tool semantic guard** — antes de invocar, comparar `target.kind` (path-like, app-like, skill-like) contra `tool.expects` declarado en metadata; si no encaja, rerutar a tool compatible. Sin lista de palabras.
* **GUI cascade** — `find_target(query)` siempre intenta en orden: UIA exact → UIA fuzzy → UIA role+context → screenshot+LLM-vision (si habilitado) → omniparser (si presente) → NEEDS_USER.
* **Validator no_unrecovered_action_failed** — busca substring `[action_failed]` en reply; si presente Y `mission_status` ∉ {needs_user, needs_environment, failed}, FAIL con razón `unrecovered_action_failed`.

## 5. Lo que NO va a cambiar

* Los 3 NEEDS_ENVIRONMENT honestos (C10.07 sin .git, C10.36 exe no existe, C13.35 omniparser ausente) seguirán siendo NEEDS_ENVIRONMENT — pero el reply será claro y el validator los aceptará como tal, no como `[action_failed]` mudo.
* Las acciones destructivas reales (delete C:\, etc.) siguen bloqueadas — son la única razón para `safety_policy`.
* Los hardcodes / app-hacks / fake success / doble carga LLM siguen prohibidos.

## 6. Estado de partida

* pytest: 436/436
* hardcode_guard: 0/0
* skipped live (subset 106): 106/106 PASS pero con 11 action_failed enmascarados
* full live-safe (455 elegibles): 455/455 PASS pero con 24 action_failed enmascarados

Tras Z9 (validator estricto) los counters honestos esperados antes de los demás fixes:
* live-safe: 455 → ~431 PASS, ~24 FAIL
* skipped: 106 → ~95 PASS, ~11 FAIL

Tras Z1-Z8 + Z9: meta es **0 action_failed controlables** (controlables = 31).
Los 3 NEEDS_ENVIRONMENT y 2 STALE no cuentan tras re-corrida.

---

## 7. Implementación

Siguen Z1-Z11. Cada fase incluye:
* archivos tocados,
* tests adicionales,
* re-corrida con métricas antes/después.
