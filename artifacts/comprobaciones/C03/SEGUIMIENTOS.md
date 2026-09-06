# C03 — seguimientos elípticos: dónde estaba el defecto de verdad

`seguimiento-1` … `seguimiento-14`, misma población de doce turnos (más nueve
de encargo nuevo desde `-4`), Granite 4.2 3B Q4_K_M registrado.

## Lo que se creía y lo que se midió

Las rondas 10 y 12 del panel anotaron esta clase como «la ruta contextual de la
mente sólo corre para `conversation_kind` `followup`/`None` y estas preguntas
se clasifican `knowledge`». Forzar esa ruta se midió en `seguimiento-3` y no
mejoró, con una regresión: `explain what a VPN is` se contestó «¿Para qué sirve
un proxy?», el tema del turno anterior arrastrado a una pregunta que traía el
suyo.

La traza de composición (`compose-audit.jsonl`, campo `situation` añadido aquí)
enseña otra cosa. Para **todo** turno conversacional que degrada, los hechos que
recibe el compositor son:

```
{"kind":"conversation","polarity":"success"}
```

Nada más. Ni la respuesta que escribió la mente, ni el historial, ni el tema.
El compositor vuelve a contestar la pregunta desde cero con el texto del turno
como único dato. Con una pregunta que se basta —«explícame qué es la caché»—
sale bien. Con un seguimiento elíptico —«¿por qué importa?»— no puede salir
bien: no hay nada que diga de qué se habla.

Por eso todas las respuestas de esta clase eran variaciones de la misma frase
vacía: «Porque entender por qué importa ayuda a tomar decisiones», «It matters
because understanding why something matters helps clarify purpose». No era el
modelo evadiéndose: era el único texto posible con esos hechos.

## La reparación

La elipsis es una lectura del pedido, así que vive donde vive la lectura:

* `request_reading.is_elliptical_followup(text)` — una pregunta (lleva un
  interrogativo) que no nombra su tema, por armazón (todas sus palabras son
  interrogativos, cópulas, pronombres o verbos de causa y utilidad) o por
  anáfora («eso», «it», «usarla», «lo necesita»). Un demostrativo seguido de su
  sustantivo —«this PC»— es determinante, no anáfora.
* `request_reading.request_topic(text)` — el tema tal y como lo nombró la
  persona, leído de «qué es X», «what is X», «explícame X», «define X».
* `request_reading.followup_topic(text, pedidos_anteriores)` — el tema del
  último pedido que tenía uno, y `None` en cuanto la pregunta trae el suyo.
  Esa última condición es la que impide el arrastre de `seguimiento-3`.

El dato cruza la frontera desde el shell: `ModelMessageComposer.CreateFacts`
lleva `priorRequests` —lo que la persona pidió antes, no lo que se le
contestó— en los turnos de conversación y aclaración. Quien lo interpreta es la
mente; el shell no lee idioma ni tema.

`priorRequests` no entra en los hechos del prompt: es contexto para saber de
qué se habla, no un hecho publicable.

## Medida

Nueve seguimientos elípticos en la población.

| Corrida | Cambio | Nombran su tema |
|---|---|---|
| `seguimiento-3` | ruta contextual forzada (retirada) | 0 de 9 |
| `seguimiento-8` | `priorRequests` compilado en Debug — el conductor usa Release | 0 de 9 |
| `seguimiento-10` | tema en el compositor | 8 de 9 |
| `seguimiento-11` | tema + veto de respuesta-pregunta | 9 de 9 |
| `seguimiento-12` | además «ya lo sabe, no lo definas» + veto de definición | 6 de 9 |
| `seguimiento-13`, `-14` | vuelta a la variante de `-11` | 7–9 de 9 |

`seguimiento-8` no midió nada: `Directory.Build.props` fija
`BaxyDevelopmentConfiguration=Release` y el conductor arranca ese binario, así
que un `dotnet build -c Debug` no llega a la corrida. Queda anotado porque
costó dos rondas.

## Segunda variante medida y retirada

`seguimiento-12` añadió a la instrucción «ya sabe qué es X: no lo definas otra
vez» y un validador `restated_the_topic` que vetaba la definición desnuda. El
modelo salió de la definición por la puerta de atrás: «En caché, es el estado
donde información temporal se guarda…», «En el tema de kernel, se usa cuando…».
De nueve seguimientos en tema se bajó a seis. La regla del goal se aplica:
dos variantes sin mejora semántica obligan a abandonar la estrategia, no a
numerar otro parche. La instrucción vuelve a la de `-11` y el validador se
retira; queda la nota en el código donde vivía.

## Lo que sí se queda

* El tema del seguimiento llega al compositor y a `llm.chat`.
* `answered_with_a_question`: un borrador de conversación que sólo devuelve
  otra pregunta ante una pregunta de conocimiento se rechaza y se reintenta.
* En la mente, una explicación (`knowledge`/`followup`) que sólo es una
  pregunta rompe el contrato del turno y va a recuperación. Un turno social sí
  puede terminar preguntando.

## Lo que la regresión encontró en mi propia reparación

`panel-opus-13/051`: «what are your limits on this PC» se contestó con la
definición de máscara de subred del turno anterior. La lectura de la elipsis
tomaba «this» por anáfora, así que una pregunta de límites heredaba el tema.
Un determinante va seguido de su sustantivo y un sustantivo nunca es armazón;
además un seguimiento pregunta, así que hace falta un interrogativo. Con las dos
condiciones, «what are your limits on this PC», «what can you do here», «close
that» y «ábreme eso» dejan de ser seguimientos, y los doce casos verdaderos
siguen siéndolo. Fijado en `tests/test_request_reading.py` y comprobado sobre la
secuencia entera en `limites-13/`.

Sin correr la regresión, esta reparación habría entrado en el tramo D
llevándose por delante las preguntas de límites.

## Lo que sigue abierto

El seguimiento ya está en tema, pero a menudo contesta *qué es* en vez de *por
qué importa*: nombra la caché y repite su definición. Eso ya no es falta de
contexto sino generación conversacional, y es donde tocan C05/C06. Queda
medido, no reparado: forzarlo desde el prompt fue justo lo que empeoró en
`seguimiento-12`.

Sigue habiendo un `composition_failed` espontáneo por corrida (t10) y fugas del
contrato de idioma («en español», «One sentence in English:») que vienen de
antes de esta reparación.
