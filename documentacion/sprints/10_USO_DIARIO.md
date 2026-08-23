# Goal 10 — El uso diario

> **Esto es un goal, no una tarea.** Se lanza y corre hasta cumplirse. No pares a
> mitad a pedir aprobación ni a preguntar: ante una duda, elige la opción más
> razonable, anótala y sigue. Acabas cuando los criterios de cierre estén
> marcados, o cuando hayas medido que uno es inalcanzable y publicado la evidencia
> que lo demuestra. No hay una tercera forma de acabar.

## Dónde trabajas

Repositorio: `C:\Users\usuario\Desktop\ETC\Programacion\BAXY Definitivo`.
Rama: `main`. Modelo: **Grok 4.6**, esfuerzo `high`.

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

## Cómo trabajas aquí

No es estilo: es lo que esta máquina y este harness te dan, y lo que este repositorio
ya midió que hace falta decir.

**Esfuerzo `high` de suelo.** Súbelo con `/effort xhigh` en el tramo que lo merezca —un
diseño abierto, un fallo que no se explica— y bájalo después. Cada peldaño multiplica
los tokens de razonamiento, y este goal está escrito para `high`.

**Busca y lee con tus tools, no con la shell.** `grep` es ripgrep por dentro: acótalo a
`src tests scripts main.py` salvo que vayas a la evidencia a propósito, y pide rutas
antes que líneas. Lee rangos con `read_file`, no ficheros enteros. En la shell **no
existe `rg`**: es PowerShell, y `run_terminal_command` es para git, pytest, dotnet y
procesos. Antes de abrir algo grande, mira el tamaño: `git ls-tree -r -l HEAD -- ruta`.

**Lo que tarda, en segundo plano.** Corridas de medición, compuerta y builds Release se
lanzan en segundo plano y sigues con trabajo independiente; recoges el resultado con
`get_command_or_subagent_output`, sin sondear en bucle.

**Sin subagentes.** `spawn_subagent` hereda tu modelo: paga otra vez contexto y
razonamiento para devolverte un informe que además tienes que leer. Esto se resuelve en
el hilo principal. Única excepción: una exploración de sólo lectura acotada cuyo
resultado quepa en rutas + rangos + conclusión.

**El estado, escrito en el repositorio.** La ventana es de 500K y se compacta sola al
80 %: lo que sólo esté en la conversación se pierde. Deja el mapa, la medición y las
decisiones en ficheros a medida que avanzas, y haz commit después de cada paso medido.
Plantilla: `docs/AI_HANDOFF_TEMPLATE.md`.

**Y lo commiteado se empuja, en el mismo momento.** `git push origin main` detrás de
cada commit —no al final del goal—. El dueño trabaja en varias máquinas y lo que no
está en `origin` no existe para las demás: este repositorio llegó a acumular **101
commits sin publicar**, cinco goals de trabajo que vivían en un solo disco. Si el push
lo rechaza porque otra máquina empujó antes, `git pull --rebase origin main`, resuelves
y vuelves a empujar; no lo dejes pendiente.

**Verificas ejecutando, no navegando.** BAXY es un producto de escritorio y aquí no hay
herramientas de navegador. Un cambio de interfaz se comprueba con `py main.py` y con
sus pruebas, y dices qué no pudiste verificar.

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

## Este goal se mide en dosis, no en calendario

**Decisión del dueño, 2026-08-21: el producto sale antes de la semana de uso, no
después.** Esperar días de calendario para poder entregar retrasa el lanzamiento sin
comprarle nada al producto, y el uso continuado va a existir igual —de verdad y
todos los días— en cuanto BAXY esté terminado. No lo restaures.

Lo que una semana de uso compraba se compra de otra forma, y sigue siendo obligatorio:

| Lo que daba el calendario | Cómo se consigue ahora |
|---|---|
| Volumen y variedad de peticiones reales | Una **dosis medida** de turnos reales, concentrada |
| La fricción que sólo aparece repitiendo | **Repetir** lo que más se va a usar, no esperar a que se repita solo |
| Fugas, degradación, arranque día tras día | Un **encendido continuo** que corre solo mientras trabajas en otra cosa |
| Que se gane quedarse instalado | Eso lo dice el uso **después** de entregar, y no bloquea la entrega |

Lo que el uso real siga encontrando después del lanzamiento entra por
`documentacion/APLAZADOS.md` y se cobra en una tanda de mantenimiento. No desaparece:
deja de ser una puerta antes de entregar.

## Qué haces

Usarlo. De verdad, para cosas reales, hasta completar la dosis. Y arreglar lo que
salga.

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

- [ ] **≥ 200 turnos reales**, pedidos por el dueño en uso normal —no guionizados, no
      de corpus—, en **tres sesiones o más**, sin un solo momento en que BAXY afirme
      algo que no era cierto, ejecute algo que no le pidieron, o suelte una frase de
      plantilla. Un solo fallo de honestidad no se anota: se arregla y se repite la
      sesión.
- [ ] Dentro de esos turnos, **las cinco peticiones que más se van a usar, repetidas
      veinte veces cada una**. La fricción sale de la repetición, y ahí es donde se
      mide si algo cansa.
- [ ] **≥ 24 h de encendido continuo** con arranque automático y escucha permanente,
      mientras la máquina se usa para otra cosa, incluyendo **un apagado y encendido
      de Windows** dentro del tramo. Al final BAXY sigue despertando igual que al
      principio.
- [ ] Consumo en reposo medido y publicado **al principio y al final** de ese tramo:
      si sube, es una fuga y es un defecto, no una nota.
- [ ] Los dos modos, la narración y el panel de memoria comprobados **usándolos**.
- [ ] La compuerta verde sobre el árbol final del goal.
- [ ] El registro de lo que encontraste usándolo: arreglado, abierto, o dejado como
      está y por qué.
- [ ] **Publicado.** `git status --short` vacío y
      `git rev-list --count origin/main..main` en **0**: todo lo del goal está en
      `origin/main`. Un goal con el trabajo sólo en este PC no está cerrado, por
      verdes que estén los demás criterios.

## Cuando lo cumplas

BAXY usable, y el registro honesto de lo que encontraste. Más la lista de
limitaciones que quedan, nombradas una por una: las ambientales de verdad —causa
fuera del código de BAXY, que BAXY no puede reparar— se declaran y se cubren con un
degradado honesto. Las demás son bugs.

Y anota en `documentacion/APLAZADOS.md`, en una línea cada cosa, lo que viste y no
perseguiste.
