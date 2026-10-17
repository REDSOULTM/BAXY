# Decisión 20: ajuste palanca por palanca de Qwen3.5-4B

Decisión del dueño (2026-10-16): reabrir el ajuste dentro del goal para sacar el máximo de Qwen3.5-4B con buenas
prácticas y fuentes. Cada palanca se investiga con su fuente, se mide por separado en práctica y se queda sólo si
gana por encima del ruido, sin romper `<reglas>` ni los 4 GB. Cuando ninguna gane: congelar, crear y correr UNA vez un
holdout nuevo sellado, y documentar el techo como límite honesto con su evidencia.

## Protocolo de medida

- **Bancos:** sólo los abiertos de práctica.
  - `renew_v1/practica/decision2.json`: 270 turnos, decisión (268 medidos: dos casos de operaciones retiradas quedan fuera).
  - `renew_v1/escenas/practice.json`: 39 escenas, instinto y silencio.
  - `renew_v1/e2e/practice.json`: computer use y voz, en el notebook (ver «E2E de práctica (notebook, …)» más abajo; ronda final 30: decía «sólo en el PC», y ninguna corrida e2e de la decisión 20 es del PC).

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
| P4 | Menos herramientas por turno con un recuperador del catálogo | [ToolScope, ACL 2026 (arXiv 2510.20036)](https://arxiv.org/abs/2510.20036); [DTDR (arXiv 2512.17052)](https://arxiv.org/abs/2512.17052); contrapunto: [TRAJECT-Bench (arXiv 2510.04550)](https://arxiv.org/pdf/2510.04550) | **Descartada por la latencia, con la cuenta:** la plantilla de Qwen3.5 pone las herramientas al principio del sistema, así que un juego de herramientas distinto en cada turno no deja ningún prefijo en caché. El calentamiento medido procesa unos 37k tokens en 15,2 s (base-s0, `warm_s`), unos 2.400 tokens/s en esta GPU. Un turno con unas 4k tokens de herramientas elegidas, más sistema e historial, tardaría ~1,7 s sólo en leerse, y el p50 de la decisión tiene que quedar ≤ 1 s (con el prefijo cacheado, 0,84–0,89 s en `base` y `base9e`, PC y notebook). Una selección en dos pasos por el propio modelo sumaría además una generación |
| P5 | Orden del contexto | Liu et al., [«Lost in the Middle» (TACL 2024)](https://arxiv.org/abs/2307.03172): una curva en U, lo que está al principio y al final del contexto se usa mejor que lo del medio | Brazo `tail`: tras las palabras de la persona, un recordatorio de las reglas de las que depende la decisión |
| P6 | Cabecera única de resultados | Anthropic, [«Writing effective tools for agents»](https://www.anthropic.com/engineering/writing-tools-for-agents) | Brazo `head`: cómo terminó cada llamada del turno va antes del resultado, no después. Sólo se ve en turnos de varios pasos: se mide en e2e de práctica |
| P7 | Guías con ejemplos para computer use | Brown et al., [«Language Models are Few-Shot Learners» (NeurIPS 2020)](https://arxiv.org/abs/2005.14165) | Brazo `cuex`: un ejemplo del ciclo mirar → pulsar → comprobar en la regla 9. Se mide en decision2 y en e2e de práctica (computer use 1/10 en el holdout v2) |
| P8 | Gramática de llamadas en llama.cpp | llama.cpp: gramáticas *lazy* para llamadas nativas (PR #9639, #12034) | **Ya aplicada**. Comprobado el 2026-10-16 con `--verbose` en b11609: «Grammar triggered on token 248058 (`<tool_call>`)». Las llamadas quedan restringidas en cuanto el modelo abre una. Sin brazo |
| P9 | El sistema en inglés | Shi et al., [«Language Models are Multilingual Chain-of-Thought Reasoners» (ICLR 2023)](https://arxiv.org/abs/2210.03057): con modelos multilingües, las indicaciones en inglés dan un razonamiento competitivo o mejor que en la lengua de la tarea; Etxaniz et al., [«Do Multilingual Language Models Think Better in English?» (NAACL 2024)](https://arxiv.org/abs/2308.01223), que trata la traducción de la entrada al inglés, es un apoyo indirecto | Brazo `sysen`: **no gana** (220,3 contra 232,0 y 3 molestas) |
| P10 | Una llamada por decisión | [llama.cpp function-calling](https://github.com/ggml-org/llama.cpp/blob/master/docs/function-calling.md): las llamadas en paralelo vienen «disabled by default» | Brazo `noparallel`: **no gana** (232,0 = `base9e`, más lento) |

## Resultados

Por brazo: aciertos de decisión en las semillas 0, 1 y 2 (media y dispersión), p50 de la decisión, escenas y escenas molestas o de riesgo. El campo `temp` de los registros es la variable de entorno del banco (0.2); en los brazos con temperatura fija (`qwen`, `t07`, `t0`, `think`) no es la que se usó.

**P1, PC (2026-10-16):**

| Brazo | Decisión | Media | Dispersión | p50 | Escenas | Molestas/riesgo |
|---|---|---|---|---|---|---|
| `base` | 233, 229, 230 | 230,7 | 4 | 0,891 s | 31, 31, 31 | 0/0 |
| `qwen` | 232, 225, 231 | 229,3 | 7 | 0,922 s | 30, 33, 30 | 0/0 |
| `t07` | 229, 217, 229 | 225,0 | 12 | 0,813 s | 32, 33, 30 | 0/0 |

En el notebook (D:, misma mente):

| Brazo | Decisión | Media | Dispersión | p50 | Escenas |
|---|---|---|---|---|---|
| `base` | 231, 234, 230 | 231,7 | 4 | 0,844 s | 32, 32, 32 |
| `pp15` | — | 231,7 | 2 | 0,906 s | 32 |
| `t0` | 227, 228, 230 | 228,3 | 3 | 0,844 s | 32, 32, 32 |

`t0` muestra que el piso de ruido de llama.cpp es de unos ±3 casos aunque la semilla no cuente (lotes y caché no deterministas). Ninguna variante de P1 supera a `base`, así que **se queda el muestreo actual**.

**P2, razonamiento en toda decisión (`think`, notebook):**
- Decisión: 186, 195 y 186 (media 189,0, dispersión 9), 43 casos por debajo de `base`.
- Latencia: p50 2,63 s y p90 5–6 s; rompe el p50 ≤ 1 s. Ninguna decisión llegó a 4096 tokens (máximo 734).
- Lo más grave: con razonamiento, el 4B **contesta en texto afirmando lo que no hizo**. Pasa en 86–108 conversaciones de 270 (en `base`, 58), y 40–54 de ellas son fallos (en `base`, 8–9). Por ejemplo, «ponte en modo no molestar» → «¡Entendido! Ya está activado» sin llamar a nada. Eso son falsedades de la regla 3.
- Escenas: 33/39 (+1, dentro del ruido), 0 molestas.

**No gana.** Queda por medir el razonamiento por etapa (`thinkcont`) en el e2e, mirando el mismo riesgo.

**P5, recordatorio de reglas al final del turno (`tail`, notebook):**
- Decisión: 201, 195 y 202 (media 199,3, dispersión 7), 32 casos por debajo de `base`. Pierde sobre todo en MASSIVE (83/120 contra 103), con erratas, spanglish y la cola larga del catálogo.
- De los 33 casos perdidos en s0, 23 son porque **contesta en texto en vez de llamar la herramienta**, a veces repitiendo la orden («Pausa la música que está sonando.») y a veces inventando un dato («la descarga va al 45 %» sin leerla).
- Escenas: 32/39, igual que `base`.

**No gana**, y añade falsedades. «Lost in the Middle» describe dónde atiende mejor el modelo (principio y final); con este 4B, repetir las reglas tras las palabras de la persona hace que les conteste a ellas. La réplica del PC dio 202, 196 y 204 en decisión (la escena de s1 no se corrió: se paró la tanda). Lo medido en el notebook ya decidía.

**P9, el sistema en inglés (`sysen`, PC, contra `base9e`):**
- Decisión: 222, 221 y 218 (media 220,3, dispersión 4), 12 casos por debajo de `base9e` (232,0).
- Escenas: 33/39 en las tres semillas, pero con **3 molestas en total** (1 por semilla): pierde silencios.

**No gana.** Las reglas en español, el idioma de las personas y de los casos, le van mejor a este 4B que la misma regla en inglés.

**E2E de práctica (notebook, 30 casos, producto 9eadc3d79), semillas 0 y 1:**

| Brazo | Aciertos | Media | Primera respuesta p50 | Observaciones |
|---|---|---|---|---|
| `base` | 19, 20 | 19,5 | 3864 / 2996 ms | |
| `head` (P6) | 18, 21 | 19,5 | 2768 / 2677 ms | |
| `cuex` (P7) | 20, 19 | 19,5 | 2832 / 2914 ms | en escenas pierde silencios |
| `thinkcont` (P2 por etapa) | 19, 21 | 20,0 | 4708 / 4574 ms | +1 s por paso que razona; la mitad de pasos encadenados; turnos sin respuesta |

Ninguno sale del ±1 de `base` en aciertos. **`thinkcont` no gana** (más lento y deja turnos sin respuesta). **`cuex` no gana** (empata y pierde silencios en escenas). `head` empata en aciertos y baja la primera respuesta, pero `cuex` también la baja, así que los 3864 ms de `base` s0 pueden ser el valor atípico. Con una tercera semilla: `base` 19 (primera respuesta 2827 ms) y `head` 19 (3346 ms, con los mismos 11 fallos que `base`). En tres semillas, aciertos `base` 19,3 = `head` 19,3, y primera respuesta `base` media 3229 ms (de 2827 a 3864), `head` 2930 ms (de 2677 a 3346). La diferencia de ~300 ms queda dentro del ruido de `base`, y en s2 `head` fue más lento. **`head` (P6) no gana.** Las falsedades de práctica de `head` ya no se juzgaron, porque no entra.

## Cierre de la decisión 20

Ninguna palanca (medida, o descartada por su cuenta como P4) supera a `base` por encima del ruido sin romper una condición (aciertos, silencios, falsedades, p50 ≤ 1 s, 4 GB):
- **No ganan:** P1, P2, P2 por etapa, P5, P6, P7, P9 y P10.
- **Ya aplicadas:** P3 y P8.
- **Descartada por la latencia:** P4.

El producto se congeló en **ff863b47f** (tag `renew-d20-congelado`), sin ningún cambio de la mente respecto de `base9e` (la mente de 9eadc3d79: ninguna palanca entró). El holdout v3, sellado por agentes aislados en `F:\BAXYeval\renew_v3`, se corrió una sola vez sobre ese commit (cifras en `PROGRESO.md` y en `metas.json`; los arreglos de honestidad
posteriores, entre ellos 45 descripciones del catálogo y 8 entradas de argumentos cambiadas desde ff863b47f tras la ronda final 37 (diff de claves), no se midieron en él), y su resultado es el techo medido con Qwen3.5-4B en este harness: una sola corrida sellada de esa configuración.

**P10, una llamada por decisión (`noparallel`, PC, contra `base9e`):** decisión 230, 233 y 233 (media 232,0, la misma que `base9e`; dispersión 3 contra 0), p50 0,938 s (más lento); escenas 30/39, 0 molestas. **No gana.**

**P7 (`cuex`), PC:** decisión 232, 229 y 232 (media 231,0, dispersión 3, p50 0,735 s), dentro del ruido de `base`. Escenas 29, 29 y 28, con **3 molestas en total** (1 por semilla): pierde silencios. **No gana**; el ejemplo en el sistema hace que el latido actúe de más. (Sus brazos se escribieron sobre 9eadc3d79, que cambió una descripción, la de filesystem.explorer.count (diff de claves 7a4030054..9eadc3d79; las otras dos diferencias del volcado eran las listas de apps y juegos de la máquina); `base` se mide otra vez sobre esa mente, `base9e`.)

**`base9e`** (la mente de 9eadc3d79, PC): decisión 232, 232 y 232 (las semillas fallan casos distintos y el total coincide), media 232,0, p50 0,859 s; escenas 30, 30 y 30, 0 molestas. Contra esta base, `cuex` (231,0; 28–29 con 3 molestas) sigue sin ganar.

Las escenas no varían con la semilla en `base`. La decisión de intervenir del latido es greedy con semilla 0 fija; la llamada que sigue usa el muestreo de decisión con la semilla del brazo, y en `base` dio lo mismo en las tres. Su ruido se toma de lo observado entre corridas y commits, unos ±2.
