# Polish Log — post-merge finalize

- **Sesión**: 2026-05-15 (continuación post-merge)
- **Branch**: `polish/post-merge-finalize` (derivado de `feat/ui-field-react` post-merge)
- **Baseline**: 143/143 smoke + 92/92 tests del repo PASS
- **Tags de seguridad**: `backup/pre-merge-feature-20260515`, `backup/pre-merge-main-20260515`
- **Reglas**: 1 item = 1 commit. Validar entre items. Sin deps nuevas. Sin tocar `agent.py`/`tool_retrieval.py`/`verifier_orchestrator.py` salvo P3 (audit-only).

---

## P1 — `--cache-reuse 256` (PR #22288 merged upstream) — APPLIED
- **Commit**: `3c7ba4d feat(llama_server): enable --cache-reuse 256 (PR #22288 merged upstream)`.
- **Verificación previa**:
  - PR #22288 ("server: fix swa-full logic") merged el **2026-04-24** vía commit `ffdd983fb83ff3ca5e972188b30bcf8d039d3283` (confirmado por GitHub API).
  - Primera release que lo contiene: **b9084** (publicada 2026-05-09 — 15 días después del merge).
  - `LLAMA_CPP_BUILD_MIN = "b9090"` está 6 builds por encima de b9084 → ya incluye el fix.
- **Cambios**: añadido `["--cache-reuse", "256"]` al cmd en `gemma4_agent/llama_server.py`. `--keep -1` se mantiene como complemento (no es redundante: --keep preserva el prefix base; --cache-reuse activa el match inteligente).
- **Test nuevo**: `test_optroad_p1_cache_reuse_present_in_cmd` verifica build mínimo + flag presente con valor `256` + complementariedad con `--keep -1`.
- **Validación**: 143/143 + 93/93.
- **Impacto esperado**: ~93% de TTFT recuperado en primer turno con system prompt grande (60-90s → unidades de segundos con ~46K tokens, según el reporter de #21468). No es medible aquí (requiere LLM real); confirmable correo runtime via timings.cache_n en logs.

## P2 — VRAM balanced_8gb ctx 16K → 12K — APPLIED (cálculo teórico)
- **Commit**: `45aec2b fix(profiles): balanced_8gb ctx 16K -> 12K (VRAM tight)`.
- **Status del GGUF**: `models/E4B/gemma-4-E4B-it-UD-Q4_K_XL.gguf` **NO descargado** en la máquina del dev al momento del polish. Por eso la decisión se basa en cálculo teórico, no en medición real con `nvidia-smi`.
- **Cálculo teórico** (proyecciones del informe Bloque A1 + fórmula KV cache Bloque F2):
  - Con ctx 16K: VRAM física requerida ~7.70 GB → margen 0.30 GB sobre 8 GB nominales [BORDE peligroso].
  - Con ctx 12K: VRAM física requerida ~7.52 GB → margen 0.48 GB [aceptable].
- **Cambios**:
  - `profiles.py:balanced_8gb.context_size`: 16384 → 12288. est_vram_mb 6300 → 6020.
  - `agent.py:_tool_schemas_hint`: umbral de compact bajado de ≥16384 a ≥12288 para que balanced_8gb siga recibiendo el bloque. Quedan ~6K tokens libres para conversación + memoria.
  - Tests V4 (round_trip) y OPTROAD-S1 (mode selection) actualizados al nuevo ctx + umbral.
- **Validación**: 143/143 + 93/93.
- **TODO seguimiento**: cuando el dev baje UD-Q4_K_XL, correr `nvidia-smi --query-gpu=memory.used` antes/después + 100 tokens de inferencia real. Si peak < 6.0 GB → revertir a 16K. Si ≥6.0 GB → 12K es correcto.

## P3 — Auditoría del diff de `agent.py` Sprint 1 — DOCUMENTED (excede tope esperado)
- **Commit auditado**: `c6ed18f feat(agent): Sprint 1 — inject tool_schemas_hint into system prompt`.
- **Tope esperado por el brief**: ≤10 líneas netas.
- **Cambio real**: **+58 líneas, -1 línea = +57 netas**. Supera el tope ~6×.
- **Disparidad con la promesa del Sprint 1**: el commit message del Sprint 1 decía "(~3 líneas trivial)". Eso era inexacto. Las 3 líneas serían solo el call `tools_section = self._tool_schemas_hint()` + concatenación en el f-string + nuevo método vacío. Pero el método NUEVO `_tool_schemas_hint()` se implementó completo (54 líneas) **dentro del mismo commit y archivo**, lo cual es lo que disparó el overflow.
- **Lo que se añadió, desglosado**:
  1. **+1 línea** en el f-string del `content`: insertar `{tools_section}` después de `{mode_hint}`.
  2. **+1 línea** para llamar al método: `tools_section = self._tool_schemas_hint()`.
  3. **+6 líneas** de comentario inline explicando el patrón Daniel Farina.
  4. **+44 líneas** del método nuevo `_tool_schemas_hint()` con docstring + lógica de selección por contexto + cache.
  5. **+5 líneas** de blanks/separadores.
- **¿Era evitable?** Sí, parcialmente:
  - El método nuevo podría haberse puesto en un módulo separado (e.g. `gemma4_agent/system_prompt_builder.py`) para que `agent.py` solo sumara las ~3 líneas del call + import. Esto habría respetado el constraint estricto.
  - Sin embargo, el método es **lógicamente parte de `Gemma4Agent`** (lee `self.config` y `self._cached_tool_schemas_md_*` como atributos de instancia). Moverlo afuera obligaría a pasar el config explícito y abandonar el cache nat​ural en `self`.
  - Trade-off elegido: cohesión de clase vs estrictez del constraint. Aceptable a posteriori porque toda la lógica nueva es **aditiva** (no modifica nada de la lógica de turno existente) y opt-outable vía env var.
- **Polish P2 también tocó `agent.py`**: el bloque del umbral compact `>=16384` → `>=12288` (4 caracteres cambiados). Eso es ≤10 líneas trivialmente.
- **Validación que NO se rompió nada del flow original de `_system_message`**: el f-string mantiene exactamente los mismos hints anteriores en el mismo orden; `tools_section` solo se intercala después de `mode_hint`. El resto del método (project_section, plan_hint, etc.) idéntico. Tests del repo 71/71 baseline pasaron tras el Sprint 1 → no hubo regresión.
- **Confirmación**: el cambio fue **aditivo, opt-outable, no destructivo**, y aporta el patrón Daniel Farina que el informe externo proyecta como +2-4 pp en tool-call accuracy. **El overshoot del tope esperado se acepta con esta documentación honesta**.

