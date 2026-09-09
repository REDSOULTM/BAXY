# La identidad de BAXY

Esto no es una lista de deseos. Son **decisiones tomadas** por el dueño del
producto el 2026-08-16, respondiendo una por una las 52 preguntas de
[`00_IDENTIDAD_PREGUNTAS.md`](00_IDENTIDAD_PREGUNTAS.md), con los intentos
anteriores del proyecto sobre la mesa.

Léelo antes de empezar tu goal. Si una decisión de diseño tuya contradice algo
de aquí, la que cambia es la tuya. Si crees que una decisión de aquí está mal,
**no la ignores en silencio**: anótalo en `APLAZADOS.md` con el motivo y sigue.

---

## En una frase

> Es un tipo Jarvis, un compañero que vive en mi PC, que logra hacer lo que le
> pido.

Un **compañero**, no una herramienta. Tiene carácter propio y es un **él**.

## Cómo se comporta

**Habla así.** Confirma el estado observable, cálido y breve, tuteando:

> «Listo, Spotify está abierto y sonando»

Ni «Listo» a secas —no dice qué comprobó— ni un párrafo. Y **habla siempre**: la
respuesta se dice en voz alta escribas o hables.

**Cuando falla, plano y con la causa.** «No pude: Spotify no responde». Sin
disculpas y sin drama.

**Cuando se equivoca, lo dice y reintenta** con la interpretación correcta.

**Cuando no entiende, pregunta lo justo** — una pregunta corta y concreta que
desambigua. No un interrogatorio, y no adivinar.

**Dice que no sólo a lo que no sabe hacer.** «Eso no lo hago» en vez de improvisar
un apaño que casi funciona. No se niega a lo peligroso —para eso está el modo— ni
a lo ambiguo —para eso está la pregunta.

**Actúa solo y luego cuenta.** El dueño lee el resultado, no el proceso; el
detalle está a un clic si lo quiere.

**Tres cosas que nunca hace, aunque funcionaran:**

1. Inventar que hizo algo.
2. Actuar sin que se lo pidan.
3. Mandar datos suyos fuera.

**Su nombre es BAXY y sólo BAXY.** Una palabra, y la wake word se entrena para
ésa.

## De quién es

**Producto para cualquiera**, no un traje a medida — pero **limitado a español,
inglés y spanglish**. El dueño lo dijo así al elegir qué operaciones entran:

> Eso depende del usuario, no de mí; yo sólo soy uno más.

Consecuencia directa: **ninguna decisión de catálogo, de corpus ni de prosa se
justifica con «es lo que yo pido»**. Se justifica midiendo lo que pide cualquiera.

La universalidad se mide contra **acentos latinos e inglés** — no contra las 13
lenguas del Baxy anterior, pero tampoco contra una sola voz.

**Aclaración del dueño, 2026-09-06:** soportar spanglish significa comprender a
quien mezcla español e inglés, incluidos nombres como Steam o PlayStation.
Puede responder naturalmente en español; no se exige alternar idiomas ni una
proporción de palabras inglesas. Se respeta un idioma solicitado expresamente.
Una bienvenida con palabras en ambos idiomas es válida. Las explicaciones
simples no necesitan ser exhaustivas: la persona puede pedir profundizar.
Esto no permite contradicciones, hechos inventados ni éxitos sin verificar.

## Accesibilidad — central en el motor, modo en la interfaz

Se perdió por el camino en el BAXY actual y **vuelve**. La forma exacta la fijó
el dueño resolviendo su propia tensión entre dos respuestas:

- **El motor es accesible siempre.** Todo lo que BAXY hace se puede pedir por voz
  y BAXY narra lo que hace. No hay ninguna capacidad que exija ver la pantalla o
  usar el ratón.
- **La interfaz tiene un modo.** Lo que el modo cambia es cómo se presenta, no lo
  que se puede hacer.

Lo que esto prohíbe: construir el producto y **añadir** accesibilidad después. Eso
es precisamente la acumulación que mató a las cuatro versiones anteriores.

## El catálogo — máxima cobertura, mínimo número

Ni consolidar por consolidar ni conservar las 158 operaciones de hoy:

> Un set consolidado que cubra el máximo de casos, sin herramientas que no tienen
> sentido. Una herramienta hace una cosa. Y lo que no se logra con una, se logra
> con **misiones compuestas**: «Abre Steam y ve a la biblioteca» → `Open App` →
> `Click X`.

El dueño afinó después el criterio, y así queda:

> Tienen que haber las máximas herramientas para cubrir todo el uso del PC de un
> usuario, pero éstas tienen que ser las mínimas posibles. **No reducir cobertura:
> hacer más con menos.**

Eso no es «consolidar». Es una función objetivo con dos términos, y el orden entre
ellos importa:

1. **La cobertura no baja.** Si una operación desaparece y con ella desaparece algo
   que el usuario podía hacer, eso es una pérdida, no un ahorro. Ni siquiera si
   sube el acierto.
2. **Con la cobertura intacta, gana siempre el número menor.** Dos herramientas que
   cubren lo mismo que una son una de más.

El resultado se mide con dos números a la vez —**cobertura y cuenta**—, nunca con
uno solo. Un catálogo de 16 que cubre menos que el de 158 no ha cumplido; uno de
40 que cubre lo mismo que 158, sí.

Y hay una tercera vía que no consume ninguno de los dos términos: lo que no cabe en
una herramienta **se encadena**. Encadenar amplía la cobertura sin añadir una sola
entrada al catálogo. Ésa es la palanca para «hacer más con menos», y por eso el
goal 07 es parte de esta decisión y no un goal aparte.

**El criterio de qué entra: cubrir el PC, no las apps.** Todo lo que Windows
permite hacer —ventanas, audio, ficheros, aplicaciones, sistema—; nada específico
de una app concreta. Cero listas de apps hardcodeadas: ése fue un antipatrón
documentado de Carter contra su propio valor, y el BAXY actual lo repite —190
menciones de Steam y 94 de Spotify en el código, con adaptadores dedicados.

**El número y la forma los mide el goal 03**, no los decide una preferencia.
Paramétrica («controla el audio») contra específica («sube volumen») se compara
con datos reales y gana la que más acierte por token **a igual cobertura**.

Contexto que el goal 03 hereda: 67 → 31 → 16 → 158 fue crecimiento por
acumulación que nadie decidió, y Carter midió **−68 % de tokens sin perder
calidad** al consolidar a 16.

**Operar cualquier aplicación abierta es el núcleo**, no un extra: la cascada
UIA → OCR → visión es lo que hace posible el segundo paso de una misión compuesta.

## Peligro y confirmación — dos modos

BAXY **sí** puede borrar ficheros, cerrar programas con trabajo sin guardar y
apagar el equipo. Con dos modos:

| Modo | Comportamiento |
|---|---|
| **Normal** (por defecto) | Confirma **sólo si destruye datos** — borrar, sobrescribir, cerrar sin guardar. Apagar o cerrar sesión van directos. |
| **Bypass** | Sin frenos. Se activa con **un ajuste consciente** y queda encendido hasta que se apague. |

La confirmación sigue ligada a la invocación exacta, no a la intención aproximada.

## Velocidad — el listón real es el silencio

**Depende de la tarea.** Abrir Spotify es instantáneo; una misión compuesta puede
tardar y está bien.

Pero hay un número duro, y es éste:

> **Más de 3 segundos sin señal** y el dueño cierra la ventana y lo hace a mano.

Lo que mata no es la espera: es el silencio. De ahí sale la regla operativa:

- Si va a tardar poco, **calla y responde**.
- Si va a tardar, **avisa** — y ese aviso nunca afirma un resultado.

Entre ser más listo y quitarse sobrecarga, **se quita sobrecarga primero**. Carter
medía 16 s por turno con un modelo que tardaba 4,26 s: diez segundos eran capas
propias. El camino del texto a la acción es el más corto posible.

## Honestidad — y cómo convive con responder rápido

El invariante viene de un hecho concreto: **BAXY actúa sobre el PC**. Si sólo
hablara, mentir daría igual.

El dueño pidió que **responda y verifique después**, corrigiéndose solo si no
cuadra. Eso convive con «nada se afirma sin verificar» de una única manera, y no
hay otra lectura válida:

1. La señal temprana **no afirma un resultado**. Dice que entendió y está en ello.
2. La afirmación de que algo pasó **llega verificada**, siempre.
3. Si la verificación desmiente lo dicho, **BAXY se corrige solo**, sin esperar a
   que se lo pregunten.

Que BAXY diga «no pude confirmarlo» **da confianza**. Si lo dice a menudo, el
problema es la verificación y se arregla ahí — no callándolo.

## Memoria y privacidad

**Recuerda:** las preferencias del usuario, lo que suele pedir, y la conversación
reciente.

**Se puede ver, editar y borrar** entero.

**La red:** local no significa aislado.

> Baxy debe poder buscar en la web, pero más no enviar nada de mí. Por ejemplo, si
> no sabe algo, lo busca sin problema.

La línea es de dirección, no de conexión: **puede entrar información, no puede
salir contenido del usuario**. El modelo sigue siendo local; no hay API de pago
resolviendo lo que el modelo local no puede.

**Pantalla y ficheros: sí, cuando los necesita**, y diciéndolo. Sin esto no hay
«operar cualquier aplicación».

## Forma y presencia

- Vive en la **bandeja del sistema**.
- **Arranca con Windows** y se queda. La fricción de arrancarlo es lo que lo mata.
- Muestra **el resultado**, con el detalle a un clic si se pide.

Que arranque siempre y escuche siempre choca de frente con el presupuesto de
recursos: es el problema real del goal 08 y del 10, y no se resuelve
recortando la presencia.

**Escucha siempre**, con wake word local, **y se puede apagar** con un interruptor
visible. **Voz con carácter, español neutro.**

## La personalidad vive en el prompt

Sin fine-tuning. El Baxy anterior ya conseguía «Soy Baxy» sólo con el system
prompt. Cambiar el carácter debe ser editar un texto.

Sobre las palabras inventadas que arrastra el BAXY actual —«cuecer», «vertir»,
«alredad»—, el dueño no compra la solución heredada de subir a Q4 sin más:

> Que se evalúe bien y simplemente se elija lo mejor posible, siempre pensando en
> el menor uso de recursos que funcione bien.

Se mide. FunctionGemma es una pista fuerte (Q2 rompe la prosa, Q4_K_XL QAT la
arregla en ~1,5 GB), no una conclusión heredada.

## BAXY no se termina — se cambia por piezas

Esto es una decisión de producto, no de ingeniería, y por eso está aquí:

> Imagínate que BAXY está listo y de repente me da por mejorarlo, o construyo algo
> este mes y en dos meses veo que salieron cosas nuevas. **El código de hoy no
> tiene por qué ser el de mañana** si mañana salieron tecnologías que ayuden a
> BAXY.

Un asistente local vive sobre piezas que se mueven rápido: el modelo, la
cuantización, el motor de voz, el reconocedor. Si mejorar una obliga a reescribir
el producto, el producto se abandona. Ya pasó cuatro veces.

**BAXY entero es modular**, no sólo la pila del modelo: la memoria, la
verificación, la automatización de aplicaciones, la capa visual, el journal. Cada
pieza se cambia una por una.

Pero eso va en **dos niveles**, y confundirlos es lo que produce la sobreingeniería
que mató a las cuatro versiones anteriores:

- **La forma** —una responsabilidad por pieza, nadie conoce las tripas de nadie,
  dependencias hacia dentro, nada global y mutable— **aplica a todo y no cuesta
  nada**. Es escribirlo bien, y es lo que hace que cualquier pieza se pueda cambiar.
- **El mecanismo de cambio** —la medición que decide y la declaración en el
  manifiesto— **sí cuesta trabajo**, así que lo llevan las piezas que de verdad se
  van a comparar contra un candidato. Están en [`03_COSTURAS.md`](03_COSTURAS.md).

Lo que **no** se escribe nunca: una interfaz con un solo implementador «por si
algún día», un registro de plugins, o configuración para elegir entre
implementaciones que no existen. Eso no es modularidad, es peso.

La arquitectura es modular por tres bordes, no por un sistema de plugins:

- **El LLM, el STT, el wake word y el TTS viven fuera del proceso**, detrás de un
  protocolo versionado. Cambiar el modelo no recompila nada: se apunta a otro
  binario, se mide, y entra.
- **La verificación, los providers y la operación de apps** viven detrás de
  `Contracts` y `Kernel`, que no dependen de nada.
- **El catálogo y los corpus son datos**, no código.

Y ninguna pieza cambia en silencio: cada una se declara en el manifiesto de runtime
con su nombre y su SHA-256, y un binario distinto del declarado pone la compuerta
en rojo. Puedes cambiarlo todo; no puedes cambiar nada sin decirlo.

Y lo que hace sustituible a una pieza no es la interfaz — es **la medición que
decide si el candidato es mejor**. Con un corpus y un número, cambiar de motor de
STT es una tarde. Con una interfaz preciosa y sin número, no puedes decidir, así
que no lo cambias nunca. Por eso cada fila del registro lleva su medición y su
fecha: la fecha es lo que avisa de que una decisión ha caducado.

**Cero código muerto.** Una pieza sustituida se borra en el mismo cambio. Dos
implementaciones vivas de lo mismo son la acumulación otra vez.

## Por qué esta vez no hay una quinta reescritura

El dueño reconoció el diagnóstico de Carter y lo explicó:

> No quiero que nada se apile, sólo que se coloquen las piezas bien. Lo que pasó
> es que al empezar no sabía lo grande que era el proyecto, entonces por eso
> tantos routers: uno para solucionar el anterior, y así. La idea es aprender de
> todos los errores y lograr un BAXY en su estado puro.

Dos consecuencias que obligan a todos los goals:

**1. La línea roja es que vuelva a apilarse.** Nada se añade encima de algo que
ya no sirve. Si tu goal necesita una capa nueva, **retira la que sustituye** en
el mismo goal. Un router que arregla el caso que el router anterior falló es la
señal exacta de fracaso.

**2. Lo que evita la quinta versión es que el producto se use.** Un año después,
el éxito es *«que lo use a diario sin pensarlo»*. Eso hace del goal 10 —uso
diario— una prueba del producto, no un adorno final.

Y una precisión del dueño del **2026-08-21**, porque cambia cómo se cierra ese
goal: **el uso continuado ocurre después de entregar, no antes**. El producto sale
lo más rápido posible; en cuanto esté terminado se usa todos los días de verdad.
Ningún goal se cierra esperando a que pase el calendario: el goal 10 mide una
**dosis** de uso real —turnos, repetición y encendido continuo— y lo que el uso
siga encontrando después entra por `APLAZADOS.md` a una tanda de mantenimiento.

El momento en que el dueño dijo «esto no va» fue **cuando no acertaba la
herramienta**. Ése es el fallo que el goal 03 tiene que cerrar, y es el mismo
que hoy sigue abierto: la decisión ve hasta 28 candidatos y elige mal.

## Lo que justifica el proyecto entero

Tres pruebas, y hacen falta las tres:

1. **Abrir un juego y llegar adentro** — varias operaciones encadenadas sobre una
   app real.
2. **Manejar el PC sin tocarlo** — voz y accesibilidad juntas.
3. **Entenderle a la primera siempre** — se diga como se diga, en el idioma que
   salga.

Y lo que hay que quitarle de encima al usuario, en sus palabras: **levantarse del
teclado**.
