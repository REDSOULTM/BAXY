# Performance & Hardcode Audit — Carter v2
**Mission:** OPUS 4.7 — OPTIMIZACIÓN FINAL DE CARTER: 5–8s REAL + CERO HARDCODE LINGÜÍSTICO
**Date:** 2026-05-02
**Repo:** `Carter_v2/`
**Mode:** read-only audit (no code changes yet)

---

## 1. Veredicto brutal

### ¿Está Carter listo si tools/missions p95 ≈ 64s?
**No.** El cierre anterior fue contable pero no cumple latencia objetivo. Análisis real del live-safe data (n=455 non-skipped):

| categoría | p50 | p95 | max | observación |
|---|---:|---:|---:|---|
| cat 1 (saludos) | 383ms | 855ms | **12016ms** | ✓ excepto outlier de cold start |
| cat 2/15/16/17/18 | <1.3s | <2s | <2.7s | ✓ dentro de target |
| cat 3 (knowledge) | 3515ms | 7396ms | 10826ms | ✓ marginal (p95 7.4s vs 8s target) |
| cat 4/5/6/14 | <1.6s | <5.4s | <6s | ✓ |
| cat 7 (apps simples) | 2490ms | 5610ms | 5742ms | ✓ |
| **cat 9 (filesystem)** | 2548ms | **65471ms** | **190723ms** | ✗ zip desktop real I/O |
| **cat 10 (terminal/app open)** | 2720ms | **64626ms** | **98010ms** | ✗ window-wait timeout en cmd/powershell |
| **cat 12 (compound missions)** | 3703ms | **212958ms** | **457349ms** | ✗ GUI multi-step con retries que agotan timeout |

**Diagnóstico:** Los 6 casos más lentos NO son representativos (son real I/O o window-wait), pero el target del usuario explícitamente exige que esto no sea “excusa”.

### ¿Dónde se está perdiendo tiempo?
Top 10 slow cases (live-safe, scripted backend, 0 LLM calls — todo es tool execution):

| cid | cat | ms | tools | prompt | causa |
|---|---|---:|---:|---|---|
| C12.13 | 12 | 457349 | 3 | "abre notepad, escribe hola, ciérralo" | mission loop con re-observación que no converge |
| C12.34 | 12 | 212958 | 3 | "abre notepad, espera 1s, ciérralo" | mismo pattern |
| C9.36 | 9 | 190723 | 2 | "compress my desktop into a zip" | I/O real, sin estimación previa |
| C9.35 | 9 | 184519 | 1 | "comprime mi escritorio en un zip" | mismo |
| C10.17 | 10 | 98010 | 1 | "ejecuta un comando largo" | terminal timeout default 60s + extra |
| C10.16 | 10 | 96528 | 1 | "open powershell" | wait_for_window timeout |
| C9.37 | 9 | 65471 | 1 | "abre el archivo X" | resource not found + retries |
| C10.31 | 10 | 64626 | 1 | "abre cmd" | wait_for_window timeout |
| C10.32 | 10 | 64348 | 1 | "open cmd" | mismo |
| C1.01 | 1 | 12016 | 0 | "hola" | cold-start outlier (1 case de 40) |

### ¿El cambio en terminal.py metió hardcode lingüístico?
**Sí.** Confirmado por `grep_search`:

```python
# src/carter_v2/capabilities/terminal.py L268-289
_BENIGN_PATTERNS = (
    "could not find process",
    "process not found",
    "no such process",
    "no se encontr",          # ES past tense
    "no se encuentra",        # ES present singular
    "no se encuentran",       # ES present plural
    "is not started",
    "service is not started",
    "no se ha iniciado",
    "cannot find the file",
    "cannot find the path",
    "no se puede encontrar",
    "could not be found",
    "the system cannot find the file",
    "the system cannot find the path",
    "file not found",
    "no matching files",
    "no files were found",
    "no se han encontrado",
)
```

Este bloque viola la regla vital del usuario: **lista de frases ES+EN usada como lógica de runtime para reclasificar exit codes**. Solo funciona en es-MX/es-ES/en-US. Falla silencioso en cualquier otro locale.

### ¿`hardcode_guard` actual es suficiente o está ciego?
**Está ciego para este patrón.** El guard actual ([audit/hardcode_guard.py](Carter_v2/audit/hardcode_guard.py)) detecta:
- `BRAND_RE` — nombres de app específicos
- `MULTILANG_LITERAL_RE` — frases conector ("y luego", "and then", "abre steam")
- `VOCAB_CONTAINER_RE` — variables `_TOKENS` / `_PHRASES` / `_VERBS` / `_ALIASES` no vacías

NO detecta:
- Tuplas/listas de frases de error como decisión lógica (`_BENIGN_PATTERNS`, `_USER_KEYWORDS`, `_ENV_KEYWORDS`)
- Regex con vocabulario humano de error (`_NOT_FOUND_RE` con palabras "not found|could not find")
- Substring matching contra texto humano natural en stderr/stdout

Además, `terminal.py`, `process.py`, `recovery/classifier.py` y `ledger.py` están en `BRAND_ALLOWED_FILES`, así que ni el escaneo actual los inspecciona profundamente.

### ¿Qué hay que implementar para cerrar?
Real, no cosmético:
1. Detector estricto de **listas de frases lingüísticas usadas como switch** en hardcode_guard (P1).
2. Reemplazo de `_BENIGN_PATTERNS` por **mapa por-utilidad de exit codes benignos** (P2).
3. Reemplazo de `process.py` line 381 `if any(text in lowered for text in (...))` por exit-code check (P2).
4. Ledger/`recovery/classifier.py`: documentar como classifiers aceptables (post-hoc, no decisión de éxito), pero reducir el tamaño de las listas y añadir comentario `H-LANG-NN` que el guard reconozca como audit-trail intencional. (P2-doc)
5. Performance gate runner con matriz acotada para que la verificación sea repetible y rápida (P9).
6. Bajar `wait_for_window` para shells (cmd/powershell) — para "open cmd" no hace falta esperar 60s; el proceso arranca instantáneo (P6).
7. Estimación previa para zip de desktop, con NEEDS_USER si > umbral (P8).
8. Cap más estricto al mission loop GUI multi-step (P5/P6).

---

## 2. Top slow cases (ya tabulados arriba en sección 1)

Causa probable + fix por caso:

| cid | causa | fix universal |
|---|---|---|
| C12.13 / C12.34 | Mission loop GUI re-observación no converge en notepad multi-step | Cap iterations ≤ N efectivos, fail-fast con `[partial_with_next_step]` (P5/P6) |
| C9.35 / C9.36 | Zip de Desktop entero (real I/O variable según contenido) | Pre-estimación de tamaño y warning si > umbral; alternativa stream/folder-by-folder (P8) |
| C10.16 / C10.31 / C10.32 | `app_open` shells espera UIA window; cmd/powershell aparecen como CONSOLE_HOST que UIA tarda en indexar | Para shells/console-class, usar verificación por proceso (PID alive) en vez de UIA (P6) |
| C10.17 | "ejecuta un comando largo" — terminal timeout default 60s | Es real; status COMPLETED debería emitir progress trace (P3 instrumentation) |
| C9.37 | "abre el archivo X" — basename inexistente, resolver fallback agota | Cap `_safe_path` recursive scan a max N entries, fail-fast (P8) |
| C1.01 | "hola" 12016ms = cold start de model load. p95 855ms es OK. | Aceptable: 1/40 outlier. No fix. |

---

## 3. Latencia por etapa (instrumentación actual)

El trace ya incluye (per memory L1-L12 + agent.py): `prompt_build_chars`, `memory_block_chars`, `catalog_size`, `tool_calls_made`, `llm_calls`, `total_ms`. Lo que **falta** para diagnóstico fino:

- `prompt_build_ms` (separar de total)
- `tool_exec_ms` por tool
- `vision_ms` por tier (UIA/screenshot/OCR/LLM-vision)
- `mission_steps_count` y `per_step_ms`
- `slow_stage` (string con la etapa que comió >50% del tiempo)

P3 añadirá esto al trace y volcará un `PERFORMANCE_BASELINE.json`.

---

## 4. Hardcode lingüístico — hallazgos confirmados

| archivo | línea/símbolo | string/patrón | por qué es hardcode | reemplazo universal |
|---|---|---|---|---|
| [src/carter_v2/capabilities/terminal.py](Carter_v2/src/carter_v2/capabilities/terminal.py#L268-L289) | `_BENIGN_PATTERNS` (tuple, 19 frases) | "no se encuentra"/"file not found"/"cannot find the path"/etc. | Lista ES+EN aplicada a stderr para reclasificar exit codes. Falla en cualquier locale fuera de es/en. | Mapa `(utility_name → set[returncode])` con códigos OS estándar (taskkill→128, dir→1, sc→1060/1062, net→2/2185). Sin texto humano. |
| [src/carter_v2/capabilities/process.py](Carter_v2/src/carter_v2/capabilities/process.py#L381) | `if any(text in lowered for text in ("no installed package found", "no se encontró", "no encontrado", "not found"))` | 4 frases ES+EN | Mismo patrón: substring de texto humano para detectar "winget no encontró el paquete" | winget tiene exit code propio para "package not found" (0x8A15002B = -2138865621); usar `rc` y `os.errno`-equivalente |
| [src/carter_v2/turn/ledger.py](Carter_v2/src/carter_v2/turn/ledger.py#L209-L246) | `_ENV_KEYWORDS` (12), `_USER_KEYWORDS` (~25) | "not installed"/"no instalad"/"verify it is installed"/"verifica"/"timeout"/"verification failed"/etc. | Listas ES+EN para clasificar fallo en NEEDS_ENVIRONMENT/NEEDS_USER. **Decisión lógica.** | Capabilities deben emitir un campo estructurado `failure_class` (`needs_env`/`needs_user`/`unknown`) en `CapabilityResult`. Ledger consulta ese campo, no texto. (Ver propuesta en §5 P2). |
| [src/carter_v2/recovery/classifier.py](Carter_v2/src/carter_v2/recovery/classifier.py#L23-L60) | `_NOT_FOUND_RE`, `_TIMEOUT_RE`, `_FOCUS_FAIL_RE`, `_NOT_READY_RE`, `_MISSING_PARAM_RE`, `_STALE_RE` | Regex con vocabulario inglés ("not found", "timeout", "could not focus", "not enabled", "missing", "stale"). | Decisión de `FailureKind` (RETRY/FATAL) basada en regex inglés. Falla en outputs ES de capabilities. | Mismo enfoque: `CapabilityResult.failure_class` enum. Conservar regex como fallback solo si `failure_class` es None. |

**Hallazgo lateral:** Los archivos `database.py`, `email.py`, `filesystem.py`, `media_files.py`, `pdf.py` emiten strings *user-facing* tipo `"File not found: {path}"` — eso es texto presentacional aceptable (mensaje al usuario) y NO se usa como decisión lógica. No hay que tocarlos.

---

## 5. Plan de optimización

### P1 — hardcode_guard estricto
Añadir 2 reglas nuevas:
- `lang_phrase_tuple`: detecta tuplas/listas/sets de ≥3 strings string-literal donde ≥1 contiene marcador trivial es/en (`"no se "`, `"could not "`, `"file not"`, `"not found"`, `"verifica"`, `"no encontr"`) Y la asignación está en archivo bajo `src/carter_v2/capabilities/` o `src/carter_v2/turn/` (excepto `_text.py` y `_system_prompt.py` que tienen prompt-text legítimo).
- `stderr_phrase_match`: detecta patrones `if any(... in <stderr|stdout|message|combined|lowered|errors> for ... in (...))` con tupla de strings que contiene español/inglés común.
Marcador de allowlist: comentario `# H-LANG-NN intentional` al final de la línea (igual que `H-XYZ-NN` actual).

### P2 — Eliminar hardcode lingüístico
- **terminal.py**: reemplazar `_BENIGN_PATTERNS` por `_BENIGN_EXIT_CODES: dict[str, set[int]]` (utility name → benign returncodes). Sin texto humano.
- **process.py L381**: chequear `rc` específico de winget en vez de substring.
- **ledger.py / recovery/classifier.py**: añadir campo opcional `failure_class: Literal["needs_env", "needs_user", "transient", "fatal"] | None` en `CapabilityResult`. Marcar las llamadas con `# H-LANG-01` (intentional fallback para texto sin clase). El guard P1 reconoce el marcador.

### P3 — Instrumentación
Extender el trace ya existente (`audit/runners/full_live_llm_validation.py` write loop) con `prompt_build_ms`, `tool_exec_ms`, `vision_ms`, `slow_stage`. Volcar `audit/results/PERFORMANCE_BASELINE.json` con top-30 + breakdown por etapa.

### P4 — Prompt diet
Verificar que `agent.py` ya hace gating de catalog/memory para turnos triviales (memoria L1-L12 dice que sí). Auditar que para tools simples no se inyecte `prior_ctx` ni `active_app_context` cuando no aplica. **Si ya está implementado, dejar nota.**

### P5 — Reducir LLM calls
Mission compuesta GUI: ya usa scripted backend en live-safe (0 LLM calls). El problema es retries de tool execution, no LLM. Capturar en trace y cap iteraciones.

### P6 — Optimizar observación GUI/visión y app open
- `app_open` para shells (cmd, powershell, pwsh, bash, wt): NO usar `wait_for_window` UIA (timeout default 15s+). Usar `Popen.poll() is None` (PID alive ~10ms) y devolver inmediatamente.
- vision_router ya tiene cascade (UIA → screenshot → OCR → LLM-vision opt-in). Verificar que no se invoque en tools simples.

### P7 — Optimizar web/browser
Ya hay reuse de Playwright contexto en runner (memoria notes). No tocar salvo si performance gate revela problema nuevo.

### P8 — Optimizar filesystem/terminal
- Zip de Desktop: pre-estimar tamaño (`os.scandir` + `st_size`) y si > 500MB devolver `[needs_user] confirma compresión de carpeta grande`. Universal.
- `_safe_path` recursive scan: cap a N=500 entries para no agotar.

### P9 — Performance gate runner
`audit/runners/performance_gate.py` con matriz reducida (5–10 cases por categoría representativa, no 30, para que sea ejecutable repetidamente en <2 min). Volcar `PERFORMANCE_GATE.json`.

### P10 — Re-ejecución total
pytest, hardcode_guard, full live-safe, skipped-live, performance gate. Volcar `PERFORMANCE_AND_HARDCODE_FINAL_GATE.json`.

### P11 — Reporte final
`PERFORMANCE_AND_HARDCODE_REPORT.md` con before/after y veredicto.

---

## Resumen

- **Hardcode lingüístico real confirmado:** 4 sitios (terminal.py, process.py L381, ledger.py classifier, recovery/classifier.py). El más egregio es `_BENIGN_PATTERNS` añadido en el cierre anterior.
- **hardcode_guard actual:** ciego para este patrón. Necesita P1.
- **Latencia:** 95% del catálogo está dentro de target. Los outliers son 6 casos específicos (compound notepad missions + zip desktop + open shells + abrir archivo inexistente). Fix universal en P6/P8.
- **No hay deferred** por complejidad: todo el plan es ejecutable en este turno.
