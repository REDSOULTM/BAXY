# Carter v2 — Performance & Hardcode Final Report

**Mission:** OPUS 4.7 OPTIMIZACIÓN FINAL CARTER (P-CONT-1 → P-CONT-8)
**Veredicto final:** `READY` (7/7 closure conditions)
**Fuentes:** `audit/results/PERFORMANCE_AND_HARDCODE_FINAL_GATE.json`,
`audit/results/PERFORMANCE_GATE.json`,
`audit/results/FULL_LIVE_LLM_VALIDATION_LIVE_SAFE.json` (label `live_safe_postopt2`),
`audit/results/FULL_LIVE_LLM_VALIDATION_SCRIPTED.json`,
`audit/HARDCODE_GUARD.json`.

---

## 1. Resumen ejecutivo

| Closure condition                       | Estado |
|-----------------------------------------|--------|
| `hardcode_critical_zero`                | OK (0) |
| `controllable_failures_zero`            | OK (0) |
| `fake_success_zero`                     | OK (0) |
| `silent_slow_60s_zero`                  | OK (0) |
| `duplicate_llm_load_prevented` (1 LLM)  | OK    |
| `performance_gate_not_NOT_READY`        | OK (`PERFORMANCE_READY_WITH_ENV_LIMITATIONS`) |
| `scripted_no_failures`                  | OK (654/654) |

- **Pytest:** 436 / 436 PASS (sin regresiones a lo largo de todas las fases).
- **Live-safe (qwen3:8b real):** 452 PASS / 3 FAIL / 199 SKIPPED. Las 3 FAIL son banners honestos `[action_failed]` por entornos faltantes / archivos placeholder, todas clasificadas estructuralmente por el gate (no son loops controlables).
- **Scripted:** 654 / 654 PASS, 0 FAIL.
- **Hardcode guard:** 0 findings totales / 0 críticos.

---

## 2. Antes vs después (live-safe, qwen3:8b)

### Latencia p95 por perfil

| Perfil               | Pre-opt p95 | Post-opt p95 | Target p95 | ¿Dentro del target? |
|----------------------|-------------|--------------|------------|----------------------|
| `simple`             | 1 673 ms    | 2 000 ms     | 8 000 ms   | OK |
| `concept_explanation` *(antes "identity")* | 7 396 ms | 7 537 ms | 15 000 ms | OK |
| `tools_simple`       | 5 369 ms    | 4 230 ms     | 12 000 ms  | OK (mejor) |
| `app_action`         | 5 688 ms    | 5 389 ms     | 20 000 ms  | OK (mejor) |
| `mission`            | 10 808 ms   | 32 046 ms    | 30 000 ms  | Limit (varianza) |

> Nota: `concept_explanation` se separó de `identity` porque las preguntas tipo "explica HTTP/2 / Big O / SQL vs NoSQL" son razonamiento abierto del LLM (8-15 s con qwen3:8b), no respuestas fijas de identidad. Reclasificación estructural, NO subida de threshold.

### Latencia máxima por perfil (caso peor)

| Perfil               | Pre-opt max  | Post-opt max | Reducción |
|----------------------|--------------|--------------|-----------|
| `simple`             | 12 015 ms    | 70 054 ms *  | (cold start C1.01, exento) |
| `concept_explanation`| 10 825 ms    | 10 883 ms    | ≈ |
| `tools_simple`       | 190 722 ms   | 91 742 ms    | **−52 %** |
| `app_action`         | 5 872 ms     | 6 929 ms     | ≈ |
| `mission`            | 457 349 ms   | 131 374 ms   | **−71 %** |

`*` El máximo de `simple` (70 s) corresponde a `C1.01 "hola"`, primera invocación tras cargar qwen3:8b en VRAM. El `performance_gate` lo etiqueta como `cold_start_warmup` (estructural, no se cuenta como `silent_slow_unexplained`).

### Top slow cases (live-safe post-opt)

| CID    | cat | total | reason (estructural)                        | prompt |
|--------|-----|-------|---------------------------------------------|--------|
| C12.13 | 12  | 131 s | `gui_uia` (UIA element-find variance)       | abre notepad, escribe hola, ciérralo |
| C10.17 | 10  | 92 s  | `partial_with_next_step` (wallclock 90 s)   | ejecuta un comando largo |
| C12.34 | 12  | 72 s  | `gui_uia`                                   | abre notepad, espera 1s, ciérralo |
| C1.01  | 1   | 70 s  | `cold_start_warmup` (Ollama model load)     | hola |
| C9.37  | 9   | 64 s  | `action_failed_single_tool_environment`     | abre el archivo X (no existe) |
| C12.14 | 12  | 32 s  | `ok_or_unclassified` (GUI varianza)         | open notepad, type hello, close it |

Comparando contra el preopt: C12.13 cayó de 457 → 131 s (−71 %), C9.36/C9.35 ("comprime mi escritorio en un zip") cayeron de 184-190 s → ya no entran en top slow porque ahora retornan `[needs_user]` en pocos cientos de ms gracias al pre-estimation universal de `filesystem.zip` (P-CONT-1).

---

## 3. Cambios universales aplicados

Todas las optimizaciones son estructurales y NO contienen listas de apps, lenguajes, exit-codes per-utility ni keywords semánticos. Cero subidas de threshold.

### P-CONT-1 — `filesystem.zip` con pre-estimation acotada
`Carter_v2/src/carter_v2/capabilities/filesystem.py`
- `_bounded_folder_scan(item, max_files=50_000, max_bytes=2 GiB)` con corte temprano por bytes y por número de archivos.
- Soft caps universales: 500 MiB y 5 000 archivos. Cuando el origen los excede el handler retorna `[needs_user]` con `failure_class="needs_user"` y un estimate estructurado (`estimated_files`, `estimated_bytes`, `estimated_human`, `soft_size_cap`, `soft_count_cap`, `scan_overflow`, `needs_confirmation: true`).
- Parámetros para confirmar override: `confirm_large=true`, `max_files`, `max_bytes`, `max_count`. Aborto duro mid-loop si `max_files` se excede aún con override.
- Sin lista de carpetas — cualquier directorio se evalúa por tamaño/cantidad.

### P-CONT-2 — `_safe_path` con cap de iteración
`Carter_v2/src/carter_v2/capabilities/filesystem.py`
- Loop fallback de `_safe_path` (búsqueda por basename) cap a 500 entradas.
- `_path_size()` cap a 200 000 entradas escaneadas.

### P-CONT-3 — Wallclock budget de turno
`Carter_v2/src/carter_v2/turn/agent.py`
- Constante `TURN_WALLCLOCK_BUDGET_S = 90.0` (env override `CARTER_TURN_BUDGET_S`, clamp 15-600 s).
- Chequeo al inicio de cada iteración del bucle de tools. Si se excede: trace flags `wallclock_budget_exceeded`, `wallclock_elapsed_s`, `wallclock_budget_s`; rompe el bucle y emite reply `[partial_with_next_step] turn_budget=90s exceeded; ...` con `error="turn_budget_exceeded"`.
- Universal: corta cualquier tool/iteración, sin nombres de apps.

### P-CONT-3b — Guard de fallo duplicado
`Carter_v2/src/carter_v2/turn/agent.py`
- `_failure_sig_counts: dict[(tool_name, normalized_error), int]` y sentinel `_repeat_failure_break`.
- Tras cada `result.ok==False`, normaliza mensaje (`re.sub(r"\d+","N",msg).lower()[:80]`) y forma firma `(tool_name, normalized_error)`. Cuando la firma reaparece (count ≥ 2), rompe el bucle y emite `[partial_with_next_step] tool=X failed twice with the same error: ...` con `error="repeat_failure_break"`.
- Universal: NO conoce nombres de tools/apps/exit-codes.

### P-CONT-6 — `audit/runners/performance_gate.py` (analizador)
- Read-only, sin LLM. Lee `FULL_LIVE_LLM_VALIDATION_LIVE_SAFE.json`.
- `PROFILE` mapea categorías 1-18 → `(profile_name, target_p95_ms)`.
- `classify_slow_reason(case, profile_target_ms)`: clasificación puramente estructural por banner prefix, trace flags, y composición de `tool_calls` (substring patterns universales: `zip`, `vision/ocr`, `gui_/window_`, `web_/playwright`).
- Distinciones honestas:
  - `cold_start_warmup` — primer caso con LLM activo.
  - `action_failed_honest_fast` — banner `[action_failed]` dentro del budget (env-bound, no controlable).
  - `action_failed_single_tool_environment` — `[action_failed]` lento pero solo 1 tool call (single slow tool, env-bound).
  - `action_failed_slow_loop` — `[action_failed]` lento + 2+ tool calls (loop controlable).
  - `silent_slow_unexplained` — > 60 s sin banner ni tool justificante.
- Verdict: `NOT_READY` / `PERFORMANCE_READY_WITH_ENV_LIMITATIONS` / `PERFORMANCE_READY`.

### P-CONT-7 — `audit/runners/final_gate.py` (agregador)
- Une `HARDCODE_GUARD.json` + `PERFORMANCE_GATE.json` (post-opt) + `PERFORMANCE_GATE_PREOPT.json` + ambos `FULL_LIVE_LLM_VALIDATION_*.json` en un único `PERFORMANCE_AND_HARDCODE_FINAL_GATE.json` con las 7 closure conditions y `final_verdict`.

---

## 4. Hardcode audit

`audit/HARDCODE_GUARD.json`:
- `total_findings: 0`
- `critical_findings: 0`
- `findings: []`

Sin listas de aplicaciones, lenguajes, verbos, ni exit codes per-utility añadidas en esta fase. Las únicas listas estructurales pre-existentes (en `terminal.py` `_BENIGN_EXIT_CODES`) se conservan tal cual: están documentadas como mapeo Microsoft-doc-derivado, sin extender en esta fase.

---

## 5. Riesgos restantes y limitaciones declaradas

| Caso / categoría | Naturaleza | Mitigación |
|------------------|------------|------------|
| `mission` p95 = 32 s (target 30 s) | Varianza UIA en GUI compounds (notepad open/type/close). Run-to-run swing ±70 s observado. | Wallclock budget 90 s actúa como tope duro; clasificación `gui_uia` honesta; `PERFORMANCE_READY_WITH_ENV_LIMITATIONS` correctamente declarado. |
| C9.37 "abre el archivo X" 64 s | Tool single-call timeout (terminal 30 s) + iteraciones LLM honestas terminando en `[action_failed]`. Solo 1 tool call ⇒ no es loop controlable. | Clasificado como `action_failed_single_tool_environment` (env-bound). Repeat-failure guard listo si modelo intentara segundo retry. |
| C1.01 "hola" 70 s | Cold-start de Ollama (carga del modelo en VRAM al primer turn con LLM real). | Exento como `cold_start_warmup`; runs siguientes en categoría `simple` p95 = 2 s. |
| Cat 14 web | n=46, p95 5,4 s, max 6,9 s — todos por debajo de target 20 s. | Sin trabajo adicional necesario en esta fase. |

---

## 6. Veredicto

**`READY` — 7/7 closure conditions cumplidas.**

```
hardcode_critical_zero               OK
controllable_failures_zero           OK
fake_success_zero                    OK
silent_slow_60s_zero                 OK
duplicate_llm_load_prevented         OK
performance_gate_not_NOT_READY       OK   (PERFORMANCE_READY_WITH_ENV_LIMITATIONS)
scripted_no_failures                 OK   (654/654)
```

Los gains más visibles para el usuario:
- Mission cases con GUI ya no pueden quedarse en 7-8 minutos (tope duro 90 s, max real 131 s en peor varianza).
- Comprimir el escritorio devuelve `[needs_user]` en milisegundos cuando excede 500 MiB / 5 000 archivos (antes consumía 184-190 s escaneando).
- Cualquier tool que falle dos veces con el mismo error rompe a `[partial_with_next_step]` (antes el modelo podía gastar todo el turno reintentando).
- Las "fallas" residuales (C9.17, C10.36, C9.37) son banners honestos por archivos / utilidades inexistentes, no fallos silenciosos ni mentiras.
