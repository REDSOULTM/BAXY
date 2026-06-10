# HANDOFF — sesión 2026-06-10 (para el siguiente agente)

Resumen de TODO lo hecho esta sesión, qué quedó listo, qué quedó a medias, y qué
falta. Leé esto primero, después el backlog (`_backlog/BACKLOG_MAESTRO.md`).

> **Estado git:** todo commiteado y sincronizado en los 4 refs (origin+asistia,
> main+Dev). HEAD = `c254b8d`. Verificá con los 3 rev-parse antes de empezar.
> **Regla de privacidad NUEVA (CLAUDE.md):** los repos son PÚBLICOS — los mensajes
> de commit, comentarios y docs NO deben exponer la conversación ("el usuario
> pidió", "aprobado por", referencias a chat/loop/agentes). Voz impersonal.
> Ya se reescribió la historia de la sesión una vez por esto (force-push a los 2
> repos). De acá en adelante: commits limpios desde el inicio.

---

## 1. Lo que se ARREGLÓ y está cerrado (verificado en vivo)

| commit | qué | estado |
|--------|-----|--------|
| `7c88ebf` | over-firing: "qué linda mañana"/"qué tal" iban a web (eran exclamaciones) | ✅ cerrado |
| `f575b6e` | fecha/hora local no arrastra web+source_manager de ruido | ✅ |
| `723e4ba` | "uso de CPU/RAM" = métrica local (system), no concepto | ✅ |
| `ea166f7` | **Steam "página de X" fallaba** por appid inventado por el 4B | ✅ 3 capas: schema + guarda `_is_placeholder_appid` + routing limpio. En vivo 3/3 |
| `e6dc8b0` | **cálculos verbales** "el doble de N"/"la mitad de N"/"raíz de N" → "no pude" | ✅ extendido `try_arithmetic`. En vivo 5/5 directo |
| `b7fba61` | **KV-cache K q8_0** (libera ~0.25-0.5GB VRAM) | ✅ aplicado. SOLO K (V requiere flash-attn, que está OFF). Kill-switch `GEMMA4_KV_CACHE_K` |

**Router multilingüe (B2) — varios commits** (`bba9ab4`, `b15cf7b`, `acc4a74`):
el corpus de eval pasó de medir SOLO español a medir+mejorar EN/IT/DE. Destapó
~13 huecos ocultos del router, cerró la mayoría vía reentreno del encoder.
**B2 está 🟡 BASE SÓLIDA pero es ítem GRANDE multi-sesión** (rendimientos
decrecientes: cada lote de corpus expone más huecos).

---

## 2. Lo que quedó A MEDIAS (continuar acá)

### 2.1 Confirm filler con personalidad — WIP (`c254b8d`)
**El módulo está LISTO y testeado (5/5); FALTA cablearlo.**
- `gemma4_agent/agent_core/action_filler.py`: `pick_filler()` + `intent_target_for_filler()`.
  Dos niveles: GENÉRICO seguro ("Dame un segundo", "calentando motores" si tarda)
  con personalidad de Baxy; INTENT-AWARE ("Abriendo Spotify") SOLO con alta
  confianza (tool openable + nombre propio claro). Ante duda → genérico (no miente).
- **PRÓXIMO PASO (cablear):** en `agent.py::run_content`, entre `_decide_turn`
  (línea ~5693) y `_execute_turn` (~5701): si hay `_active_tts_sink` (= modo voz)
  y el turno NO es early_reply (esos ya responden instantáneo), llamar
  `pick_filler(...)` y vocarlo al sink ANTES de `_execute_turn`. Pasar
  `intent_target_for_filler(user_text, selected_tool_names)` para el intent-aware.
  Rotar con un contador de turno de instancia (sin random — rompe resume).
- **CUIDADO:** el filler se voca, el reply REAL sale después (no lo reemplaza). El
  usuario oye "Dame un segundo… [pausa] Listo, abrí Spotify." NO vocar el filler
  en early_reply (responde ya) ni en modo texto/GUI (sink=None).
- **MEDIR EN VIVO (regla #3.5):** que el filler suene natural, que el intent-aware
  no mienta (probar "abrí Spotify" → "Abriendo Spotify" + reply real coherente; y
  un caso donde el 4B haga OTRA cosa → el genérico no contradice).
- Decisión del usuario: quiere genérico con personalidad + intentar intent-aware
  donde sea seguro, avisando si es muy riesgoso.

---

## 3. Lo INVESTIGADO (no era bug / aceptado / descartado)

- **Transcripción en inglés con settings en ES:** es limitante OFICIAL de Parakeet
  v3 (LID interno automático, NO se puede forzar idioma; malo en frases cortas).
  El usuario ACEPTÓ la limitante (no usar Whisper). Doc
  `03_voz_stt/research/parakeet_v3_uso_correcto`.
- **Outlier de latencia "qué hora es" ~20s:** NO es un loop. Es cold-start del
  encoder del router (~8-11s la 1ª vez). YA mitigado por `agent_runner.
  _bg_warmup_router()`. Con warmup el 1er turno es ~3.3s. No hay bug. Doc
  `03_voz_stt/_DIAGNOSTICO_logs_sesion`.
- **Auditoría del uso del modelo Gemma 4** (`151697b`, doc
  `00_producto/AUDITORIA_uso_del_modelo`): VEREDICTO = lo usamos muy bien.
  Sampling dual greedy, gateo de thinking por complejidad, few-shot dinámico,
  formato nativo, Q4_K_M — todo óptimo. Desviaciones de la guía oficial (FA off,
  sin cache-reuse) son decisiones MEDIDAS por bugs CUDA. Candidatos: KV-cache
  (HECHO), FR-CoT (DESCARTADO por medición — el thinking ya es chico), TTS
  paralelo (= el filler WIP).
- **Re-FT del LLM E2B:** NO tocar para idioma/tool-choice — ya falló 2× y es
  irreducible en el 2B (ver memoria `Re-finetuning v1 ROLLBACK`). La elección de
  tool no-determinista del 4B es el techo del modelo → E4B (bloqueado por VRAM).

---

## 4. Lo que FALTA (backlog, para sesiones dedicadas)

Ordenado por valor/accionabilidad:

1. **Cablear el confirm filler** (2.1 arriba) — el más cercano a listo.
2. **Residual del gate de abstención** (impedimento documentado): "what is the CPU
   usage" (EN) → [] aunque _suggest_tools ofrece system; lo borra el pipeline
   head→abstain→semantic→web-nav. Requiere instrumentar `select_tool_names`
   end-to-end + unificar las guardas LOCAL-FACT en un punto canónico. ES anda;
   solo el frame EN cae. Doc `02_router/B2_corpus_multilingue_hallazgos`.
3. **B2 más volumen** (EN/IT/DE) + atacar los huecos que cada lote expone
   (find-app, salir-de-app IT, etc.). Ítem grande.
4. **B1/B4** (reentreno encoder + calibración abstain por idioma) — ahora con base
   gracias a B2.
5. **Mejora menor cold-start:** bloquear el 1er turno hasta que el warmup termine,
   o "iniciando…", para el caso "usuario habla a los 3s de arrancar". ROI bajo.
6. **Bloqueados por recursos:** E4B (VRAM 4GB), binario CPU/Vulkan (mercado),
   corpus multilingüe a paridad total.

---

## 5. Gotchas de esta sesión (no repetir)

- **El V cache cuantizado EXIGE flash-attn** (que está OFF por crash CUDA #22527).
  Solo cuantizar K. Confirmado en llama.cpp #21450/#19036.
- **Medir con `Gemma4Agent()` pelado SIN runner** da artefactos (no dispara el
  warmup del encoder → falso "cold start" de 8s + falso "loop de 8 llamadas").
  Para medir latencia real, precargar el encoder como hace `_bg_warmup_router`.
- **El reentreno del encoder:** entrenar a temp dir (`GEMMA4_ENCODER_OUT_DIR`) +
  swap atómico; regenerar SIEMPRE centroides+exemplars con `router_ft_pipeline.py`
  (si no, se comparan espacios distintos). El encoder (449MB) NO se versiona
  (gitignored); la receta `tool2vec_queries.jsonl` + artefactos chicos SÍ
  (force-track con `git add -f`). Seed 42 fijo.
- **`git add` sin `-f`** rechaza cambios a archivos data/ ya tracked pero
  gitignored. Usar `-f` siempre para esos.
- **Tests ajenos que fallan en la suite (NO son tuyos):** `test_vision_input_*`
  (Codex, ImportError `_average_features`), `test_jarvis_taste_profile` (warm-state
  leak del encoder singleton). Verificar con git stash que un fallo es pre-existente
  antes de asumir que lo rompiste.
- **NO tocar `vision_input/`** (workstream de Codex, en desarrollo).
- **Commits a AMBOS repos** (origin+asistia, main+Dev, 4 refs) SIEMPRE. Patrón:
  push main x2, checkout Dev, merge --ff-only, push Dev x2, checkout main.
  (Stashear los cambios M de Codex antes de cambiar de rama; pop al volver.)
