# Backlog research × código × memoria (2026-06-01)

Cruce de 10 agentes de investigación (5 research + 5 auditoría de código, solo-lectura)
contra la **memoria persistente del repo** (117 topic files) y verificación directa de
defaults en el código actual. Objetivo: hallar oportunidades REALES de calidad/latencia/
rendimiento, descartando lo ya-aplicado y lo medido-y-rechazado.

**Método (regla del repo):** nada se afirma sin verificar contra el código o una medición.
Cada ítem marcado: [VERIFICADO] medido/leído por mí · [PLAUSIBLE] sin confirmar ·
[RECHAZADO-MEMORIA] la memoria ya lo descartó · [YA-HECHO] ya está en prod.

---

## ESTADO VIVO (se actualiza con cada avance)

Rama de trabajo: `Dev`. Implementación de los 3 fixes verificados de bajo riesgo:

| # | Fix | Estado | Commit |
|---|-----|--------|--------|
| 8 | Tracing batcheado (~22ms/turno medido) | 🔲 PENDIENTE | — |
| 9 | brightness honesto (re-leer post-set) | 🔲 PENDIENTE | — |
| 10 | accent multilingüe en is_question_lexical | 🔲 PENDIENTE | — |

Leyenda: 🔲 pendiente · 🔨 en progreso · ✅ hecho+validado · ⏸️ bloqueado

**Cerrado esta sesión (no re-litigar):** FR-CoT re-medido en vivo 2026-06-02 → sigue PEOR
(rompe "subí volumen", aumenta thinking 68→164); la premisa murió (thinking ya es 0-102 tok
post-LEAN, no 268). Ver memoria `project_frcot_remeasured_dead_2026_06_02`.

---

## A. Lo que el cruce DERRIBÓ (research recomendó pero la memoria/código lo contradice)

Estos eran "hallazgos grandes" de los agentes que el cruce con memoria invalidó. NO perseguir.

1. **FR-CoT (thinking estructurado ≤32 tok)** — [RECHAZADO-MEMORIA]
   - R1/R5 lo pusieron como "el lever de latencia #1, código dormant pendiente de validar".
   - **La memoria `project_v22_faoff_crash_fix_2026_05_28.md:50` dice: "VALIDADO EN VIVO
     (2026-05-28): REGRESA y queda OFF".** Rompió audio (set_volume/mute vacío en budget 32).
     Listado entre medido-y-rechazado en `project_perfection_roadmap`. Default real `GEMMA4_FRCOT=0`.
   - **Veredicto: NO re-litigar.** El código dormant existe pero su conclusión fue NO.
     La memoria dice que la palanca real sería prefill `<|tool_call|>` — que TAMBIÉN está rechazado (ver #3).

2. **Parakeet STT (10× vs Whisper)** — [YA-HECHO]
   - R5 lo recomendó como "no usado, frena instalación NeMo".
   - **La memoria `project_parakeet_night_2026_05_23.md:61` dice: "HABILITADO EN PROD
     (RED lo aprobó): GEMMA4_STT_ENGINE default = parakeet". p50 74ms vs Whisper 1593ms.**
     Confirmado en código: default real `"parakeet"`. R5 leyó un README viejo de 07_audio.
   - **Veredicto: ya migrado hace una semana.** El STT NO es cuello de latencia (74ms p50).

3. **prefill `<|tool_call|>`** — [RECHAZADO-MEMORIA]
   - `project_latency_streaming_2026_05_29.md:53` "MALA APUESTA (medido, NO construir)";
     thinking load-bearing 4/6→0/6. NO proponer.

4. **load_context 4×/turno baja el prefix-cache** (C1) — [VERIFICADO: micro]
   - Verificado: `find_context_file` hace ~8 stat() pero solo si NO hay GEMMA4.md/JARVIS.md
     en CWD (caso típico = early-return). Submilisegundo. Mi medición p50 1.22s lo confirma.
   - **Veredicto: micro-optimización, no el cuello que C1 sugirió.**

5. **media-key verified=False dispara retry** (C3 #4) — [VERIFICADO: ya mitigado]
   - `tools.py:268` el guard `_has_unverified_signal` YA excluye `playback_verified=False`
     a propósito (comentario explícito). C3 leyó la 3961 pero no la 268.

6. **5 encodes del router = 250-750ms** (C2 #1) — [VERIFICADO: ya cacheado]
   - `intent_router.py:332-338` todas las funciones (classify_intent/is_conversational/
     wants_knowledge) comparten UN solo `sr.embed()` LRU-cached. El comentario lo dice.
     Mi p50 1.22s lo confirma. C2 vio las 5 llamadas, no el LRU compartido.

7. **MTP (multi-token prediction, 3× decode)** — [BLOQUEADO-UPSTREAM]
   - R5: no existe en llama.cpp aún (3-6 meses). Cuando exista es transparente. Esperar.

---

## B. Oportunidades REALES verificadas (bajo riesgo, no contradicen memoria)

8. **Tracing batcheado** — [VERIFICADO: 22ms/turno MEDIDO]
   - `infra/tracing.py:71` hace open/write/close por evento × ~150 eventos/turno.
     `enable_tracing` default = True (confirmado código). **Medí: 150 open/write/close =
     22.2ms vs 1-handle = 0.4ms → ahorro real ~21.8ms/turno.** (C4 estimó 75-300ms, exageró.)
   - Fix: handle persistente o cola async daemon. Bajo riesgo (solo diagnóstico, ya swallowing).
   - NOTA: la memoria `project_arch_audit` dice que tracing tiene fail-safe; respetar eso.

9. **brightness fire-and-hope** (C3 #5) — [PLAUSIBLE, gemelo de bug ya arreglado]
   - `tools.py` brightness reporta verified=False sin re-leer, a diferencia de
     `audio_set_volume` que sí verifica. Mismo patrón que keypress (arreglado esta sesión).
   - CAVEAT memoria `project_brightness_weather_2026_05_27`: el brillo WMI a veces falla por
     el SO (monitor sin DDC) — eso NO es bug, es honesto. El fix debe distinguir "fallo SO"
     de "no verificado". Copiar el patrón de audio_set_volume con cuidado.

10. **is_question_lexical accent-sensitive** (C2 #4) — [VERIFICADO: coincide con memoria]
    - `project_bugs_847_fixes:18` y MEMORY ya marcan "wants_knowledge accent-sensitive".
    - Restricción dura `feedback_no_monolingual_regex`: NO listas por idioma; normalizar
      NFKD antes del regex es estructural y OK. Bajo riesgo.

11. **fallback de streaming bustea cache** (C4 #1) — [VERIFICADO: real, path raro]
    - `agent.py:2765` usa `_think_now` donde el path normal (2777) usa `_pass_enable_thinking`.
      Inconsistente → bustea prefix-cache si streaming falla en summary-pass. Fix 1 línea.
    - Impacto: solo en el path de error (streaming TTS falla mid-flight). No mueve el p50.

12. **embeddings de skills sin caché por-turno** (C5 #4) — [PLAUSIBLE]
    - microagents cachean (`_MA_EMB_CACHE`) pero skills_registry no. Replicar el patrón.
    - Sin medir el costo real; estimar antes de accionar (los otros "embeddings lentos"
      se desinflaron al medir).

13. **reranker sin gate temprana** (C2 #2) — [PLAUSIBLE]
    - planner.py:688 corre reranker en turno vacío sin chequear abstain_p≥0.85 primero.
      Carga 120MB en smalltalk. early-return. Bajo riesgo.

---

## C. Grandes pendientes (alto impacto, requieren validación viva — la memoria los respalda como pendientes)

14. **cap=5 → 8** — [PENDIENTE, respaldado por memoria como GAP-5]
    - C2 #5 + memoria `project_perfection_roadmap` GAP-5: cap=5 es workaround del crash CUDA
      #22527. Con FA-off el crash se eliminó (`project_v22_faoff_crash_fix`). **Revisar si
      ahora se puede subir a 8** (la memoria de routing dice recall holdout 0.8345 igual en
      10 vs 16, así que el beneficio es para multi-intent, no recall). Requiere repro CUDA.

15. **--reasoning-budget-message** (R5, IDEAS #6) — [PENDIENTE, no medido en Gemma]
    - Cierre limpio del thinking. Flag llama.cpp trivial/reversible. Qwen +11pp; Gemma no medido.
    - Bajo riesgo, pero requiere validación viva. La memoria lo lista como backlog #6.

16. **mmproj Q8_0 (−430MB VRAM)** — [BLOQUEADO: artefacto no existe]
    - Memoria `project_grounding`/roadmap: llama-quantize falla "unsupported architecture:
      clip" (#18881 abierto). El código ya prefiere Q* si existiera. Desbloquea cuando exista el GGUF.

---

## D. Restricciones de la memoria que acotan TODO lo de arriba (no violar)

- **STT en CPU, no upgrade de Whisper** (`feedback_stt_cpu_only`, `feedback_whisper_no_upgrade`):
  pero ya es Parakeet, mejor que Whisper. Cerrado.
- **No regex monolingüe** (`feedback_no_monolingual_regex`): el fix de accent debe ser estructural.
- **No respuestas enlatadas** (`feedback_no_canned_replies`): nada de tablas fijas.
- **Universal/multi-idioma** (`feedback_universal_use`): no optimizar sobre una voz.
- **No setup al usuario** (`feedback_no_user_setup_burden`): el código garantiza precondiciones.
- **Medido-y-rechazado = NO tocar**: circuit-breaker ON, prefill `<|tool_call|>`, FR-CoT,
  FR-CoT brief-thinking, core-set, fine-tune sobre voz, KV-quant con FA-off, streaming-TTS-filler.

---

## Conclusión

El research del repo **ya estaba mayormente cosechado**; su valor fue confirmar que NO quedan
levers de latencia grandes sin probar (FR-CoT y prefill, los dos candidatos, ya fueron
rechazados en vivo). LEAN_RULES y Parakeet (los dos mayores wins) **ya están en prod**.

Los fixes nuevos reales son **pequeños y de la auditoría de código**: tracing batcheado
(~22ms, medido), brightness honesto, accent multilingüe, fallback-cache, reranker-gate.
Ninguno mueve el p50 dramáticamente (que ya está sano en 1.22s), pero suman calidad/robustez.

El cruce con memoria **derribó 7 de los hallazgos "grandes"** — exactamente el filtro que
evita re-litigar lo ya medido. Sin este cruce, habríamos perseguido FR-CoT (rechazado) y
Parakeet (ya hecho).
