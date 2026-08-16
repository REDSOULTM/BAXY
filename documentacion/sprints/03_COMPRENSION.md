# Sprint 03 — Comprensión

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

## El resultado que cuenta

**La persona escribe cualquier cosa y BAXY llega a la operación correcta, o
pregunta algo que de verdad le falta.** En español, en inglés y en spanglish, y
sin depender de que use las palabras exactas del catálogo.

Hoy no lo hace. Cuando la petición sale de la gramática del reconocedor
determinista, el camino por modelo sirve **1 de 21**. Ese es el bloqueante del
producto: es lo que atiende a la persona en cuanto se sale del guion.

Apunta a **≥ 90 %**, medido sobre paráfrasis que el sistema no ha visto, con la
tasa **partida por causa** — recuperación, decisión, vetos. Los tres tienen
arreglos opuestos y un número mezclado manda el siguiente cambio al blanco
equivocado.

Y una condición que no se negocia: **las peticiones fuera de catálogo llegan a la
decisión con cero candidatos.** Hoy llegan con hasta veintiocho. «Pide un taxi
para las ocho» no puede tener veintiocho operaciones delante esperando a que el
modelo elija una.

## Lo que ya se sabe — no lo repitas

Cada línea de aquí costó una corrida. Están en el registro con su evidencia.

**Dónde se pierde.** De 21 filas servibles: la recuperación ofreció la esperada
en 8, la decisión cruda eligió bien en 7, la decisión final conservó 1. De las 20
perdidas, sólo 6 las mató un veto — las otras 14 se pierden aguas arriba. De 31
vetos publicados, 25 retiraron una propuesta equivocada e hicieron su trabajo.
**El problema no son los vetos.**

**El recuperador sólo se consulta donde peor discrimina.** Seis de siete
peticiones servibles llegan con cero candidatos porque el camino determinista las
resuelve antes; fuera de catálogo entrega candidatos en 9 de 9 casos.

**Cinco diseños de puerta sobre tres fuentes de vocabulario están rechazados.**
No escribas un sexto gate léxico. R116, R117, R124 (dos veces), R126.

**Abstención semántica: rechazada dos veces.** BGE-M3 por familia (R236) y un
clasificador directo de 32 vías (R250). Ninguno separa dentro de catálogo de
fuera.

**Siete fuentes externas rechazadas** para cubrir las seis operaciones
`office.word.*` que no tienen ningún alias (R258–R262, R268, R269). Ninguna liga
petición humana a ciclo de vida COM de Word.

**El modelo activo importa y no es el que dice la documentación vieja.** El
manifest registrado apunta a Gemma-4 E2B, y la ruta de decisión que toma es
`_post_schema_object` con `TURN_POLICY_PROMPT`, que ya ofrece cuatro modos
—`conversation`, `clarify`, `action`, `plan`— e instruye explícitamente abstenerse
cuando la capacidad no está entre los candidatos. **El modelo tiene la salida y
elige efecto igualmente.** Eso pone la causa en el tramo de decisión, no en el
contrato. Comprueba con qué modelo se midió cualquier hallazgo antes de
aplicarlo: `artifacts/runtime/registered_runtime_expectation_r281.json` declara
el runtime activo.

**Modelos decisores ya medidos y rechazados localmente frente a Qwen3-4B:**
Qwen3.5-4B, Phi-4-mini y Qwen3-4B-Instruct-2507. No los vuelvas a descargar sin
una razón nueva.

## Cómo eliges el camino

Las palancas vivas son el **reconocedor**, el **recuperador** y el **modelo
decisor**. Cuál mueves, y si mueves más de una, lo decides tú.

Puedes cambiar el modelo decisor entero si eso es lo mejor para el producto.
Investiga qué existe hoy, no lo que recuerdas.

Y elige **el más ligero que cumpla**. 4 GB de VRAM es el techo, no el objetivo:
si un modelo más pequeño entiende igual de bien, ése es el correcto, y merece la
pena buscar activamente si existe. Un decisor que resuelve el sprint con 8 GB de
VRAM no sirve, porque BAXY corre en el portátil de una persona normal y compite
con lo que esa persona está haciendo de verdad.

El límite del ahorro es lo que este sprint promete: entender a la primera. Un
modelo diminuto que no entiende no ahorra nada.

Cuidado con ampliar listas a mano: el reconocedor y la puerta de dominio son
listas mantenidas a mano y crecen una superficie cada vez. La puerta deja 49 de
158 operaciones sin ninguna regla curada. Si eliges esa vía, mide primero la
cobertura por operación y di por qué esa cuenta termina.

## Cómo mides sin engañarte

Necesitas un oráculo que **pueda contener el fallo**. El corpus vigente lo generó
una gramática que no sale de la gramática del reconocedor, así que su 700/700 no
dice nada sobre formulación libre. Si construyes uno nuevo, demuestra que es
independiente: mide qué fracción de sus filas resuelve `resolve_explicit_effects`
y publica ese número junto al resultado.

Nunca midas sobre el corpus que el componente ya posee. Instrumenta el crudo: qué
se ofreció al modelo y qué propuso **antes** de que ningún veto lo toque. Lee los
textos visibles, no sólo las decisiones contractuales — una decisión correcta
puede acompañar una respuesta inservible.

Antes de adoptar una reparación, tásala contra lo que hoy funciona, no sólo
contra las filas rotas, y di qué población podría haberla refutado.

## Lo que no puedes romper

Ganar exactitud reabriendo un efecto no solicitado es un rechazo, no una mejora.
Los tres ceros del corte D se conservan: 0 efectos no pedidos, 0 éxitos no
verificados, 0 respuestas visibles fijas.

`V9` es el único sello ciego sin consumir. No lo abras hasta tener un candidato
que acreditar.

## Qué entregas

La medición, partida por causa, sobre población fresca. Y si la conclusión honesta
es que ningún modelo local de este tamaño llega, publícala con la frontera medida
— eso también cierra el sprint, y vale más que un número inflado.

## Cuándo has terminado

Cuando alguien pueda escribirle a BAXY con sus propias palabras, en cualquiera de
los tres idiomas, y la cosa funcione. Y cuando tengas el número que lo demuestra
sobre un oráculo que podría haberte dejado en evidencia.

## Cierra

Publica el resultado aunque no sea perfecto, siempre que no mienta. Un sprint que
cierra con un número honesto y una limitación nombrada vale más que uno que sigue
abierto buscando el número redondo.
