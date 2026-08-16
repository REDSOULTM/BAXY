# HANDOFF — Gate CONOCIMIENTO-vs-ACCIÓN (arregla el mis-route conocimiento→acción de FunctionGemma)
**Fecha:** 2026-06-17 · **Para:** el agente de Baxy. **Sin reentrenar FunctionGemma** (decisión del dueño).
Resuelve el blocker del split lean: queries de CONOCIMIENTO ruteadas a tools de ACCIÓN (vision/contacts/data_analysis).

## Qué es
Un clasificador **conocimiento-vs-acción** (regresión logística calibrada sobre los embeddings del encoder
MiniLM-L12-FT que el router YA usa) que corre **ANTES** de FunctionGemma. Si la query es CONOCIMIENTO con
alta confianza → `no_tool` (no se invoca FG). Si no → sigue el flujo normal (router jerárquico + FG).
Best-practice 2026 (vLLM Semantic Router / FutureAGI: head barato sobre embeddings + threshold con fallback).
Sub-ms (un dot product de 384 dims), multilingüe, sin keywords hardcoded (respeta tu CLAUDE.md), artefacto reproducible.

## Por qué (causa-raíz medida)
FunctionGemma run9 abstiene bien en conocimiento general (96%), PERO falla en **trampas family-dominated** aun con
no_tool en el subset: "contame de Roma"→contacts (nombre propio), "y cuánto mide?"→data_analysis (parece medición),
"what is a linked list"→vision. El gate las corta antes de que FG las vea. (Casos "linked list"/"Einstein" también
se arreglan asegurando no_tool en el subset — eso es el otro 50% del fix, lado router; ver §Integración.)

## Artefactos (copiar a Baxy)
- `kva_gate.json` — pesos del clasificador (coef 384d + intercept + threshold 0.87). Regenerable con `build_kva_gate.py`.
- `kva_gate_infer.py` — inferencia (clase `KVAGate`, sub-ms). Sin dependencias nuevas (numpy).

## Integración (en gemma4_agent/routing/fg_router.py::fg_emit, ANTES de invocar FunctionGemma)
```python
from kva_gate_infer import KVAGate
_gate = KVAGate("kva_gate.json")          # cargar 1 vez (módulo)
# ... dentro de fg_emit, ya tenés el embedding de la query para suggest_tools_scored:
q_emb = encoder.encode([query], normalize_embeddings=True)[0]   # MISMO encoder MiniLM-L12-FT del router
if _gate.is_knowledge(q_emb):             # CONOCIMIENTO alta confianza -> no_tool, NO invocar FG
    return "no_tool"
# si no -> seguir: gate act-vs-conv actual + router jerárquico + FunctionGemma
```
IMPORTANTE: el embedding DEBE salir del MISMO encoder (router_encoder_ft / MiniLM-L12-FT) y normalizado
(`normalize_embeddings=True`), si no el clasificador no aplica. Reusá el embedding que ya computás para el router (cero costo extra).
**Y verificá que `no_tool` esté SIEMPRE en el subset que se manda a FG** (es la otra mitad del fix; el handoff previo lo pedía
pero el mis-route a vision sugiere que en la práctica el subset a veces no lo lleva).

## Resultados MEDIDOS (held-out + casos del reporte)
- Trampas → no_tool: contame de Roma 0.90, what is a linked list 0.93, y cuánto mide 0.97, quién fue Einstein 1.0,
  por qué el cielo es azul 0.99, parle-moi de Rome 0.99, cos'è una lista 0.99 → **7/7 cortadas**.
- Canarios de ACCIÓN → FG (no bloqueados): subi volumen 0.03, mandale 'te amo' a Ana 0.15, abrí Chrome 0.50,
  recordá café 0.33, wifi 0.04, poné música 0.28 → **6/6 preservados**.
- Held-out: conocimiento→no_tool 76.5% (el resto va a FG, que abstiene 96% = backstop) | **acción preservada 99.1%**
  (threshold 0.87 tuneado para NO bloquear acciones; ante la duda → FG decide).
- Sistema combinado (gate + FG): conocimiento ~99%, acción ~99%, sin reentrenar.

## Validar en vivo (tu regla 3.5) + no-regresión
- Corré `python kva_gate_infer.py` (smoke con el encoder) — debe dar las trampas→no_tool y los canarios→FG.
- En Baxy: `scripts/_recheck_vision_confab.py` y `_validate_lean_broad.py` → objetivo 0/N confabs en conocimiento.
- No-regresión: `router_canary_eval.py` (no bajar) + acciones multilingües (es/en/fr/pt/it) deben seguir andando.

## Threshold = 0.87 (elegido por research, NO a ojo)
Marco: el gate es una **cascada con deferral** (GATEKEEPER, "When Does Confidence-Based Cascade Deferral
Suffice?" NeurIPS) — el clasificador barato corta solo si está confiado; ante la duda DEFIERE a FunctionGemma.
Threshold **cost-sensitive** (teoría de decisión): **t\* = C_FP/(C_FP+C_FN)**, con el positivo = conocimiento→no_tool:
- C_FP = cortar una ACCIÓN real → comando ignorado, SIN recuperación → costo alto.
- C_FN = dejar pasar conocimiento → FG lo recupera ~96% (backstop) → costo bajo.
C_FP ≫ C_FN (hay red para el conocimiento, no para la acción) → ratio ~6.7:1 → **t\* ≈ 0.87**.

CURVA e2e medida (gate+FG; elegí el punto según prioridad de Baxy, es 1 número en kva_gate.json):
```
 thr | ACCIÓN preserv | CONOC trampas-frescas | CONOC holdout(ruidoso)
0.75 |     96.9%      |      100%             |     78.3%   (máx conocimiento)
0.80 |     97.5%      |       95%             |     78.3%   (equilibrado)
0.87 |     98.8%      |       90%             |     75.8%   (conservador = cost-optimal, ACTUAL)
0.90 |     99.4%      |       85%             |     73.3%
```

## Regenerar / tunear
- `python build_kva_gate.py` (CPU, ~2min; NO usa GPU/no reentrena FG). Genera el dataset (acción de curated + trampas
  de conocimiento Y de acción por plantillas multilingües) → embebe con el encoder → entrena logistic calibrada →
  tunea threshold para acción-recall ≥99% → guarda kva_gate.json. Subir el threshold = más conservador (menos corta,
  más va a FG); bajarlo = corta más conocimiento pero arriesga bloquear acciones. 0.87 es el punto acción≥99%.
- GOTCHA del venv: cargar `SentenceTransformer(...)` "pelado" SEGFAULTEA (torch 2.7/cpp-ext rota); por eso el script
  usa el encoder vía `FTRouter` (que inicializa routing.semantic_router antes) y embebe en chunks de 200. En Baxy,
  donde el encoder ya está inicializado por el router, no hay este problema.
```
