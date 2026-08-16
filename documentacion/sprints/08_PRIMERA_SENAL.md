# Sprint 08 — La primera señal

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

**Nunca hay silencio muerto.** La persona escribe y algo pasa: un acuse, el
principio de una frase, una acción visible.

- Primera señal: **p50 ≤ 1,0 s y p95 ≤ 2,0 s**.
- Acción simple completa y verificada: p50 ≤ 2,5 s.
- Misión compuesta: sin techo fijo, pero narrando un hito cada ≤ 3 s de trabajo
  sin salida visible.

O la **mejor frontera Pareto demostrable**, si mides que el techo es inalcanzable
sin ceder exactitud o seguridad. Un rechazo medido cierra el sprint igual que un
éxito; un número inventado, no.

## Dónde está hoy

La latencia mala es exactamente la de los turnos que caen al camino por modelo —
los mismos que fallan en exactitud. De 17 peticiones, 9 las resuelve el
reconocedor en ≤ 0,071 s; las otras 8 van de 0,698 s a 2,957 s. p95 del producto:
**2,668 s**. En el camino por modelo puro se midió p50 2,440 s y p95 4,109 s.
Arranque en frío: 4,154 s.

Descomposición por llamada, mediana: `turn_policy_native_tools` **2,0379 s**,
`conversation_reply` 0,8867 s, `semantic_effect_guard` 0,5103 s,
`operation_compatibility` 0,4055 s, `final_writers` 0,3381 s,
`response_language` 0,1705 s.

**La llamada de decisión primaria sola cuesta más que la barra entera.** Y la
suma de las llamadas es prácticamente el turno completo: 3,37 s de 3,39 s. No hay
sobrecarga escondida que recortar — hay que hacer menos trabajo o hacerlo en
paralelo.

## Lo que ya se sabe — no lo repitas

**Streaming está rechazado como palanca.** Techo de ganancia 0,33 s; faltan
0,668 s. R132.

**El acuse temprano está rechazado.** Viola el invariante de cero respuestas
visibles fijas: un «un momento…» constante es exactamente el defecto que la barra
existe para evitar. Si buscas dar señal temprana, tiene que ser prosa formulada,
no una plantilla.

**Recortar el shortlist compra ~1,0 s.** Veintiocho herramientas y 9 KB cuestan
2,4–2,6 s; dos herramientas y 1,8 KB cuestan 1,27–1,72 s. Quedan ~1,3 s
irreducibles a `max_tokens=96`. R134.

**El mismo defecto paga dos veces.** Recortar el shortlist compra ese segundo *y*
quita veintiocho oportunidades de elegir mal. Si el sprint 03 ya lo recortó, parte
de esto está hecho — mídelo antes de rehacerlo.

**Aviso pagado con una corrida:** un shortlist recortado a ojo puede tirar la
operación correcta. Mide la discriminación sobre población suficiente antes de
cortar.

## Cómo mides

Sobre una población que **incluya turnos que el reconocedor no resuelve**. Medir
sólo los que resuelve la gramática da 0,071 s y no significa nada: son
precisamente los que ya iban bien.

Congela el árbol antes de medir. Editar código con una corrida en vuelo la
invalida — mata la corrida, borra la telemetría parcial, relanza.

Publica también el perfil CPU con sus propios techos medidos. BAXY nunca miente
ni actúa distinto por correr en CPU: sólo tarda más.

## Lo que no puedes romper

Sin regresión en exactitud ni en los tres ceros. Ganar 800 ms reabriendo un
efecto no solicitado es un rechazo. Y BAXY no le pelea la máquina a su dueño: si
hay carga interactiva pesada en primer plano, cede recursos.

## Qué entregas

Los números, sobre población que incluya lo difícil, con el perfil CPU aparte. Si
la conclusión es la frontera Pareto, publícala con el rechazo medido y di
exactamente qué habría que ceder para llegar a la barra.

## Cuándo has terminado

Cuando escribas algo y BAXY reaccione antes de que te dé tiempo a preguntarte si
te oyó.

## Cierra

Publica el resultado aunque no sea perfecto, siempre que no mienta. Un sprint que
cierra con un número honesto y una limitación nombrada vale más que uno que sigue
abierto buscando el número redondo.
