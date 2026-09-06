# C03 — checkpoint 2026-09-06, cierre de sesión de Opus 5 High

**Estado: EN_CURSO.** No hay 100/100 y no se declara nada cumplido. Cerrar esta
sesión no cumple el goal.

**El relevo está en [`HANDOFF_OPUS_METODO.md`](HANDOFF_OPUS_METODO.md)**: ahí
viven el candidato con sus fingerprints, lo comprobado, lo provisional, el fallo
abierto con su prueba roja, las hipótesis descartadas, la validación recogida,
los procesos y la siguiente acción. Este checkpoint no repite esa lista para no
tener dos que se contradigan.

## Causa que gobernó esta sesión

Todo turno conversacional que degrada llega al compositor con
`{"kind":"conversation","polarity":"success"}` y nada más: ni la respuesta que
escribió la mente, ni historial, ni tema. El compositor vuelve a contestar desde
cero con el texto del turno. Con una pregunta que se basta sale bien; con un
seguimiento elíptico —«¿por qué importa?»— sólo podía salir la frase vacía que
se venía midiendo. La anotación anterior de las rondas 10 y 12 —«la ruta
contextual sólo corre para `followup`/`None`»— era falsa; la traza de
composición con el campo `situation` lo enseña. Evidencia en
[`SEGUIMIENTOS.md`](SEGUIMIENTOS.md).

## Reparado en esta sesión

* El censo de prosa visible salta los docstrings de Python leyéndolos del árbol,
  como ya saltaba los comentarios. Censo: 0.
* La elipsis se lee donde se lee el pedido (`is_elliptical_followup`,
  `request_topic`, `followup_topic`) y el shell manda `priorRequests` —lo que la
  persona pidió antes, no lo que se le contestó—. De 0 de 9 seguimientos en tema
  a 7–9 de 9.
* Las preguntas por capacidades y límites se leen por su forma, no por frases
  enteras, y ya no se convierten en aclaración por ninguna de sus tres salidas.
  `limites-22/`: 8 de 9 fieles.
* El eco del encargo se detecta derivándolo de lo que se envió, con la exención
  de que las palabras del pedido no son vocabulario interno.
* `compose-audit.jsonl` v2 gana `situation` y `followup_subject`. Sin esos
  campos la causa de arriba no era visible.

## Variantes medidas y retiradas

1. Prohibir la definición en un seguimiento (`seguimiento-12` contra `-11`,
   misma población): de nueve seguimientos en tema a seis, con frases
   contorsionadas. Retirada, con la nota en el código donde vivía.
2. Antes de esta sesión: turno anterior como contexto, muestreo 0.2/0.9, y
   forzar la ruta contextual. Las tres siguen retiradas.

## Regresión propia, encontrada por el panel

`panel-opus-13/051`: «what are your limits on this PC» se contestó con la
definición de máscara de subred del turno anterior, porque la lectura tomaba
«this» por anáfora. Un determinante lleva su sustantivo detrás y un seguimiento
pregunta: con las dos condiciones el caso cae y los doce verdaderos siguen.
Comprobado en `limites-13/` y fijado en pruebas.

## Lo aplazado sigue aplazado

El seguimiento en tema que repite la definición, el saludo mal formado, la
persona impersonal y los agotamientos siguen abiertos y **no** se marcan
reparados; los que tocan generación conversacional siguen apuntando a C05/C06.
Las adjudicaciones históricas y sus límites se conservan tal cual, con la
corrección de la causa falsa anotada en `panel-opus-10` y `panel-opus-12`.

## Siguiente acción

La del handoff: poner en verde la prueba roja identificando el veto exacto,
después `panel-opus-14`, y sólo con el panel fiel congelar la población v19 y
correr el tramo D.
