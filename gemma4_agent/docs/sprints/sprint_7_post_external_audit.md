# PROMPT — Sprint 7 (acciones de la auditoría externa)

> Continúa el mismo chat de Claude Code que corrió Sprints 0+1+2+3a+4+5a+5b+6 + el refactor de prompts a markdown.
>
> **Origen:** una auditoría externa (Claude Sonnet/Opus 4.x leyendo
> los 9 delta docs + PROMPT_FOR_EXTERNAL_AUDIT.md) propuso 7 acciones
> accionables. El operador validó las 7 contra datos reales y
> aprobó este sprint para ejecutarlas.

---

## Hallazgos confirmados por datos reales (no por intuición)

Antes del sprint, el operador verificó:

1. **`semantic_router` SÍ sub-selecciona schemas.** Distribución medida sobre 708 turns:
   - 46.6% turns → 0 schemas (smalltalk, solo CORE_PROMPT)
   - 51.0% turns → 1-5 schemas
   - 2.4% turns → 6+ schemas (peor caso medido: 16, 1 vez)
   - **0% turns con 17+ schemas.** El router funciona.

2. **`barge-in` confirmado NO existe.** `voice/controller.py:331`
   ignora audio en estado SPEAKING. El audit tenía razón.

3. **`voice_e2e_latency_ms` confirmado NO existe.** Cero matches en grep.

4. **Crash recovery SÍ existe** (`llama_server.detect_crash_signature`,
   `recycle_for_vision_leak`, `restart()`). Pero NO está documentado
   en `01_delta_system.md`.

---

## Prompt completo (copy/paste al chat existente)

```
Continuamos. Estado: rama PortandoLoMejor, HEAD 746c614, working
tree limpio, 65 compound tools intactas, plan cerrado pero con 7
acciones validadas por auditoría externa.

# OBJETIVO DE SPRINT 7

Ejecutar las 7 acciones de la auditoría externa, ordenadas por
ROI/riesgo. Todas son chicas (S = <1h cada una), riesgo bajo,
mensurables. Total estimado: 5-8h.

# REGLAS GENERALES (mismas que sprints anteriores)

1. Trabajás en PortandoLoMejor. Commits chicos, prefijo "sprint7.X:".
   NO push, NO toques main.
2. Después de cada commit:
   - `python -c "import gemma4_agent"`
   - `python -c "from gemma4_agent.tools import COMPOUND_TOOL_SCHEMAS;
      print(len(COMPOUND_TOOL_SCHEMAS))"` → debe imprimir 65.
   - Si rompe: reset --hard HEAD~1, log el blocker, siguiente tarea.
3. NO instales deps. NO ejecutes el agente real ni llama-server.
4. NO toques mission_goal.py, mission_outcome.py, verifiers.py,
   verify_core.py, personas.py, microagents.py, skills_registry.py.
5. NUNCA git add -A. Siempre archivos específicos (lección de Sprint 5b).
6. Si dudás: dejá. Anotá en log. NO improvises.

# CONTEXTO

- `docs/architecture/08_findings_post_plan.md` — deuda restante.
- `docs/architecture/sprint_prompts/_sprint6_log.md` — último log.
- Sprint 7 es out-of-original-plan, validado por audit externo.

# WORKFLOW

7 tareas independientes (pueden hacerse en cualquier orden, pero las
listo por ROI descendente). Cada una es 1 commit chico.

## 7.1 — Instrumentar voice_e2e_latency_ms + prompt_built_tokens

**Por qué:** el audit externo señaló (correctamente) que no hay
métrica de latencia end-to-end voice ni de tamaño de prompt construido.
Para un agente voice-first es la métrica clave.

### Paso A: voice latency

Agregá en `voice/controller.py` un timestamp `_wake_ts` que se setea
en `_on_wake_detected` y un emit en el primer chunk de TTS:

```python
# voice/controller.py — en _on_wake_detected:
self._wake_ts = time.monotonic()

# voice/controller.py — donde el TTS arranca a producir audio:
#   (probablemente dentro del worker que recibe text chunks del agent
#    y los manda a Piper. Ubicalo con grep "feed_tts_chunk\|begin_tts")
# La PRIMERA vez por turn que se sintetiza audio:
if hasattr(self, "_wake_ts") and self._wake_ts is not None:
    elapsed_ms = int((time.monotonic() - self._wake_ts) * 1000)
    # Publish al BUS para que LogRecorder + analyze_traces lo vean.
    # Importá BUS lazy para no acoplar voice/ a events_bus en module-level.
    try:
        from ..events_bus import BUS
        BUS.publish({
            "kind": "voice_e2e_latency",
            "elapsed_ms": elapsed_ms,
            "phase": "wake_to_first_phoneme",
        })
    except Exception:
        pass
    self._wake_ts = None  # reset, solo medimos primer phoneme
```

Si no podés ubicar exactamente dónde "el TTS arranca audio" sin
modificar `voice/tts.py`, una aproximación buena: emitir al `set_state(SPEAKING)`
(que el agent llama después del primer LLM token). NO es exacto a
"first phoneme" pero está cerca.

### Paso B: prompt tokens

Agregá en `agent.py` después del `selected_schemas = self.tools.schemas_for_names(...)`
(aprox línea 665) un trace event nuevo:

```python
# Estimar tokens grosero: chars / 4. Es aproximado pero suficiente
# para detectar p50/p95 por turn.
prompt_chars = len(system_message["content"])
schemas_chars = sum(len(json.dumps(s)) for s in selected_schemas)
total_chars = prompt_chars + schemas_chars
estimated_tokens = total_chars // 4

self.trace.event(
    turn_id, "prompt_built",
    system_chars=prompt_chars,
    schemas_chars=schemas_chars,
    total_chars=total_chars,
    estimated_tokens=estimated_tokens,
    schemas_count=len(selected_schemas),
)
```

Verificá que `system_message` ya esté construido en esa línea
(probablemente sí — `_system_message()` se llama justo antes).
Si no, hacelo después del primer chat call.

**Tests:** correr 1 turn smoke test con mock LLM (`test_gemma4agent_contract.py`
ya tiene mocks). Verificar que el evento aparece en `self.trace.events`.

Commit: "sprint7.1: instrument voice_e2e_latency + prompt_built_tokens"

## 7.2 — TTL real en state.json (cierra findings baseline §2.3)

**Por qué:** el plan documentó "purgar a mano" como solución. El
auditor externo señaló (correctamente) que se va a olvidar. Implementar
TTL real elimina el zombie set persistente sin romper consumers.

### Cambios en `gemma4_agent/state.py`:

1. Agregar `closed_at` timestamp cuando `mark_cleaned` ejecuta:

```python
def mark_cleaned(self, resource_id: str, result: dict[str, Any] | None = None) -> dict[str, Any]:
    with self._lock:
        data = self._load()
        resource = data.get("resources", {}).get(resource_id)
        if not resource:
            return {"ok": False, "error": "resource not found", "resource_id": resource_id}
        resource["status"] = "closed"
        resource["closed_at"] = _now()  # ← NUEVO
        if result is not None:
            resource["result"] = result
        self._save(data)
        return {"ok": True}
```

2. Agregar método `purge_stale_closed(max_age_days=7)`:

```python
def purge_stale_closed(self, max_age_days: int = 7) -> dict[str, Any]:
    """Borra resources con status='closed' y closed_at más viejo que
    max_age_days. Resources cerrados sin closed_at (legacy pre-Sprint7)
    se borran también — asumimos antiguos."""
    from datetime import datetime, timedelta
    cutoff = datetime.now() - timedelta(days=max_age_days)
    with self._lock:
        data = self._load()
        before = len(data.get("resources", {}))
        kept = {}
        for rid, r in data.get("resources", {}).items():
            if r.get("status") != "closed":
                kept[rid] = r
                continue
            closed_at = r.get("closed_at")
            if not closed_at:
                # Legacy closed sin timestamp: borrar.
                continue
            try:
                dt = datetime.fromisoformat(closed_at)
                if dt > cutoff:
                    kept[rid] = r
            except (ValueError, TypeError):
                # closed_at malformed: borrar.
                continue
        data["resources"] = kept
        self._save(data)
        return {
            "ok": True,
            "before": before,
            "after": len(kept),
            "purged": before - len(kept),
        }
```

3. Llamar `purge_stale_closed()` en startup. **Lugar exacto:** al
construir `Gemma4Agent`, después de instanciar `self.state`. Agregalo
en `agent.py:__init__` envuelto en try/except para no romper boot
si falla:

```python
# En Gemma4Agent.__init__ después de self.state = AgentState(...)
try:
    purge_result = self.state.purge_stale_closed(max_age_days=7)
    if purge_result.get("purged", 0) > 0:
        self.trace.event(
            "startup", "state_purge",
            **purge_result
        )
except Exception as exc:
    # Purge NUNCA debe romper boot. Solo loguear.
    import logging
    logging.getLogger(__name__).warning(
        "state.json purge failed: %s", exc,
    )
```

**Tests:** agregar a `test_state_safety.py` (si existe) o crear
`test_state_purge.py`:
- Resource sin closed_at + status="closed" → se borra.
- Resource con closed_at de hace 30 días + status="closed" → se borra.
- Resource con closed_at de hace 1 día + status="closed" → se queda.
- Resource con status="open" → se queda sin importar timestamp.
- Resource con closed_at malformed → se borra.

Commit: "sprint7.2: TTL real en state.json (closed_at + purge_stale_closed)"

## 7.3 — Rotación preventiva en TraceLogger

**Por qué:** evitar archivos de varios MB en 6 meses.

### Cambios en `gemma4_agent/tracing.py`:

Agregar al `TraceLogger`:

```python
DEFAULT_MAX_SIZE_MB = 50
DEFAULT_KEEP_FILES = 3

class TraceLogger:
    def __init__(self, ..., max_size_mb: int = DEFAULT_MAX_SIZE_MB,
                 keep_files: int = DEFAULT_KEEP_FILES):
        ...
        self._max_size_bytes = max_size_mb * 1024 * 1024
        self._keep_files = keep_files
        self._maybe_rotate()  # En startup, rotamos si ya está grande.

    def _maybe_rotate(self):
        """Si el archivo actual supera el límite, rotalo a .1, y los
        existentes corren al siguiente número. Borra .N+1."""
        try:
            if not self._path.exists():
                return
            if self._path.stat().st_size < self._max_size_bytes:
                return
            # Rotar: actual → .1, .1 → .2, ..., .keep → eliminar
            for i in range(self._keep_files, 0, -1):
                src = self._path.with_suffix(f".jsonl.{i}")
                dst = self._path.with_suffix(f".jsonl.{i+1}")
                if i == self._keep_files and src.exists():
                    src.unlink()
                elif src.exists():
                    src.rename(dst)
            self._path.rename(self._path.with_suffix(".jsonl.1"))
            # El próximo `event()` va a crear un .jsonl nuevo vacío.
        except Exception:
            # Rotación nunca debe romper el agente.
            pass

    def event(self, turn_id, kind, **payload):
        # Verificar rotación cada N events para no hacerlo cada turn.
        # Variable de instancia _rotate_counter, check cada 100.
        ...
```

**Tests:** crear `test_tracing_rotation.py`:
- Archivo < límite → no rota.
- Archivo > límite + sin .1/.2/.3 → rota a .1, crea nuevo .jsonl.
- Archivo > límite + .1 y .2 existen → .2→.3, .1→.2, actual→.1.
- Si hay .3 + nueva rotación → .3 se borra.
- Falla de IO durante rotación → no rompe el logger.

Commit: "sprint7.3: rotación preventiva en TraceLogger (50MB / 3 files)"

## 7.4 — Verificación post-ALTER en experience.sqlite (fail-loud)

**Por qué:** evitar columnas missing silencioso por antivirus que
lockea SQLite en cold start.

### Cambios en `gemma4_agent/experience.py:106-120`:

```python
# Después del bloque for col_def in (...):
# Verificar que las 5 columnas existen. Si falta alguna, fail-loud.
cur = conn.execute("PRAGMA table_info(experiences)")
existing_cols = {row[1] for row in cur.fetchall()}
expected_cols = {
    "outcome_code", "failure_reason_code", "args_signature",
    "capability_label", "grounding_flagged",
}
missing_cols = expected_cols - existing_cols
if missing_cols:
    raise RuntimeError(
        f"experience.sqlite schema migration failed: missing columns "
        f"{sorted(missing_cols)}. The ALTER TABLE statements were "
        f"swallowed by an `except sqlite3.OperationalError`. Common cause: "
        f"the SQLite file is locked by another process (antivirus, "
        f"backup tool, OneDrive sync). Workaround: move the agent "
        f"directory outside synced/scanned paths, or whitelist it. "
        f"Path: {self.path}"
    )
```

**Tests:** crear `test_experience_schema_drift.py`:
- DB recién creada: las 5 columnas existen, no falla.
- DB con experiences vacía sin las 5 columnas: el ALTER las agrega,
  no falla.
- DB con columnas faltantes simulado (mock que hace que el except
  trague el ALTER): falla con RuntimeError descriptivo.

Commit: "sprint7.4: fail-loud en experience.sqlite schema migration"

## 7.5 — Documentar barge-in design (NO implementar todavía)

**Por qué:** el audit señaló (correctamente) que `voice/controller.py:331`
ignora audio en estado SPEAKING. Eso es un gap voice-first. Implementar
es Sprint 8; este sprint solo documenta el diseño para revisión.

### Crear `docs/architecture/design/barge_in.md`:

Documento con:

1. **Estado actual (citado del código):**
   - `voice/controller.py:331` — handler ignora audio en SPEAKING.
   - `voice/controller.py:264` — comentario admite "SPEAKING descarta
     audio entrante".
   - Consecuencia UX: usuario no puede interrumpir respuesta del agente.

2. **Propuesta de diseño:**
   - En estado SPEAKING, NO descartar audio. Ruta paralela:
     - Audio chunk → Silero VAD rápido (no Whisper).
     - Si VAD detecta speech sostenido (>500ms): `barge_in_triggered`.
   - Acción al trigger:
     - `StreamingTTS.stop()` inmediato.
     - `state → LISTENING` (cancela el follow-up window).
     - `BUS.publish({"kind": "barge_in", ...})`.
     - El siguiente chunk de audio arranca como turn nuevo.

3. **Riesgos:**
   - **False positive:** ruido ambiente (TV, conversación de fondo)
     dispara barge-in.
   - **TTS audio echo:** si el mic capta lo que dice el agente, el VAD
     puede dispararse a sí mismo. Mitigación: ducking (el sistema ya
     tiene `_AudioDucker` en `voice_runner.py`) + cancelación de
     eco si está disponible en pycaw.

4. **Mitigación de false positives:**
   - VAD threshold más alto durante SPEAKING (300ms sostenido?).
   - Opcional: re-correr wake-word check primero. Si NO matchea "gemma"
     en los primeros 500ms post-trigger, abortar barge-in y volver a
     SPEAKING. Más conservador.

5. **Plan de implementación (Sprint 8):**
   - Cambio en `voice/controller.py:_on_audio_chunk` para ruta paralela
     en SPEAKING.
   - Nuevo método `_check_barge_in(chunk)` con VAD chunk-level.
   - Stop hook en `StreamingTTS`.
   - Tests: simular speech durante SPEAKING, assert que TTS stop fue
     llamado, state pasó a LISTENING.

6. **Estimado:** 30-50 LOC code + 3-5 tests. Esfuerzo M, riesgo M
   (puede degradar UX si false positives, por eso doc-first).

Commit: "sprint7.5: barge-in design doc (Sprint 8 will implement)"

## 7.6 — Documentar crash recovery existente

**Por qué:** el audit dijo "falta", pero existe en código. Solo no está
documentado. Mover la doc a un lugar visible.

### Modificar `docs/architecture/01_delta_system.md`:

Agregar al final una sección §7:

```markdown
## 7. Crash recovery y resilience del subprocess llama-server

(Documentado tras la auditoría externa post-plan, que detectó que
estos componentes existen pero no estaban descritos.)

### 7.1 Detección de crash

`gemma4_agent/llama_server.py:LlamaServerManager.detect_crash_signature()`
inspecciona el tail del err.log buscando patrones conocidos de crash:
- CUDA illegal memory access
- Out of memory
- otros patrones documentados línea 424+

Returns dict con `summary` (str|None) que el caller puede usar para
decidir si vale la pena reintentar.

### 7.2 Vision relaunch (anti-leak conocido)

`recycle_for_vision_leak()` reinicia el subprocess cuando se detecta el
leak progresivo del mmproj de Gemma 4 (issue ggml-org/llama.cpp#21690).
Trigger automático en `multimodal._bump_image_counter()` al cruzar
threshold (default 40 imágenes / turn).

### 7.3 Restart limpio en cambio de profile

`restart(profile)` = `stop()` + `start(profile)`. Usado por
`profile_watcher` cuando cambia VRAM-aware profile (Performance →
Balanced → Light).

### 7.4 Lo que NO existe

- Auto-restart si llama-server crashea **durante un turn activo** (mid-LLM-call).
  El cliente HTTP recibe error, el guard `_guard_unverified_final` debería
  catchar, pero NO hay re-spawn automático del subprocess. Si crasheó
  mid-turn, el siguiente turn dispara autostart de nuevo via
  `_autostart_llama_server`.
- Health probe continuo durante turns largos. Solo se probe en boot
  warmup.

### 7.5 Gaps documentados para Sprint 8+

- Auto-restart mid-turn con re-try del mismo turn.
- Health probe periódico durante turns que se sospechan colgados.
```

Commit: "sprint7.6: document existing crash recovery in 01_delta_system.md"

## 7.7 — Mejorar analyze_traces.py con "% turns donde fired"

**Por qué:** el criterio `count == 0` para Sprint 3b no es suficiente —
un componente puede tener count > 0 por edge case. La métrica útil es
`% turns donde componente cambió el outcome` o, como aproximación,
`% turns donde fired`.

### Cambios en `scripts/analyze_traces.py`:

Agregar columna `% of turns` a las tablas de Sección B (personas),
Sección C (microagents+skills), Sección D (capability classifier).

```python
# pseudocódigo
total_turns = count_distinct_turn_ids(events)
for component, count in sorted_counter.items():
    pct = (100.0 * count / total_turns) if total_turns else 0.0
    print(f"  {component:30s}  {count:5d}  {pct:5.1f}%")
```

Agregar al final de cada sección una recomendación textual:
- `< 1%` → "candidate to delete in Sprint 3b"
- `1-5%` → "review: low usage, may not justify maintenance cost"
- `> 5%` → "keep"

Commit: "sprint7.7: improve analyze_traces.py with % of turns column"

## 7.8 — Reporting

Escribí `docs/architecture/sprint_prompts/_sprint7_log.md`:

- Timestamp inicio/fin.
- Tareas hechas con SHA + breve descripción.
- Tareas SKIPPED con razón.
- LOC delta: `git diff --shortstat 746c614..HEAD` (esperado ~+200 LOC
  porque agregamos tests + features pequeñas).
- Tests nuevos agregados (4 archivos: test_state_purge,
  test_tracing_rotation, test_experience_schema_drift, opcional otros).
- Verificación: `python -m pytest gemma4_agent/ -q --tb=no | tail -3`.
- Estado final: `git log --oneline -10` + `git status`.

Adicionalmente, actualizar `docs/architecture/08_findings_post_plan.md`
con un nuevo §0.1 al inicio:

```markdown
## 0.1 Acciones de Sprint 7 (post-auditoría externa)

Una auditoría externa post-plan (claude.ai, 2026-05-XX) identificó
7 acciones accionables que el operador validó contra datos reales:
- §2.1 state.json TTL: IMPLEMENTADO en Sprint 7.2.
- §2.2 traces rotation: IMPLEMENTADO en Sprint 7.3.
- §3 instrumentation voice_e2e_latency + prompt_tokens: IMPLEMENTADO en Sprint 7.1.
- Schema fail-loud experience.sqlite: IMPLEMENTADO en Sprint 7.4.
- Barge-in design: DOCUMENTADO en Sprint 7.5 (implementación es Sprint 8).
- Crash recovery docs: AÑADIDOS en Sprint 7.6.
- analyze_traces % column: IMPLEMENTADO en Sprint 7.7.

Auditoría externa NO modificó decisiones conservadas conscientemente
(MainWindow, SettingsDialog, AgentWorker/Runner workers). Validó que
las decisiones de conservación están bien justificadas.
```

Commit: "sprint7: write log + update findings"

# VERIFICACIONES OBLIGATORIAS AL CIERRE

```bash
# 1. Import + tools
python -c "import gemma4_agent; from gemma4_agent.tools import COMPOUND_TOOL_SCHEMAS; print(len(COMPOUND_TOOL_SCHEMAS))"
# Esperado: 65

# 2. Launcher status
python -m gemma4_agent.launcher status 2>&1 | head -5

# 3. Tests nuevos
python -m pytest gemma4_agent/test_state_purge.py \
                 gemma4_agent/test_tracing_rotation.py \
                 gemma4_agent/test_experience_schema_drift.py -q

# 4. Suite completa (regresiones)
python -m pytest gemma4_agent/ -q --tb=no 2>&1 | tail -5

# 5. analyze_traces.py corre
python scripts/analyze_traces.py --limit 100 2>&1 | head -10
```

# QUÉ NO HAGAS

- NO implementar barge-in real (solo documentar). Es Sprint 8.
- NO refactorizar god classes. Sigue siendo deuda conservada.
- NO cambiar COMPOUND_TOOL_SCHEMAS ni los 65 tools.
- NO modificar voice/controller.py salvo el evento de latency en 7.1.
- NO instales deps.
- NO uses git add -A.

Arrancá.
```

---

## Notas para vos al despertar

1. **LOC esperadas:** ~+200 (mayoría tests + features chicas).
2. **El #1 más importante:** Sprint 7.1 (instrumentación). Sin esa
   métrica, futuras decisiones siguen siendo intuición.
3. **El #5 (barge-in doc) habilita Sprint 8:** después de que el agente
   produzca `barge_in.md`, revisalo. Si te convence el diseño,
   implementación en Sprint 8 son ~30-50 LOC.
4. **Después de 1 semana de uso con instrumentación de 7.1 activa,**
   re-corré `scripts/analyze_traces.py` (mejorado en 7.7) y vas a tener
   datos reales de:
   - p50/p95 voice latency (Jarvis-like ≈ <800ms, aceptable <2000ms).
   - p50/p95 prompt tokens (target: <6000 según audit).
   - Uso real de personas/microagents/skills (Sprint 3b).

Si los datos muestran problemas, Sprint 8 ataca esos específicamente.
