# Evaluación y métricas

> Cómo se mide el router, qué corpus existen, qué significan las métricas y
> cuáles son los gates de éxito. Mandamiento del proyecto: **nunca declarar una
> mejora sin un número contra un gate definido de antemano.**

---

## Los dos corpus (y por qué dos)

### 1. Corpus CURADO — `router_eval_corpus.curated.jsonl` (1733 filas)
Labels hand-authored por Opus (NO oráculo automático — uno corrompió labels una
vez). Es el ground-truth de desarrollo. **Pero está saturado/sesgado**: recall
0.9964 no refleja la dificultad real.

- Cada fila: `{"q", "expected": ["tool"...] | [], "source", "label_origin"}`
- `expected` no-vacío → **RECALL**: al menos una tool aceptable en el subset.
- `expected == []` → **NO-TOOL**: el router NO debe ofrecer tool de dominio.

### 2. Corpus de LOGS REALES — `router_corpus_real_logs.jsonl` (1071 pares)
**La verdad de campo.** Extraído de `traces.jsonl`: el mensaje real del usuario
+ la tool que el agente REALMENTE ejecutó. En la forma de hablar del usuario
(typos, "porfavor", deícticos). Mucho más duro: recall honesto **89.1%**.

- Multi-label `expected_equiv`: tools del mismo dominio funcional cuentan como
  válidas (ej: "reanuda el video" puede ser media O audio). Separa miss-REAL de
  label-ruidoso. Se activa con `--equiv`.
- Campo `prev`: la query del turno anterior (para resolver deícticos con `--inherit`).

⚠️ **Los labels de los logs reales son RUIDOSOS** (la tool ejecutada esa vez no
siempre fue la correcta). NO auto-curarlos con un clasificador — ya corrompió
labels antes. Ver [05_HISTORIAL_SPRINTS](05_HISTORIAL_SPRINTS.md) (S3c gotcha).

---

## Anti-overfit: el split holdout

Cada fila se asigna a **dev (80%)** o **holdout (20%)** por un hash estable de
su texto (`SHA256("router-eval-2026-05-20" + q) % 5 == 0`). Independiente del
orden, fijo entre corridas, no derivable del planner.

**Regla:** se desarrolla/afina contra dev SOLO. El holdout se reporta como el
número honesto nunca-visto. El mismo salt lo usan los entrenadores
(`train_abstain_head.py`) para que el head nunca vea el holdout.

---

## Las métricas

| Métrica | Qué mide | Gate de éxito |
|---------|----------|---------------|
| **TOOL RECALL** | % de turnos-con-tool donde el subset incluye una tool aceptable | ≥ 0.97 |
| **NO-TOOL keep** | % de turnos-sin-tool donde el subset NO trae tool de dominio | ≥ 0.95 |
| **PRECISIÓN — ruido** | tools-extra/turno (dominio ofrecido de más sobre el expected) | → ~0 (el norte) |
| **turnos muy ruidosos** | cuántos turnos ofrecen ≥3 tools-extra | minimizar |
| **paridad por idioma** | recall por idioma, ningún subgrupo degradado | ≤ 0.05 de spread |

La **precisión (ruido)** es el norte del usuario y se agregó al harness en S0
(antes era invisible). Un router perfecto = ruido ~0.

---

## Cómo correr el eval

```bash
# Corpus curado, con holdout anti-overfit (lo principal):
python scripts/router_eval.py

# Logs reales (la verdad de campo) con dominio-equiv + inherit:
python scripts/router_eval.py --corpus gemma4_agent/data/router_corpus_real_logs.jsonl --equiv --inherit

# Ver las fallas concretas:
python scripts/router_eval.py --show-fails

# Slices anti-overfit (por idioma, short, continuation):
python scripts/router_eval.py --slices

# Tabla de recall por tool:
python scripts/router_eval.py --by-tool

# Canarios (regresión dura — tools que nunca deben perderse):
python scripts/router_canary_eval.py
```

### Flags útiles
| Flag | Efecto |
|------|--------|
| `--corpus <path>` | Evaluar otro corpus |
| `--equiv` | Contar hit si se ofreció una tool del MISMO dominio (solo logs reales) |
| `--inherit` | Simular el inherit de continuaciones cortas de `agent.py` (recall REAL de prod) |
| `--use-prev` | Pasar el turno previo (resuelve deícticos) |
| `--split {dev,holdout,all,both}` | Qué split medir |
| `--slices` | Recall + NO-TOOL keep por slice |

---

## Snapshot (medido 2026-05-30 — PRE-regeneración de artefactos)

> ⚠️ Este snapshot se midió ANTES de:
> - la regeneración del encoder FT + cabezas del 2026-06-02 (resolvió el
>   exemplar-staleness; el holdout ES **0.9964 sigue vigente**, confirmado en el
>   [BACKLOG_MAESTRO](../_backlog/BACKLOG_MAESTRO.md));
> - la eliminación de `smart_home` y el fix de desalineación del `tool_head`
>   (62→61 tools);
> - el SPRINT5 anti-primacy (`b812841`).
>
> Las cifras de RUIDO y de logs reales pueden haberse movido levemente. Para el
> número exacto de HOY, corré `python scripts/router_eval.py`. El gate de
> no-regresión (recall 0.9964 / NO-TOOL 1.0000) es lo que se mantiene.

```
CURADO (1733):
  holdout TOOL RECALL 0.9964   NO-TOOL keep 1.0000   RUIDO 1.51   muy-ruidosos 54
  dev     TOOL RECALL 0.9939   NO-TOOL keep 0.9974   RUIDO 1.44   muy-ruidosos 168

LOGS REALES (1071, --equiv --inherit):
  holdout TOOL RECALL 0.8604   RUIDO 1.35
  dev     TOOL RECALL 0.8999   RUIDO 1.42

POR IDIOMA (holdout curado): es 0.996, en/fr/it/pt 1.000  (sin slice degradado)
```

---

## Verificación EN VIVO (regla #3.5 de CLAUDE.md)

Los tests unitarios mockeados NO bastan: el 4B es no-determinista. Un cambio que
toca el ruteo debe correrse contra el LLM REAL.

```bash
# Necesita el server en :8080. Verifica los fixes S3 (info-intent, abstain, collapse):
python scripts/_live_verify_router_s3.py
```

Lo FÍSICO irreversible (que "abre el navegador" abra el navegador de verdad)
queda para el usuario; el router se verifica a nivel de subset + elección del 4B.

---

## Tests automatizados de regresión

| Test | Qué congela |
|------|-------------|
| `tests/test_router.py` | Outcome del subset en ~63 queries (must_include/must_exclude) + 2 regresiones S3 |
| `tests/test_intent_router.py` | Los centroides multilingües + "hablame de X" (S3b) |
| `tests/test_router_coverage_invariant.py` | **Robustez:** toda tool de dominio tiene cobertura; agregar MCPs no regresa nativa (S5) |
| `tests/test_mcp_enrollment.py` | El cap se respeta con MCPs; no se cuelan en queries irrelevantes |

```bash
python -m pytest gemma4_agent/tests/ -k "router or intent or planner or mcp or coverage" --ignore=gemma4_agent/ui -q
```
