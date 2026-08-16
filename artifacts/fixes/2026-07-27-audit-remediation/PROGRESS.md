# Remediación de auditoría BAXY — 2026-07-27

## Baseline preservado

- Repositorio canónico: `D:\BAXY\source`.
- Rama: `codex/baxy-rebuild-v3`.
- Commit auditado: `f23b23f064211154e954d82883ba6bee5c2c466c`.
- Instalación auditada: BAXY 1.0.8.
- Los artefactos originales bajo
  `artifacts/audit/2026-07-27-night-audit/` son evidencia del usuario y no se
  modifican ni eliminan.
- Cambios preexistentes preservados al iniciar:
  `artifacts/product/voice_system_gate.json`,
  `artifacts/audit/` y
  `artifacts/product/audit-2026-07-27-app-open.json`.

## Estado por defecto

`pendiente` significa que la causa está documentada en la auditoría, pero la
reproducción de remediación y la verificación posterior aún no se han
registrado aquí.

| ID | Estado | Causa confirmada | Archivos modificados | Prueba de regresión | Reproducción posterior | Evidencia | Regresiones encontradas |
|---|---|---|---|---|---|---|---|
| AUD-001 | verificado | `InvalidDataException` de AppID cruzaba la frontera Steam y terminaba JSONL | `SteamLocalAdapter.cs`; `ExternalCapabilityHandlers.cs`; pruebas de proveedor/integración | AppID inválido y excepción inesperada en frontera externa; continuidad con `system.time` | 4/4 respuestas `steam_app_id_invalid`, exit 0; el mismo core procesa después una solicitud válida | `evidence/core-boundaries/baxy-aud001-{before,after}.json`; 14/14 pruebas de proveedor y 8/8 de integración focalizadas | ninguna |
| AUD-002 | verificado | `Win32Exception` por `winget.exe` ausente cruzaba la frontera de inventario | `WindowsInventoryAdapter.cs`; `ExternalCapabilityHandlers.cs`; pruebas de proveedor/integración | runner inyectable: ejecutable ausente, timeout y continuidad JSONL | 2/2 respuestas `winget_adapter_unavailable`, exit 0; continuidad posterior verificada | `evidence/core-boundaries/baxy-aud002-{before,after}.json`; pruebas focalizadas | ninguna |
| AUD-003 | verificado | enumeración WinRT Bluetooth sin timeout impedía alcanzar el fallback | `WindowsDeviceControlAdapter.cs`; `ExternalCapabilityHandlers.cs`; pruebas de proveedor/integración | inventario WinRT cancelable con presupuesto total y fallback PowerShell acotado | 2/2 ciclos sin timeout externo; máximo 5,904 s; core siguió disponible | `evidence/core-boundaries/baxy-aud003-{before,after-timeout4}.json`; pruebas focalizadas | ninguna |
| AUD-004 | verificado | la bienvenida activaba resolución contextual sobre un saludo no elíptico | `src/baxy_mind/llm.py`; `src/Baxy.App/MainWindowViewModel.cs`; `tests/test_turn_policy.py`; `tests/Baxy.Integration.Tests/PlannerAppBoundaryTests.cs` | `test_social_greeting_after_welcome_does_not_enter_reference_resolution`; rechazo de metadiscurso en `ConversationReplySafetyOnlyEnforcesOutputSafety` | 240 pruebas Python focalizadas y 50/51 pruebas de integración focalizadas (1 gate físico omitido) | `routing-before.json`; salida de pruebas | ninguna |
| AUD-005 | verificado | `WM_CLOSE` no cerraba la ventana UWP hospedada de Calculadora | `WindowsWindowControlProvider.cs`; pruebas de ventana | `WM_CLOSE` + verificación y fallback `WM_SYSCOMMAND/SC_CLOSE` sobre la misma identidad | Calculadora cerrada y verificada; `CalculatorApp` 0; `ApplicationFrameHost` ajeno preservado | `evidence/windows-providers/aud-005-022-runtime-evidence.json` | ninguna |
| AUD-006 | verificado | órdenes completas de apertura se degradaban a aclaraciones de otra intención | `src/baxy_mind/effect_intent.py`; `src/baxy_mind/__main__.py`; `tests/test_effect_intent.py` | matriz declarativa de efectos, apps autenticadas y paráfrasis ES/EN | matrices vivas 60/60, 62/62 y regresiones 10/10; aperturas simples y coordinadas conservaron nombres exactos | `evidence/global/routing-original-60-final-v4.json`; `evidence/global/routing-adversarial-62-final-v2.json`; `evidence/global/routing-live-regressions-10-final-v2.json` | ninguna |
| AUD-007 | verificado | la política contextual degradaba `system.time` a charla o aclaración | `src/baxy_mind/effect_intent.py`; `src/baxy_mind/__main__.py`; `src/baxy_mind/llm.py`; pruebas Python/E2E | hora y fecha como efectos cerrados; historial de usuario preservado en follow-ups | matriz viva 60/60; gate físico 9/9 observó exactamente dos `system.time`, incluido el plan hora + CPU | `evidence/global/routing-original-60-final-v4.json`; `artifacts/product/audit-remediation-2026-07-27/mind-shell-e2e-final-v3.{json,trx,attestation.json}` | el E2E v2 reveló pérdida del historial de usuario y del segundo efecto; ambos quedaron corregidos y verificados en v3 |
| AUD-008 | verificado | timeout de UI anterior al resultado durable certificado por el core | `CoreProcessClient.cs`; `CoreProcessClientTimeoutTests.cs` | reconciliación conserva la solicitud 55 s adicionales y desconecta una sola vez tras el presupuesto total | 5 selecciones Spotify certificadas entre 19,38 y 42,39 s; la UI puede recibir el resultado posterior a 20 s | `evidence/browser-media-voice/aud-008-027-runtime-evidence.json`; 3/3 pruebas de timeout | un primer control SMTC quedó ambiguo; la postlectura inmediata sí observó pausa y no se declaró éxito para esa invocación |
| AUD-009 | verificado | alias superficial `notepad` no se normalizaba a `windows.notepad` tras extracción | `src/Baxy.App/MainWindowViewModel.cs`; `tests/Baxy.Integration.Tests/PlannerAppBoundaryTests.cs` | `MindApplicationArgumentsNormalizeKnownAliasesAfterExtraction` | 50/51 pruebas de integración focalizadas (1 gate físico omitido) | salida de `dotnet test` focalizado | ninguna |
| AUD-010 | verificado | compuerta `app.open` limitaba el catálogo JSONL a 64 KiB y PowerShell 5.1 añadía BOM | `scripts/test_app_open.ps1`; pruebas de compuerta limpia | límite alineado a 1 MiB, UTF-8 sin BOM y acceso acotado sin enumerar `WindowsApps` protegido | hello real de 73.493 bytes; gate `passed`, foco/ventana, replay sin duplicado y limpieza | `evidence/windows-providers/aud-005-022-runtime-evidence.json`; Python 30 + 5 subpruebas | la reproducción descubrió BOM/acceso protegido; ambos quedaron corregidos |
| AUD-011 | verificado | verificación fría de Bloc de notas no esperaba convergencia PID/ventana/foco | `WindowsApplicationOpenVerifier.cs`; pruebas de app open | espera convergencia conservando PID, creación, ejecutable y paquete exactos | 7/7 aperturas físicas, un proceso creado por ciclo y 0 residuales | `evidence/windows-providers/aud-005-022-runtime-evidence.json` | ninguna |
| AUD-012 | verificado | la ruta de acción simple perdía `confirmation_required` y permitía narración falsa | `src/Baxy.App/MainWindowViewModel.cs`; fixture de mente; `tests/Baxy.Integration.Tests/MindShellEndToEndTests.cs` | `SimpleMindActionPreservesCoreConfirmationInsteadOfClaimingSuccess` | core real pidió confirmación, UI la conservó, no afirmó navegación y cancelar vació outbox | salida focalizada 50 aprobadas, 1 gate físico omitido | ninguna |
| AUD-013 | verificado | navegación nombrada y lectura usaban sesiones CDP distintas | `NamedBrowserAdapter.cs`; `WebBrowserAdapter.cs`; pruebas de adaptadores | binding durable al mismo target CDP entre navegación nombrada y lectura | Opera 8/8; título `Example Domain` leído desde el mismo target | `evidence/browser-media-voice/aud-008-027-runtime-evidence.json` | ninguna |
| AUD-014 | verificado | cierre de última pestaña convertía la desaparición esperada del endpoint en fallo | `WebBrowserAdapter.cs`; pruebas de adaptadores | desaparición del target tras cerrar la última pestaña cuenta como postcondición `target_absent` | navegador genérico 8/8, incluida última pestaña | `evidence/browser-media-voice/aud-008-027-runtime-evidence.json` | ninguna |
| AUD-015 | verificado | tolerancia ±2 permitía omitir una orden de volumen absoluto | `WindowsAudioControlProvider.cs`; pruebas de audio | omisión preefecto exige porcentaje exacto; ±2 queda solo para postlectura | 3 % → 5 % → 3 %; mismo endpoint, restauración aplicada, sin mute | `evidence/windows-providers/aud-005-022-runtime-evidence.json` | ninguna |
| AUD-016 | verificado | búsqueda certificaba estructura sin relevancia para la consulta | `WebBrowserAdapter.cs`; pruebas de adaptador | RSS filtra por términos normalizados de la consulta y falla sin resultados pertinentes | feed irrelevante → `web_search_results_irrelevant`; consulta relacionada → 5 resultados verificados | `evidence/windows-providers/aud-005-022-runtime-evidence.json` | ninguna |
| AUD-017 | bloqueado | no existe un ONNX wake-word BAXY redistribuible ni su informe acústico FAR/FRR vinculado por hash | `voice.py`; compuertas de runtime/empaquetado y documentación ya exigen modelo + calibración aprobados | fail-closed sin activo; modo de micrófono directo preservado; gate de voz focalizado | no puede verificarse wake real sin autoridad/activo externo; instalar con `scripts/install_baxy_wake_model.ps1` y repetir gate cuando exista | `evidence/browser-media-voice/aud-008-027-runtime-evidence.json`; 38/38 pruebas de voz | bloqueo externo genuino; no se fabricó un modelo ni una calibración |
| AUD-018 | verificado | STT sin n-best dejaba `Spotify` fuera del umbral conservador | `corrector.py`; `voice.py`; pruebas de corrector/runtime | corrección acotada por términos del catálogo y muestra histórica sin abrir micrófono | muestra recuperó `Spotify`, 12 caracteres/2 tokens; transcript no persistido | `evidence/browser-media-voice/aud-008-027-runtime-evidence.json`; 38/38 pruebas de voz | ninguna |
| AUD-019 | verificado | serialización singular abría un segundo objeto JSON raíz inválido | `FilesystemHandlers.cs`; `ExternalCapabilityHandlers.cs`; pruebas de integración | hash singular válido seguido por `system.time` en el mismo loop JSONL | cadena completa 23/23, exit 0, sin cierre del core | `evidence/core-boundaries/baxy-aud019-{before,after}.json`; 8/8 pruebas de integración focalizadas | ninguna |
| AUD-020 | verificado | UIA no cargaba `UIAutomationTypes` y no tenía fallback sin `TextPattern` | `DesktopSelectAll.ps1`; `WindowsExternalCapabilityProvider.cs`; pruebas de adaptador | WPF usa `SendInput` verificado; WinForms `EM_SETSEL` + `EM_GETSEL` sobre control enfocado | blancos sintéticos WPF y WinForms 2/2, cerrados en `finally` | `evidence/windows-providers/aud-005-022-runtime-evidence.json` | ninguna |
| AUD-021 | verificado | estados de ventana se verificaban una sola vez antes de converger | `WindowsWindowControlProvider.cs`; pruebas de ventana | maximize/minimize/restore esperan convergencia acotada | cadena WPF 25/25; todas las transiciones verificadas, 0 recuperaciones tardías | `evidence/windows-providers/aud-005-022-runtime-evidence.json` | ninguna |
| AUD-022 | verificado | ventana UIAccess de OSK requería fallback `SC_CLOSE` verificable | `WindowsWindowControlProvider.cs`; pruebas de ventana | fallback `SC_CLOSE` usa la misma identidad y exige desaparición observable | `app.close` físico verificado; 0 `osk.exe` residuales | `evidence/windows-providers/aud-005-022-runtime-evidence.json` | ninguna |
| AUD-023 | verificado | el LLM podía perder efectos reconocibles y `plan` reinfería sin conservarlos | `src/baxy_mind/effect_intent.py`; `src/baxy_mind/__main__.py`; `src/baxy_mind/planner.py`; `src/Baxy.App/MindSidecarClient.cs`; `src/Baxy.App/MainWindowViewModel.cs`; pruebas Python/.NET | contrato `effectOperations`, esqueleto conservador, grounding por fragmento, cardinalidad y catálogo autenticado | matrices vivas 60/60 + 62/62 + 12/12 + 4/4 + 10/10; gate físico 9/9 completó y verificó hora + CPU | `evidence/global/routing-*-final-v2.json`; `evidence/global/routing-original-60-final-v4.json`; `artifacts/product/audit-remediation-2026-07-27/mind-shell-e2e-final-v3.json` | el E2E v2 encontró que `revisa/check` no separaba la segunda cláusula; la solución general ES/EN pasó además vetos documentales |
| AUD-024 | verificado | errores de memoria perdían `memory_disabled` y caían a un 500 opaco | `src/Baxy.App/MainWindowViewModel.cs`; `tests/Baxy.Integration.Tests/MemoryAppFlowTests.cs` | `DisabledMemoryFailureKeepsTheStableCauseAndHumanRecoveryStep`; recuperación de sesión | 50/51 pruebas focalizadas; mensaje explica habilitar memoria y no contiene 500/código interno | salida de `dotnet test` focalizado | una expectativa heredada actualizada al nuevo mensaje humano |
| AUD-025 | verificado | reformulación de memoria no exigía preservar `label: value` verificados | `src/Baxy.App/MainWindowViewModel.cs`; `tests/Baxy.Integration.Tests/PlannerAppBoundaryTests.cs` | `StatusCompositionCannotDropProjectedMemoryFacts` | compositor que omite los hechos es rechazado y usa la proyección completa | salida focalizada 50 aprobadas + 1 gate físico omitido | ninguna |
| AUD-026 | verificado | navegación certificaba URL antes de que el documento fuese consumible | `NamedBrowserAdapter.cs`; `WebBrowserAdapter.cs`; pruebas de adaptadores | navegación espera estado consumible y la lectura inmediata reutiliza target, sin demora artificial | streaming + lectura inmediata 4/4; 3,355 s + 2,449 s | `evidence/browser-media-voice/aud-008-027-runtime-evidence.json` | ninguna |
| AUD-027 | verificado | selección exacta Spotify no reintentaba un control transitorio ausente | `SpotifyDesktopAdapter.cs`; pruebas de adaptadores | reintento acotado solo antes de cualquier efecto ambiguo, con postlectura exacta | selección exacta 5/5; cadenas completas 4/5 perfectas y una 5/6 reportada honestamente | `evidence/browser-media-voice/aud-008-027-runtime-evidence.json`; Providers 392 aprobadas/4 omitidas | una pausa SMTC ambigua en ciclo 1; no se repitió a ciegas, el estado final quedó pausado y restaurado |

## Validaciones globales

| Compuerta | Resultado |
|---|---|
| Pruebas focalizadas Python/.NET | verificado: focal final 552 Python; Mind Shell 8 aprobadas + 1 física omitida; focales por defecto registradas en cada fila |
| Reproducciones originales seguras | verificado: 26 defectos con reproducción posterior; AUD-017 permanece bloqueado por activo externo |
| Recuperación JSONL post-error | verificado: continuidad posterior a Steam, winget, Bluetooth y hash; `evidence/core-boundaries/` |
| Suite Python completa | verificado: 1076 pruebas + 367 subpruebas, 0 fallos; `evidence/python-full-final-v2.xml` |
| Suite .NET completa serial | verificado con .NET SDK/runtime 10.0.100: 2117 aprobadas, 17 omisiones esperadas según el runner, 0 fallos; `evidence/dotnet-full-final-v4/` |
| Smoke de 168 operaciones | verificado: 168/168 resultados de frontera seguros; 157 rechazos de esquema + 11 rechazos privados autenticados; `evidence/global/catalog-smoke-168.json` |
| Matrices reales de routing/planificación | verificado: 60/60 canónica, 62/62 adversarial, 12/12 cardinalidad, 4/4 conservación parcial, 10/10 regresiones |
| Casos físicos seguros | verificado: grupos de provider, navegador/multimedia/voz, gate Mind Shell 9/9 y estado de audio final 3 % sin mute |
| Stress de protocolo/reinicio/replay | verificado: recuperación 11/11, fuzz 500/500, burst 5000/5000, replay/restart, reinicio abrupto 20/20 y paralelo 36/36 |
| Build y paquete oficiales | verificado como artefacto de desarrollo Release 1.0.9 dirty: 35 archivos, 171.509.336 bytes; ZIP 171.522.938 bytes, SHA-256 `9ddeb115785262a8bf487aae7619a350ca0c9f5c66ba7e814e5c715063710b65` |
| Build Setup / instalación oficial | bloqueado por autoridad: `build_setup.ps1` rechaza correctamente el working tree dirty y exige snapshot Git HEAD limpio; la orden del usuario prohíbe commit sin petición explícita |
| Validación de instalación | bloqueado por la misma restricción; instalación activa preservada en 1.0.8 y rollback 1.0.7, sin mutaciones |
| Limpieza de procesos/roots/estado | verificado: 0 procesos propios; cuatro roots de esta sesión enviados a Papelera; audio 3 % y activo |
| `git diff --check` | verificado, exit 0 sobre el estado final |

## Cierre técnico

- Build final:
  `artifacts/product/build/audit-remediation-20260727-v109-dev-v2`.
- Paquete final:
  `artifacts/product/build/package-audit-remediation-20260727-v109-dev-v2/BAXY-1.0.9-f23b23f06421-dirty-win-x64.zip`.
- El core final tiene SHA-256
  `f7ede1afc717329da00660a612364e63e233f03daa8b74d561c838b5303b8e32`,
  idéntico al core sometido al smoke de 168 operaciones y a los stress.
- Gate físico final:
  `artifacts/product/audit-remediation-2026-07-27/mind-shell-e2e-final-v3.json`,
  9/9, journal HMAC válido y exactamente
  `memory.status`, `system.time`, `system.time`, `system.status`.
- Integridad de la auditoría original: 289 archivos, 24.218.416 bytes y
  agregado SHA-256
  `a37f93de1f4e7e92519a30b4ae2b45da2b7091948c0166f7cc536e1129d75578`,
  idéntico al baseline.
- Resultado AUD: 26 verificados, 1 bloqueado (`AUD-017`). El bloqueo de Setup
  es independiente del backlog y requiere autorización explícita para crear
  un commit limpio que pueda incorporar estas fuentes.
