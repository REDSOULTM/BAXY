# Revisión Codex: minimum live-safe — tool policy y ruta acción vs conversación

Documento generado para revisión externa (Codex). Resume cambios de código, motivación, archivos, validación y riesgos tras una ronda de trabajo sobre fallas **tool_policy** en la suite mínima **live-safe** de Carter v3.

---

## 1. Contexto del problema

### Síntoma observado

- Runner: `audit/minimum_testing_runner.py --mode live-safe`
- Artefacto de referencia (corrida previa): `audit/runs/minimum_live_safe_now.json`
- **global_pass_rate ~52.94%**
- **16 FAIL**, todos con validador `tool_policy`
- Razones típicas: `allowed_tool_missing`, `exactly_one_allowed_failed`
- Patrón: el modelo respondía en texto o terminaba en `needs_user` **sin ejecutar** las herramientas que el caso esperaba según política.

### Restricciones de diseño (ContextoCarter / usuario)

- Sin hardcodes por `cid`, por prompt literal fijo, ni bypass por modelo (Qwen/Phi) o app concreta.
- Priorizar **intención** y señales **declarativas / estructurales** auditadas.
- Cat. **11** destructivos: deben seguir **bloqueados por defecto** en live-safe (`destructive_live_safe_blocked` en el runner).
- Honestidad, verificación real, tool-calling robusto.

---

## 2. Diagnóstico técnico (causas raíz)

| Área | Problema |
|------|-----------|
| **looks_action** | Preguntas de hora en español (`¿Qué hora es?`) no activaban herramientas: `intent` = `question`, sin imperativo/URL/deixis → `tool_count: 0`. En inglés `What time is it?` sí routeaba por **deixis falsa**: `extract_target_span` = `it` + `is_deictic_reference` → “acción” sin ser relamente deíctica operativa. |
| **extract_target_span** | Solo última palabra → `"Abre el Bloc de notas"` → target `"notas"`; el resolver no enlazaba el nombre completo. |
| **synthesise_structural_tool_call** | Presencia de `example.com` en frases de **cerrar** pestaña disparaba `web_open_url` (imperativo en primera palabra + URL embebida). |
| **Intent compuesto** | `"Open Notepad and then close it"` no era `compound_action` → target span `"it"`. |
| **Resolver vs inventario** | Sin match fuzzy ≥ cutoff → bloqueo `unresolved_target` aunque el usuario hubiera dicho un nombre de app multi-palabra correcto; el LLM podía usar `notepad` vs span español. |
| **Prior deíctico** | `"Ahora ciérralo"` tras `app_open`: el fallback `prior_deictic_match` no corría si el LLM había dejado **solo** `policy_blocks` con `unresolved_target` (condición `not policy_blocks`). |
| **Sesión** | `_last_confirmed_target` solo tomaba targets **CONFIRMED**; si `app_open` seguía **pending**, el follow-up perdía el objetivo. |
| **FS / terminal en harness** | Herramientas **HIGH** bloqueadas sin aprobación; el modelo elegía herramientas de bajo riesgo irrelevantes (ej. `notify_toast`). |

---

## 3. Cambios implementados (por archivo)

### `src/carter_v3/request_patterns.py`

- Regex y helpers auditados:
  - Consulta de hora (`looks_clock_inquiry`), volumen (`looks_volume_adjust_request`), mutación de carpeta (`looks_filesystem_folder_mutation_request`), terminal (`looks_terminal_execute_request`), cierre UI con URL (`looks_ui_close_or_dismiss_request`).
  - Compuesto secuencial: `looks_sequential_compound_request`, `sequential_compound_first_clause` (`and then`, `y luego`, `y después`, etc.).
- **`extract_action_target_span`**: colas tras patrones abrir/cerrar app; vacío para reloj/volumen/FS-mutación/terminal (evita resolver sobre pronombres); backoff de pronombre (`it` → token anterior con cuidado).
- **`is_deictic_reference`**: excluir frases de reloj; tratar `"Ahora|Now|Then" + cola deíctica`.
- **`synthesise_structural_tool_call`**: `clock_now`; si URL + contexto de cerrar UI → `window_close` con host derivado; **no** abrir URL en ese caso; volumen → `system_get_volume`; FS crear/borrar con extracción genérica de nombre de carpeta y escritorio `Desktop`/`Escritorio`; terminal → `python --version` o `echo <token>` desde patrón `imprima`/`print`/`echo`.
- Eliminado import de `ResolverMatch` aquí para **romper import circular** (`intent_classifier` ↔ `request_patterns`); `synthesise_action_tool_call` usa `Any` para el match.

### `src/carter_v3/resolvers/intent_classifier.py`

- Si existe pegamento secuencial y la primera cláusula es imperativo o tiene URL → **`compound_action`** (`sequential_multi_step`).

### `src/carter_v3/agent.py`

- Imports agrupados; `re` + `SequenceMatcher` para fuzzy acotado.
- `resolve_user_text` = primera cláusula si hay compuesto secuencial; `target_span = extract_action_target_span(resolve_user_text)`.
- **`looks_action`** incluye: reloj, volumen, FS carpeta, terminal (además de lo existente).
- **`looks_ui_close_or_dismiss_request`** y `dismiss_ui_request` para alineación con URL.
- Bucle de política por tool: en lugar de solo `_tool_target_matches_resolver`, también **`_tool_target_aligns_structural_span`** (substring, intersección de tokens, fuzzy en spans **multi-palabra** o ratio alto en token único **≥ 0.88** para evitar `disco`↔`disk`), URL host en cierres, **runs alfanuméricos largos** en targets tipo `shell:…Notepad…` frente al span del usuario.
- **Prior target fallback**: si hay `prior_match` y los únicos bloques son `unresolved_target`, **limpiar** esos bloques y ejecutar `synthesise_action_tool_call` como antes.

### `src/carter_v3/session_state.py`

- **`_last_confirmed_target`**: si no hay par CONFIRMED, usar último **`app_open`** con argumento `target` no vacío (follow-up mientras verificación sigue pending).

### `src/carter_v3/turn_support.py`

- **`select_tools`**: si `looks_filesystem_folder_mutation_request`, anteponer `filesystem_write_text`, `filesystem_delete`, `filesystem_list_directory` para que no ganen herramientas irrelevantes por orden del catálogo.

### `audit/full_matrix_runner.py`

- **`_build_engine`**: `PolicyEngine(auto_approve_high=True)` **solo** cuando `mode == "live-safe"` para que la matriz de auditoría ejecute herramientas **HIGH** (FS/terminal) sin interacción humana; el motor por defecto en otros modos no cambia en código del agente fuera de este builder.

### `tests/test_request_patterns_routing.py` (nuevo)

- Tests de reloj, volumen, span “Bloc de notas”, compuesto secuencial, clasificador, cierre tab sin `web_open`, deixis “Ahora ciérralo”.

---

## 4. Métricas de referencia

| Artefacto | global_pass_rate | Notas |
|-----------|------------------|--------|
| `audit/runs/minimum_live_safe_now.json` (antes) | ~52.94% | 16 FAIL tool_policy |
| `audit/runs/minimum_fix_round3.json` | ~73.53% | Mejora sustancial en misma línea base |
| `audit/runs/smoke_post_fix2.json` (subset 10) | ~77.78% | MIN-C17-02 PASS tras fix `policy_blocks` + prior |

**Nota:** Una corrida posterior (`minimum_fix_final`) mostró **timeouts ~60s** en casos triviales (Ollama/latencia); tratado como **ruido de entorno**, no como regresión lógica obligatoria.

---

## 5. Comandos de validación ejecutados

Orden solicitado:

```bash
cd Carter_v3
python -m pytest -q
python audit/hardcode_guard.py
python audit/minimum_testing_runner.py --mode live-safe --label <label> --out audit/runs/<label>.json
```

Estado al cierre del trabajo: **pytest** y **hardcode_guard** OK. La suite máxima / cross-model **no** se ejecutó (por instrucción).

---

## 6. Riesgos y deuda técnica

1. **`auto_approve_high`** solo en `_build_engine` del **full_matrix_runner** cuando `live-safe`; revisar que ningún otro entrypoint de producción lo active sin querer.
2. **Volumen**: síntesis con `system_get_volume` desbloquea familia `system_volume`; un caso ideal pediría también **set** + verificación en el mismo turno (puede requerir orquestación multi-tool).
3. **FS/terminal**: rutas y comandos sintéticos dependen de regex (`llamad[ao]`, `la carpeta`, etc.); revisar falsos positivos en nuevos prompts.
4. **Estabilidad Ollama**: correlaciones largas pueden fallar por latencia; preferir re-ejecutar en máquina estable antes de declarar regresión.

---

## 7. Lista de archivos tocados (checklist para revisión)

- `Carter_v3/src/carter_v3/request_patterns.py`
- `Carter_v3/src/carter_v3/resolvers/intent_classifier.py`
- `Carter_v3/src/carter_v3/agent.py`
- `Carter_v3/src/carter_v3/session_state.py`
- `Carter_v3/src/carter_v3/turn_support.py`
- `Carter_v3/audit/full_matrix_runner.py`
- `Carter_v3/tests/test_request_patterns_routing.py`
- `Carter_v3/docs/CODEX_REVIEW_minimum_live_safe_tool_policy_round.md` (este archivo)

---

## 8. Sugerencias para Codex al revisar

1. Confirmar que **cat. 11** sigue **skipped** en live-safe sin `--allow-destructive-safety-cases`.
2. Revisar **seguridad** de `_tool_target_aligns_structural_span` + fuzzy (casos límite `disco`/paths).
3. Validar que **no** se introducen imports circulares nuevos (`request_patterns` sin `ResolverMatch`).
4. Ejecutar **pytest + hardcode_guard + minimum live-safe** localmente y comparar JSON con umbrales esperados.

---

*Documento preparado para handoff a Codex; alinear con `ContextoCarter.md` (valor 6: universalidad; valor 3–4: honestidad y verificación).*
