# Decisión 20: ajuste palanca por palanca de Qwen3.5-4B

Decisión del dueño (2026-10-16): reabrir el ajuste dentro del goal para sacar el máximo de Qwen3.5-4B con buenas
prácticas y fuentes. Cada palanca se investiga con su fuente, se mide por separado en práctica y se queda sólo si
gana por encima del ruido, sin romper `<reglas>` ni los 4 GB. Cuando ninguna gane: congelar, crear y correr UNA vez un
holdout nuevo sellado, y documentar el techo como límite honesto con su evidencia.

## Protocolo de medida

- **Bancos:** sólo los abiertos de práctica.
  - `renew_v1/practica/decision2.json`: 270 turnos, decisión (268 medidos: dos casos de operaciones retiradas quedan fuera).
  - `renew_v1/escenas/practice.json`: 39 escenas, instinto y silencio.
  - `renew_v1/e2e/practice.json`: computer use y voz, sólo en el PC.

  Ningún banco sellado se abre.
- **Brazos:** `scripts/renew/make_arms_d20.py` escribe cada brazo como una copia de `src/baxy_mind` con una sola
  palanca cambiada, en `F:\BAXYeval\renew_v1\ab\d20-<brazo>-s<semilla>`. Los bancos los miden con `--src`. La mente
  fija su semilla, así que cada brazo se mide con tres semillas (0, 1 y 2).
- **Ruido:** la dispersión entre semillas del brazo `base`. Una palanca gana si la media de sus tres semillas supera
  a la de `base` por más que esa dispersión. Además debe cumplir:
  - no pierde silencios ni suma riesgo en escenas;
  - la decisión mantiene p50 ≤ 1 s;
  - la VRAM queda ≤ 4 GB.
- **Combinación:** lo que gane se combina, y la combinación se vuelve a medir contra `base`.
- **Reglas:** sólo presentación, protocolo o inferencia (reglas 1 y 2). Nada que interprete a la persona en código.

## Palancas

| # | Palanca | Fuente | Estado |
|---|---|---|---|
| P1 | Muestreo recomendado por Qwen (sin razonamiento: temperature 0.7, top_p 0.8, top_k 20, min_p 0, presence_penalty 1.5) | [Ficha Qwen3.5-4B](https://huggingface.co/Qwen/Qwen3.5-4B), Quickstart | Brazos `qwen`, `t07`, `pp15`, `t0` contra `base` (0.2/0.8/20/0) |
| P2 | Razonamiento on/off por tarea | Misma ficha: Qwen3.5 razona por defecto; muestreo con razonamiento 1.0/0.95/20/0/pp1.5 | Brazo `think`: razonamiento en toda decisión. Brazo `thinkcont`: por etapa del protocolo, nunca leyendo las palabras de la persona; la primera decisión del turno sin razonar (p50 ≤ 1 s) y cada decisión tras un resultado razonando, que son los pasos de computer use y de los pedidos de varios pasos. Se mide en e2e de práctica |
| P3 | Plantilla nativa de herramientas de Qwen | Ficha: parser `qwen3_coder` (XML `<function=…><parameter=…>`); [llama.cpp function-calling](https://github.com/ggml-org/llama.cpp/blob/master/docs/function-calling.md): `--jinja` usa la plantilla del modelo | **Ya aplicada**. Comprobado el 2026-10-16 con llama-server b11609 y `/apply-template`: la sección `# Tools` va en el sistema, las llamadas en XML y el parser devuelve `tool_calls` correctos. Sin brazo |
| P4 | Menos herramientas por turno con un recuperador del catálogo | [ToolScope, ACL 2026 (arXiv 2510.20036)](https://arxiv.org/abs/2510.20036); [DTDR (arXiv 2512.17052)](https://arxiv.org/abs/2512.17052); contrapunto: [TRAJECT-Bench (arXiv 2510.04550)](https://arxiv.org/pdf/2510.04550) | **Descartada por la latencia, con la cuenta:** la plantilla de Qwen3.5 pone las herramientas al principio del sistema, así que un juego de herramientas distinto en cada turno no deja ningún prefijo en caché. El calentamiento medido procesa unos 37k tokens en 15,2 s (base-s0, `warm_s`), unos 2.400 tokens/s en esta GPU. Un turno con unas 4k tokens de herramientas elegidas, más sistema e historial, tardaría ~1,7 s sólo en leerse, y el p50 de la decisión tiene que quedar ≤ 1 s (hoy 0,83–0,89 s con el prefijo cacheado). Una selección en dos pasos por el propio modelo sumaría además una generación |
| P5 | Orden del contexto | Liu et al., [«Lost in the Middle» (TACL 2024)](https://arxiv.org/abs/2307.03172): lo que está al final del contexto se usa mejor | Brazo `tail`: tras las palabras de la persona, un recordatorio de las reglas de las que depende la decisión |
| P6 | Cabecera única de resultados | Anthropic, [«Writing effective tools for agents»](https://www.anthropic.com/engineering/writing-tools-for-agents) | Brazo `head`: cómo terminó cada llamada del turno va antes del resultado, no después. Sólo se ve en turnos de varios pasos: se mide en e2e de práctica |
| P7 | Guías con ejemplos para computer use | Brown et al., [«Language Models are Few-Shot Learners» (NeurIPS 2020)](https://arxiv.org/abs/2005.14165) | Brazo `cuex`: un ejemplo del ciclo mirar → pulsar → comprobar en la regla 9. Se mide en decision2 y en e2e de práctica (computer use 1/10 en el holdout v2) |
| P8 | Gramática de llamadas en llama.cpp | llama.cpp: gramáticas *lazy* para llamadas nativas (PR #9639, #12034) | **Ya aplicada**. Comprobado el 2026-10-16 con `--verbose` en b11609: «Grammar triggered on token 248058 (`<tool_call>`)». Las llamadas quedan restringidas en cuanto el modelo abre una. Sin brazo |

## Resultados

Por brazo: aciertos de decisión en las semillas 0, 1 y 2 (media y dispersión), p50 de la decisión, escenas y escenas molestas o de riesgo. El campo `temp` de los registros es la variable de entorno del banco (0.2); en los brazos con temperatura fija (`qwen`, `t07`, `t0`, `think`) no es la que se usó.

**P1, PC (2026-10-16):**

| Brazo | Decisión | Media | Dispersión | p50 | Escenas | Molestas/riesgo |
|---|---|---|---|---|---|---|
| `base` | 233, 229, 230 | 230,7 | 4 | 0,891 s | 31, 31, 31 | 0/0 |
| `qwen` | 232, 225, 231 | 229,3 | 7 | 0,922 s | 30, 33, 30 | 0/0 |
| `t07` | 229, 217, 229 | 225,0 | 12 | 0,813 s | 32, 33, 30 | 0/0 |

En el notebook, `base` dio 231, 234 y 230 (media 231,7, dispersión 4) y 32/39 en escenas en las tres semillas. Ninguna variante de P1 supera a `base`, así que **se queda el muestreo actual**.

**P7 (`cuex`), PC:** decisión 232, 229 y 232 (media 231,0, dispersión 3, p50 0,735 s), dentro del ruido de `base`. Escenas 29, 29 y 28, con **3 molestas**: pierde silencios. **No gana**; el ejemplo en el sistema hace que el latido actúe de más. (Sus brazos se escribieron sobre 9eadc3d79, que cambió tres descripciones; `base` se mide otra vez sobre esa mente, `base9e`.)

**`base9e`** (la mente de 9eadc3d79, PC): decisión 232, 232 y 232 (las semillas fallan casos distintos y el total coincide), media 232,0, p50 0,859 s; escenas 30, 30 y 30, 0 molestas. Contra esta base, `cuex` (231,0; 28–29 con 3 molestas) sigue sin ganar.

Las escenas no varían con la semilla en `base`: el latido decide en greedy con semilla 0 fija. Su ruido se toma de lo observado entre corridas y commits, unos ±2.
