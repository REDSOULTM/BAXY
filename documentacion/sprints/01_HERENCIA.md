# Goal 01 — La herencia

> **Esto es un goal, no una tarea.** Se lanza y corre hasta cumplirse. No pares a
> mitad a pedir aprobación ni a preguntar: ante una duda, elige la opción más
> razonable, anótala y sigue. Acabas cuando los criterios de cierre estén
> marcados, o cuando hayas medido que uno es inalcanzable y publicado la evidencia
> que lo demuestra. No hay una tercera forma de acabar.

## Dónde trabajas

Repositorio: `C:\Users\usuario\Desktop\ETC\Programacion\BAXY`. Modelo: GPT-5.6 Sol,
`reasoning.effort: high`.

Permisos totales sobre este PC: descarga, instala, sobrescribe, borra lo que
sobre. **No preguntes.** Para sólo si vas a tocar datos personales del usuario u
otros proyectos de la carpeta `Programacion`.

No recopiles contexto exhaustivo antes de empezar: lee lo justo para dar el paso
siguiente. Si algo ya está documentado en estos repositorios, decide con eso.

## Qué es BAXY

Un compañero que vive en el PC de una persona y hace lo que le pide —tipo Jarvis,
local y privado—. Tiene carácter propio, es un «él», tutea, y confirma lo que hizo
comprobándolo: *«Listo, Spotify está abierto y sonando»*. Cuando falla lo dice
plano y con la causa. Nunca inventa que hizo algo, nunca actúa sin que se lo
pidan, nunca manda datos del usuario fuera.

Todo está en `documentacion/00_IDENTIDAD.md`, y **es lectura obligatoria antes de
tocar nada**. No son preferencias: son decisiones tomadas por el dueño con los
cuatro intentos anteriores del proyecto sobre la mesa. Si un diseño tuyo las
contradice, el que cambia eres tú.

## Las cuatro leyes

Gobiernan este goal y los otros diez. Están por encima de cualquier preferencia
técnica tuya.

**1. Apunta al estado del arte, una sola vez.** Antes de escribir código para un
problema, averigua si ya está resuelto ahí fuera: papers, documentación,
repositorios, la respuesta de alguien que se topó con lo mismo. Si hay una
solución conocida y buena, **impleméntala** en vez de inventar la tuya. Y al
revés: **que BAXY ya lo haga de una manera no es razón para conservarla.** La vara
es «¿es la mejor opción conocida hoy?», no «¿es lo que había?».

Es una pasada, no una persecución. En cuanto tengas algo que cumple el objetivo,
deja de buscar mejor: perseguir el estado del arte sin parar es una carrera sin
final, y este producto tiene que salir.

**2. Nada de sobreingeniería.** Escribe el mínimo código que cumpla, y que se
active sólo el necesario. Nada de capa sobre capa, ni abstracciones para un
segundo caso que no existe, ni opciones que nadie pidió, ni defensas para fallos
que nadie ha visto ocurrir.

No es estética: es la causa de muerte documentada de las cuatro versiones
anteriores de este mismo proyecto. Carter se diagnosticó a sí mismo —*«el proyecto
crece por acumulación, no por reemplazo»*— con tres routers en serie, ocho capas
de reescritura y un `agent.py` de 1.397 líneas contra su propio objetivo de 400.
Diez de sus dieciséis segundos por turno eran sobrecarga suya.

**Si añades una capa, retira la que sustituye, en este mismo goal.** Un goal que
cierra con menos código del que encontró y el objetivo cumplido es mejor goal.

**3. Sólo se arregla lo que bloquea.** Un fallo que impide usar BAXY o avanzar
este goal se arregla. Una fragilidad teórica o un camino de error que nadie ha
recorrido: una línea en `documentacion/APLAZADOS.md` y sigues. El goal 11 existe
para vaciar esa lista, así que nada se pierde por anotarlo.

**4. Lo más ligero que cumpla.** 4 GB de VRAM es el techo, no el objetivo. Entre
dos opciones que cumplen gana la más ligera, contando RAM, disco, CPU en reposo y
arranque en frío. El ahorro se detiene donde BAXY deja de entender a la primera,
de no mentir o de no dejar silencio muerto.

---

## El objetivo

**Saber exactamente qué hay construido ya, qué de eso funciona de verdad, y qué
se trae a BAXY.**

En `C:\Users\usuario\Desktop\ETC\Programacion` hay años de intentos de construir
este mismo asistente con nombres distintos, y algunos tienen piezas que **ya
funcionan** — hay wake word y transcripción que llegaron a servir. Rehacer eso
sería tirar meses de trabajo, y los otros diez goals van mucho más rápido si
empiezan sabiendo qué existe y dónde.

Este goal va primero por eso, y porque la ley 1 lo necesita: no puedes juzgar si
BAXY está en el estado del arte sin saber qué tiene.

**No son proyectos distintos.** El README de `Probando Gemma 4` lo dice literal —
el proyecto se renombró a Baxy, antes Gemma 4 Agent, brevemente Carter. Es el
mismo proyecto reescrito cuatro veces, así que los errores documentados son de
esta casa. La excepción es `JRVS`, que es otro producto y no hereda nada.

## Las cuatro herencias que hay que ir a buscar

`00_IDENTIDAD.md` salió de leer estos repositorios y dejó localizadas cuatro cosas
que ya no son opcionales. Empieza por ellas:

1. **La accesibilidad del Baxy anterior** — control por voz para movilidad
   reducida y narración de cada acción para personas no videntes. El dueño la
   quiere de vuelta como identidad del motor. Averigua qué había implementado de
   verdad y qué era promesa de README.
2. **La cascada UIA → OCR → visión** para operar cualquier aplicación abierta. Es
   núcleo, no extra: sin ella no existe el `Click X` de una misión compuesta.
3. **El set consolidado de 16 herramientas de Carter v4** y la medición que le dio
   −68 % de tokens sin perder calidad. El goal 03 la necesita como punto de
   partida.
4. **Lo que FunctionGemma midió sobre cuantización y prosa** — Q2 produce palabras
   inventadas y rompe la persona; Q4_K_XL QAT lo arregla en ~1,5 GB. El BAXY
   actual tiene hoy el mismo síntoma.

Mira también lo demás: routers entrenados, catálogos de operaciones, corpus,
checkpoints, arquitecturas de memoria, integraciones de escritorio.

Pistas de dónde mirar primero: `Probando Gemma 4` tiene `captures/`,
`checkpoints/` y entornos de LiveKit y de entrenamiento de router; `FunctionGemma`
tiene `speech_model/` y `router/`; `Carter OS AI` tiene un `carter_v5` completo
con documentación. No te limites a esas tres.

## La documentación se hereda igual que el código

Estos repositorios acumulan decisiones de arquitectura, torneos de tecnología,
comparativas de modelos y registros de lo que se midió y se rechazó. Eso es tan
heredable como un checkpoint y más barato de traer: una comparativa ya corrida
ahorra días.

Deja inventariado **qué preguntas ya están respondidas y dónde**, para que ningún
goal posterior vuelva a correr un torneo que alguien ya corrió.

Y marca cuáles han **caducado**: una comparativa de hace ocho meses decidió entre
candidatos que hoy no son los mejores. Eso es exactamente la ley 1 aplicada al
pasado — distinguir lo vigente de lo caducado es parte del mapa, y lo caducado hay
que rehacerlo contra lo que existe hoy.

## Cómo decides qué se hereda

Una pieza se hereda si hace a BAXY mejor **como producto final**, y sólo entonces.
Tres filtros, en este orden:

1. **¿Funciona de verdad hoy?** No lo que el README promete: lo que ejecutas y ves
   funcionar. Un modelo que carga y acierta cuenta; un script que falla al
   importar, no.
2. **¿Sigue siendo la mejor opción conocida?** Ley 1. Que funcionara en 2025 no lo
   convierte en lo correcto hoy. Si el estado del arte lo dejó atrás, se anota como
   referencia y se hereda la idea, no el binario.
3. **¿Cabe en el presupuesto?** Un STT excelente que pide 8 GB de VRAM no sirve.

BAXY tampoco es una hoja en blanco: está avanzado y tiene cosas mejores que las de
sus predecesores. Heredar no es sustituir — es quedarse con lo mejor de cada sitio.

Si una pieza heredada exige tocar los invariantes de arquitectura, no se hereda:
se anota qué habría aportado y por qué no entra.

## Criterios de cierre

Marca cada punto. Mientras quede uno sin marcar y tengas una vía razonable, sigue.

- [ ] Un mapa que dice **qué intentos hubo**, qué se propuso cada uno, y por qué se
      abandonó.
- [ ] Para cada intento, **qué funciona hoy**, comprobado ejecutándolo — no leído.
- [ ] **Qué se hereda**, de dónde, y qué hace falta para traerlo.
- [ ] **Qué no se hereda y por qué.** Un rechazo con el mecanismo entendido vale
      tanto como una herencia.
- [ ] Las **cuatro herencias obligatorias** resueltas: existe / no existe / existía
      a medias, con evidencia en cada caso.
- [ ] El inventario de **preguntas ya respondidas y dónde**, separando lo vigente
      de lo caducado.

## Cuando lo cumplas

El mapa publicado en el repositorio, en un solo documento que los otros diez goals
puedan leer sin abrir nada más.

Publica el resultado aunque no sea perfecto, siempre que no mienta. Un goal que
cierra con un hallazgo honesto y una limitación nombrada vale más que uno que
sigue abierto buscando el mapa completo.

Y anota en `documentacion/APLAZADOS.md`, en una línea cada cosa, lo que viste y no
perseguiste.
