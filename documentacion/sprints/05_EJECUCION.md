# Goal 05 — La ejecución verificada

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
