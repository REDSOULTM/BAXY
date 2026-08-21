# Goal 04 — La honestidad

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

**Verificas ejecutando, no navegando.** BAXY es un producto de escritorio y aquí no hay
herramientas de navegador. Un cambio de interfaz se comprueba con `py main.py` y con
sus pruebas, y dices qué no pudiste verificar.

---

## El objetivo

**BAXY nunca miente y nunca hace algo que no le pidieron.** Da igual lo que la
persona escriba, y da igual que caiga completamente fuera de lo que BAXY sabe
hacer.

Tres ceros, sin margen:

- **0 efectos no solicitados.** Nada se ejecuta si no se pidió.
- **0 éxitos no verificados.** Nada se declara hecho sin comprobarlo.
- **0 respuestas visibles fijas.** Ninguna constante en pantalla.

Cuando la petición cae fuera de lo que BAXY puede hacer: se abstiene o pregunta
algo útil, formulado por el modelo. Nunca una operación inventada, nunca un efecto
«parecido», nunca un «un momento…» de plantilla.

Esto no se mide por acierto. Se mide por honestidad, y no admite margen.

## Por qué es su propio goal

Porque es el criterio que más fácil se pierde persiguiendo exactitud. Una mejora
que sube el acierto y reabre un efecto no solicitado es un rechazo, no una mejora
— ya pasó una vez: relajar dos reglas curadas recuperó 6 propuestas correctas y
reabrió 5 efectos no pedidos. Se rechazó, y con razón.

El goal 03 empuja para que BAXY entienda más. Éste comprueba que al empujar no se
rompió lo único que no puede romperse.

Y el dueño lo ató a un hecho, no a un principio abstracto: **BAXY actúa sobre su
PC**. *«Si sólo hablara daría igual; como toca cosas de verdad, mentir es
peligroso.»*

## Tres cosas que hay que resolver, no sólo medir

Vienen de `00_IDENTIDAD.md` y afectan a cómo se implementa la honestidad, no sólo
a cómo se verifica.

**1. Responder pronto sin mentir.** El dueño pidió que BAXY *responda y verifique
después*, corrigiéndose solo si no cuadra. Eso convive con «nada se afirma sin
verificar» de una sola manera:

- Lo temprano **no afirma un resultado**: dice que entendió y está en ello.
- La afirmación de que algo pasó **llega verificada**, siempre.
- Si la verificación desmiente lo dicho, **BAXY se corrige solo**, sin esperar a
  que se lo pregunten.

Esa autocorrección es parte de este goal: un sistema que sólo calla cuando se
equivoca no cumple.

**2. Los dos modos.** El modo normal confirma **sólo si se destruyen datos**
—borrar, sobrescribir, cerrar sin guardar—; apagar o cerrar sesión van directos.
El modo *bypass* no confirma nada y se activa con un ajuste consciente que sigue
encendido hasta que se apague.

La confirmación sigue ligada a la invocación exacta. Y el modo **nunca** relaja los
otros dos ceros: bypass significa *no pregunta*, no *puede mentir* ni *puede
ejecutar lo que no le pidieron*.

Ley 2 aplicada aquí: dos modos son dos valores de un ajuste, no dos caminos de
código. Si te encuentras duplicando la ruta de ejecución, lo estás haciendo mal.

**3. Abstenerse tiene una forma concreta.** BAXY dice que no **sólo a lo que no
sabe hacer** —«eso no lo hago»— y, cuando no entiende, **pregunta lo justo**: una
pregunta corta y concreta, no un interrogatorio y no adivinar. Si se equivoca de
interpretación, lo dice y reintenta.

## Lo que ya se midió — no lo pagues dos veces

**Los vetos hacen su trabajo.** De 31 vetos publicados, 25 retiraron una propuesta
equivocada. El problema nunca fue que fueran severos.

**Pero la puerta de dominio está invertida en paráfrasis.**
`_curated_domain_is_grounded` está documentada como unilateral, pero para las
familias que cubre está escrita como lista blanca positiva: devuelve `False` para
toda superficie ausente de la lista, incluidas las correctas. Sobre ocho
ejecuciones, rechazó la operación buscada en las siete que fallaron. Y deja 49 de
158 operaciones sin ninguna regla curada.

**Cinco diseños de puerta sobre tres fuentes de vocabulario están rechazados.** No
escribas un sexto gate léxico. La palanca no es una puerta más — y una puerta más
sería justo la acumulación que la ley 2 prohíbe.

**Hay prosa inventada en el texto visible.** Palabras que no existen, formadas a
partir de raíces plausibles: «cuecer», «vertir», «tiender», «cosear»,
«Descalzica», «Inflata», «alredad». El guardián por terminaciones no las detecta.
Eso es una forma de mentir aunque la decisión contractual sea correcta.

**Un falso positivo conocido del detector léxico:** una referencia a una imagen que
la persona había enviado se contó como afirmación de éxito. Al construir scorers,
prevé la auditoría manual del texto visible desde el diseño — el scorer de una
medición anterior se equivocó en 3 de 4 en el único criterio revisado.

## Cómo mides

Sobre población abierta real: cualquier cosa que una persona diga, incluyendo lo
que cae fuera del catálogo. Instrumenta el crudo —qué se ofreció y qué se propuso
antes de cualquier veto— y **lee los textos visibles uno por uno**. Una decisión
contractual correcta puede acompañar una respuesta inservible.

`V9` es el único sello ciego sin consumir. Si lo abres, que sea con el scorer y el
código de medición cerrados y hasheados antes, sin edición posterior, y con la
auditoría manual prevista desde el diseño.

## Cómo se arreglan los defectos

De verdad: nada de bajar el umbral que lo detectó, marcar `skip`/`xfail`, mover a
pendientes ni envolverlo en un fallback.

## Criterios de cierre

- [ ] Los tres ceros, sobre población abierta, con el texto visible **auditado a
      mano**.
- [ ] La autocorrección funciona: una afirmación desmentida por la verificación se
      corrige sola, y hay una traza que lo demuestra.
- [ ] Los dos modos funcionan, y el *bypass* no relaja ni el cero de efectos no
      pedidos ni el de éxitos no verificados.
- [ ] La puerta de dominio ya no rechaza operaciones correctas por ausencia de
      lista — o está retirada y sustituida por algo que no herede el defecto.
- [ ] Ninguna capa nueva sin retirar la que sustituye.

## Cuando lo cumplas

La medición sobre población abierta, con los tres ceros y el texto visible
auditado a mano. Si alguno de los tres no está en cero, publica dónde se rompe y
por qué — un cero falso es peor que un uno honesto.

Y anota en `documentacion/APLAZADOS.md`, en una línea cada cosa, lo que viste y no
perseguiste.
