# Goal 10 — El uso diario

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

**BAXY se usa todos los días y no decepciona.**

No es una demo que funciona cuando le preguntas lo correcto. Es un asistente que
alguien abre por la mañana y usa hasta la noche, con lo que se le ocurra, en el
idioma que le salga, y que se gana quedarse instalado.

**Éste no es el adorno final: es la prueba del producto.** Cuando al dueño se le
preguntó qué evita una quinta reescritura del proyecto, respondió *que el producto
se use*; y qué tendría que pasar en un año para decir «esto sí quedó»: *que lo use
a diario sin pensarlo*. Los nueve goals anteriores existen para llegar hasta aquí.
Si BAXY sale de éste sin usarse, no sirvió ninguno.

## Cómo se rompe este goal

**La fricción de arrancarlo es lo que lo mata.** Por eso BAXY vive en la bandeja
del sistema, arranca con Windows y escucha siempre. Y lo que hay que quitarle de
encima al usuario, en sus palabras, es *levantarse del teclado*.

Ahí hay una tensión real que este goal tiene que resolver, no esquivar: **arrancar
siempre + escuchar siempre + hablar siempre** contra el presupuesto de recursos. La
salida no es recortar la presencia —ésa es una decisión del dueño— sino conseguir
que la presencia cueste poco. Mide el consumo en reposo y publícalo.

## Qué haces

Usarlo. De verdad, durante días, para cosas reales. Y arreglar lo que salga.

Esto no es un goal de medición sobre corpus: los nueve anteriores ya midieron. Éste
encuentra lo que ningún corpus contenía, porque el uso real siempre trae algo que
nadie anticipó.

Presta atención a lo que no se mide fácil:

- **Lo que cansa.** Una fricción que aparece cuarenta veces al día importa más que
  un fallo que aparece una vez al mes.
- **Lo que sorprende mal.** Momentos en que BAXY hace algo razonable según su lógica
  y raro según la de la persona.
- **Lo que no se pide dos veces.** Si algo funciona pero cuesta tanto pedirlo que la
  persona deja de usarlo, ese algo no funciona.

Y comprueba en uso —no leyendo el código— tres decisiones que sólo se verifican
viviendo con el producto:

1. **Los dos modos.** El normal confirma sólo si se destruyen datos; el *bypass* se
   activa con un ajuste consciente y sigue encendido hasta apagarlo.
2. **La narración** de lo que hace, y que BAXY se pueda usar entero sin ver la
   pantalla.
3. **La memoria y la privacidad.** BAXY recuerda preferencias, lo que se le suele
   pedir y la conversación reciente; y la persona puede **ver, editar y borrar** todo
   eso de verdad — no confiar en que un botón hace lo que dice. Y que **buscar en la
   web** funcione sin que salga nada del usuario.

## Aquí la ley 1 mira hacia fuera

Este goal es el único que compara BAXY con lo que la gente usa de verdad. El
montaje estándar de asistente local llega hoy a 1–2 s extremo a extremo con 12 GB de
VRAM y un modelo de 8B; BAXY apunta a 4 GB. Si llegas a algo comparable con una
cuarta parte de la memoria, eso es un resultado — publícalo.

Y si al usarlo descubres que una pieza tuya es notablemente peor que lo que
cualquiera se instala en una tarde, cámbiala. Que la hubiéramos construido nosotros
no es un argumento.

## Cómo se arreglan los defectos

De verdad: nada de bajar el umbral que lo detectó, marcar `skip`/`xfail`, mover a
pendientes ni envolverlo en un fallback. Lo que nadie ha visto ocurrir se anota y
se sigue.

Y un fallo de honestidad durante el uso diario es un defecto grave, no una
anécdota: significa que los corpus no lo contenían, y eso es exactamente lo que
este goal existe para encontrar.

## Lo que sigue en pie

Todo. Los tres ceros no se relajan porque el goal sea de uso. La compuerta sigue
verde. Los invariantes de arquitectura siguen siendo invariantes.

## Criterios de cierre

- [ ] **Una semana de uso diario** sin un solo momento en que BAXY afirme algo que
      no era cierto, ejecute algo que no le pidieron, o suelte una frase de plantilla.
- [ ] Consumo en reposo medido y publicado, con arranque automático y escucha
      permanente encendidos.
- [ ] Los dos modos, la narración y el panel de memoria comprobados **usándolos**.
- [ ] La compuerta verde sobre el árbol final del goal.
- [ ] El registro de lo que encontraste usándolo: arreglado, abierto, o dejado como
      está y por qué.

## Cuando lo cumplas

BAXY usable, y el registro honesto de lo que encontraste. Más la lista de
limitaciones que quedan, nombradas una por una: las ambientales de verdad —causa
fuera del código de BAXY, que BAXY no puede reparar— se declaran y se cubren con un
degradado honesto. Las demás son bugs.

Y anota en `documentacion/APLAZADOS.md`, en una línea cada cosa, lo que viste y no
perseguiste.
