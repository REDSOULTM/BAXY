# Router de tools de Baxy — documentación completa

> **Punto de entrada único** para entender el router de selección de tools.
> Estado a 2026-06-04. Esta carpeta es la fuente AUTORITATIVA y vigente; el
> research histórico en [`documentacion/_historico/`](../_historico/)
> incluye documentos OBSOLETOS (ver aviso abajo).
>
> **Nota de nombre:** el PRODUCTO se llama **Baxy** (antes "Gemma 4 Agent" →
> "Carter" → "Baxy"). El **MODELO** sigue siendo **Gemma 4** (de Google) — eso
> NO se renombra. Cuando este doc dice "Gemma 4" se refiere al modelo; cuando
> dice "Baxy" se refiere al producto/asistente.

---

## Qué es el router

El router decide, en cada turno de voz/texto, **qué subconjunto pequeño de
herramientas** se le ofrece al LLM (modelo Gemma 4 E2B-FT, desplegado in-place
en `models/E2B/`) para que elija. No ejecuta nada; solo arma una lista de ≤5
tools (más algunas meta-tools) a partir del mensaje del usuario, y desde el
SPRINT5 (2026-06-02/03) las **reordena anti-primacy** (la tool de mayor
confianza primero).

**Por qué importa:** el 4B es chico y no-determinista. Si le ofrecés 68 tools,
elige peor y más lento. Si le ofrecés las 2 correctas, acierta. El router es la
disciplina que mantiene el subset chico Y correcto.

**El norte (pedido del usuario, 2026-05-29):**
1. **Precisión** — ofrecer SOLO lo necesario, sin ruido ("si requiere 2 tools,
   no ofrecer 5").
2. **Recall** — la tool correcta SIEMPRE está en el subset (ya saturado en 0.9964).
3. **Robustez** — agregar tools o MCPs mañana NO debe desconfigurar el router.
4. **Universalidad** — multi-idioma, multi-acento (ley del producto).

---

## Mapa de esta carpeta

| Documento | Contenido |
|-----------|-----------|
| [01_ARQUITECTURA.md](01_ARQUITECTURA.md) | El pipeline completo: las capas, el flujo por turno, el diagrama de decisión |
| [02_COMPONENTES.md](02_COMPONENTES.md) | Cada módulo (`planner`, `intent_router`, `semantic_router`, `exemplar_router`…) y cada artefacto de datos, con su rol |
| [03_GATES_Y_CONFIG.md](03_GATES_Y_CONFIG.md) | Todas las variables de entorno `GEMMA4_*` del router: default, efecto, cuándo tocarlas |
| [04_EVAL_Y_METRICAS.md](04_EVAL_Y_METRICAS.md) | Cómo medir el router: los corpus, `router_eval.py`, las métricas (recall / NO-TOOL keep / precisión-ruido) y los gates de éxito |
| [05_HISTORIAL_SPRINTS.md](05_HISTORIAL_SPRINTS.md) | Qué se hizo y por qué: S0–S6 con resultados MEDIDOS |
| [06_PENDIENTE_Y_NO_FORZADO.md](06_PENDIENTE_Y_NO_FORZADO.md) | **Lo diferido y lo rechazado** con la medición que lo justifica. Lo que se debería hacer después |

Plan maestro original (vivo): [`PLAN_MAESTRO_router.md`](PLAN_MAESTRO_router.md).

---

## Estado actual (artefactos regenerados 2026-06-02, holdout vigente)

### Corpus curado (1733 filas, anti-overfit con holdout 20%)
- **Recall holdout: 0.9964** (saturado) — la tool correcta casi siempre está.
  Sigue vigente tras la regeneración del encoder FT + cabezas del 2026-06-02
  (ver [BACKLOG_MAESTRO](../_backlog/BACKLOG_MAESTRO.md) línea "Encoder FT…
  holdout ES 0.9964").
- **NO-TOOL keep holdout: 1.0000** — no ofrece tools en charla/preguntas.
- **Ruido holdout: ~1.51 tools-extra/turno** (medido en S3d, 2026-05-30).

> ⚠️ Las cifras de ruido y de logs reales de abajo se midieron el 2026-05-30,
> ANTES de la regeneración de artefactos (encoder/cabezas) del 2026-06-02 y de
> los fixes de SPRINT5/smart_home. Para re-medir el snapshot exacto: corré
> `python scripts/router_eval.py` (ver [04_EVAL_Y_METRICAS](04_EVAL_Y_METRICAS.md)).

### Logs reales del usuario (1071 pares, la verdad de campo)
- **Recall: 89.1%** honesto (dominio-equivalente). NO es el 99.6% sintético:
  el corpus curado está saturado/sesgado; los logs reales son más duros.
- Ruido: 1.35–1.42 tools-extra/turno.

### Ruido conocido sin atacar (MEDIDO, en el backlog)
- `wants_web_store` falso-positivo en menciones de entretenimiento/celebridad
  ("quién es batman", "pon stranger things") → inyecta `browser+browser_real` de
  ruido en 189 tool-turns. A/B OFF: ruido 1.519→1.453, recall SUBE
  0.9929→0.9953. **NO aplicado** (toca clasificador semántico, exige validación
  EN VIVO).
- `web→source_manager` + head débil: "qué día es hoy"/"what time is it"→web
  (prohibido, es dato local); "qué es pytest"→web+knowledge+source_manager. El
  per-tool head dispara `web` con margen débil evadiendo la guarda `_LOCAL_FACT`.
  **NO aplicado.** Ver [06_PENDIENTE_Y_NO_FORZADO](06_PENDIENTE_Y_NO_FORZADO.md).

### Multilingüe
- ES/EN/PT/FR/IT: bien. **DE (alemán): límite del encoder base** — documentado
  en [06_PENDIENTE_Y_NO_FORZADO.md](06_PENDIENTE_Y_NO_FORZADO.md).

### Actualizaciones de routing (2026-06-05 → 2026-06-09)
- **Encoder reentrenado** con corpus `train.jsonl` (SOLO train, sin holdout
  contaminado): aprende `text→tool` del dataset del LLM, sin hardcode — p.ej.
  "en el navegador" rutea a browser. Artefactos regenerados (`2dede36`, `8068279`).
- **`cancel_turn` espurio arreglado:** "ve a X" / "desmutea" ya no caían a
  session-only (`a0d23c3`).
- **web responde con lo buscado:** "háblame de X" buscaba pero abría un tab en vez
  de resumir → guard que tras `search` responde con los snippets; `open` solo si
  el user quiere VER (`50038cb`, `808df2a`). Calidad de fuentes por FORMA
  (foro/discusión vs estándar), sin allowlist de dominios.
- **Detectores de honestidad en el planner** (cacería): `_is_howto`,
  `_is_prompt_injection`, `_is_trigger_declaration`, `_is_low_signal_noise` — ver
  §9 del [BACKLOG_MAESTRO](../_backlog/BACKLOG_MAESTRO.md).

---

## ⚠️ Aviso sobre el research histórico (OBSOLETO en parte)

Los documentos en `gemma4_agent/docs/research/router/` que hablan de **RRF,
BM25, bandas HIGH/MEDIUM/LOW, cap 8/16** (sobre todo
`router_calibracion_tight_cluster_band.md` y
`router_arquitectura_retriever_hibrido_rrf.md`) describen un **RouterV2 que se
BORRÓ** en el rebuild de 2026-05-21. El router ACTUAL es `planner.py`
(keyword + encoder FT + Tool2Vec + abstain head + per-tool head). Las cifras
viejas (0.835 / 0.881) son de OTRO sistema. **No apliques esos fixes directo.**

El research que SÍ sigue vigente: el principio de "abstención calibrada como
decisión única", "el encoder base es el techo para queries cortas de voz", y la
idea del encoder FT sobre la distribución propia. Ver
[`router_rebuild_2026_05_21.md`](../_historico/router_rebuild_2026_05_21.md).

---

## Arranque rápido (para el próximo agente)

```bash
# Medir el router contra el corpus curado (con holdout anti-overfit):
python scripts/router_eval.py

# Medir contra los LOGS REALES del usuario (la verdad de campo):
python scripts/router_eval.py --corpus gemma4_agent/data/router_corpus_real_logs.jsonl --equiv --inherit

# Ver fallas concretas:
python scripts/router_eval.py --show-fails --slices

# Verificar en vivo los fixes recientes (necesita el server en :8080):
python scripts/_live_verify_router_s3.py
```

**Reglas de oro (de CLAUDE.md):**
- Nunca declares una mejora sin un número contra un gate definido de antemano.
- 0 regresión en el corpus curado (recall 0.9964 / NO-TOOL 1.0000) es no-negociable.
- Nada de listas de keywords por idioma para decidir: clasificación por
  embeddings multilingües + guardas estructurales. El encoder generaliza.
