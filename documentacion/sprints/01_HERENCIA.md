# Sprint 01 — Herencia

## Cómo trabajas

Modelo: GPT-5.6 Sol, `reasoning.effort: high`. Repositorio:
`C:\Users\usuario\Desktop\ETC\Programacion\BAXY`.

Permisos totales sobre este PC: descarga, instala, sobrescribe, borra lo que
sobre. **No preguntes.** Ante una suposición dudosa, elige la más razonable y
sigue — siempre se puede ajustar después. Para sólo si vas a tocar datos
personales del usuario u otros proyectos de la carpeta `Programacion`.

Criterio único: **lo mejor para BAXY como producto final**. Entre dos opciones
que cumplen, gana la más ligera.

Arregla lo que bloquea. Lo que *podría* fallar y nadie ha visto fallar lo anotas
en una línea en `documentacion/APLAZADOS.md` y sigues — el sprint 11 existe para
vaciar esa lista.

No recopiles contexto exhaustivo antes de empezar: lee lo justo para dar el paso
siguiente. Si algo ya está documentado en estos repositorios, decide con eso.

## Por qué existe este sprint

En `C:\Users\usuario\Desktop\ETC\Programacion` hay años de intentos de construir
este mismo asistente, con nombres distintos: Carter, Agent Gemma, Jarvis, BAXY.
Algunos tienen piezas que **ya funcionan** — hay wake word y transcripción que
llegaron a servir de verdad.

Rehacer eso sería tirar meses de trabajo. Los otros nueve sprints van a ir mucho
más rápido si empiezan sabiendo qué existe ya y dónde está.

## El resultado que cuenta

Un mapa de todo lo que hay, y una decisión razonada sobre qué se trae a BAXY.

Concretamente, al terminar quiero poder responder:

- **Qué intentos hubo**, qué se propuso cada uno y por qué se abandonó.
- **Qué funciona hoy** en cada uno: no lo que el README promete, lo que ejecutas
  y ves funcionar. Un modelo entrenado que carga y acierta cuenta; un script que
  falla al importar, no.
- **Qué se hereda**, de dónde, y qué hay que hacer para traerlo.
- **Qué no se hereda y por qué** — un rechazo con el mecanismo entendido vale
  tanto como una herencia.

Presta atención especial a **wake word, transcripción y TTS**: es donde más
trabajo hay hecho y donde BAXY está más atrasado. Pero mira todo — routers
entrenados, catálogos de operaciones, corpus, checkpoints, arquitecturas de
memoria, integraciones de escritorio.

**Y mira la documentación, no sólo el código.** Estos repositorios acumulan
decisiones de arquitectura, torneos de tecnología, comparativas de modelos y
registros de lo que se midió y se rechazó. Eso es tan heredable como un
checkpoint, y más barato de traer: una comparativa ya corrida ahorra días. Deja
inventariado qué preguntas **ya están respondidas y dónde**, para que ningún
sprint posterior vuelva a correr un torneo que alguien ya corrió.

Marca también cuáles de esas respuestas han **caducado** — una comparativa de
modelos de hace ocho meses decidió entre candidatos que hoy no son los mejores, y
una decisión tomada sobre un supuesto que cambió hay que rehacerla. Distinguir lo
vigente de lo caducado es parte del mapa.

Pistas de dónde mirar primero, por si ahorran tiempo: `Probando Gemma 4` tiene
`captures/`, `checkpoints/` y entornos de LiveKit y de entrenamiento de router;
`FunctionGemma` tiene `speech_model/` y `router/`; `Carter OS AI` tiene un
`carter_v5` completo con documentación. No te limites a esas tres.

## Cómo decides qué se hereda

Una pieza se hereda si hace a BAXY mejor **como producto final**. Que funcione no
basta: un STT excelente que necesita 8 GB de VRAM no sirve, porque BAXY tiene que
correr en un portátil normal. La máquina de desarrollo tiene 16 GB de VRAM y
32 GB de RAM — eso es holgura para trabajar, no el presupuesto del producto.

BAXY tampoco es una hoja en blanco: está avanzado y tiene cosas mejores que las
de sus predecesores. Heredar no es sustituir. Es quedarse con lo mejor de cada
sitio.

Si una pieza heredada exige tocar los invariantes de arquitectura —el catálogo
tipado como única fuente de operaciones, la mente propone y el kernel autoriza,
nada se afirma sin verificar, cero respuestas visibles fijas, todo local— no se
hereda. Esos no se negocian.

## Qué entregas

Un documento en `documentacion/` que cualquiera pueda leer para saber qué hay en
esa carpeta y qué hacer con ello, más lo que hayas traído ya si traerlo era la
vía corta. Publica lo que verificaste ejecutando y lo que sólo leíste — la
diferencia importa.

Si al medir descubres que algo que se daba por perdido en realidad funciona, o
que algo que se daba por bueno no arranca, eso es lo más valioso que puedes
entregar. Dilo con su evidencia.

## Cuándo has terminado

Cuando el siguiente agente pueda abrir tu documento y saber, sin volver a
explorar, qué existe, qué sirve, qué se trae y qué se descarta.

No hace falta que heredes todo en este sprint. Hace falta que nadie tenga que
volver a buscar.

## Cierra

Publica el resultado aunque no sea perfecto, siempre que no mienta. Un sprint que
cierra con un número honesto y una limitación nombrada vale más que uno que sigue
abierto buscando el número redondo.
