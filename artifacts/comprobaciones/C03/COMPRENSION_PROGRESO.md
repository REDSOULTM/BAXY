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
| F1 conjuntos DEV-A / DEV-B / FINAL + puntuador + base | en curso | — |
| F2 diagnóstico por camino + modelo libre | pendiente | — |
| F3 torneo de modelos | pendiente | — |
| F4 mecanismos | pendiente | — |
| F5 ventana oficial con DEV-B | pendiente | — |
| F6 cierre (FINAL una vez) | pendiente | — |

## Dónde está cada cosa

- Conjuntos (privados, fuera de git): `%LOCALAPPDATA%\BAXY\comprension-2026-09-25\` (D3). SHA-256 en este fichero
  cuando estén cerrados.
- Base del conjunto de regresión: salidas de `verify_chain2.sh` en el scratchpad de la sesión anterior
  (`…\6f29a6a5-…\scratchpad\`: `lit-fin2.jsonl`, `layers-fin2.jsonl`, `uso\hold-fin2.jsonl`, `finc2\`, `cien-103`,
  `uso\fin2-NN.out`).

## Bitácora

- 2026-09-25 12:0x — F0: tag, ficheros de estado. Verificación anterior en curso (capas A/B/C).
