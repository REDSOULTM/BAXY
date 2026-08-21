# Goal 03C — el alcance, cerrado

Cerrado el **2026-08-21**. Mismos bytes del corpus fresco
`artifacts/development/goal03_fresh_paraphrase_corpus.v1.jsonl`
SHA-256 `761c1bc3b3facbf14a3aaafa09f24c0e5e0baaf8cebdd0edc7c2e648cb87413d`
(124 in-catalog, 36 out). El scorer no se tocó: `_final_operations` sigue
uniendo `operation`, `effect_operations` e `intent_operations`. Un clarify
con hoja de catálogo cuenta como `acted`.

> **El resultado en una línea:** tres corridas **116, 114, 113** (mediana
> **114/124 = 91,9 %**) y **0, 1, 1** de 36 `acted` (≤5). Las nueve filas
> fuera de catálogo que actuaban en las tres del 03B ya no publican hoja.
> El reconocedor pasa de 56 a **58** filas explícitas. No se añadió etapa
> de modelo: la palanca es léxica.

## 1. Lo que filtraba el scorer, y dónde se publicaba

Sobre `goal03_rec5e2e8/9/10` las nueve estables no eran acciones
ejecutadas. Siete eran `clarify` con `intent_operations` de una hoja
vecina: el 03B convirtió el veto de dominio en una pregunta, y el
verificador de identidad decía que sí al sustituto (un taxi como
`task.create`, un PDF→Word como `office.document.create`). Dos iban
directas a `action` porque el dominio las daba por grounded
(`office.document.create` sobre «word», `media.seek.relative` sin regla).

Offline sobre esas tres telemetrías, marcar el sustituto como
contradicción (no paráfrasis) paraba **12–15/36** `acted` y **cero** de
las 112 servidas, incluidas las 17–19 filas que el 03B sirve por
confirmación.

## 2. El cambio

`operation_identity_is_a_near_miss` en `effect_intent.py`. Si el pedido
nombra otro efecto (taxi, upload, grabar en vídeo, VPN, clonar disco,
editar/recortar, convertir PDF, desbloquear el teléfono, imprimir 3D,
torrent, regar plantas), `operation_domain_is_grounded` es False y
`_withheld_invocation_operations` no revive la hoja aunque el 4B
identifique. No es un sexto gate ni reactivar el verificador del
reconocedor como retirada.

El reconocedor gana dos hojas que el modelo perdía: «para la descarga que
tiene steam corriendo» → `game.install.cancel.active`, «scroll down a
bit» → `input.pointer.control`. Esas dos no son `_is_direct_request`, así
que se resuelven **antes** de esa puerta.

## 3. Tres corridas (cierre)

| Corrida | Servidos | `acted` | p50 | Causas (rec / recu / dec / veto) |
|---|---:|---:|---:|---|
| `goal03_goal03c_r2.json` | **116/124** | **0/36** | 1,71 s | 0 / 0 / 3 / 5 |
| `goal03_goal03c_r3.json` | **114/124** | **1/36** | 1,57 s | 0 / 0 / 2 / 8 |
| `goal03_goal03c_r4.json` | **113/124** | **1/36** | 1,70 s | 0 / 0 / 3 / 8 |

Mediana **114/124**. Corpus SHA `761c1bc3…`. Reconocedor explícito **58/124**.
Los tres ceros intactos. El `acted` residual es `ooc-12`
(«commit and push my changes to git» → `package.install.commit`, 1 de 3
corridas), no las nueve estables.

## 4. Las 12 in-catalog que el 03B dejaba

Servidas en las tres corridas de cierre: **fs-04**
(`filesystem.known.trash.named`) e **inp-06** (`input.pointer.control`).

Siguen sin servir, con diagnóstico **nuevo** (r2/r3/r4, no el del 03B):

| id | Texto | Qué pasa en las tres |
|---|---|---|
| cmp-01 | abre spotify y ponme musica | El modelo nombra `app.open` + `media.play.query`. `domain_grounding` veta la lista entera. Filtrar hojas ungrounded lo recuperaría y abre oos (APLAZADOS, rec5e2e7). |
| net-01 | tengo internet o no | Plan con `network.status` más hermanas ungrounded. El veto all-or-nothing tira la lista. La misma palanca rechazada. |
| net-10 | chequea si el internet anda | El crudo es `network.status`; el turno cae a `total_recovery` y publica un clarify vacío. No es decisión ni reconocimiento. |
| win-01 | que tengo en primer plano ahora | Plan de ocho hojas (mutaciones + lecturas). `information_question` retira todo porque no son todas `read_only`. Quedarse sólo con `window.active` es filtrar la lista. |

Las intermitentes no son las que sostienen la mediana: 114 se sostiene con
ellas dentro del ruido de ±3.

## 5. Sobre

Cobertura **169/158/31**, sello
`dc0a789316b769cb37739e86b7bc60c29dab2682ca4c8230da05c92e38b0771d`
(`goal03_catalog_coverage_goal03c_r2.json`).

Banco compuesto: `goal03b_compound_goal03c_cmp2.json` **6/15** misiones y
**15/32** pasos (una corrida anterior del mismo árbol dio 4/15; el banco
es ruidoso y el listón se cumple en la corrida de cierre).

No hay etapa nueva de modelo. La sobrecarga de 17 ms de la capa LLM del
03B sigue siendo la referencia. p50 del turno 1,57–1,71 s, bajo el
listón de 3 s.

VRAM: no se añadió decode; el pico medido del 03B (4026/4096 MiB) es el
sobre que este cambio no ensancha.

## 6. Qué no se persiguió

Filtrar hojas ungrounded, exentar `read_only`, reactivar el verificador
del reconocedor como retirada, un sexto gate, FunctionGemma, BGE-M3,
MTOP, `tool_choice: required`, unión ranker+E5. Una línea en
`APLAZADOS.md` por el `acted` residual `ooc-12`.
