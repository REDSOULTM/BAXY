# Goal 05 — La ejecución verificada

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
   combinación** de las que hay, que muchas veces es lo que gana. El goal 01 dejó
   el mapa de qué existe y dónde.
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

**Lo que BAXY dice que pasó, pasó — y hay algo independiente que lo comprueba.**

«Se envió el comando» no es «se completó la misión». Un resultado sólo se declara
cuando un verificador que no es quien lo ejecutó confirma el estado observable.

Y cuando algo sale mal, el estado terminal es honesto:

- `pending` significa exclusivamente **reintentable**.
- Un efecto externo ambiguo que no se puede reintentar es `failed` terminal con
  `effectMayHaveOccurred`, y no se replanea ni se repite a ciegas hasta reconciliar
  el estado.
- La confirmación se liga a la **invocación exacta**, no a la intención aproximada.

Éste es el goal que hace verdadera la frase que el usuario lee: *«Listo, Spotify
está abierto y sonando»*. Esa frase afirma dos estados observables, no un código de
retorno. Si BAXY no puede comprobar que suena, no puede decirlo.

## Qué cubre

El catálogo tipado que salga del goal 03, con sus efectos reales sobre esta
máquina: abrir aplicaciones, controlar ventanas, audio, sistema de archivos, notas,
tareas, recordatorios, capturas, navegador, medios, wifi, energía. Lo que BAXY dice
que puede hacer, tiene que hacerlo de verdad y saber si lo hizo.

Con providers habilitados y efectos reales. Éste es el goal donde BAXY toca la
máquina de verdad, así que trabaja sobre superficies que puedas dejar como estaban.

## Cómo se verifica de verdad

Por observación del estado, no por el código de retorno de quien ejecutó. Un
`app.open` se verifica mirando si la ventana existe; un `note.create` leyendo la
nota; un `audio.volume` consultando el nivel.

Aquí la ley 1 tiene un sitio concreto: **cómo se observa el estado de Windows de
forma fiable es un problema resuelto y documentado** —UI Automation, WMI, las APIs
del sistema, lo que la comunidad de automatización lleva años usando—. Antes de
escribir un verificador propio, mira qué se usa hoy para eso. Y antes de dar por
buena la forma en que BAXY lo hace hoy, comprueba que sigue siendo la mejor.

Y la ley 2: **un verificador por operación, no un marco de verificación.** Si te
encuentras construyendo una jerarquía de estrategias de verificación con registro
de plugins, para y escribe las comprobaciones directas.

## Lo que ya se sabe

**El kernel autoriza, el provider ejecuta. La mente sólo propone.** Ninguna
superficie —texto, corpus, skills, UI, modelos, prompts— puede agregar una
operación ni elevar su autoridad. Si algo necesita saltarse eso para funcionar, no
funciona.

**Ya se cerraron dos pérdidas de conservación** que habrían ejecutado un
subconjunto silencioso de la misión pedida. Es el fallo típico aquí: se pide A y B,
se ejecuta A, y nadie nota que B se perdió por el camino. Búscalo.

**Journal y replay** existen sobre respuestas terminales. Úsalos: son la forma de
demostrar qué pasó sin creerte lo que el sistema dice de sí mismo.

**Una operación sin regla curada de dominio puede ejecutarse sin que nada la
frene.** Eso es del goal 04 pero se paga aquí.

## Qué caminos de error persigues, y cuáles no

Los que **ocurren de verdad al usar BAXY** — y sobre todo uno: el provider que
informa éxito sin haber hecho nada, porque ése rompe el invariante central. Si te
topas con uno, ciérralo.

No inventes el catálogo completo de fallos posibles ni construyas defensas para
escenarios que nadie ha visto. Eso es una cadena de reparación sin final, es
exactamente lo que la ley 2 prohíbe, y el goal 11 existe para lo que quede.

## Criterios de cierre

- [ ] La matriz de operaciones con su verificación, **ejecutada de verdad** en esta
      máquina.
- [ ] Ningún resultado se declara con el código de retorno del ejecutor.
- [ ] Los estados terminales honestos funcionan: `pending` sólo reintentable, y el
      efecto ambiguo no reintentable acaba en `failed` con `effectMayHaveOccurred`.
- [ ] Un provider que miente no consigue que BAXY mienta. Pruébalo provocándolo.
- [ ] Las operaciones que **no se pueden verificar** están listadas con su razón.
- [ ] Cero marcos de verificación genéricos: comprobaciones directas.

## Cuando lo cumplas

La matriz publicada. Y la lista de lo que no se pudo verificar, con la razón: si el
sistema operativo no expone la API para comprobar algo, eso es una limitación
ambiental legítima — se nombra y se cubre con un degradado honesto.

Y anota en `documentacion/APLAZADOS.md`, en una línea cada cosa, lo que viste y no
perseguiste.
