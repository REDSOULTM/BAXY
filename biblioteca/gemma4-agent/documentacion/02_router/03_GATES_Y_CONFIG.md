# Gates y configuración

> Todas las variables de entorno `GEMMA4_*` del router: default, qué hacen,
> cuándo tocarlas. Todos los umbrales se afinaron SOLO sobre el dev split
> (anti-overfit); el holdout se mide una vez al final.

⚠️ **Antes de tocar un umbral:** medí el efecto en AMBOS corpus (curado + logs
reales). Un cambio que mejora un caso suele romper otros. La regla dura es
0 regresión en `router_eval.py` (recall 0.9964 / NO-TOOL 1.0000).

---

## Estructura / cap

| Variable | Default | Efecto |
|----------|--------:|--------|
| `GEMMA4_MAX_SELECTED_TOOLS` | `5` | Máximo de tools de dominio en el subset. Disciplina de precisión (más degrada el 4B). Ver nota cap=5 en [01_ARQUITECTURA](01_ARQUITECTURA.md). |
| `GEMMA4_RELATED_BUDGET` | `1` | Cuántas tools "relacionadas" (deps especulativas) agregar. **S1a lo bajó 3→1**: el related metía ruido puro (steam→app+window+verify) sin proteger recall. |
| `GEMMA4_ANTIPRIMACY` | `1` (ON) | **S5 (`b812841`).** Reordena el subset tras el cap: la tool de DOMINIO de mayor score va PRIMERA (sesgo de primacía del LLM). NO cambia el conjunto, solo el orden. `pending_intent` queda fija al frente; infra (session/verify/state/dependency/safety) al final (`planner.py:188,906-913`). |

---

## Collapses de precisión

| Variable | Default | Efecto |
|----------|--------:|--------|
| `GEMMA4_HIER_COLLAPSE` | `1` (ON) | **S3d.** Collapse jerárquico simple↔avanzado. Quita `browser_real` cuando el turno es nav simple (`score(browser) > score(browser_real)`). Recall-neutral medido. |
| `GEMMA4_CLUSTER_COLLAPSE` | `0` (OFF) | **S1b.** Collapse de dominio ({app,window}→app). GATED OFF: medido que pierde recall (0.9964→0.9820) sin discriminador real. Ver [06](06_PENDIENTE_Y_NO_FORZADO.md). |

---

## Abstención (NO-TOOL keep)

| Variable | Default | Efecto |
|----------|--------:|--------|
| `GEMMA4_VETO_P` | `0.78` | P(no_tool) por encima del cual el abstain head VETA el per-tool head. Alto → solo veta charla clara, no comandos borderline. |
| `GEMMA4_SEM_CONFIDENT` | `0.45` | Score sobre el cual una tool top-1 anula el gate conversacional (un comando de 1 palabra). |
| `GEMMA4_SEM_CONF_BAND` | `0.12` | Banda alrededor del pico que se conserva al anular (no la cola ruidosa). |
| `GEMMA4_SEM_PEAK_KEEP` | `0.50` | Escape confident-peak: score mínimo para tratar una tool como comando real pese al abstain head. |
| `GEMMA4_SEM_PEAK_GAP` | `0.15` | Gap mínimo sobre el 2º para el confident-peak (la charla pico plano <0.15). |
| `GEMMA4_RERANK_ABSTAIN_MAX` | `0.85` | El cross-encoder rescata solo si P(no_tool) está por debajo de esto (no resucita tools en "hola"). |
| `GEMMA4_KW_PROTECT_INFO_BLOCK` | `0.55` | Score INFO sobre el cual una keyword NO se protege del abstain wipe (es una pregunta, no comando). |

---

## Per-tool head

| Variable | Default | Efecto |
|----------|--------:|--------|
| `GEMMA4_HEAD_MIN_MARGIN` | `0.05` | Margen mínimo que una tool debe cruzar su umbral para disparar (firings débiles = ruido). |
| `GEMMA4_HEAD_TOP_N` | `3` | Máximo de tools que el head aporta. |

---

## Rescates operacionales

| Variable | Default | Efecto |
|----------|--------:|--------|
| `GEMMA4_CU_SEM_RESCUE` | `0.44` | Score de `computer_use` sobre el cual se rescata para in-app nav (Discord, mic). |
| `GEMMA4_SEM_TOPN` | `5` | Tamaño del fallback semántico cuando head Y keyword vienen vacíos. |

---

## Exemplar router

| Variable | Default | Efecto |
|----------|--------:|--------|
| `GEMMA4_EXEMPLAR_ROUTER` | ON | Activa el exemplar router. |
| `GEMMA4_EXEMPLAR_MIN_SCORE` | `0.92` | Coseno mínimo para considerar un match histórico. |
| `GEMMA4_EXEMPLAR_TOP_K` | `5` | Cuántos vecinos votan. |
| `GEMMA4_EXEMPLAR_CONFLICT_SCORE` | `0.975` | Umbral para detectar conflicto NO-TOOL vs tool casi-idéntico. |
| `GEMMA4_EXEMPLAR_ABSTAIN_MARGIN` | `0.05` | **S3c.** El voto-abstención debe SUPERAR al mejor voto-tool por este margen para abstener (no por un empate). Sin esto, "abre el navegador" daba vacío. |

---

## Intención (centroides)

| Variable | Default | Efecto |
|----------|--------:|--------|
| `GEMMA4_INTENT_VS_ACTION` | `0.05` | Margen que info debe superar a action para `wants_knowledge`. |
| `GEMMA4_INTENT_CONV_MARGIN` | `0.03` | Margen que las clases conversacionales deben superar a las "worldly" para `is_conversational`. |
| `GEMMA4_INTENT_META_FLOOR` | `0.36` | Piso absoluto que META debe cruzar para tratarse como directiva de política. |
| `GEMMA4_NAV_MARGIN` / `GEMMA4_SHOP_MARGIN` / `GEMMA4_EMAIL_MARGIN` | varios | Márgenes de los clasificadores de intención específicos (navegación web / compra-en-tienda / email). |

---

## MCP (Model Context Protocol)

| Variable | Default | Efecto |
|----------|--------:|--------|
| `GEMMA4_MCP` | gate | Activa el enrolamiento de tools MCP al router. |
| `GEMMA4_MCP_PEAK_KEEP` | `0.40` | Barra separada para tools MCP (viven en rango coseno más bajo). Una MCP que la cruza se promueve al frente. **Subido 0.30→0.40 al regenerar el encoder FT (3ep):** con la weather MCP enrolada, las relevantes ("qué clima/temperatura") caen 0.455–0.685 y "qué hora es" 0.304 (se colaba con 0.30); el gap limpio [0.304, 0.455] ubica el bar en 0.40 (`planner.py:67`). |

---

## Subsistemas opcionales (gated)

| Variable | Default | Efecto |
|----------|--------:|--------|
| `GEMMA4_CONTEXT_ROUTER` | gate | Decide cuánto historial mandar al LLM por turno. |
| `GEMMA4_DEICTIC` / `GEMMA4_DEICTIC_MARGIN` | gate | Detector de deícticos + inyección del referente. |
| `GEMMA4_RERANKER` / `_FLOOR` / `_MODEL` / `_TOPK` | gate | Cross-encoder de rescate condicional. |
| `GEMMA4_SEMANTIC_FALLBACK` | gate | Fallback semántico cuando el encoder degrada. |
| `GEMMA4_SPLIT_ACTION_MARGIN` / `GEMMA4_SPLIT_MULTILANG` | varios | Command splitter (cadenas multi-paso). |

---

## Cómo experimentar con un gate sin tocar el default

```bash
# Probar un valor distinto sin editar el código (env var lo sobreescribe):
GEMMA4_HIER_COLLAPSE=0 python scripts/router_eval.py          # desactivar S3d
GEMMA4_EXEMPLAR_ABSTAIN_MARGIN=0.0 python scripts/router_eval.py  # revertir S3c
```

Así medís el efecto A/B de cualquier gate antes de cambiar su default en el código.
