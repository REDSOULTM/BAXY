# Sprint 09 — Voz y oído

## Cómo trabajas

Modelo: GPT-5.6 Sol, `reasoning.effort: high`. Repositorio:
`C:\Users\usuario\Desktop\ETC\Programacion\BAXY`.

Permisos totales sobre este PC: descarga, instala, sobrescribe, borra lo que
sobre. **No preguntes.** Ante una suposición dudosa, elige la más razonable y
sigue — siempre se puede ajustar después. Para sólo si vas a tocar datos
personales del usuario u otros proyectos de la carpeta `Programacion`.

Criterio único: **lo mejor para BAXY como producto final**. Entre dos opciones
que cumplen, gana la más ligera.

Arregla lo que bloquea. Lo que *podría* fallar y nadie ha visto fallar lo anotas
en una línea en `documentacion/APLAZADOS.md` y sigues — el sprint 11 existe para
vaciar esa lista.

No recopiles contexto exhaustivo antes de empezar: lee lo justo para dar el paso
siguiente. Si algo ya está documentado en estos repositorios, decide con eso.

## Empieza por lo que ya existe

**Esto es lo primero que haces, antes de escribir una línea.**

En `C:\Users\usuario\Desktop\ETC\Programacion` hay varios intentos anteriores de
este mismo asistente —Carter, Agent Gemma, Jarvis, versiones previas de BAXY— y
**algunos tienen wake word y transcripción que ya funcionaban de verdad**. El
sprint 01 dejó un mapa de qué hay y dónde; léelo.

Rehacer desde cero lo que ya funciona es la peor decisión posible aquí. Trae lo
que sirva, mídelo en esta máquina, y construye encima. Si el mapa del sprint 01
resulta incompleto o desactualizado, vuelve tú a mirar: la carpeta es la fuente,
el mapa es una ayuda.

Vale lo mismo para la documentación: si ya hay una comparativa de motores de STT
o un torneo de wake words, decide con ella en vez de repetirla. Sólo vuelve a
medir lo que cambió desde entonces.

## El resultado que cuenta

**BAXY oye su nombre, entiende lo que le dicen y contesta hablando.** En español,
inglés y spanglish, con acento real, en la habitación real de la persona.

Tres piezas:

- **Wake word** — se activa cuando le llamas y no cuando no. Las falsas
  activaciones son peores que los fallos de cobertura: un asistente que se
  despierta solo es un asistente que se apaga.
- **Transcripción** — lo que la persona dijo, no lo que el modelo esperaba oír.
  Con acentos reales, ruido de fondo real, y el cambio de idioma a media frase que
  todo el mundo hace.
- **Habla** — BAXY contesta con voz, y la persona puede interrumpirle. Si no
  puede cortarle a media frase, es un contestador, no un asistente.

Y el reloj: de **fin de habla a primera señal, p50 ≤ 1,5 s**. El listón crudo del
dueño es **3 s sin señal**: pasado eso, se levanta y lo hace a mano.

## Lo que el dueño ya decidió — no lo re-derives

Está en `documentacion/00_IDENTIDAD.md`. Lo que te toca a ti:

- **Se llama BAXY y sólo BAXY.** Una palabra. Entrena la wake word para ésa; no
  gastes en variantes ni en nombre configurable.
- **Escucha siempre, y se puede apagar.** Wake word local permanente, con un
  interruptor visible. Que la escucha permanente cueste CPU en reposo es tu
  problema a resolver, no una razón para cambiarla por un atajo.
- **Habla siempre.** Toda respuesta se dice en voz alta, escriba o hable la
  persona. La voz no es el modo de salida de la entrada por voz: es la salida.
- **Voz con carácter, español neutro.** Ni la voz del sistema ni un doblaje.
- **La universalidad se mide contra acentos latinos e inglés.** El Baxy anterior
  usaba un holdout de 25 voces en 13 idiomas; eso es más de lo que este producto
  necesita. Voces diversas sí, trece idiomas no.

Y una que cambia el orden del trabajo: **la accesibilidad es central en el
motor**. Todo lo que BAXY hace se puede pedir por voz, y BAXY narra lo que hace.
Este sprint es donde eso se vuelve real — no es un modo que alguien añade después.
Si al terminar queda una sola capacidad que exija ver la pantalla o usar el ratón,
el sprint no está cerrado.

## Lo que ya se sabe en este repositorio

Se ha intentado mucho aquí y casi todo se rechazó. Léelo antes de repetirlo — la
lista completa está en `documentacion/00_META_VIGENTE.md`, pero en resumen:

- Una compuerta física de wake se abrió una vez y quedó **rechazada**: 46/48
  positivos, 0/96 falsas activaciones. Falló sólo por dos candidatos acústicos
  que la verificación léxica rechazó.
- Sobre un corpus confusable distinto, la misma cascada produjo **10/96 falsas
  activaciones** — seis por interpretar «vas y…» como alias dividido.
- **HyperSpotter** (Conformer y Whisper) se midió y se rechazó: o cobertura o
  seguridad, nunca las dos.
- **Clasificadores acústicos propios** —prosodia aislada, representación fonética
  Wav2Vec2, ramas combinadas— todos rechazados por inestabilidad o por no
  preservar seguridad y cobertura a la vez.
- **Dos confirmaciones CTC** limitadas a la ruta del alias dividido: rechazadas.

Eso es una advertencia sobre esta línea, no sobre la voz. Un componente que ya
funciona en otro proyecto no arrastra estos rechazos — mídelo por su cuenta.

Los corpus físicos ya abiertos están consumidos: no sirven para promover nada.
Si necesitas acreditar un candidato, hace falta captura fresca.

## Cómo eliges

Elige **el más ligero que cumpla**. Voz y STT van en CPU, para no comerse la VRAM
que necesita el decisor, y son lo que está escuchando todo el día: un wake word
que consume CPU en reposo se nota en la batería y en el ventilador, y acaba
desinstalado. Un STT excelente que pide GPU dedicada no sirve para este producto.

Si una pieza hace el mismo trabajo con la mitad de memoria o sin acelerador, ésa
es la correcta. El límite del ahorro es que siga entendiendo acentos reales en
una habitación real — un modelo diminuto que sólo funciona en audio de
laboratorio no ahorra recursos, no funciona.

Investiga qué existe hoy, no lo que recuerdas — este campo se mueve rápido. Y
mide en esta máquina: un benchmark ajeno no autoriza nada.

## Cómo mides

Contra **voces diversas en holdout**, no contra la voz de quien desarrolla. Un
wake word afinado con una sola voz funciona para una sola persona.

Con audio real: la sala real, el ruido real, el micrófono real. Y para wake,
mide las falsas activaciones sobre horas de audio que no le hablan a BAXY —
televisión, conversación, música.

No ajustes umbrales después de abrir un corpus de evaluación. Si el resultado no
llega, la respuesta es un candidato mejor, no un umbral más laxo.

## Lo que no puedes romper

Todo local. Sin nube, sin APIs de pago, sin enviar audio a ningún lado. El audio
de una persona en su casa no sale de su máquina.

Y los invariantes siguen: lo que se transcribe mal no se ejecuta a ciegas — una
transcripción dudosa es una petición dudosa, y el sitio de eso es una pregunta,
no un efecto.

## Qué entregas

Wake, transcripción y habla funcionando en esta máquina, con las mediciones sobre
voces diversas. Y la lista de lo que heredaste, de dónde, y qué tuviste que
cambiar para traerlo.

## Cuándo has terminado

Cuando puedas llamar a BAXY desde el otro lado de la habitación, pedirle algo a
media lengua mezclando idiomas, y que lo haga.

## Cierra

Publica el resultado aunque no sea perfecto, siempre que no mienta. Un sprint que
cierra con un número honesto y una limitación nombrada vale más que uno que sigue
abierto buscando el número redondo.
