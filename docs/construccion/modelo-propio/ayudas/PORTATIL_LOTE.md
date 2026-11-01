# Candidato a lote `d7a76adf1` en el notebook (2026-10-19/20)

El lote es `hub/pc-ayudas-6` `d7a76adf1`, recompilado con c2-e1.0. Con `BAXY_AYUDAS` sin definir enciende cinco
ayudas: `calculator_next`, `accessible_scope`, `work_folder` (3b), `place_unverified` (1c) y `person_folder_sentence`
(8).

- **Vivo:** W1, F1, F2 y E001 salen 3/3 cada uno en s0-2. El primer sonido de E001 llega entre 3,1 y 3,5 s. No hubo
  `setup_failed` ni app.open detrás de otra ventana.
- **Recursos (`measure_resources.py`):**
  - VRAM 3.902 MiB, con un pico de GPU de 3.978 MiB.
  - RAM del producto 1.790 MiB: mente 298, app 25, core 13, worker-uia 88 y llama-server 1.366 (USS).
  - Ambas quedan por debajo de 4 GB.
- **Suites:** Kernel 574/574, Contracts 69/69, Setup 477/477, Providers 2332/2332 y pytest 44/44.
- **Falsedades:** s1 y s2 de A (`none`) y de B (el lote), con `--no-judge`. Las transcripciones están en el PC, que
  las juzga. La s0 es `nb-comb1-*`.

## e2e: seis semillas en el notebook

- **De dónde salen:** s0-2 son de la combinación en `2a5a0aad5` con la lista explícita; s3-5 son de `d7a76adf1` con la
  variable sin definir.
- **Corridas:** A = `none` y B = el lote, intercalados.
- **Limpieza:** 0 `error` y 0 `setup_failed`. El frente se comprobó en cada corrida.

| | s0 | s1 | s2 | s3 | s4 | s5 | Media |
|---|---|---|---|---|---|---|---|
| A `none` | 26 | 25 | 24 | 25 | 25 | 25 | 25,00 |
| B lote | 27 | 26 | 27 | 28 | 27 | 28 | 27,17 |

- **Resultado conjunto:** Δ +2,17 ítems (IC95 bootstrap [0,00, +4,83]). Ninguna semilla de B baja de la
  de A.
- **Por caso** (veces OK de 6, B frente a A):

| Caso | B | A | Nota |
|---|---|---|---|
| E011 | 6 | 6 | |
| E017 | 6 | 3 | |
| E027 | 6 | 2 | |
| E015 | 6 | 0 | El oráculo ahora busca las marcas de la biblioteca y la 1c hace mirar antes de responder |
| E024 | 3 | 4 | Ruido: corrida limpia con `--only` y 6 semillas, A 4/6 y B 3/6 |
| E006 | 0 | 0 | Sin resolver |
| E020 | 0 | 0 | Sin resolver |

## Fase 4 preparada (sin abrir el holdout)

Los guiones están en `scripts/renew/notebook/ayudas/fase4/`.

- `hacer_fase4_ay.py`:
  - Lee el formato de SEALED_AYUDAS.md.
  - Excluye los casos con `e2e.segura=false` y las operaciones y apps peligrosas.
  - Pasa al juez `reply_re`, `reply_not_re`, `lang` y `modo`.
  - Después de cada caso devuelve `presentation-mode` a `normal`.
- `juzgar_fase4_ay.py`: si un caso da OK pero su respuesta no cumple `reply_re` / `reply_not_re`, pasa a
  RESPUESTA_MAL.
- `correr_fase4_ay.sh`: con `BAXY_AYUDAS` sin definir corre el lote.
