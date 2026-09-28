# Goal v3 — «comprensión natural», segunda vuelta (2026-09-28)

Sigue a `GOAL_COMPRENSION_NATURAL_v2_2026-09-28.md` (todas sus reglas de trabajo siguen vigentes) y al cierre
`COMPRENSION_NATURAL_2026-09-28.md`. Lo redactó la sesión revisora a pedido del dueño tras revisar el FINAL turno a
turno (`window/final-once/REVIEW.reviewed.jsonl`). Decisiones nuevas del dueño (28-09): **4 GB de VRAM es innegociable**
(«esa es la gracia de BAXY») y **sólo modelos con licencia que permita distribuir** (Apache-2.0, MIT o equivalente):
nada no comercial (xLAM) ni con tope de ingresos (LFM Open License). Hay más cómputo: redpc (RTX 4060 Ti 16 GB) por
SSH para entrenar y generar datos; la inferencia del producto sigue ≤ 4 096 MiB.

## 1. Por qué «el modelo toca techo» es sólo una parte

El FINAL con revisor dio 56,9 % (87 fallos de 202). Clasificados por causa:

| causa | fallos | qué es | ¿es el modelo base? |
|---|---|---|---|
| repregunta datos ya dados / argumentos | ≈ 20 | «Cambia la alarma de las 8 a las 9» → pregunta la hora; «abre el Calendar» → pide el nombre; carpeta y nombre dados → los pide | no: el paso de argumentos, separado del decisor |
| límite o alcance mal decidido | ≈ 17 | luces, lavar ropa, apps del móvil → pregunta o actúa; lo personal («where does James live», «fechas límite de matthews») → busca en la web | en parte: faltan negativos de fuera de alcance y la regla «lo de la persona no se busca» |
| búsqueda | ≈ 16 | eco de un snippet, publicidad, «No lo encontré»; **los buscadores bloquean esta red desde el 26-09** | no: fuente de búsqueda frágil (scraping) y redacción del informe |
| ⚠ sin respuesta | 10 | `composition_failed`: la redacción veta y agota reintentos | no: la tubería de redacción |
| conocimiento o código del 4B | ≈ 16 | receta errónea, dato astronómico mal, código pedido → busca o repregunta | sí en los datos; no en el código (se mandó a la web) |
| otros e inventado | ≈ 8 | lista vacía presentada como «tu cuarta lista», un promedio inventado | mixto |

Además: el decisor `full3` **solo** da 88,9 % en DEV-B y el producto sólo-mente 80–81 %; la app resta otros 5–7.
Conclusión: al menos **~60 de los 87 fallos no dependen del modelo base** sino de mecanismos (argumentos, alcance,
búsqueda, redacción). Ahí está la vuelta.

## 2. Plan de la segunda vuelta (en este orden; cada paso con regla prerregistrada)

1. **Medida limpia primero.** El FINAL ya está gastado: pasa a ser conjunto de desarrollo (sus fallos se miran). Crea
   un **FINAL-2** sellado (≈ 250 turnos, mitad conversaciones, sala limpia, doble etiquetado ciego, excluye todo lo
   visto y todo lo de entrenamiento) y un **DEV-D** para iterar. La métrica que manda es la del **revisor en la app
   real** (lo que ve la persona), no sólo la de decisión; el puntuador automático sirve para iterar rápido.
2. **Búsqueda fiable y distribuible.** El scraping de Bing/DuckDuckGo se bloquea y no sirve para un producto que se
   distribuye. Investiga (estado del arte, términos de uso) una fuente que funcione sin bloquearse y respete la
   identidad (sólo sale la consulta, nunca datos de la persona): API de búsqueda con clave del usuario, instancias
   propias, APIs abiertas por dominio (Wikipedia/Wikidata para conocimiento, la de clima que ya se usa, etc.) y un
   fallback honesto. Separa la medida de búsqueda del resto hasta que la fuente funcione. **PREGUNTAR** si exige
   cuenta o clave del dueño.
3. **Decisión y argumentos en una sola salida.** El decisor devuelve la operación **con sus argumentos** en el mismo
   esquema restringido; el paso de extracción aparte sólo completa lo que falte. Entrena el LoRA también sobre
   argumentos (horas, duraciones, nombres de apps, carpetas, títulos). Meta intermedia: cero repreguntas de un dato
   que el mensaje o el historial ya da.
4. **Datos de entrenamiento a escala y verificados** (en redpc). Hoy son ≈ 5,6 mil ejemplos sintéticos. Sube a
   decenas de miles con el método de APIGen/APIGen-MT (generar → comprobar formato → comprobar contra el catálogo →
   comprobar semántica): (a) particiones de **entrenamiento** públicas (MASSIVE train es/en, MTOP train, SGD train,
   CLINC train con fuera de alcance) mapeadas **por intención** al catálogo o a «límite» (las de validación y test
   quedan para medir); (b) conversaciones **vividas en la app**: un simulador de usuario (subagentes con hablantes
   variados) conversa con BAXY en la app y lo vivido, revisado, entra al entrenamiento; (c) negativos de alcance y de
   «lo personal no se busca». Nunca DEV/FINAL/742/guion/held-out.
5. **Redacción que no falla.** ⚠ ≤ 1 %: un resultado verificado siempre se puede decir; la charla, el código y las
   explicaciones las escribe el modelo (nunca se mandan a la web); el informe de búsqueda responde la pregunta o dice
   que no lo encontró, sin eco de snippets ni publicidad.
6. **Conocimiento honesto.** Hechos con fecha, cifras y recetas se buscan antes de afirmar (cuando la búsqueda
   funcione); si no se puede, BAXY lo dice en vez de recitar de memoria.
7. **Margen de VRAM.** Hoy BAXY está en ≈ 3 960–4 020 MiB, al borde. Mide cuánto contexto hace falta de verdad
   (ventana de historial) y deja ≥ 300 MiB de margen sin perder calidad.
8. **Modelo base, sólo con licencia libre.** Qwen3.5-4B (Apache-2.0) sigue salvo que otro con licencia Apache/MIT
   que quepa en 4 GB gane con margen prerregistrado **después** de los pasos 3–4 (el torneo anterior fue con otro
   entrenamiento).
9. **Cierre:** FINAL-2 una sola vez en la app real con revisor independiente, más la verificación completa de v2.

## 3. Metas

| | hoy | meta |
|---|---|---|
| FINAL-2 revisor (app real) | 56,9 % | **≥ 85 %** |
| FINAL-2 puntuación automática | 74,3 % | **≥ 90 %** |
| repreguntas de un dato ya dado | ≈ 10 % de los turnos | **0** |
| ⚠ sin respuesta | 5 % | **≤ 1 %** |
| inventados | 1 | **0** |
| VRAM de BAXY | ≈ 4,0 GB | **≤ 3,8 GB** |

Y todo lo de v2 sin retroceder (guion ≥ 53/60, held-out ≥ 29/30, cien 100/100, reserva ≥ 88 %, capa A ≥ 96 %, 742
revisadas, Full verde, latencia p50 ≤ 3 s). Si al final el revisor queda por debajo, el informe dice cuántos fallos
quedan por causa y cuáles son del modelo base.
