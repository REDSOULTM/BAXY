# Fase 3.5 — meta ampliada por el dueño (2026-09-22, noche)

**Sustituye la lista de 13 entregables de `SEMANTICA_PROGRESO.md`.** Lo ya hecho (harness `semantic_replay.py`,
held-out del 22, baseline, clase 1) se hereda: no se rehace. Esta meta recupera la misión original de
`PROMPT_FABLE_SEMANTICA_2026-09-23.md` (un solo lugar, legible, estado del arte), que sigue vigente entera, y la
amplía en el corpus y en el criterio de cierre.

## La misión, en palabras del dueño

La 3.5 es el puente que **junta toda la detección en un solo lugar** y hace que BAXY entienda el lenguaje natural
**de cualquier forma en que el dueño le hable o cualquier persona**, en español y en inglés (el spanglish que mezcla los dos cuenta). Los
742 son una encuesta, no el techo: hay mucha más historia. BAXY Definitivo tiene que **heredar lo mejor de todos los
BAXY anteriores** (ley 1 de `AGENTS.md`) y usar **todos sus casos históricos** como ejemplos de los que generalizar.
Entender también es saber **qué es BAXY y qué no hace**: BAXY no hace cualquier cosa, tiene límites, y esos límites
están en la encuesta de los 742, en `documentacion/00_IDENTIDAD.md` y en la documentación de los BAXY anteriores.

## Qué cuenta como «entendió» (decisión del dueño)

Un turno sale **bien** si BAXY lee bien el pedido —intención, operación del catálogo y argumentos correctos, o
conversación, o aclaración sólo con ambigüedad real (D24)— y, cuando la capacidad no existe o está fuera de la
identidad, **lo dice con un límite honesto sin inventar el efecto**. Hacerlo de verdad (p. ej. clicar en Steam) es
del motor (Fase 4/5) y no se exige aquí. Nunca cuenta como bien afirmar un efecto sin operación.

## El corpus, por capas (decisión del dueño: todo, medido por capas)

Todo se usa como ejemplo para diseñar lectores y gramáticas; la nota que cierra sale de las capas marcadas.

| Capa | Qué es | Dónde | Papel |
|---|---|---|---|
| **A — real del dueño** | Mensajes que una persona le dijo de verdad a algún BAXY (no a los agentes que lo programaban), en español o inglés | `tests/data/historical_messages.jsonl` con `origin = observed_user` (3 639 filas; usá las `dedup_status = canonical_source`); los 742 de `%LOCALAPPDATA%\BAXY\C03-survey-requirements336-private\requirements.jsonl`; las conversaciones reales de BAXY Definitivo en `%LOCALAPPDATA%\BAXY\dev-mente-v2\conversation\conversation.v1.jsonl` y cualquier otro perfil **de uso real** (no los perfiles de tandas `C03-*`, que son sintéticos) | **Cierra: ≥ 95 %** |
| **B — herencia curada** | Casos y requisitos escritos por los BAXY anteriores | mismo fichero, `origin` ∈ `curated_history`, `acceptance_example`, `historical_test`, `document_requirement`, `document_example` | Se mide y se publica por dominio; toda caída respecto del baseline se explica |
| **C — corpus sintéticos** | Frases generadas para entrenar routers viejos (FunctionGemma `router_corpus_*`, `train_v3`, trazas de Probando Gemma 4, benches de Carter) | mismo fichero, por `source` | Cobertura de formas; se publica la cifra, no cierra |
| **Held-out nuevo del dueño** | Frases y conversaciones que el dueño escribe a su manera y que vos no ves hasta el final | lo entrega el dueño cuando se lo pidas | **Cierra: ≥ 95 %** |

- **No todas las filas cuentan. Dos filtros antes de medir nada, publicados con sus cifras:**
  1. **Idioma: BAXY es para español e inglés** (y su mezcla). El fichero tiene 14 836 filas, 10 867 canónicas;
     `language` dice es 6 470, en 1 146, spanglish 483 y `other` 6 737. Ese `other` es sobre todo español o inglés
     corto que el etiquetador viejo no reconoció («déjalo así», «thank you»), más frases de verdad en otros
     idiomas (chino, ruso, alemán, tamil, portugués…) y ruido (símbolos, emojis sueltos). Re-etiquetá el idioma de
     cada fila con un método reproducible (no con la etiqueta vieja) y dejá fuera todo lo que no sea español,
     inglés o su mezcla.
  2. **Destinatario: sólo lo que se le dijo a BAXY.** Muchas filas son instrucciones a los agentes que programaban
     BAXY (Codex, Claude, notificaciones de tareas, comandos de Python, notas de código): clases
     `engineering_instruction` y `product_requirement`, y textos con código. No son pedidos a BAXY y no cuentan.
     Ojo con la capa A: de las 3 639 filas `observed_user`, una estimación rápida da unas 900 dirigidas a BAXY en
     español o inglés y otras tantas dirigidas a los agentes.
  Estimación rápida hecha al redactar esta meta (heurística, no oficial): quedan unas 5 700 frases seguras y hasta unas
  2 500 dudosas por idioma. Publicá tu cifra real por capa tras los dos filtros, y guardá lo descartado en un
  fichero con el motivo para que el dueño pueda revisar una muestra.
- **Oráculo.** `tests/data/historical_message_mapping.jsonl` (misma cantidad de filas) ya mapea cada mensaje a
  misión, operaciones, operaciones prohibidas, riesgo y `acceptance_scope`. Es el esperado de partida. Si una
  fila está mal o se refiere a un catálogo viejo, se re-etiqueta **a la vista**: cuántas, por qué regla, una entrada
  en `DECISIONES_OPUS_2026-09-22.md` y una muestra de 50 re-etiquetas al azar para que el dueño las revise. Nunca en
  silencio, nunca para subir la cifra.
- **Fuentes vivas.** Si hace falta más que el corpus congelado (código de lectores, rechazos medidos, requisitos),
  las fuentes del linaje (BAXY, Carter OS AI, FunctionGemma, Probando Gemma 4) están en
  `documentacion/herencia/00_MAPA.md` y `09_5_FUENTES.md`, y la biblioteca de los intentos anteriores se consulta con
  la skill `evidencia-baxy`. Si una fuente no está en esta máquina, preguntale al dueño dónde está; no recorras el
  disco a ciegas.
- **Ley 1 por dominio.** Antes de escribir el lector de un dominio, buscá cómo lo resolvieron los BAXY anteriores y
  qué se rechazó ya; citalo en `SEMANTICA.md`. Heredá lo que funcionó, no lo reinventes.

## Seguridad del corpus grande (no negociable)

- Las capas A, B y C se corren **sólo-decisión** (`turn.decide` o el `read()` nuevo), **sin ejecutar nada**: son
  miles de frases con «cerrá», «borrá», «mandá». Las conversaciones con efectos reales quedan para los guiones
  contextuales y el held-out, con la ventana guardia y la comprobación de que VS Code sigue vivo tras cada guion.
- VS Code no se cierra nunca (D17): también aloja esta sesión.
- Que el corpus corra rápido es parte del diseño: la lectura determinista en segundos, la vía del modelo sobre una
  muestra estratificada por dominio y capa si no cabe entera. Nada de editar `src` con una corrida en marcha.

## Entregables

1. **Clase 1 cerrada y commiteada** con la cifra de c1c (lo que hay ahora en el árbol). Las clases 2–5 no se
   abandonan: pasan a ser parte del dominio `dialogue` de `semantic/`.
2. **Baseline por capas** sobre `b5c9fe72` y sobre el HEAD con la clase 1: capa A, B y C por dominio y por tipo
   de fallo (no leído, leído mal, aclaración innecesaria, límite falso, límite que faltó, efecto inventado).
3. **`src/baxy_mind/semantic/`** con una puerta `read(text, history, catalog) -> Reading`, módulos por dominio,
   normalización única, gramáticas por intención y la identidad/límites como lectura de primera clase (qué es BAXY,
   qué no hace y por qué). Los lectores viejos de `effect_intent.py`, `__main__.py`, `llm.py`, `planner.py` y los
   parsers de `src/Baxy.App/` se retiran cuando el nuevo los cubre (ley 2: no quedan dos caminos). Commit por
   dominio con la cifra de las capas en el mensaje.
4. **`documentacion/SEMANTICA.md`**: legible en diez minutos por cualquier agente; incluye de qué BAXY anterior se
   heredó cada pieza.
5. **Cierre**: capa A ≥ 95 %, held-out nuevo del dueño ≥ 95 %, Full verde, cien 100/100, sellos re-anclados,
   informe `SEMANTICA_<fecha>.md` con antes/después por capa, y todo commiteado y pusheado.

## El held-out nuevo del dueño

Cuando `semantic/` esté migrado y la capa A pase, pedíselo al dueño. Lo corrés **una vez**. Si no llega a 95 %, se
arreglan las causas generales (nunca la frase), el held-out usado pasa a ser corpus, y el dueño escribe otro.

## Cómo se informa

`SEMANTICA_PROGRESO.md` lleva la tabla de capas con la última cifra medida y el comando que la produjo. Al cerrar
cada dominio, cifras al dueño, no narrativa. Las decisiones sin el dueño siguen en `DECISIONES_OPUS_2026-09-22.md`
con el mismo criterio (lo sellado; si no alcanza, la práctica establecida; entre dos, la más reversible y la que
nunca afirma un efecto que no ocurrió).
