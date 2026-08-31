# Goal 09.5.5 — Síntesis: modelos, router e idiomas

Cerrado 2026-08-31. Fuente de verdad machine-readable:
[`artifacts/goal095/synthesis/09.5.5_modelos_router_idiomas.v1.json`](../../artifacts/goal095/synthesis/09.5.5_modelos_router_idiomas.v1.json).
Inventario desde tarjetas 09.5.2–09.5.4 y `_09510_requirements.json`, no desde
cuerpos de `biblioteca/` ni árboles fuente.

Siguiente prompt humano: [`../sprints/09.5.6_VOZ_AUDIO_PRESENCIA.md`](../sprints/09.5.6_VOZ_AUDIO_PRESENCIA.md).

## Constraint vinculante

El catálogo sigue siendo **datos tipados** autorizados por el kernel, **nunca
nombres cocidos en pesos**. ES, EN y spanglish tienen cobertura. Otros idiomas
(pt/fr/de/it del probe FunctionGemma, etc.) son procedencia o contaminación y
**no crean trabajo**.

## Decisión actual

Todas las piezas de la pila de habla/decisión quedan `conservar`. Cero
`reemplazar_candidato`. Cero `medir` que autorice un torneo ahora: no hay
evidencia nueva comparable que gane al vigente sobre el corpus fresco
`goal03_fresh_paraphrase_corpus.v1.jsonl` SHA `761c1bc3…` (124 dentro + 36 fuera,
es/en/spanglish).

| Pieza | Elegido | Decisión | Umbral que un recambio debe ganar |
|---|---|---|---|
| LLM decisor | Qwen3-4B-Q4_K_M `7485fe6f…` | `conservar` | ≥82/124 cruda, ≥33/36 OOD, p90 idle ≤3.02 s; no subir acierto bajando abstención; VRAM ≤4 GiB |
| Cuantización | Q4_K_M del mismo Qwen | `conservar` | GGUF más ligero **del mismo modelo** + A/B prosa ES. Q2 Gemma no se hereda |
| Runtime | llama.cpp b9980 | `conservar` | Mismo GGUF a ambos lados. No `--reasoning-budget 0` |
| Encoder | e5-small `passage:`/`query:` | `conservar` | ≥103/124 expected-in-shortlist; rankea operaciones, no familias |
| Abstención | puerta léxica de dominio | `conservar` | conservación y OOD juntos; no sexta capa KVA |
| Catálogo | 169 ops tipadas | `conservar` | no `tool_schemas.py` ni FT de nombres |
| Verificador de hoja | mismo Qwen, 24 tokens, p50 0.15 s | `conservar` | ≥46/48 correctas, ≥21/84 rechazos; FG selector prohibido mientras cueza nombres |

## Candidatos (todos los hallados en las tarjetas)

Comparabilidad = mismo corpus fresco y este hardware. Una cifra de otro
instrumento o de 16 GB VRAM **no es un win**.

| Id | A favor | En contra | ¿Comparable? |
|---|---|---|---|
| **qwen3-4b-q4_k_m** (vigente) | Goal 03: 82/124 vs Gemma E2B 63; e2e 56 vs 49; p90 3.02 vs 3.59 s. MVP: venció 3.5-4B, Phi-4-mini, Instruct-2507 aquí | 46% e2e; bajo carga p50 3.7–4.0 s; es 30/73, en 15/35 | sí |
| gemma4-e2b-qat | ADR 76.5/92.9/87, VRAM 1540 MiB | Goal 03 pierde; thinking EN 200–400 tok; `--reasoning-budget 0` publica el borrador | sí (Goal 03) / ADR 21-tool no |
| gemma4-e4b / 26B / 31B | Harness Carter | Ley 4; GGUF de `Probando Gemma 4/models` ausente (`pg4-gguf-models`, hashes **not invented**) | no |
| **functiongemma-270m-ft** | Holdout 88.3%, 0.15 s, 278 MB | **No conversa** (0/3 conocimiento, 0/4 smalltalk). **Catálogo cocido en pesos**. **Abstención rota en el primer split 0/3**. Live inventa `set_volume`/`no_query_query` | no (holdout ≠ 160 fresco) |
| qwen3.5-4b | ADR tools 84.8% | EN→ES 6/30; MVP 11 errores GPU / más VRAM | no vs Goal 03 |
| qwen3.5-0.8b / lfm2.5-1.2b | pequeños | Abstención hard-gate ADR | no |
| qwen3-4b-instruct-2507 | más rápido | ABBA 178/180, `arguments-06` GPU x2 | no (MVP 180 ≠ 160) |
| qwen3-8b / qwen2.5-7b / hermes3-8b | lab Carter | thinking 31 s; perfiles 6–24 GB; switch a medias; ley 4 | no |
| phi-4-mini | VRAM holgada | ADR: no emite tools `--jinja`; MVP 3+4 fallos | no |
| **e5-small** (vigente) | 674/675; 103/124 ops | 37 LOO peligrosos; score no abstiene | sí |
| embeddinggemma-300m | 21 peligrosos LOO | más pesado; sin dato 169 ops | no (ADR only) |
| MiniLM / Tool2Vec | 0.9521 @31; 2.1 ms | granularidad familia; ADR MiniLM hard-gate | no |
| Qwen3-Embedding-0.6B | LOO 88.3% | hard-gate cobertura | no |
| bge-m3 / cross-encoder | experimentos R186–R244 | R209 16/77 rechazado; capa extra | no |
| llama.cpp b9980 (vigente) | Goal 03 p50 2.18 s | reasoning-budget 0 rompe prosa | sí |
| Ollama | Carter | tres backends; cloud; sesgo tools= | no |
| Agent/Function Schema | tests «no inventar» | `tool_schemas.py` en el prompt = reject | n/a (invariante 1) |
| Q2 Gemma | −0.43 GB | degenera; más lento; no es Qwen | no |
| Q4_K_XL QAT Gemma | prosa OK en E2B | atada al modelo que Goal 03 perdió | sí entre Q2/Q4 Gemma |
| Q8_0 FG | 278 MB | quant del modelo rechazado | no |
| KVA head | respuesta al 0/3 | sexta capa; MiniLM; probe pt/fr/de/it fuera de alcance | no |
| puerta léxica (vigente) | 33/36 OOD vs 16/36 sin ella | techo de vocabulario, no semántica | sí |
| Qwen-VL / Qwen-ASR | hallados en tarjetas | recinto 09.5.7/08 y **09.5.6**; no se silencia | n/a |

## Qué se reabre antes del Goal 10

- **LLM / encoder / quant / catálogo:** nada. Conservar.
- **Blobs Gemma 4 omitidos:** sólo si 09.5.9 nombra el GGUF exacto → 09.5.10
  `FALLO_DE_AMBIENTE` (`_09510_requirements.json`). No inventar hashes.
- **Voz / STT / TTS / wake:** 09.5.6. Qwen-ASR y audio nativo Gemma van allí.
- **Tools / schemas transplantables:** 09.5.7. Aquí sólo el veto al catálogo en
  pesos/prompt.
- Si 09.5.9 reabre un LLM, el instrumento es el benchmark ciego
  `goal03_fresh_es_en_spanglish_v1` (cuatro columnas + `catalog_swap_probe` +
  techo 4 GiB). Presupuesto: una corrida, cero ajuste de umbral al abrir.

Pesos vivos, encoder y manifiestos de producto: **no se tocaron**.
