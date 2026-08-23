# Goal 08 — La primera señal

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

**Nunca hay silencio muerto.** La persona escribe y algo pasa: un acuse, el
principio de una frase, una acción visible.

- Primera señal: **p50 ≤ 1,0 s y p95 ≤ 2,0 s**.
- Acción simple completa y verificada: p50 ≤ 2,5 s.
- Misión compuesta: sin techo fijo, pero narrando un hito cada ≤ 3 s de trabajo sin
  salida visible.

O la **mejor frontera Pareto demostrable**, si mides que el techo es inalcanzable
sin ceder exactitud o seguridad. Un rechazo medido cierra el goal igual que un
éxito; un número inventado, no.

## El listón real del dueño, y por qué cambia la forma de la señal

Los números de arriba son el objetivo de diseño. El listón crudo, en sus palabras,
es otro: **más de 3 s sin señal y cierra la ventana y lo hace a mano**. Y sobre
cuánto puede tardar BAXY respondió **«depende de la tarea»** — abrir Spotify es
instantáneo, una misión compuesta puede tardar y está bien.

Lo que hay que garantizar no es un tiempo de respuesta uniforme: es que **nunca
pasen 3 s en silencio**, en ninguna tarea, incluidas las largas.

Y hay una decisión suya que cambia **cuándo** se emite la señal:

> Si va a tardar poco, calla y responde. Si va a tardar, avisa.

O sea: **la señal temprana no es incondicional**. En un turno que se resuelve en
900 ms, un acuse previo es ruido. BAXY tiene que estimar antes de responder si va a
pasarse del silencio tolerable, y avisar sólo entonces. Cómo se estima eso —coste
del camino elegido, número de pasos de la misión, historial— es tuyo, y aplica la
ley 2: una heurística de dos líneas que acierte vale más que un predictor.

**Y la señal temprana nunca afirma un resultado.** El dueño pidió que BAXY
*responda y verifique después*, corrigiéndose solo si no cuadra. Eso convive con
«nada se afirma sin verificar» de una sola manera: lo temprano dice que entendió y
está en ello; la afirmación de que algo pasó llega verificada, siempre; y si la
verificación desmiente lo dicho, BAXY se corrige solo. Una señal temprana que diga
«abriendo Spotify» y acabe sin Spotify abierto **es una mentira**, aunque llegue
rápido.

## Dónde está hoy

La latencia mala es exactamente la de los turnos que caen al camino por modelo —
los mismos que fallan en exactitud. De 17 peticiones, 9 las resuelve el reconocedor
en ≤ 0,071 s; las otras 8 van de 0,698 s a 2,957 s. p95 del producto: **2,668 s**.
En el camino por modelo puro se midió p50 2,440 s y p95 4,109 s. Arranque en frío:
4,154 s.

Descomposición por llamada, mediana: `turn_policy_native_tools` **2,0379 s**,
`conversation_reply` 0,8867 s, `semantic_effect_guard` 0,5103 s,
`operation_compatibility` 0,4055 s, `final_writers` 0,3381 s, `response_language`
0,1705 s.

**La llamada de decisión primaria sola cuesta más que la barra entera.** Y la suma
de las llamadas es prácticamente el turno completo: 3,37 s de 3,39 s. No hay
sobrecarga escondida que recortar — hay que hacer menos trabajo o hacerlo en
paralelo.

Ojo a esa lista de seis llamadas: **son seis pasadas por modelo para un turno**.
Antes de optimizar cada una, pregúntate cuántas hacen falta de verdad. El dueño,
puesto a elegir entre ser más listo y quitarse sobrecarga, eligió **quitarse
sobrecarga primero**.

## Lo que ya se midió — no lo pagues dos veces

**Streaming está rechazado como palanca.** Techo de ganancia 0,33 s; faltan
0,668 s. R132.

**El acuse temprano de plantilla está rechazado.** Viola el invariante de cero
respuestas visibles fijas: un «un momento…» constante es exactamente el defecto que
la barra existe para evitar. La señal temprana tiene que ser prosa formulada.

**Recortar el shortlist compra ~1,0 s.** Veintiocho herramientas y 9 KB cuestan
2,4–2,6 s; dos herramientas y 1,8 KB cuestan 1,27–1,72 s. Quedan ~1,3 s
irreducibles a `max_tokens=96`. R134.

**El mismo defecto paga dos veces.** Recortar el shortlist compra ese segundo *y*
quita veintiocho oportunidades de elegir mal. Si el goal 03 ya consolidó el
catálogo, parte de esto está hecho — mídelo antes de rehacerlo.

**Aviso pagado con una corrida:** un shortlist recortado a ojo puede tirar la
operación correcta. Mide la discriminación sobre población suficiente antes de
cortar.

## Cómo mides

Sobre una población que **incluya turnos que el reconocedor no resuelve**. Medir
sólo los que resuelve la gramática da 0,071 s y no significa nada: son precisamente
los que ya iban bien.

Congela el árbol antes de medir. Editar código con una corrida en vuelo la invalida
— mata la corrida, borra la telemetría parcial, relanza.

Publica también el perfil CPU con sus propios techos medidos. BAXY nunca miente ni
actúa distinto por correr en CPU: sólo tarda más.

## Lo que no puedes romper

Sin regresión en exactitud ni en los tres ceros. Ganar 800 ms reabriendo un efecto
no solicitado es un rechazo. Y BAXY no le pelea la máquina a su dueño: si hay carga
interactiva pesada en primer plano, cede recursos.

## Criterios de cierre

- [ ] Los números, sobre población que incluya lo difícil, con el perfil CPU aparte.
- [ ] **Ninguna tarea, de ninguna duración, pasa 3 s en silencio.**
- [ ] La señal temprana es condicional —sólo cuando se prevé tardar— y es prosa
      formulada, no una constante.
- [ ] Ninguna señal temprana afirma un resultado, y la autocorrección funciona
      cuando la verificación desmiente.
- [ ] Publicado cuántas llamadas por modelo quedan por turno y por qué cada una
      sigue ahí.
- [ ] Sin regresión en exactitud ni en los tres ceros.
- [ ] **Publicado.** `git status --short` vacío y
      `git rev-list --count origin/main..main` en **0**: todo lo del goal está en
      `origin/main`. Un goal con el trabajo sólo en este PC no está cerrado, por
      verdes que estén los demás criterios.

## Cuando lo cumplas

Los números publicados. Si la conclusión es la frontera Pareto, publícala con el
rechazo medido y di exactamente qué habría que ceder para llegar a la barra.

Y anota en `documentacion/APLAZADOS.md`, en una línea cada cosa, lo que viste y no
perseguiste.
