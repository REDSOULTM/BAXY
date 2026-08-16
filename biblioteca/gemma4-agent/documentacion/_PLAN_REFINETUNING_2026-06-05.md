# Plan de RE-FINE-TUNING del dataset de Baxy — derivado de las 6 tandas de cacería

**Estado: PLAN para tu aprobación. NO se entrenó nada todavía.**

Construido con: medición directa sobre los 6162 casos re-run + los 992 bugs del juez
LLM + los 853 líneas de clusters narrativos (t1-t4) + auditoría del `curated.jsonl`
real (6661 ejemplos). Dos workflows multi-agente (7 agentes) + verificación mía.

---

## TL;DR — qué arregla y cómo

El re-fine-tuning ataca lo que el PROMPT no pudo vencer (medido en vivo): son
**dataset-level**. 4 focos + 2 sub-modos, con ~74 ediciones al original y ~210
ejemplos nuevos (67 ya redactados como semilla en `scripts/_diag/_ftfail/_seed_examples.jsonl`).

| Foco | Bug | Causa raíz (medida) | Fix |
|------|-----|---------------------|-----|
| **P0 Identidad** | "Soy Gemma 4" | 63 líneas lo enseñan, **0** dicen "Baxy" | editar 63 + ~20 nuevos |
| **P1 Honestidad** | auto-confirma irreversibles, afirma no-hecho | **subcobertura** (solo 5 ej `honestidad_bajo_presion`, no mal-etiquetado masivo) | 2 ediciones + ~45 nuevos |
| **P2 Routing** | estado→acción, how-to→ejecuta, conocimiento→web | ejemplos correctos existen pero **mal balanceados por idioma** | 2 ediciones + ~75 nuevos |
| **P3 Idioma** | reply post-tool en español | **representacional**: "Listo," en 340 reply_styles = atractor cross-lingüe | 1 edición + ~70 nuevos |
| gap B10 | multi-paso: placeholder en el GT | 7 GT enseñan `"[descripción]"` literal = el leak que cazamos | 8 nuevos (diferir al tool) |
| gap B11/B12 | resume-texto→media, antónimos (para→play) | colisión léxica + faltan pares contrastivos | 9 nuevos |

---

## 3 correcciones que los agentes hicieron a MIS supuestos (importante)

El análisis midió contra el dataset y corrigió 3 cosas que habrían hecho un dataset peor:

1. **Idioma NO es mal-etiquetado.** De 1407 replies non-ES con tool, solo **1** arranca
   con "Listo,". Las etiquetas non-ES están bien. El bug es 100% representacional (el
   prefijo "Listo," domina 340 ejemplos y el modelo lo memoriza como plantilla
   universal de cierre-de-acción). → Fix = **agregar masa balanceada**, casi nada de
   re-etiquetar. (Bajísimo riesgo.)

2. **Honestidad NO está "llena de mentiras".** Solo **2 líneas** auto-afirman
   verificación; **0** mensajería afirma entrega. El bug es **subcobertura** (prior
   fuerte de "narrá éxito" + pocos ejemplos del freno honesto). → Fix = 2 ediciones +
   bloque de cobertura, NO una purga masiva. (Mucho menos riesgo del que pensaba.)

3. **El rebrand son 63 líneas en 5 idiomas** (es 44, en 11, de 4, fr 3, it 1), no 50.
   Y hay **0 ejemplos de "Soy Baxy"** → el modelo no tiene de dónde aprenderlo.
   CUIDADO: 31 menciones de "Gemma 4" son legítimas (el MODELO) — NO tocarlas.

---

## Estrategia (anti-regresión es la prioridad)

**Principio:** el FT actual logra 0% tools inventadas. Se sostiene porque ES es mayoría
holgada y los `correct_tools` están bien. **No tocamos `correct_tools` de lo que
funciona; el 90% del trabajo es `correct_reply_style` + ejemplos nuevos.**

- **Tope duro:** ningún modo nuevo > ~1.5% del dataset. Bloque nuevo total ~3.1%.
- **ES se mantiene** en ~58% (de 60%) → no degrada el español.
- **Reparto del bloque nuevo** prioriza pt/de/fr/it (más flacos); EN no domina.
- **Regla de PARIDAD:** cada ejemplo de consulta/how-to/freno entra con su **gemelo de
  acción legítima** del mismo recurso → el asistente no se vuelve tímido (latencia
  tier-Alexa intacta).
- **user-recall SIEMPRE** como template `[nombre guardado]` + fallback honesto, nunca
  un nombre concreto hardcodeado en el GT (evita que invente "Red").

## Gates EN VIVO antes de entrenar (regla 3.5)

Cada foco se valida con el LLM real (`run_content`), variando fraseos, ANTES de entrenar:
- **Identidad:** "se nombra Baxy" ≥0.95 multilingüe; "cómo me llamo"(user)→memory; anti-regresión "¿qué modelo usás?"→"Gemma 4" ≥0.95.
- **Honestidad:** 0 claims de "verifiqué/eliminado" sobre delete/send; irreversibles frenan; anti-regresión: benignos NO empiezan a pedir confirmación.
- **Routing:** por idioma, state→reporta, how-to→explica, conocimiento→responde; anti-regresión: imperativos siguen ejecutando.
- **Idioma:** reply-language-match ≥0.95 POR IDIOMA (no promedio) sin que ES baje.
- **Global post-FT:** 0% tools inventadas preservado + ningún subgrupo degrada. Smoke test chico antes de la corrida completa.

## Riesgos top + mitigación
- **Romper ES:** ES queda ~58% holgado; medir antes/después en cada gate.
- **Find-replace ciego Gemma→Baxy:** editar SOLO las 63 líneas de self-naming (regex de sujeto), preservar las 31 del modelo.
- **Cambiar un loro por otro** ("Done,/Pronto," como nuevas plantillas rígidas): variar openers DENTRO de cada idioma.
- **Asistente tímido:** regla de paridad + bloque honesto acotado a ~3-5%.
- **El placeholder-leak del GT multi-paso:** los nuevos ejemplos DIFIEREN la descripción al tool real, no emiten `[descripción]`.

## Definición de Hecho
Dataset auditado al 100% (script versionado verde: JSON válido, tools ∈ registry, 0
nombres-de-usuario hardcodeados, 0 self-naming "Gemma 4"/"Carter", Baxy>0) + 4 gates en
vivo verdes + 0% tools inventadas preservado + ES no degradado + memoria actualizada.
**Recién ahí se commitea el dataset y se entrena.**

---

## Artefactos generados (para revisar)
- `scripts/_diag/_ftfail/_seed_examples.jsonl` — **67 ejemplos semilla** (formato curated, balanceados por idioma)
- `scripts/_diag/_ftfail/_plan_maestro.txt` — plan detallado del sintetizador (con todas las mediciones)
- `scripts/_diag/_ftfail/_analyses_full.json` — análisis completo por foco (diagnóstico + fixes + riesgos)
- `scripts/_diag/_ftfail/_gaps_full.json` — los 17 ejemplos de los sub-modos B10/B11/B12
- `scripts/_diag/_ftfail/_failmode_*.json` — los casos crudos por foco

## Próximo paso (espera tu OK)
1. Escalar los 67 semilla → ~210 siguiendo el reparto, + aplicar las ~74 ediciones.
2. Escribir el script de auditoría 100% del dataset.
3. Correr los gates en vivo por foco.
4. Smoke test → entrenar → gate global.
