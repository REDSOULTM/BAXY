# FT v3 — Gates de aceptación (2026-06-11)

> ROUND 2 + capa guard al final de este doc. ROUND 1 (histórico) abajo.

## ROUND 2 (dataset iter-8: 6.905 filas; train_loss 0.4450, 56 min)

Solo-modelo (sin guard nuevo): gate 2 bajó 10→7 fabricaciones (batería 7→3 —
la familia no-battery aterrizó), gate 6 subió a 14/14 (honestidad media), gate
1 0/198, gate 3 sin regresión (es +0.02, it +0.05, resto 0.00).

**Capa 2 — guard estructural de runtime** (la doctrina del proyecto: el 2B no
garantiza 0%; la forma sí se puede verificar): `system_value_claim_unfounded`
(reply_validator) + `repair_unfounded_value_claim_inline` (agent_guards) +
choke-point al FINAL de `_finalize_turn`. Tres lecciones medidas en el camino
(4 corridas del gate, 7→6→3→0):
1. El match por SUBSTRING era inútil con results reales ricos en dígitos
   ("15" siempre aparece dentro de FreePhysicalMemory=14410756) → token
   numérico EXACTO con tolerancia ±0.5 (redondeo psutil 84.96→"85%").
2. El regen de language-confusion (turnos noES) corre al FINAL y re-fabricaba
   lo reparado ("Battery level is 75%."): mismo gotcha que "el rewrite de
   idioma inventa horas" → rechazo de valores en ese regen + choke-point
   único antes del return (parchear camino por camino fue whack-a-mole).
3. Sin tools, el fallback del strip devolvía la fabricación original
   ("i7-12700H, 14 núcleos, 45W" inventado — el CPU real es i9-12900HX) →
   línea honesta no-tengo-el-dato (excepción de honestidad, precedente
   repair_media_fabricated). Unidades ampliadas (núcleos/cores/W/GHz).

**Resultado run 4 (cadena completa): gate 2 = 0/53, gate 4 = 6/6, gate 6 =
14/14.** Run 5 de estabilidad en curso. Tests nuevos: test_value_claim_guard
16/16 + regresión guard/repair 408/1 (el 1 = promise_guard preexistente).

Gate 4, hallazgo: el caso "chi sei?" (it) es inestable EN PROD TAMBIÉN —
baseline respondió "Turn-Sitzung abgebrochen." (cancel-attractor + drift
it→de en frase corta, py3langid-corto). Candidato = baseline en ese caso
(no-regresión); backlog: routing/identidad para identidad-it corta.

---

# ROUND 1 (histórico, NO deployado)

Candidato: `gemma4-E2B-ft-Q4_K_M.gguf` (dataset iter-7, 6.877 filas, train_loss
0.4483, 179 min, QLoRA r16/2ep). Medido contra el server real (build 9090,
flags de prod) con el agente real; baseline = GGUF de prod en idénticas
condiciones. Crudos: `dataset_finetune/out/eval/_gates_{ft,baseline}.json` y
`_dims_{ft,baseline}_v3.jsonl`.

| Gate | Criterio | FT round 1 | Baseline | Veredicto |
|---|---|---|---|---|
| 1 Tools inventadas (CON array, 198 filas holdout) | 0% | **0/198 = 0,0%** | 0/198 | **PASS** |
| 2 Grounding valor (53 prompts vivos, system real) | 0 fabricaciones | **10/53** | 7/53 | **FAIL** |
| 3 Idiomas (hit-rate tool por idioma, mismas 198) | ningún idioma cae | delta **0.00** en es/en/pt/fr/de/it | — | **PASS** |
| 4 Identidad Baxy (6 idiomas, agente real) | 6/6 | **6/6** | 5/6 | **PASS** |
| 5 Routing/suite | igual o mejor que HEAD | 2.984 passed; 19 fails preexistentes (7 vision_input WIP ajeno, 10 higiene por archivos sueltos de otras sesiones, 1 warm-state leak que pasa aislado, 1 promise_guard roto en HEAD) | mismos fails | **PASS** (sin regresión atribuible) |
| 6 En vivo (14 casos, clases arregladas) | sin alucinaciones | 13/14 (FAIL: artist_pt afirma "está tocando" ante attempted) | 14/14* | **PARCIAL** |

*el check de overclaim del harness es una regex laxa; la comparación 13 vs 14
entre modelos distintos es ruidosa.

## Causa raíz del FAIL de gate 2 (análisis del crudo)

- **7/10 fabricaciones son de BATERÍA en una desktop**: el tool real devuelve
  `has_battery: false` (tools.py:3803) y el modelo igual responde "85%"/"78%"/
  "0%". El dataset iter-7 SOLO contenía baterías con porcentaje
  (`has_battery=True` siempre) — el modelo nunca vio el caso desktop.
- 2/10: respondió valores SIN llamar tool ("a cuánto está el CPU",
  "is the battery charging?") — residual del atractor v1/v2.
- 1/10: misroute it→web ("quanta RAM libera ho").
- **Lo que SÍ se arregló vs el bug raíz de 2026-06-10**: hora/fecha salen
  GROUNDED en la hora real del sistema (antes se fabricaban). Cero
  fabricaciones de hora en 53 prompts.

## Iteración 8 del dataset (aplicada, pre round 2)

1. Familia battery del synth: ~40% `has_battery=false` con shape real calcado
   + reply honesto "no tiene batería — es de escritorio" ×6 idiomas.
2. Familia aug `aug_v3_battery_desktop`: 25 fraseos VARIANTES (no los del
   gate — entrenar el test contaminaría la medición) de batería/CPU/RAM con
   results reales citados. Total batería: 16 sin / 15 con.
3. Media attempted: artista-sin-título 50%→75% attempted; play general
   25%→35% (gate 6: el modelo aún decía "reproduzco X" ante `played: false`).

Dataset round 2: **6.905 filas, 24 gates PASS, máscara PASS.**
