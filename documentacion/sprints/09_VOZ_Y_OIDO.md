# Goal 09 — La voz y el oído

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

**BAXY oye su nombre, entiende lo que le dicen y contesta hablando.** En español,
inglés y spanglish, con acento real, en la habitación real de la persona.

Tres piezas:

- **Wake word** — se activa cuando le llamas y no cuando no. Las falsas
  activaciones son peores que los fallos de cobertura: un asistente que se despierta
  solo es un asistente que se apaga.
- **Transcripción** — lo que la persona dijo, no lo que el modelo esperaba oír. Con
  acentos reales, ruido de fondo real, y el cambio de idioma a media frase que todo
  el mundo hace.
- **Habla** — BAXY contesta con voz, y la persona puede interrumpirle. Si no puede
  cortarle a media frase, es un contestador, no un asistente.

Y el reloj: de **fin de habla a primera señal, p50 ≤ 1,5 s**. El listón crudo del
dueño es **3 s sin señal**: pasado eso, se levanta y lo hace a mano.

## Lo que el dueño ya decidió — no lo re-derives

- **Se llama BAXY y sólo BAXY.** Una palabra. Entrena la wake word para ésa; no
  gastes en variantes ni en nombre configurable.
- **Escucha siempre, y se puede apagar.** Wake word local permanente, con un
  interruptor visible. Que la escucha permanente cueste CPU en reposo es tu problema
  a resolver, no una razón para cambiarla por un atajo.
- **Habla siempre.** Toda respuesta se dice en voz alta, escriba o hable la
  persona. La voz no es el modo de salida de la entrada por voz: es la salida.
- **Voz con carácter, español neutro.** Ni la voz del sistema ni un doblaje.
- **La universalidad se mide contra acentos latinos e inglés.** El Baxy anterior
  usaba un holdout de 25 voces en 13 idiomas; eso es más de lo que este producto
  necesita. Voces diversas sí, trece idiomas no.

Y una que cambia el orden del trabajo: **la accesibilidad es central en el motor**.
Todo lo que BAXY hace se puede pedir por voz, y BAXY narra lo que hace. Este goal es
donde eso se vuelve real — no es un modo que alguien añade después. Si al terminar
queda una sola capacidad que exija ver la pantalla o usar el ratón, el goal no está
cerrado.

## Empieza por lo que ya existe

**Esto es lo primero que haces, antes de escribir una línea.**

En `C:\Users\usuario\Desktop\ETC\Programacion` hay varios intentos anteriores de este
mismo asistente y **algunos tienen wake word y transcripción que ya funcionaban de
verdad**. El goal 01 dejó un mapa de qué hay y dónde; léelo.

Rehacer desde cero lo que ya funciona es la peor decisión posible aquí. Trae lo que
sirva, mídelo en esta máquina, y construye encima. Si el mapa resulta incompleto o
desactualizado, vuelve tú a mirar: la carpeta es la fuente, el mapa es una ayuda.

**Pero heredar no es conservar.** Aplica la ley 1 antes de adoptar: la voz local se
mueve rápido y una elección de motor de hace un año puede estar superada. La pila
que monta hoy todo el mundo —reconocimiento local, LLM local, síntesis local— está
documentada hasta el aburrimiento; cópiala donde encaje en vez de diseñar la tuya, y
comprueba cuál es el mejor motor **hoy** para español con acento latino, no cuál lo
era cuando se eligió.

Vale lo mismo para la documentación: si ya hay una comparativa de motores de STT o
un torneo de wake words, decide con ella en vez de repetirla. Sólo vuelve a medir lo
que cambió desde entonces — que, en este campo, es bastante.

## Lo que ya se rechazó en este repositorio

Se ha intentado mucho aquí y casi todo se rechazó. Léelo antes de repetirlo — la
lista completa está en `documentacion/00_META_VIGENTE.md`, pero en resumen:

- Una compuerta física de wake se abrió una vez y quedó **rechazada**: 46/48
  positivos, 0/96 falsas activaciones. Falló sólo por dos candidatos acústicos que la
  verificación léxica rechazó.
- Sobre un corpus confusable distinto, la misma cascada produjo **10/96 falsas
  activaciones** — seis por interpretar «vas y…» como alias dividido.
- **HyperSpotter** (Conformer y Whisper) se midió y se rechazó: o cobertura o
  seguridad, nunca las dos.
- **Clasificadores acústicos propios** —prosodia aislada, representación fonética
  Wav2Vec2, ramas combinadas— todos rechazados por inestabilidad o por no preservar
  seguridad y cobertura a la vez.
- **Dos confirmaciones CTC** limitadas a la ruta del alias dividido: rechazadas.

Eso es una advertencia sobre **esta línea**, no sobre la voz. Un componente que ya
funciona en otro proyecto, o uno del estado del arte de hoy, no arrastra estos
rechazos — mídelo por su cuenta.

Los corpus físicos ya abiertos están consumidos: no sirven para promover nada. Si
necesitas acreditar un candidato, hace falta captura fresca.

## Cómo eliges

Voz y STT van en CPU, para no comerse la VRAM que necesita el decisor, y son lo que
está escuchando todo el día: un wake word que consume CPU en reposo se nota en la
batería y en el ventilador, y acaba desinstalado. Un STT excelente que pide GPU
dedicada no sirve para este producto.

Si una pieza hace el mismo trabajo con la mitad de memoria o sin acelerador, ésa es
la correcta. El límite del ahorro es que siga entendiendo acentos reales en una
habitación real — un modelo diminuto que sólo funciona en audio de laboratorio no
ahorra recursos: no funciona.

Mide en esta máquina: un benchmark ajeno no autoriza nada.

## Cómo mides

Contra **voces diversas en holdout**, no contra la voz de quien desarrolla. Un wake
word afinado con una sola voz funciona para una sola persona.

Con audio real: la sala real, el ruido real, el micrófono real. Y para wake, mide las
falsas activaciones sobre horas de audio que no le hablan a BAXY — televisión,
conversación, música.

No ajustes umbrales después de abrir un corpus de evaluación. Si el resultado no
llega, la respuesta es un candidato mejor, no un umbral más laxo.

## Lo que no puedes romper

Todo local. Sin nube, sin APIs de pago, sin enviar audio a ningún lado. El audio de
una persona en su casa no sale de su máquina — y esto no tiene la excepción de la
búsqueda web: eso es información entrando, el audio sería contenido saliendo.

Y los invariantes siguen: lo que se transcribe mal no se ejecuta a ciegas. Una
transcripción dudosa es una petición dudosa, y el sitio de eso es una pregunta, no
un efecto.

## Las tres piezas van detrás de la frontera de proceso

Wake word, STT y TTS son tres de las piezas más volátiles del producto: en dos
meses habrá algo mejor. Las tres se montan **fuera del proceso de la aplicación**,
detrás del protocolo versionado, y se declaran en el manifiesto de runtime con su
nombre y su SHA-256 — igual que el LLM.

Eso significa que sustituir cualquiera de las tres más adelante es apuntar a otro
binario, correr la medición y actualizar el manifiesto. **Sin recompilar la
aplicación.** Si tu diseño acaba con el motor de STT dentro del proceso .NET, has
ganado unos milisegundos y has perdido la sustituibilidad: no lo hagas sin medir
las dos cosas y decirlo.

Y rellena las tres filas de `documentacion/03_COSTURAS.md` antes de cerrar: qué
corpus y qué número deciden un sustituto. Ésa es la parte que hace que el próximo
cambio sea una tarde.

## Criterios de cierre

- [ ] Wake, transcripción y habla funcionando en esta máquina, medidos sobre voces
      diversas y audio real.
- [ ] Las tres detrás de la frontera de proceso, declaradas en el manifiesto con su
      hash, y sus tres filas de `03_COSTURAS.md` rellenas.
- [ ] Falsas activaciones medidas sobre horas de audio que no le hablan a BAXY.
- [ ] De fin de habla a primera señal, p50 ≤ 1,5 s, y nunca 3 s en silencio.
- [ ] Se le puede interrumpir a media frase.
- [ ] **Ninguna capacidad de BAXY exige ver la pantalla o usar el ratón.**
- [ ] Publicado qué heredaste, de dónde, qué cambiaste — y qué descartaste porque el
      estado del arte lo dejó atrás.
- [ ] Consumo en reposo medido, con la escucha permanente encendida.

## Cuando lo cumplas

Poder llamar a BAXY desde el otro lado de la habitación, pedirle algo a media lengua
mezclando idiomas, y que lo haga.

Y anota en `documentacion/APLAZADOS.md`, en una línea cada cosa, lo que viste y no
perseguiste.
