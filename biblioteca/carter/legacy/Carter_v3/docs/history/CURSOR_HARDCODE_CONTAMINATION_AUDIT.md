# CURSOR_HARDCODE_CONTAMINATION_AUDIT

Fecha: 2026-05-05

## Alcance auditado

- `git show --stat 6aae2b0a`
- `git show --name-only 6aae2b0a`
- `git diff HEAD~1..HEAD`
- `git diff`
- búsqueda explícita de patrones `looks_*`, `re.compile`, ramas por `user_text/text/prompt`, y vocabulario prohibido.

## Hallazgos y decisiones

| Archivo | Cambio sospechoso | ¿Es hardcode? | Por qué | Mantener/Revertir/Refactorizar | Alternativa universal |
|---|---|---|---|---|---|
| `src/carter_v3/request_patterns.py` | `_FILESYSTEM_READ` + `looks_filesystem_read_request()` con `lee/read/abre/open` | Sí | Routing por palabras del usuario para intención semántica | Revertir | Usar selección de tool por capacidad/estado y, cuando aplique, extracción estructural de ruta sin helper semántico de intención |
| `src/carter_v3/request_patterns.py` | `IMPERATIVE_SUFFIXES` agregó `pon` | Sí (sospechoso fuerte) | Token específico de lenguaje agregado para cubrir casos concretos del log | Revertir | Mantener heurística morfológica genérica, sin sumar verbos concretos por incidente |
| `src/carter_v3/request_patterns.py` | `extract_windows_path()` nuevo | No | Parsing estructural de forma de ruta Windows | Mantener (aislado, sin routing semántico) | Si se usa, invocarlo solo después de decisión estructural de herramienta, no por intención textual |
| `src/carter_v3/agent.py` | `looks_action` incluye `looks_filesystem_read_request` | Sí | Acopla ejecución a helper semántico basado en palabras | Revertir | Dejar decisión al flujo general LLM + TOOL_CATALOG + policy/verifier |
| `src/carter_v3/agent.py` | `_local_short_reply` con regex explícito `hgo+la+` | Sí | Branch por typo específico del log (`HGOla`) | Revertir | Manejo general por clasificador/LLM corto sin tokens de typo puntuales |
| `src/carter_v3/turn_support.py` | `select_tools()` prioriza `filesystem_read_text` con `looks_filesystem_read_request` | Sí | Enrutamiento semántico por palabras | Revertir | Priorización basada en forma estructural/capacidades, no en frase concreta |
| `src/carter_v3/response_composer.py` | lectura `outcome.evidence["preexisting"]` | No | Usa evidencia del verificador, no texto usuario | Mantener | Mantener composer basado en evidence/data |
| `src/carter_v3/resolvers/intent_classifier.py` | regex typo `h+g*o+l+a+` | Sí | Detector de typo específico para pasar caso puntual | Revertir | Clasificación general de low-info sin patrones de typo ad-hoc |
| `src/carter_v3/intent_classifier.py` | archivo solicitado por checklist no existe | N/A | La implementación real está en `src/carter_v3/resolvers/intent_classifier.py` | N/A | Mantener referencia correcta en próximos audits |
| `src/carter_v3/cli/launcher.py` | `_safe_print` para `UnicodeEncodeError` | No | Robustez de I/O, sin semántica de intención | Mantener | Continuar manejo de encoding como plumbing |
| `audit/hardcode_guard.py` | guard previo no detectaba `looks_filesystem_read_request` ni branches `if "lee" in user_text` | Sí (brecha de guard, no bug runtime) | Permitía reintroducción de hacks semánticos | Refactorizar/Endurecer | Regla explícita para `semantic_token_in_text_branch` y `looks_helper_semantic_intent_name` |
| `tests/test_no_semantic_hardcodes.py` | faltaban casos para ramas por tokens semánticos y helper `looks_filesystem_read_request` | Sí (brecha de test) | Cobertura incompleta del guard | Refactorizar/Endurecer | Añadir tests negativos para patrones prohibidos |
| `tests/test_live_regressions_from_user_log.py` | expectativa rígida de `TRIVIAL` para `HGOla` | Sí (acoplamiento a typo) | Incentiva hardcode de typo específico | Refactorizar | Validar ausencia de tool-call y comportamiento seguro, no token exacto |
| `tests/test_runtime_persona_and_capabilities.py` | casos con términos como `alarma` | No | Uso en test/documentación permitido | Mantener | Mantener assertions estructurales por TOOL_CATALOG |
| `tests/test_pending_intent_followups.py` | prompts con nombres de apps en fixtures | No | Test de flujo, no routing hardcode en core | Mantener | Conservar como regresión de comportamiento |
| `tests/test_runtime_no_fake_success_live_cases.py` | textos de ejemplo con `alarma/steam` | No | Evidencia de no-fake-success, no lógica de core | Mantener | Continuar validando por evidence/status |

## Resultado del endurecimiento (antes de tocar producción)

- `python -m pytest tests/test_no_semantic_hardcodes.py -v` -> **FAIL** (detectó contaminación real).
- `python audit/hardcode_guard.py` -> **FAIL** con:
  - `request_patterns.py: looks_helper_semantic_intent_name (looks_filesystem_read_request)`

Esto confirmó contaminación efectiva y habilitó la fase de revert/refactor.

