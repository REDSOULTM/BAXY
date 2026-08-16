# Goal 03 — La comprensión

> **Esto es un goal, no una tarea.** Se lanza y corre hasta cumplirse. No pares a
> mitad a pedir aprobación ni a preguntar: ante una duda, elige la opción más
> razonable, anótala y sigue. Acabas cuando los criterios de cierre estén
> marcados, o cuando hayas medido que uno es inalcanzable y publicado la evidencia
> que lo demuestra. No hay una tercera forma de acabar.

## Dónde trabajas

Repositorio: `C:\Users\usuario\Desktop\ETC\Programacion\BAXY Definitivo`.
Rama: `main`. Modelo: GPT-5.6 Sol, `reasoning.effort: high`.

**Ojo con el nombre.** En la misma carpeta `Programacion` hay un repositorio
llamado `BAXY` a secas: ése es el intento anterior y es **fuente de herencia, no
tu sitio de trabajo**. Todo lo que escribas va en `BAXY Definitivo`.

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

## Las cinco leyes

Gobiernan este goal y los otros diez. Están por encima de cualquier preferencia
técnica tuya.

**1. Hereda primero, estado del arte después, construye al final.** En ese orden,
y sin saltarte pasos:

1. **¿Ya está resuelto en un BAXY anterior?** Este proyecto se ha escrito cuatro
   veces y muchos problemas ya cayeron. Trae esa solución — o la **mejor
   combinación** de las que hay, que muchas veces es lo que gana.

   **Empieza en [`biblioteca/00_INDICE.md`](../../biblioteca/00_INDICE.md).** Son
   1.350 documentos de las cuatro escrituras anteriores —estudios, auditorías,
   investigaciones encargadas, benchmarks y rechazos con el mecanismo entendido—
   indexados por qué pregunta responde cada área. Si buscas algo concreto,
   [`biblioteca/01_INVENTARIO.md`](../../biblioteca/01_INVENTARIO.md) los lista
   todos con su título y su fecha.

   Abrir una línea de investigación sin haber buscado ahí primero es la forma más
   cara de perder un día.
2. **¿Está resuelto ahí fuera?** Papers, documentación, repositorios, la respuesta
   de alguien que se topó con lo mismo. Si hay una solución conocida y buena,
   **impleméntala** en vez de inventar la tuya.
3. **Sólo si ninguna de las dos**, constrúyelo. Y entonces di en el cierre por qué
   ninguna servía.

Y al revés: **que BAXY ya lo haga de una manera no es razón para conservarla.** La
vara es «¿es la mejor opción conocida hoy?», no «¿es lo que había?». Heredar es
traer lo que funciona, no conservar lo que estaba.

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

**5. Cada pieza sustituible, y ninguna más.** BAXY no se termina. Dentro de dos
meses saldrá un STT mejor o un modelo más pequeño que entiende igual, y hay que
poder cambiarlo sin reescribir el producto: **el código de hoy no tiene por qué ser
el de mañana**.

Esto va en **dos niveles**, y confundirlos es el error que lleva a la
sobreingeniería que prohíbe la ley 2.

**Nivel 1 — la forma, y aplica a todo lo que escribas.** No cuesta nada: es
escribirlo bien.

- **Una responsabilidad por pieza.** Si describirla necesita la palabra «y» tres
  veces, son tres piezas. `MainWindowViewModel`, con 3.678 líneas y 169 miembros,
  es el contraejemplo y está en este repositorio.
- **Nadie conoce las tripas de nadie.** Se depende del qué, no del cómo. Si cambiar
  el interior de A obliga a tocar B, no hay borde entre A y B.
- **Las dependencias apuntan hacia dentro.** `Contracts` no depende de nada,
  `Kernel` sólo de `Contracts`. Nunca al revés.
- **Nada global y mutable.**
- **Cero código muerto.** Lo sustituido se borra en el mismo cambio; dos
  implementaciones vivas de lo mismo son la acumulación con otro nombre.

**Nivel 2 — el mecanismo de cambio, y sí cuesta trabajo.** Por eso lo llevan las
piezas del registro de `documentacion/03_COSTURAS.md`: las que de verdad se van a
comparar contra un candidato. Son tres cosas y sin las tres la pieza no es
sustituible de verdad: el borde del nivel 1, **la medición que decide si el
candidato es mejor**, y la declaración en el manifiesto para que el cambio no pueda
ser silencioso.

Lo del medio es lo que suele faltar y lo que de verdad importa: con un corpus y un
número, cambiar de motor es una tarde; con una interfaz preciosa y sin número no
puedes decidir si mejoraste, así que no lo cambias nunca.

Lo que **no** se escribe: una interfaz con un solo implementador «por si algún
día», un registro de plugins, o configuración para elegir entre implementaciones
que no existen. Eso no es modularidad, es peso.

Si este goal toca una pieza del registro, **rellena su fila antes de cerrar**: qué
medición decide un sustituto, qué elegiste y por qué, y la fecha. La fecha importa
— una medición de hace ocho meses decidió entre candidatos que hoy ya no son los
mejores.

## Y una consigna que une las cinco

Ésta es la **quinta** escritura de BAXY, y tiene que ser **la más rápida de las
cinco**. No porque haga menos —es la definitiva— sino porque **no vuelve a
descubrir nada que ya se descubrió**.

Cada hora que gastes re-derivando algo que ya está medido en estos repositorios es
una hora que este proyecto ya pagó una vez. Si te encuentras diseñando desde cero
algo que suena a que alguien ya resolvió, para y ve a buscarlo primero.

---

## El objetivo

**La persona escribe cualquier cosa y BAXY llega a la operación correcta, o
pregunta algo que de verdad le falta.** En español, en inglés y en spanglish, y
sin depender de que use las palabras exactas del catálogo.

Hoy no lo hace. Cuando la petición sale de la gramática del reconocedor
determinista, el camino por modelo sirve **1 de 21**. Ese es el bloqueante del
producto: es lo que atiende a la persona en cuanto se sale del guion.

Y es personal para el dueño: cuando se le preguntó en qué momento dijo «esto no
va» sobre los intentos anteriores, respondió **cuando no acertaba la herramienta**.
Este goal es ese momento, con arreglo.

Apunta a **≥ 90 %** sobre paráfrasis que el sistema no ha visto, con la tasa
**partida por causa** — recuperación, decisión, vetos. Los tres tienen arreglos
opuestos, y un número mezclado manda el siguiente cambio al blanco equivocado.

Y una condición que no se negocia: **las peticiones fuera de catálogo llegan a la
decisión con cero candidatos.** Hoy llegan con hasta veintiocho. «Pide un taxi
para las ocho» no puede tener veintiocho operaciones delante esperando a que el
modelo elija una.

## Antes de investigar nada: esto ya se ha resuelto aquí

**No empieces este goal diseñando.** Empiézalo buscando.

Este problema —llevar lenguaje libre a la operación correcta— se ha abordado en
**cada una de las cuatro escrituras de BAXY**, y en varias se resolvió. Hay routers
entrenados, corpus reales, catálogos consolidados y torneos ya corridos en
`Probando Gemma 4`, `FunctionGemma` y `Carter OS AI`. El goal 01 dejó el mapa.

La instrucción del dueño es literal:

> Este problema ha sido abordado en cada BAXY, y muchas veces solucionado; sólo se
> debe exportar la mejor solución **o la mejor combinación de soluciones**.

Lo segundo importa tanto como lo primero. Puede que el mejor recuperador esté en un
repositorio, el mejor decisor en otro, y el corpus de evaluación en un tercero.
Combinarlos es una respuesta válida y probablemente la buena.

Sólo cuando hayas agotado eso, mira el estado del arte de fuera. Y sólo si tampoco,
construyes — diciendo en el cierre por qué ninguna servía.

## El catálogo: máxima cobertura, mínimo número

El catálogo creció por acumulación y nadie decidió el crecimiento: 67 herramientas
→ 31 en el set lean → **16 en Carter v4** → **158 operaciones hoy**. Carter midió
que consolidar a 16 daba **−68 % de tokens sin perder calidad**.

La decisión del dueño, en sus dos partes:

> Un set consolidado que cubra el máximo de casos, sin herramientas que no tienen
> sentido. Una herramienta hace una cosa. Y lo que no se logra con una, se logra
> con misiones compuestas: «Abre Steam y ve a la biblioteca» → `Open App` →
> `Click X`.

> Tienen que haber las máximas herramientas para cubrir todo el uso del PC de un
> usuario, pero éstas tienen que ser las mínimas posibles. **No reducir cobertura:
> hacer más con menos.**

**Eso no es un mandato de consolidar: es una función objetivo con dos términos, y
el orden importa.**

1. **La cobertura no baja.** Si una operación desaparece y con ella desaparece algo
   que el usuario podía hacer, es una pérdida, no un ahorro — ni siquiera si sube
   el acierto. Recortar el catálogo para que el decisor acierte más es hacer trampa
   en este goal.
2. **Con la cobertura intacta, gana siempre el número menor.**

Por eso **publicas dos números, no uno: cobertura y cuenta.** Un catálogo de 16 que
cubre menos que el de 158 no ha cumplido. Uno de 40 que cubre lo mismo, sí.

Necesitas por tanto una **medida de cobertura** definida antes de tocar el catálogo
—qué puede hacer el usuario hoy, enumerado— para poder demostrar que no bajó. Si no
la defines antes, no vas a poder distinguir consolidar de amputar.

Y hay una tercera vía que no gasta ninguno de los dos términos: **encadenar**. Lo
que no cabe en una herramienta no se resuelve añadiendo otra, se resuelve con una
misión compuesta, y eso amplía cobertura sin añadir una entrada al catálogo. Es la
palanca principal de «hacer más con menos», y por eso este goal y el 07 se deciden
juntos: si consolidar te deja un hueco, comprueba primero si lo cierra una cadena.

El criterio de qué entra, también decidido: **cubrir el PC, no las apps**. Todo lo
que Windows permite hacer —ventanas, audio, ficheros, aplicaciones, sistema—; nada
específico de una aplicación concreta. Y aquí hay trabajo real, no teoría: el BAXY
actual tiene **190 menciones de Steam y 94 de Spotify** en `src/`, con adaptadores
dedicados (`SpotifyDesktopAdapter`, `SteamLocalAdapter`, `YouTubeMpvAdapter`,
`WindowsCalculatorOpenProvider`) y scripts `.ps1` por aplicación. Eso es cobertura
falsa: cubre cuatro apps, no el PC. Sustituirlo por capacidad genérica es a la vez
menos catálogo y más cobertura — exactamente lo que pide este goal.

Lo que decides **tú, midiendo**:

- **El número**, sujeto a que la cobertura no baje.
- **La forma.** Paramétrica (`audio.control(accion, valor)`) contra específica
  (`subir_volumen`, `bajar_volumen`, `silenciar`). Compara ambas con datos reales y
  quédate con la que más acierte por token **a igual cobertura**.

Y una trampa: consolidar sube el acierto de la decisión y baja la expresividad del
argumento. Si mueves trabajo del catálogo al relleno de parámetros, mídelo también
ahí — un acierto de herramienta del 100 % con argumentos mal rellenados no es una
mejora, es la misma pérdida en otro sitio.

## Lo que ya se midió — no lo pagues dos veces

Cada línea de aquí costó una corrida. Están en el registro con su evidencia.

**Dónde se pierde.** De 21 filas servibles: la recuperación ofreció la esperada en
8, la decisión cruda eligió bien en 7, la decisión final conservó 1. De las 20
perdidas, sólo 6 las mató un veto — las otras 14 se pierden aguas arriba. De 31
vetos publicados, 25 retiraron una propuesta equivocada e hicieron su trabajo.
**El problema no son los vetos.**

**El recuperador sólo se consulta donde peor discrimina.** Seis de siete peticiones
servibles llegan con cero candidatos porque el camino determinista las resuelve
antes; fuera de catálogo entrega candidatos en 9 de 9 casos.

**Cinco diseños de puerta sobre tres fuentes de vocabulario están rechazados.** No
escribas un sexto gate léxico. R116, R117, R124 (dos veces), R126.

**Abstención semántica: rechazada dos veces.** BGE-M3 por familia (R236) y un
clasificador directo de 32 vías (R250). Ninguno separa dentro de catálogo de fuera.

**Siete fuentes externas rechazadas** para cubrir las seis operaciones
`office.word.*` sin ningún alias (R258–R262, R268, R269).

**El modelo activo no es el que dice la documentación vieja.** El manifest
registrado apunta a Gemma-4 E2B, y la ruta de decisión que toma es
`_post_schema_object` con `TURN_POLICY_PROMPT`, que ya ofrece cuatro modos
—`conversation`, `clarify`, `action`, `plan`— e instruye explícitamente abstenerse
cuando la capacidad no está entre los candidatos. **El modelo tiene la salida y
elige efecto igualmente.** Eso pone la causa en el tramo de decisión, no en el
contrato. Comprueba con qué modelo se midió cualquier hallazgo antes de aplicarlo:
`artifacts/runtime/registered_runtime_expectation_r281.json` declara el runtime
activo.

**Modelos decisores ya medidos y rechazados localmente frente a Qwen3-4B:**
Qwen3.5-4B, Phi-4-mini y Qwen3-4B-Instruct-2507. No los vuelvas a descargar sin
una razón nueva.

## Cómo eliges el camino

Las palancas vivas son el **catálogo**, el **reconocedor**, el **recuperador** y el
**modelo decisor**. Cuál mueves, y si mueves más de una, lo decides tú.

Aplica la ley 1 aquí con ganas: enrutar lenguaje libre a un catálogo de
herramientas es un problema **muy** resuelto ahí fuera, y se ha movido rápido.
Antes de afinar lo que hay, averigua qué se está usando hoy —cómo se recupera,
cómo se decide, cómo se abstiene— y si hay una solución conocida que encaje,
implántala. Que BAXY lleve dos años con un diseño no lo justifica.

Y elige **el más ligero que cumpla**: si un modelo más pequeño entiende igual de
bien, ése es el correcto, y merece la pena buscar activamente si existe. Un decisor
que resuelve el goal con 8 GB de VRAM no sirve, porque BAXY corre en el portátil de
una persona normal y compite con lo que esa persona está haciendo de verdad.

Cuidado con ampliar listas a mano: el reconocedor y la puerta de dominio son listas
mantenidas a mano y crecen una superficie cada vez. La puerta deja 49 de 158
operaciones sin ninguna regla curada. Si eliges esa vía, mide primero la cobertura
por operación y di por qué esa cuenta termina. Y ojo — una lista que crece cada vez
que falla un caso es exactamente la acumulación que mató a las cuatro versiones
anteriores.

## Cómo mides sin engañarte

Necesitas un oráculo que **pueda contener el fallo**. El corpus vigente lo generó
una gramática que no sale de la gramática del reconocedor, así que su 700/700 no
dice nada sobre formulación libre. Si construyes uno nuevo, demuestra que es
independiente: mide qué fracción de sus filas resuelve `resolve_explicit_effects`
y publica ese número junto al resultado.

Nunca midas sobre el corpus que el componente ya posee. Instrumenta el crudo: qué
se ofreció al modelo y qué propuso **antes** de que ningún veto lo toque. Lee los
textos visibles, no sólo las decisiones contractuales — una decisión correcta puede
acompañar una respuesta inservible.

Antes de adoptar una reparación, tásala contra lo que hoy funciona, no sólo contra
las filas rotas, y di qué población podría haberla refutado.

## Lo que no puedes romper

Ganar exactitud reabriendo un efecto no solicitado es un rechazo, no una mejora.
Los tres ceros se conservan: 0 efectos no pedidos, 0 éxitos no verificados, 0
respuestas visibles fijas.

`V9` es el único sello ciego sin consumir. No lo abras hasta tener un candidato que
acreditar.

## Criterios de cierre

- [ ] ≥ 90 % sobre paráfrasis frescas, con la tasa **partida por causa**.
- [ ] Las peticiones fuera de catálogo llegan a la decisión con **cero candidatos**.
- [ ] **Cobertura y cuenta publicadas juntas**, con la cobertura medida antes y
      después: no bajó.
- [ ] El número y la forma del catálogo **justificados midiendo**, no eligiendo.
- [ ] El acierto de argumentos medido aparte, para que la ganancia no se haya
      mudado de sitio.
- [ ] Los tres ceros intactos.
- [ ] Publicado **qué heredaste y de dónde** — y sólo si no heredaste nada, por qué
      ninguna de las soluciones anteriores servía.
- [ ] El LLM decisor sigue **detrás de la frontera de proceso** y declarado en el
      manifiesto con su hash: cambiarlo mañana no debe recompilar nada.
- [ ] Rellenas las filas de `03_COSTURAS.md` que te tocan —LLM decisor, runtime,
      recuperador, reconocedor, forma del catálogo— con la medición que decide un
      sustituto.

## Cuando lo cumplas

La medición partida por causa, sobre población fresca, y el catálogo resultante.

Si la conclusión honesta es que ningún modelo local de este tamaño llega,
publícala con la frontera medida — eso también cierra el goal, y vale más que un
número inflado.

Y anota en `documentacion/APLAZADOS.md`, en una línea cada cosa, lo que viste y no
perseguiste.
