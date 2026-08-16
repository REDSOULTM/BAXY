# FULL_TEST_CAPABILITY_MAP

Fecha: 2026-05-06

## Inventario de pruebas

- Pytest: 32 archivos `tests/*.py`, 478 tests recolectados en baseline.
- Minimum runner: 36 casos, 18 categorías x 2.
- Full matrix runner: 654 casos, 18 categorías, mínimo 30 por categoría; importa `legacy/Carter_v2/audit/runners/full_live_llm_cases.py`.
- No existe runner separado `category_30_runner.py`; el runner equivalente es `audit/full_matrix_runner.py --category N`.

## Cobertura full matrix por categoría

| Categoría | Casos full | Casos minimum | Clase solicitada |
|---:|---:|---:|---|
| 1 | 40 | 2 | CONVERSATION |
| 2 | 32 | 2 | IDENTITY_PERSONA |
| 3 | 31 | 2 | CONVERSATION |
| 4 | 31 | 2 | MEMORY_WRITE / MEMORY_RECALL / MEMORY_FORGET / PRIVACY_SECRET |
| 5 | 35 | 2 | MEMORY_WRITE / IDENTITY_PERSONA |
| 6 | 37 | 2 | CALENDAR_TIME / VOLUME_AUDIO / TERMINAL_SAFE read-only/system |
| 7 | 33 | 2 | APPS_WINDOWS |
| 8 | 36 | 2 | BROWSER_WEB |
| 9 | 38 | 2 | FILESYSTEM / DANGEROUS_POLICY_BLOCK |
| 10 | 37 | 2 | TERMINAL_SAFE / DANGEROUS_POLICY_BLOCK |
| 11 | 49 | 2 | DANGEROUS_POLICY_BLOCK / PRIVACY_SECRET |
| 12 | 40 | 2 | FOLLOW_UP_PENDING / APPS_WINDOWS / FILESYSTEM / BROWSER_WEB |
| 13 | 47 | 2 | GUI_PERCEPTION |
| 14 | 46 | 2 | FOLLOW_UP_PENDING / APPS_WINDOWS ambiguity |
| 15 | 30 | 2 | CONVERSATION / latency / anti-placeholder |
| 16 | 31 | 2 | IDENTITY_PERSONA / CALENDAR_TIME / APPS_WINDOWS multilingual |
| 17 | 31 | 2 | FOLLOW_UP_PENDING |
| 18 | 30 | 2 | Real user regressions mixed |

## Tabla obligatoria de capacidades por test/caso

| Categoría | Caso/Test | Qué exige | Capacidad real necesaria | Existe hoy | Estado | Riesgo | Qué módulo toca |
|---|---|---|---|---|---|---|---|
| CONVERSATION | Full C1.* / MIN-C01-* / tests chat guards | Responder saludos, fillers e inputs triviales sin tools ni active-app leak | Chat LLM-first, intent low-info, guards | Sí | PASS histórico; baseline pytest no falla aquí | Latencia, canned replies | `intent_classifier.py`, `agent.py`, `llm_verbalizer.py`, `guards.py` |
| IDENTITY_PERSONA | Full C2.* / MIN-C02-* / persona tests | Identificarse como Carter local y explicar alcance real | Prompt persona derivado de catálogo | Sí | PASS | Generic cloud disclaimer | `turn_support.py`, `llm_verbalizer.py` |
| CONVERSATION | Full C3.* / MIN-C03-* | Conocimiento general sin tools | Chat/knowledge route sin usar active app | Sí | PASS | Hallucinations | `agent.py`, `llm_verbalizer.py`, `guards.py` |
| MEMORY_WRITE | Full C4 declarative / MIN-C04-01 / memory tests | Guardar hechos explícitos no secretos | `memory_save` + `MemoryStore` SQLite | Sí | PASS histórico | Guardar ruido o secreto | `memory/store.py`, `declarative_detector.py`, `agent.py` |
| MEMORY_RECALL | Full C4 recall / MIN-C04-02 / memory tests | Recordar facts locales y pending session facts | `memory_recall`, memory snapshot, pending offer | Sí | PASS | Inventar memoria ausente | `memory/store.py`, `turn_support.py`, `llm_verbalizer.py` |
| MEMORY_FORGET | Full C4 delete prompts | Borrar memoria solicitada | `memory_delete` | Sí | Cubierto en matrix; unit coverage parcial | Borrar demasiado | `memory/store.py`, `policy.py` |
| PRIVACY_SECRET | Full C4 secret prompts / tests secret | No guardar passwords/SSN/cookies/SSH | `secret_filter`, policy blocks | Sí | PASS | Exfil/secret persistence | `secret_filter.py`, `policy.py`, `agent.py` |
| IDENTITY_PERSONA | Full C5.* / MIN-C05-* | Preferencias de estilo one-shot/durables solo si explícitas | Style prompting + optional memory | Parcial | PASS histórico | Persistir preferencias accidentales | `declarative_detector.py`, `llm_verbalizer.py` |
| CALENDAR_TIME | Full C6 time / MIN-C06-01 / time tests | Leer hora local | `clock_now`; `system_get_time` redundante | Sí | PASS | Responder hora sin tool | `dispatch_misc.py`, `request_patterns.py` |
| VOLUME_AUDIO | Full C6 volume / MIN-C06-02 / audio tests | Leer/set/mute volumen con verificación o needs_environment | `system_get_volume`, `system_set_volume`, `system_mute` | Sí | PASS si pycaw o needs_environment honesto | Fake success sin pycaw | `dispatch_system.py`, `verifier.py`, `agent.py` |
| TERMINAL_SAFE | Full C6 system probes | System read-only, procesos, IP, RAM/CPU/GPU | Read-only tools | Sí | PASS | Usar terminal como workaround | `dispatch_system.py`, `dispatch_misc.py`, `terminal_helpers.py` |
| APPS_WINDOWS | Full C7.* / MIN-C07-* / resolver tests | Abrir/cerrar apps por nombre resuelto, verificar | `app_open`, `app_close`, resolver, verifier | Sí | Parcial: app_close absent behavior en transición | Fake success, cerrar ventana equivocada | `agent.py`, `app_resolver.py`, `dispatch_app.py`, `verifier.py` |
| BROWSER_WEB | Full C8.* / MIN-C08-* / web tests | Open/search/extract web liviano | `web_open_url`, `web_search`, `web_extract` | Sí | PASS histórico | Privacidad/historial/browser side effects | `dispatch_web.py`, `web_helpers.py`, `verifier.py` |
| FILESYSTEM | Full C9.* / MIN-C09-* / filesystem tests | List/read/search/write/delete controlado, backup/verifier | Filesystem tools + policy | Sí | PASS histórico | Borrado amplio/destructivo | `dispatch_filesystem.py`, `filesystem_helpers.py`, `policy.py`, `verifier.py` |
| TERMINAL_SAFE | Full C10.* / MIN-C10-* / terminal tests | Ejecutar comandos seguros, bloquear destructivos | `terminal_run_command` + allow/deny safety | Sí | PASS histórico | taskkill/shutdown/rm -rf | `dispatch_terminal.py`, `terminal_helpers.py`, `policy.py`, `verifier.py` |
| DANGEROUS_POLICY_BLOCK | Full C11.* / MIN-C11-* | Bloquear borrado, shutdown, force kill, exfil, registry, secrets | Pre-LLM policy + tool policy | Sí | PASS histórico; debe revalidarse | Acción real crítica | `policy.py`, `agent.py`, runners |
| FOLLOW_UP_PENDING | Full C12.* compound / MIN-C12-* | Ejecutar misiones compuestas con verificación por paso | Step materialization + budget + session | Parcial | PASS histórico | Marcar complete con pasos pendientes | `agent.py`, `contracts.py`, `session_state.py` |
| GUI_PERCEPTION | Full C13.* / MIN-C13-* / perception tests | Window/process/UIA/screenshot, sin VLM pesado | Perception ladder + screenshot/window_list/gui stubs | Parcial | PASS scope limitado | Usar visión para trivial; GUI unsafe | `perception/*`, `dispatch_window.py`, `dispatch_misc.py` |
| FOLLOW_UP_PENDING | Full C14.* / MIN-C14-* | Typos/ambigüedad; preguntar si target genérico | Resolver + ambiguity gates | Sí | PASS histórico | App wrong launch | `resource_resolver.py`, `agent.py`, `request_patterns.py` |
| CONVERSATION | Full C15.* / MIN-C15-* / guard tests | Anti-placeholder, recovery, latency | Guards + retries | Sí | PASS | Canned/low-info output | `guards.py`, `agent.py`, `llm_verbalizer.py` |
| IDENTITY_PERSONA | Full C16.* / MIN-C16-* | Multilingüe; same structural behavior | LLM language prompt + catalog | Sí | PASS | Script mismatch | `turn_support.py`, `guards.py` |
| FOLLOW_UP_PENDING | Full C17.* / MIN-C17-* | Prior turns y deictic follow-ups limpios | `prior_turns`, `SessionState` | Sí | PASS histórico; diff inicial mejora shape | Active-app contamination | `session_state.py`, `turn_support.py`, `agent.py` |
| CONVERSATION/APPS_WINDOWS | Full C18.* / MIN-C18-* | Regresiones reales del usuario | Mixed capabilities | Sí | PASS histórico | Recaer a fake success/app hacks | Varios |
| ALARMS_REMINDERS | `test_alarm_missing_does_not_claim_success`, `test_missing_delayed_capability_does_not_suggest_direct_terminal_workaround`, smoke S22/S23 | Antes exigía rechazo honesto al no existir tool; prompt actual exige implementar si legítimo | Local reminder/alarm create/list/cancel/get/cleanup persistente y verificable | No | NOT READY para true capability closure | Fake success, terminal workaround, OS alarm hallucination | Nuevo módulo store/dispatch/verifier/composer/tests |
| DANGEROUS_POLICY_BLOCK | Dangerous prompts reales | Prompt puede ejecutarse, acción peligrosa no | Policy blocks y no dispatch | Sí | Debe revalidarse final | Critical failures | `policy.py`, runners |

## Clasificación requerida

- CONVERSATION: C1, C3, C15, parte C18.
- IDENTITY_PERSONA: C2, C16 identity, persona tests.
- MEMORY_WRITE: C4 declarative, C5 durable preferences.
- MEMORY_RECALL: C4 recall, pending facts, name recall.
- MEMORY_FORGET: C4 delete/forget.
- PRIVACY_SECRET: C4 secret, C11 cookies/SSH/passwords.
- FILESYSTEM: C9, compound C12.
- TERMINAL_SAFE: C10, safe system probes.
- APPS_WINDOWS: C7, C12, C14, C16 app.
- BROWSER_WEB: C8, C12 web.
- VOLUME_AUDIO: C6 volume.
- ALARMS_REMINDERS: currently only missing-capability tests; should become real local capability tests.
- CALENDAR_TIME: C6 time; future scheduling missing.
- MESSAGING_DRAFT: not implemented; only policy/out-of-scope if encountered.
- DANGEROUS_POLICY_BLOCK: C11, destructive C9/C10.
- FOLLOW_UP_PENDING: C12, C14, C17.
- GUI_PERCEPTION: C13.
- UNSUPPORTED_OUT_OF_SCOPE: VLM/OCR full, voice, camera, destructive OS actions, real third-party messaging.

## Conclusión del mapa

La matriz actual de 654 no contiene prompts de alarma/recordatorio. Los tests unitarios actuales cubren solo honestidad de capability missing. Para cumplir el prompt de cierre verdadero y no dejar una capacidad legítima eternamente ausente, se debe añadir una capability local de recordatorios/alarmas y convertir los tests missing-capability en tests de create/list/cancel/persistencia/no-fake-success.
