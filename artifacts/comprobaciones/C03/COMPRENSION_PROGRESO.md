# Fase 3.5b «comprensión natural» — progreso (fuente de verdad ante un corte)

Goal: [`PROMPT_OPUS_COMPRENSION_NATURAL_2026-09-25.md`](PROMPT_OPUS_COMPRENSION_NATURAL_2026-09-25.md). Decisiones sin
el dueño: [`DECISIONES_COMPRENSION_2026-09-25.md`](DECISIONES_COMPRENSION_2026-09-25.md). Rama `codex/kiro-goal-c03`.

## Punto de partida

- Tag local `opus-cn-inicio` = `4f510ee7` (informe de la verificación encima de `b34c3f39`; `src` idéntico a
  `b34c3f39`).
- Al empezar seguía corriendo la segunda verificación completa de la sesión anterior (`verify_chain2.sh` sobre
  `b34c3f39`: 742, capas, reserva MASSIVE, guion y held-out, cien-103, tandas 1–10 en la ventana). Mide el mismo `src`
  que el punto de partida: es la base del conjunto de regresión (D2).

## Estado por fase

| Fase | Estado | Cifra |
|---|---|---|
| F0 etiqueta y ficheros | hecho | — |
| F1 conjuntos DEV-A / DEV-B / FINAL + puntuador + base | **hecho** | DEV-A 59,6 %, DEV-B 69,2 % |
| F2 diagnóstico por camino + modelo libre | **hecho** | Qwen3.5-4B libre: DEV-A 70,0 %, DEV-B 77,5 %, seguimientos B 84,8 % (`DIAGNOSTICO_F2_2026-09-25.md`) |
| F3 torneo de modelos | **hecho**: gana Qwen3.5-4B | 393/513 (76,6 %), seguimientos 112/134; ninguno lo desplaza (`DIAGNOSTICO_F2_2026-09-25.md` §F3) |
| F4 mecanismos | en curso | — |
| F5 ventana oficial con DEV-B | pendiente | — |
| F6 cierre (FINAL una vez) | pendiente | — |

## Dónde está cada cosa

- Conjuntos (privados, fuera de git): `%LOCALAPPDATA%\BAXY\comprension-2026-09-25\sets\` (D3). Scripts que los
  construyen y encargos de los subagentes: `comprension-f1/` (junto a este fichero).

## Conjuntos de F1 (cerrados 2026-09-25 12:40)

| conjunto | turnos | sueltos | en conversación (conv.) | seguimientos que dependen | SHA-256 |
|---|---|---|---|---|---|
| DEV-A (se miran sus fallos) | 260 | 125 | 135 (35) | 68 | `cffb39cd90ba378c92902401f48da8330712a0d0233f0d89985d0c7ad7044e75` |
| DEV-B (sólo su cifra) | 253 | 125 | 128 (35) | 66 | `5f7eda2a1602c4b7e6cb9c0b5a17c0dad8c37bbf7e04d66f6c93b469b26462c9` |
| FINAL (sellado, sólo lectura) | 202 | 100 | 102 (27) | 57 | `e05cf27e8af6dca7d38f77689d866d0a94ddf19bd8bf203d5b9e2bc71323d993` |

- Sueltos por fuente en cada conjunto (por 125): MASSIVE val es 18 / en 10, MTOP test+eval es 14 / en 8, CLINC150 12,
  OVOS-ILENIA 12, CSTOP (spanglish) 20, PRESTO test es 14 / en 7 (code-mixing, disfluencias, auto-correcciones),
  oasst2 es 10. Ninguna frase ya vista (D4: 79 464 textos + 13 371 hashes).
- Conversaciones: públicas (PRESTO humano con contexto, SGD test, oasst2 es) + 54 escritas en sala limpia por tres
  subagentes (chileno, rioplatense, mexicano, colombiano, España, inglés EE. UU., spanglish; dictado, erratas,
  muletillas, cortés, seco, largo), repartidas por hablante entre los tres conjuntos (D6).
- Oro: escritores (sus conversaciones) y tres etiquetadores con ids opacos mezclando los tres conjuntos, según
  `comprension-f1/brief/REGLAS_ORO.md`. Auditoría a ciegas del 10 % (71 turnos): **acuerdo 70/71** (DEV-A 25/26,
  DEV-B 25/25, FINAL 20/20); el desacuerdo de DEV-A se resolvió a `limit`/`ask`.
- Base del conjunto de regresión: salidas de `verify_chain2.sh` en el scratchpad de la sesión anterior
  (`…\6f29a6a5-…\scratchpad\`: `lit-fin2.jsonl`, `layers-fin2.jsonl`, `uso\hold-fin2.jsonl`, `finc2\`, `cien-103`,
  `uso\fin2-NN.out`).

## Base de F1 en DEV (HEAD de partida, sólo decisión, `scripts/comprension_eval.py`, 14:28–14:48)

| | total | sueltos | en conversación | seguimientos que dependen | decisión p50 / p90 |
|---|---|---|---|---|---|
| DEV-A (260) | **59,6 %** (155) | 62,4 % | 57,0 % | 51,5 % (35/68) | 1,97 / 4,09 s |
| DEV-B (253) | **69,2 %** (175) | 77,6 % | 60,9 % | 53,0 % (35/66) | 1,98 / 4,03 s |

## Base del conjunto de regresión (HEAD de partida, `src` = b34c3f39)

| medida | base | cómo |
|---|---|---|
| capa A (768) | **96,5 %** (741) · registro real 90,1 % · 742 97,3 % | `semantic_corpus.py score` sobre `lit-fin2` + `layers-fin2`, referencia S8 |
| capa B (20) / capa C (1 000) | 45,0 % / 54,2 % | ídem |
| 742 sólo-decisión contra S8 | **14** decisiones distintas | `semantic_replay.py diff lit-s8 lit-fin2` |
| reserva MASSIVE (2 757) | **82,2 %** (2 265; decisión p50 0,93 s) | `score_big.py big-hold hold-fin2` |
| guion del dueño (60) / held-out (30) | **46/60** (+6 por revisar) / **24/30** — ambos bajo el «sin retroceder» del goal (53, 29): hay que recuperarlos | `semantic_replay.py summary --out finc2` |
| cien-103 | **95/100** (94 iguales + 1 mejor; mal: 008, 027, 096 pedido sin referente → límite falso, 037 «no lances Steam», 084 memoria tras session.new) | conductor; adjudicación contra cien-101 |

## Bitácora

- 2026-09-25 12:0x — F0: tag, ficheros de estado. Verificación anterior en curso (capas A/B/C).
- 12:40 — conjuntos DEV-A/DEV-B/FINAL cerrados y auditados; FINAL sellado. Esperando GPU (verificación anterior) para
  la base DEV y F2.
