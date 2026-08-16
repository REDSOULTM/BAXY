# FINAL TEXT CLOSURE REPORT — Carter v2

Branch: `radical/text-closure`  
Baseline commit: `8f67917`  
Final commit:   `1aeb12a`  
Suite:          `pytest -q --ignore=tests/test_main_jarvis.py` → **1569 / 1569 OK**  
Smoke:          18-prompt qwen3:8b (Ollama) → **18 / 18 OK** (`audit/C-SMOKE_smoke.json`)

This report ships alongside [FINAL_TEXT_CLOSURE_AUDIT.md](FINAL_TEXT_CLOSURE_AUDIT.md). It records the *measured* outcome of the closure phases, not the plan.

---

## 1. Veredicto final

Carter en modo texto puro queda **operativo, más liviano y más honesto**:

- `agent.py` pasó de **2436 → 1998 LOC** (–438, –17.9%) sin perder ninguna ruta funcional.
- El system prompt por defecto bajó de **7563 → 6890 chars** (–673, –8.9%, ≈ –180 tokens por turno).
- Se eliminaron 3 stubs muertos (`_looks_like_*_question`) más una rama muerta de retry de memoria.
- Se extrajeron los backends LLM a un módulo propio (`turn/backends.py`) sin romper imports externos: `from carter_v2.turn.agent import OpenAICompatAgentBackend` sigue funcionando vía re-export.
- Se gated el bloque `UNIVERSAL_AGENT_KERNEL` con `CARTER_UNIVERSAL_KERNEL_PROMPT` (default OFF) para que Carter texto no pague tokens por una capa que sólo aporta cuando se activa el universal-runner.

No se introdujeron hardcodes, no se desactivaron tests, no se tocaron rutas críticas (`AgentEngine.run`, `adapters/tools.py`, `gui_agent.py`, `web.py`, memoria persistente). La fila restante de deuda queda documentada en §6.

---

## 2. Antes / Después — métricas

| Métrica                              | Baseline (C0) | Final (C4)     | Δ        |
|--------------------------------------|---------------|----------------|----------|
| Tests pasando                        | 1569          | 1569           | =        |
| Tests fallando                       | 0             | 0              | =        |
| Duración pytest                      | 135.49 s      | 128.55 s       | –6.94 s  |
| `agent.py` LOC                       | 2436          | 1998           | –438     |
| `turn/backends.py` LOC               | —             | 321            | +321 (nuevo) |
| `turn/_text.py` LOC                  | —             | 62             | +62 (nuevo)  |
| **Suma neta turn-layer**             | **2436**      | **2381**       | **–55 LOC** y arquitectura separada |
| System prompt (default)              | 7563 chars    | 6890 chars     | –673     |
| System prompt template               | 6605 chars    | 6605 chars     | =        |
| Bloque universal-kernel (cuando ON)  | 672 chars     | 673 chars      | =        |
| Empty dir `custom_types.py/`         | presente      | eliminado      | –1 dir   |
| Stubs muertos `_looks_like_*`        | 3 funciones   | 0              | –3       |

> Los archivos auxiliares creados (`turn/backends.py`, `turn/_text.py`) **no son código nuevo**: contienen el código que vivía dentro de `agent.py`. La métrica que importa es "código que el lector tiene que entender al abrir `agent.py`": cae 17.9 %.

---

## 3. Fases ejecutadas (qué se cambió y por qué)

### C0 — Snapshot baseline  
Artefacto: [`audit/C0_baseline.json`](audit/C0_baseline.json).  
1569 tests verdes, 2436 LOC `agent.py`, 7563 chars system prompt.

### C1 — Borrado de stubs F8 muertos  
Commit `7e2db07`.  
- Eliminados `_looks_like_action_request_question`, `_looks_like_live_query_question`, `_looks_like_personal_memory_query` (los tres devolvían `False` incondicionalmente).  
- Simplificado `_should_accept_text_only_first_pass` a la condición real (no JSON estructurado, no `tool_name`/`work_units`, no patrón LLM-stream noise).  
- Removida la rama muerta de `_forced_memory_retry` (~líneas 1620-1640 del baseline) y su flag `_forced_memory_retry_done = False`.  
- Resultado: 2436 → 2377 LOC, pytest 1569/1569.

### C2 — Limpieza de carpeta basura  
- Eliminado `src/carter_v2/custom_types.py/` (directorio vacío con extensión `.py`, restos de un mal `mkdir`).  
- Sin commit (no estaba trackeado).

### C3 — Extracción de backends  
Commit `31c9c31`.  
- Creado [`src/carter_v2/turn/_text.py`](Carter_v2/src/carter_v2/turn/_text.py) con `_NO_TOOL_NEEDED_PREFIX`, `_strip_think_chunk`, `_strip_thinking_text`, `_looks_like_stream_noise_line` (ahora compartidos por `agent.py` y `backends.py`).  
- Creado [`src/carter_v2/turn/backends.py`](Carter_v2/src/carter_v2/turn/backends.py) con `AgentResponse`, `OpenAICompatAgentBackend` (Qwen3 / Ollama nativo / streaming), `NullAgentBackend`. Lógica preservada byte-a-byte salvo prosa de comentarios.  
- `agent.py` re-exporta los símbolos: `from .backends import (AgentResponse, NullAgentBackend, OpenAICompatAgentBackend)`. Tests que parchean `carter_v2.turn.agent.OpenAICompatAgentBackend` siguen funcionando.  
- Resultado: 2377 → 1998 LOC, pytest 1569/1569.

### C4 — Gate del kernel universal en el prompt  
Commit `1aeb12a`.  
- Nuevo flag de entorno `CARTER_UNIVERSAL_KERNEL_PROMPT`. Default OFF.  
- Cuando está OFF, `_build_system_prompt()` no antepone el bloque `UNIVERSAL_AGENT_KERNEL`. Cuando está ON (`1`/`true`/`yes`/`on`), comportamiento idéntico al baseline.  
- Test `test_universal_context_is_injected_into_agent_system_prompt` actualizado: hace `monkeypatch.setenv("CARTER_UNIVERSAL_KERNEL_PROMPT", "1")` y limpia la caché LRU. Sin assertion deshabilitada.  
- Resultado: prompt default 7563 → 6890 chars, pytest 1569/1569.

### C5 — `cloud_fallback.py` (verificado, KEEP)  
- Usado en runtime: `engine.py:26`, `main.py:564,612` (gated por `CARTER_ENABLE_CLOUD_FALLBACK`).  
- Cubierto por ~25 tests en `test_medium_priority.py`.  
- **Decisión: KEEP**. Ya está gated por env y aporta valor cuando se activa fallback a cloud.

### C6 — `intent_resolution.py` (verificado, KEEP)  
- Importado y usado por `agent.py` (`build_intent_frame`, `evaluate_direct_action_closure`).  
- **Decisión: KEEP**. Es ruta caliente de la ronda directa.

### C7 — Smoke runtime  
Artefacto: [`audit/C-SMOKE_smoke.json`](audit/C-SMOKE_smoke.json).  
- Modelo: `qwen3:8b` vía Ollama nativo.  
- 18 prompts (conversación, info live, memoria, capacidades meta, GUI con Notepad, conversación final).  
- **18 / 18 OK**. Tiempo total 111.5 s. Promedio 6.2 s / turno (min 2.6 s, max 22.2 s — el max es el primer turno con cold start).  
- Distribución de tools:
  - 11 turnos sin tool (conversacional puro / NO_TOOL_NEEDED).
  - 2 × `system_get_time`
  - 1 × `network_get_public_ip`
  - 1 × `memory_save` (durable: "color favorito = azul")
  - 3 × `app_open` (abrir / cerrar / abrir-y-cerrar Notepad)
- Latencia GUI Notepad: 6.7 – 8.8 s por turno (incluye verificación de ventana).  
- Sin retries excepto un único `text_no_tool_force` en el turno "what is the capital of France?" (turno 16) — el modelo intentó usar tool sobre conocimiento estático y el guardrail lo redirigió a respuesta de texto. Comportamiento esperado.

### C8 — Este reporte  
Artefacto: [`FINAL_TEXT_CLOSURE_REPORT.md`](FINAL_TEXT_CLOSURE_REPORT.md). Métricas brutas en [`audit/C-final_metrics.json`](audit/C-final_metrics.json).

---

## 4. Lo que NO se tocó (deuda documentada)

Decisiones explícitas para no inflar el alcance:

- **`AgentEngine.run` (~778 líneas).** Reordenar requiere cobertura de integración Qwen real, no sólo unit. Riesgo > beneficio en este ciclo.
- **`adapters/tools.py` (2234 LOC).** Dividir por dominio (memoria / GUI / web / sistema) es siguiente paso natural; no urgente.
- **`gui_agent.py` (1217 LOC) y `web.py` (1086 LOC).** Capabilities grandes pero coherentes con cobertura propia.
- **`session/skills.py` + `embeddings.py`.** Sistema experimental gated. Activarlo no afecta texto puro.
- **`interfaces/` y `plugins/`.** Off-by-default por env. KEEP_GATED.
- **`steam.py`, `power.py`.** Capabilities gated por policy.
- **MEMORY persistente (`.carter/memory.db`).** Sin cambios destructivos en este ciclo.

---

## 5. Compatibilidad / migración

- **API pública:** intacta. Todos los símbolos que vivían en `carter_v2.turn.agent` siguen importándose desde ahí. Tests existentes que parchean `carter_v2.turn.agent._auto_backend`, `carter_v2.turn.agent.OpenAICompatAgentBackend`, etc. funcionan sin cambios.
- **Configuración:** un único env nuevo, `CARTER_UNIVERSAL_KERNEL_PROMPT`. Default OFF. Si alguien dependía implícitamente del bloque universal en el prompt (por ejemplo en evaluaciones offline con LLM), debe activarlo explícitamente.
- **Backups:** ningún borrado destructivo de datos. Solo se eliminó el directorio vacío `src/carter_v2/custom_types.py/`.

---

## 6. Riesgos restantes

| Riesgo                                                                    | Mitigación |
|---------------------------------------------------------------------------|------------|
| `AgentEngine.run` sigue siendo monolítico                                 | Documentado, no urgente. Próximo ciclo: separar `_first_pass`, `_tool_loop`, `_finalise`. |
| `adapters/tools.py` mezcla tools de dominios distintos                    | Próximo ciclo: split por dominio + import lazy. |
| Smoke depende de Ollama local                                             | Documentado en `audit/smoke_runner.py`. CI debería usar mocks. |
| Bloque universal-kernel ahora opt-in                                      | Quien lo necesite (universal-plan-runner) debe exportar la env. Fail-loud: el código existe, sólo no se inyecta. |

---

## 7. Qué queda preparado para voz / cámara

La extracción C3 deja el path listo para reutilizar el backend OpenAI-compatible desde otros canales sin arrastrar `agent.py` completo:

- `from carter_v2.turn.backends import OpenAICompatAgentBackend, AgentResponse` ya es la API canónica.
- Los helpers de stream (`_strip_think_chunk`, `_looks_like_stream_noise_line`) viven en `turn/_text.py` y son reutilizables por un futuro pipeline de voz (TTS-aware streaming) sin tocar la orquestación de turnos.
- El system prompt es modular (universal-block opt-in, vision-block, alerts-block, deps-block, memory-block) — agregar un `audio-block` o `camera-block` es directo siguiendo el patrón.

---

## 8. Cómo reproducir

```powershell
cd Carter_v2
git checkout radical/text-closure
$env:PYTHONIOENCODING='utf-8'
python -m pytest -q --ignore=tests/test_main_jarvis.py     # 1569 passed
$env:CARTER_LLM_MODEL='qwen3:8b'; $env:CARTER_TIMING='1'; $env:CARTER_AUTO_APPROVE_HIGH='1'
python audit/smoke_runner_fsmoke.py                         # 18/18 ok
```

Métricas brutas: [`audit/C-final_metrics.json`](audit/C-final_metrics.json).

---

*Cierre total de modo texto: hecho. Lo siguiente es voz.*
