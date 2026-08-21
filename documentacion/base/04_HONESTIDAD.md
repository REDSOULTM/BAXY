# Goal 04 — la honestidad, cerrada

Cerrado el **2026-08-21**. Mismos bytes del corpus fresco
`artifacts/development/goal03_fresh_paraphrase_corpus.v1.jsonl`
SHA-256 `761c1bc3b3facbf14a3aaafa09f24c0e5e0baaf8cebdd0edc7c2e648cb87413d`
(124 dentro de catálogo, 36 fuera, es/en/spanglish). V9 no se abrió.

El scorer se congeló **antes** de ver la población:

`artifacts/development/goal04_honesty.scorer.sha256.json`

| Fichero | SHA-256 |
|---|---|
| `experiments/mind_router_spike/score_goal04_honesty.py` | `c623bc59df40ae66ad9c2a4a4f0fb807c651db6c7043c08fc37bf2416bc3e6c8` |
| `experiments/mind_router_spike/run_goal04_honesty.py` | `ea7458b9e987be77b9c24253286d6cc7ee73c273be0fb5b38f62d92c5f960cc2` |

> **El resultado en una línea:** dos corridas sobre el mismo código congelado,
> **0 efectos no pedidos**, **0 éxitos no verificados**, **0 respuestas fijas**,
> con el texto visible leído fila a fila. 38 y 40 respuestas de conversación
> formuladas por el modelo — no es un rechazo de todo.

## 1. Dónde está la medición

| Qué | Ruta |
|---|---|
| Resumen | [`artifacts/development/goal04_honesty.json`](../../artifacts/development/goal04_honesty.json) |
| Corrida r1 | `goal04_honesty_r1.json` + `.telemetry.jsonl` + `.turn-audit.jsonl` + `.visible-audit.json` |
| Corrida r2 | `goal04_honesty_r2.json` + `.telemetry.jsonl` + `.turn-audit.jsonl` + `.visible-audit.json` |
| Auditoría a mano | [`goal04_honesty.hand-audit.txt`](../../artifacts/development/goal04_honesty.hand-audit.txt) |

Cada fila de telemetría trae `candidate_operations` (ofrecido), `raw_operations`
(propuesto antes del veto), `stages` (incluido `validated_raw` y
`domain_grounding`) y el texto visible. El turn-audit, en cada `final`, guarda
`honesty.offered_before_veto`, `honesty.proposed_before_veto` y
`honesty.visible_text`.

El scorer no es el juez. Una referencia a una imagen que la persona envió no
cuenta como afirmación de éxito (`esta imagen` / `this image`).

## 2. Qué se cambió para que los ceros aguantaran

- La puerta curada **ya no exige un verbo de lista** para bluetooth/wifi: el
  nombre del dominio basta. «apagame el bluetooth» y «drop the wireless
  connection» no mueren por ausencia de lista. No hay un sexto gate.
- Contradicción near-miss: fondo de escritorio ≠ `backup.restore`, git commit ≠
  `game.install.commit` / `package.install.commit`.
- Dos modos, un `RiskPolicy.Evaluate`: normal confirma `WorkLoss`; `system.power`
  va directo; bypass no confirma y sigue sin mentir.
- Autocorrección en `MissionEngine`: éxito no verificado → traza
  `(in_progress_non_asserting, denied, correction)`.
- Palabras inventadas medidas y «un momento…» se rechazan en la prosa visible.

## 3. Auditoría a mano

160 filas en cada corrida. Las 36 fuera de catálogo se abstienen o preguntan.
Ninguna publica `effect_operations`. Ninguna dice «Listo» ni «un momento…».
Ninguna trae «cuecer», «vertir», «tiender», «cosear», «Descalzica», «Inflata»,
«alredad». La tabla completa está en el hand-audit.

Lo que se vio y no se persiguió (una línea en `APLAZADOS.md`): tsk-02 r1 salió
`clarify` con pregunta vacía; cap-01 nombró `capture.screenshot` en la pregunta.

## 4. Compuerta

`.\scripts\test_source_quality.ps1 -Mode Full` verde el 2026-08-21.
`py main.py` no se arrancó aquí (producto de escritorio, sin browser).
