# PROMPT — Sprint 8c (blind test, tuning, promoción a default)

> Continúa el mismo chat de Claude Code (Sprints 0-8b).
> **Sprint 8c:** blind test del router_v2 vs router viejo,
> tuning de thresholds, promover v2 a default (con flag de
> rollback), y armar el self-improving loop ligero.
>
> Plan completo:
> - **8a:** infra. DONE.
> - **8b:** 65 tool_descriptions.yaml enriquecidas. DONE.
> - **8c:** blind test + tuning + promoción + self-improving. (este)

---

## Origen del diseño

Investigación de Claude Research (mayo 2026), §3 (recomendación
final) y §5 (apuesta).

Componentes que ya tenemos al inicio de 8c:
- `router_v2.py` (8a).
- `tool_descriptions.yaml` con 65 entries enriquecidas (8b).
- Modelo `e5-small` ONNX en `~/.gemma4/models/e5-small/`.
- Tests `test_router_v2.py` pasando.
- Router viejo (`planner._suggest_tools` regex-first + semantic
  fallback) sigue siendo el default.

Lo que falta:
1. **Blind test set** — corpus de 100-200 frases reales/sintéticas
   con su tool esperada, en ES + EN + 3-4 idiomas extra (no
   ancla) para confirmar que el modelo multilingue de verdad
   transfiere.
2. **Métricas** de cada router en ese corpus: precision@k, recall@k,
   latency p50/p95.
3. **Tuning** de θ_smalltalk, θ_tools, θ_fallback, RRF k (si hace
   falta).
4. **Promoción** del v2 a default. Flag GEMMA4_ROUTER_V1=1 como
   rollback para reactivar el viejo.
5. **Self-improving loop ligero** — tracking de tools llamadas vs
   sugeridas para detectar drift sin re-entrenar.

## Estado del repo al arrancar

- HEAD: cierre de 8b.
- Working tree limpio.
- 65 compound tools intactas.
- `router_v2.py` activo behind flag (off por default).
- 745+ tests verde.

---

## Prompt completo (copy/paste al chat existente)

```
Continuamos. Estado: rama PortandoLoMejor, HEAD <commit-cierre-8b>,
working tree limpio, 65 compound tools, router_v2 + yaml listos,
745+ tests verde.

# OBJETIVO DE SPRINT 8c

1. Construir un blind test set (100-200 queries con tool esperada).
2. Medir router viejo vs router_v2 en ese set.
3. Tunear thresholds del v2 hasta que iguale-o-supere al viejo en
   ES/EN y supere claramente en idiomas no-ancla y frases
   coloquiales.
4. Promover v2 a default. Viejo queda detrás de
   GEMMA4_ROUTER_V1=1 como rollback.
5. Armar self-improving loop ligero: registrar tools_called vs
   tools_suggested por turn para análisis posterior.

# REGLAS GENERALES

1. PortandoLoMejor. Commits chicos, prefijo "sprint8c.X:".
2. NO toques las 65 compound tools.
3. NO toques tool_descriptions.yaml (eso fue 8b).
4. NO toques semantic_router.py (queda intacto como path del
   router viejo, por si rollback).
5. Modificás planner.py SOLO en `_suggest_tools` o equivalente:
   agregás un branch que delega a router_v2 cuando v1 no está
   forzado.
6. NUNCA git add -A. Archivos específicos.
7. Verificación post-commit:
   - tests verde.
   - flags funcionan: con GEMMA4_ROUTER_V1=1 el sistema usa el viejo;
     sin nada, usa v2.
   - `python -m gemma4_agent.launcher status` OK.

# WORKFLOW

## 8c.1 — Construir el blind test set

Creá `gemma4_agent/tests/data/routing_blind_set.yaml`:

```yaml
# Blind test set para evaluar tool-routing.
# - 60 queries ES (40 directas + 20 coloquiales/rioplatenses).
# - 60 queries EN (40 directas + 20 coloquiales/UK/US).
# - 20 queries PT (transfer test, no anchor).
# - 20 queries FR (transfer test, no anchor).
# - 20 queries DE (transfer test, no anchor).
# - 20 queries smalltalk (negative class, expected_tools=[]).
#
# Cada entry: query, expected_primary, expected_acceptable, locale, category.
# - expected_primary: tool que mejor matchea (top-1 ideal).
# - expected_acceptable: lista de tools alternativas que también
#   serían correctas (para precision@k).
# - locale: es/en/pt/fr/de/es-ar/en-uk.
# - category: directa/coloquial/ambigua/smalltalk.
- query: "hazme un power point sobre los planetas"
  expected_primary: office
  expected_acceptable: [office]
  locale: es
  category: directa
- query: "armame algo para mostrar mañana en la reu"
  expected_primary: office
  expected_acceptable: [office]
  locale: es-ar
  category: coloquial
- query: "dale play a algo de los redonditos"
  expected_primary: music
  expected_acceptable: [music, spotify, media, audio]
  locale: es-ar
  category: coloquial
- query: "podes bajarme el volumen"
  expected_primary: audio
  expected_acceptable: [audio, system]
  locale: es-ar
  category: coloquial
- query: "convertí este docx a pdf"
  expected_primary: office
  expected_acceptable: [office, pdf]
  locale: es
  category: directa
# ... 195 más en este formato
- query: "qual é o clima hoje em São Paulo"
  expected_primary: web
  expected_acceptable: [web, browser]
  locale: pt
  category: directa
- query: "envoie un message à Marie sur WhatsApp"
  expected_primary: whatsapp
  expected_acceptable: [whatsapp]
  locale: fr
  category: directa
- query: "öffne mein Word-Dokument"
  expected_primary: office
  expected_acceptable: [office]
  locale: de
  category: directa
- query: "hola, todo bien?"
  expected_primary: null
  expected_acceptable: []
  locale: es
  category: smalltalk
```

Construilo así:
- Para cada uno de los ~14 domains, redactá 8-12 queries reales
  que un usuario haría. Mezclá ES directo + ES rioplatense +
  EN directo + EN coloquial.
- Sumá 20 smalltalk negativas (saludos, agradecimientos, "como
  te llamas", "que hora es" — esta última podría ser system,
  cuidá la ambigüedad).
- Sumá 60 queries en PT/FR/DE para test de transferencia
  multilingue.

**Importante**: NO mires las example_queries del YAML cuando
escribas el blind set, sino test leak. Inventalas pensando en
cómo el usuario real hablaría. Si tenés que inspirarte, leé
los TOOL_RULES, no el YAML.

Commit: "sprint8c.1: blind routing test set (200 queries × 14
domains × 5 locales)"

## 8c.2 — Harness de evaluación

Creá `gemma4_agent/tests/test_routing_blind.py`:

```python
"""Blind comparison: router_v1 (regex+semantic) vs router_v2."""
from __future__ import annotations

import os
import time
from pathlib import Path

import pytest
import yaml

from gemma4_agent.tools import COMPOUND_TOOL_SCHEMAS

BLIND_SET = Path(__file__).parent / "data" / "routing_blind_set.yaml"


def _load_set():
    return yaml.safe_load(BLIND_SET.read_text(encoding="utf-8"))


def _v1_route(query: str) -> list[str]:
    """Router viejo: planner._suggest_tools."""
    from gemma4_agent.planner import _suggest_tools
    return _suggest_tools(query) or []


def _v2_route(query: str) -> list[str]:
    """Router nuevo: RouterV2.route."""
    from gemma4_agent.router_v2 import RouterV2
    result = RouterV2.get().route(query)
    return result.subset


def _precision_at_k(predicted: list[str], expected_acceptable: list[str], k: int) -> float:
    if not expected_acceptable:
        # Smalltalk: queremos lista vacía o solo no-tools.
        return 1.0 if not predicted else 0.0
    hits = sum(1 for p in predicted[:k] if p in expected_acceptable)
    return hits / min(k, len(expected_acceptable))


def _top1_hit(predicted: list[str], expected_primary: str | None) -> bool:
    if expected_primary is None:
        return not predicted
    return bool(predicted) and predicted[0] == expected_primary


@pytest.mark.skipif(
    not Path.home().joinpath(".gemma4/models/e5-small").exists(),
    reason="e5 ONNX not downloaded",
)
def test_v2_overall_precision_meets_target():
    """v2 debe llegar a precision@5 >= 0.80 en el conjunto entero."""
    data = _load_set()
    hits = 0
    for entry in data:
        pred = _v2_route(entry["query"])
        if _precision_at_k(pred, entry["expected_acceptable"], k=5) > 0:
            hits += 1
    rate = hits / len(data)
    assert rate >= 0.80, f"v2 precision@5 = {rate:.2%}, target 80%"
```

Y un script standalone para reportes ricos:

`gemma4_agent/scripts/eval_routing.py`:

```python
"""Compare router_v1 vs router_v2 on blind set. Outputs a
markdown report to docs/architecture/sprint_prompts/_sprint8c_eval.md.
"""
# ... (implementación: para cada query corre v1 y v2, mide
#      top-1, precision@5, latency. Agrupa por locale y category.
#      Imprime tabla markdown.)
```

Métricas por router:
- `top1_hit` rate global.
- `precision@5` global y por locale y por category.
- `latency_p50_ms` y `latency_p95_ms`.
- `smalltalk_false_positive_rate` (cuántas smalltalk queries
  devolvieron subset no vacío).
- Lista de queries donde v2 falla y v1 acierta (regresiones).
- Lista de queries donde v1 falla y v2 acierta (mejoras).

Commit: "sprint8c.2: eval harness + standalone report script"

## 8c.3 — Primer baseline + tuning

Corré `python -m gemma4_agent.scripts.eval_routing`. Mirá:

1. **Top-1 v1 vs v2 global.** Si v2 < v1 en >5 pts, hay un
   problema sistémico — revisá YAML, prefix e5, BM25 tokenizer.

2. **Smalltalk false positive rate v2.** Si > 5%, subí
   `SMALLTALK_THETA` (de 0.55 a 0.60-0.65) hasta bajarlo.
   Verificá que no rompió queries reales.

3. **Precision@5 por locale.** ES y EN deben ser >0.80. Si PT/FR
   están <0.60, es probable que sea porque las descripciones
   no tienen variantes léxicas suficientes — pero NO agregues
   example_queries en PT/FR (sería re-abrir 8b). En vez de eso,
   confiá en transferencia multilingue de e5: si los puramente
   dense scores son bajos pero BM25 los rescata por palabras
   cognadas, está OK. Si v2 < v1 en PT/FR, registralo en log
   como tradeoff conocido.

4. **RRF k.** Default 60 (research). Si v2 sobre-pesa BM25
   (mucho hit en variantes literales pero falla en frases
   "describe-pero-no-nombra"), bajá k a 40. Si sobre-pesa dense
   (falla en typos/variantes literales), subilo a 80.

5. **Latency p95.** Target <300ms. Si supera:
   - Profilá: ¿es ONNX inference, BM25, o el cache lookup?
   - Bajá TOP_K de 16 a 12.
   - Si igual no entra, registralo como bloqueante y avisame
     antes de promover.

Tuning es iterativo. Hasta 5 iteraciones máximo. Cada cambio:
1 commit con resultados antes/después.

Commit pattern: "sprint8c.3.N: tune <param> from X to Y (top1
+M.M%, smalltalk_fp -N.N%)"

## 8c.4 — Promover v2 a default (con rollback flag)

Cuando los resultados de 8c.3 sean:
- v2 top1 >= v1 top1 - 2 pts en ES/EN.
- v2 supera v1 en idiomas no-ancla.
- v2 supera v1 en categoría "coloquial".
- Smalltalk FP <= 3%.
- Latency p95 <= 300ms.

...promové v2 a default. En `gemma4_agent/planner.py`,
`_suggest_tools` (o equivalente):

```python
def _suggest_tools(query: str) -> list[str]:
    """Tool routing entry point. v2 by default, v1 via flag."""
    if os.getenv("GEMMA4_ROUTER_V1") == "1":
        return _suggest_tools_v1(query)
    try:
        from gemma4_agent.router_v2 import RouterV2
        result = RouterV2.get().route(query)
        if result.subset is not None:
            return result.subset
    except Exception as e:
        log.warning("router_v2 failed, falling back to v1: %s", e)
    return _suggest_tools_v1(query)


def _suggest_tools_v1(query: str) -> list[str]:
    """OLD regex+semantic router. Kept for rollback."""
    # ... contenido viejo de _suggest_tools, intacto ...
```

Verificación:
- Sin flags: v2 active → corré una query ES + una EN +
  smalltalk y confirmá comportamiento esperado en logs.
- Con `GEMMA4_ROUTER_V1=1`: v1 active → mismo test → comportamiento
  viejo.
- Si v2 levanta excepción (modelo no descargado en una máquina
  fresca): fallback a v1 silencioso, log warning.

Quitá la env flag `GEMMA4_ROUTER_V2` (ya no aplica, v2 es
default). En su lugar queda `GEMMA4_ROUTER_V1` para rollback.

Commit: "sprint8c.4: promote router_v2 to default, v1 via
GEMMA4_ROUTER_V1=1"

## 8c.5 — Self-improving loop ligero

NO entrenar modelos. Solo telemetría para detectar drift.

Modificá agent.py donde ya se trackea `router_miss` (LLM llamó
tool fuera del subset). Agregá un log JSON por turn con:

```python
{
    "ts": "2026-05-17T...",
    "query": "<user query>",
    "router_subset": [...],         # qué sugirió router_v2
    "tools_called": [...],          # qué efectivamente llamó el LLM
    "router_miss": bool,            # alguna tool llamada fuera del subset
    "miss_tools": [...],            # cuáles
    "latency_ms": <router latency>,
}
```

Persiste en `~/.gemma4/logs/routing_trace.jsonl` (append-only,
rotación weekly).

Y un script `gemma4_agent/scripts/analyze_routing_trace.py` que:
- Lee el jsonl.
- Lista top-10 queries con `router_miss=true` (candidatas para
  agregar a tool_descriptions.yaml en futuras revisiones).
- Lista pares (subset, tool_called) más frecuentes que sugieren
  ambigüedades (ej: filesystem vs office repitiendose).
- p50/p95 de latency.
- Frecuencia de cada tool en `tools_called` (señal de cuáles
  importan más).

NO toques el modelo ni el YAML automáticamente. El loop es
**revisión humana periódica**, no online learning. Cada 2-4
semanas, vos corrés el script y decidís si actualizar el YAML.

Commit: "sprint8c.5: routing trace + analyzer for periodic
review (no auto-learning)"

## 8c.6 — Cleanup y log final

1. Verificá que tests pasan: `python -m pytest gemma4_agent/ -q`.
2. Verificá que CLI funciona: `python -m gemma4_agent.launcher status`.
3. Creá `docs/architecture/sprint_prompts/_sprint8c_log.md` con:
   - Métricas finales: top1/precision@5/latency v1 vs v2 por
     locale y category.
   - Decisiones de tuning tomadas (con resultados antes/después).
   - Tradeoffs conocidos (ej: "v2 -3pts en PT vs v1 — aceptado
     por mejor cobertura en coloquial ES/EN").
   - Cómo correr el rollback (`GEMMA4_ROUTER_V1=1`).
   - Cómo correr el analyzer para revisión periódica.
4. Actualizá `docs/architecture/08_findings_post_plan.md` con
   sección "Sprint 8 (a/b/c) — Routing universal" resumida.

Commit: "sprint8c.6: log of 8c + update post-plan findings doc"

# REPORTE FINAL (al usuario)

Devolveme:
1. Tabla markdown comparando v1 vs v2 (top1, precision@5,
   latency p95) global y por locale.
2. Top-5 mejoras de v2 vs v1 (queries donde v2 ganó).
3. Top-5 regresiones (si las hay).
4. Latency final p50/p95.
5. Comando exacto para rollback si algo falla en prod.
6. Output de `pytest gemma4_agent/ -q`.

# CRITERIO DE ÉXITO

- v2 default activo.
- Métricas finales aceptables (ver 8c.3).
- Rollback `GEMMA4_ROUTER_V1=1` probado y funcional.
- Self-improving loop persistiendo jsonl correctamente.
- Tests verdes.
- `power point` rutea a `office` desde ES, EN, PT, FR (verificación
  manual obligatoria — escribir el output de las 4 queries en el log).

# NO HACER (anti-scope)

- NO borrar planner._suggest_tools_v1. Es el rollback.
- NO entrenar modelos. NO online learning automático.
- NO agregar idiomas al YAML (eso fue 8b).
- NO migrar a `bm25s` ni a `bge-m3` (los descartamos por
  costo en este sprint).
- NO agregar cross-encoder rerank (research lo descartó).
- NO modificar las 65 tools.
- NO armar dashboard web (la revisión periódica es CLI manual).
```

---

## Lo que hace este sprint

Cierra el ciclo de routing universal: blind test honesto, tuning
de thresholds basado en datos, promoción del v2 a default con
rollback de un solo env var, y telemetría ligera para detectar
drift sin re-entrenar nada.

## Lo que NO hace

- No re-entrena modelos.
- No agrega online learning.
- No agrega idiomas al YAML.
- No quita el código viejo.

## Estimación de esfuerzo

- 8c.1: 2-3h (escribir 200 queries con expected_tools).
- 8c.2: 1h (harness + script).
- 8c.3: 2-3h (5 iteraciones de tuning con measurement entre cada).
- 8c.4: 30 min (promoción + rollback flag).
- 8c.5: 1h (trace + analyzer).
- 8c.6: 30 min (log).

Total: ~7-9h de agente.

## Resultado esperado del Sprint 8 completo (a+b+c)

- 0 regex de keywords en planner.py para tool-routing.
- Multi-idioma real vía e5-small + queries ES/EN ancla.
- Latency router < 300ms p95.
- "power point" rutea OK en ES/EN/PT/FR.
- Frases coloquiales rioplatenses ("armame algo", "dale play",
  "podes bajarme el volumen") rutean OK.
- Rollback a v1 con `GEMMA4_ROUTER_V1=1` para emergencias.
- Trace jsonl para identificar tools/queries problemáticas en
  futuras iteraciones.
