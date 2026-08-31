# Handoff — 09.5.5 modelos/router/idiomas — 2026-08-31

## Objetivo
Comparar evidencia heredada de modelos de habla/decisión, cuantizaciones, routers, schemas y corpora ES/EN/spanglish, y nombrar qué reabrir antes del Goal 10.

## Estado
Hecho: síntesis 09.5.5 cerrada. Campañas 09.5.2–09.5.4 siguen pending=0 claimed=0.
En curso: nada de 09.5.5.
Sin empezar: `09.5.6_VOZ_AUDIO_PRESENCIA.md`.

## Decisiones tomadas
- Conservar Qwen3-4B-Q4_K_M, Q4_K_M, llama.cpp b9980, e5-small, puerta léxica, catálogo tipado 169, verificador de hoja Qwen. Cero `reemplazar_candidato`. Cero torneo nuevo.
- FunctionGemma: no conversa (0/3, 0/4); catálogo cocido en pesos; primer split abstención 0/3. No es hablante ni selector mientras cueza nombres.
- Gemma-4-E2B ya perdió Goal 03 (63 vs 82 cruda). E4B/26B/31B: no comparable; GGUF `pg4-gguf-models` ausente, hashes not invented.
- MiniLM/Tool2Vec 0.9521 es granularidad 31, no 169 ops.
- pt/fr/de/it no crean trabajo. Qwen-VL → 09.5.7/08; Qwen-ASR → 09.5.6.
- Pesos vivos / encoder / manifiestos: no se tocaron.

## Archivos tocados
- `artifacts/goal095/synthesis/09.5.5_modelos_router_idiomas.v1.json`
- `artifacts/goal095/ledger/synthesis-09.5.5.json`
- `documentacion/herencia/09_5_5_SINTESIS_MODELOS.md`
- `documentacion/herencia/09_5_COBERTURA.md`
- `scripts/goal095_0955_synthesis.py` + `tests/test_goal095_0955_synthesis.py`
- `artifacts/goal095/campaigns/evidence_assets.json` y `ledger/evidence_assets-132-*.json` `next_prompt` → 09.5.6

## Archivos relevantes aun sin tocar
- `documentacion/sprints/09.5.6_VOZ_AUDIO_PRESENCIA.md` — siguiente prompt humano

## Hipotesis
Confirmadas: recinto 25/25, 477/477, 132/132 pending=0. Qwen vigente sin evidencia nueva comparable en contra. FunctionGemma fallos en tarjetas, no folklore.
Descartadas: «E4B/26B/hermes3/FG 88.3% autorizan swap» — no comparable o ley 4 o catálogo cocido. «Falta relanzar 09.5.5».

## Comandos ejecutados y resultado
- `py -3.12 scripts/_goal095_validate_evidence_campaign.py` → pending=0 claimed=0 complete=132 relaunch_09_5_4=0 next_human=09.5.6
- `py -3.12 scripts/_goal095_validate_docs_campaign.py` → 25/25 pending=0
- `py -3.12 scripts/_goal095_validate_code_campaign.py` → 477/477 pending=0
- `py -3.12 -m pytest tests/test_goal095_0955_synthesis.py tests/test_goal095_evidence_ledger.py tests/test_goal095_docs_ledger.py tests/test_goal095_code_ledger.py -q` → 32 passed, 0 skip

## Problemas pendientes
Ninguno de 09.5.5. Siguiente humano: 09.5.6.

## Siguiente accion recomendada
Pegar `documentacion/sprints/09.5.6_VOZ_AUDIO_PRESENCIA.md` (sesión nueva, /goal). No relanzar 09.5.5.
