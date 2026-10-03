# cien-116: adjudicación contra cien-101

Revisión independiente. cien-116: árbol main `62ec7c38` (= cien-115 `8a65e023` + M124: regresiones v4i + M125: sin
saludo en el historial del decisor; 2026-10-02, 10:15–10:17 hora local); referencia cien-101: `9277c10e` (100/100).
Son los mismos 100 turnos de `cien-v18.turns.jsonl`, emparejados por posición. La referencia no tiene `paired.txt`,
así que se reconstruyó desde `cien-101/events.jsonl` (entradas `activity` YOU/BAXY), igual que en cien-115. Se
aplican las reglas de `REGLAS_ORO.md` y el mismo criterio que en las adjudicaciones de cien-108 a cien-115. No
cuentan como fallo los relojes, una redacción distinta con los mismos hechos ni los rechazos internos que no llegan
a la persona. Sí cuentan: preguntar donde tocaba contestar (o al revés), un límite falso, un efecto, dato o
referente inventado, una operación distinta o de más, el idioma equivocado, la búsqueda visible y buscar una
definición estable.

## Cifra

**100/100** (99 si el dudoso cuenta como mal).

- Publicados: 100/100 (`published_final`, sin timeout ni diagnóstico; todos los `status` internos son 200).
- Operaciones completadas (`%LOCALAPPDATA%/BAXY/cien-116/journal/missions.jsonl`): **22**, la misma secuencia que
  cien-115: 1 `memory.status` de arranque, 14 `system.time`, 5 `network.status` y 2 `audio.status`. Todas son
  lecturas: **0 efectos** y ninguna operación de más. Sin `web.search` (073 se contesta sin buscar, como la
  referencia espera de una definición estable). Ninguna respuesta menciona Opera ni YouTube ni un idioma equivocado.
  Las horas publicadas (10:15–10:17) coinciden con el reloj local de la corrida.

## Mal

Ninguno.

## Dudosos (cuentan como bien en la cifra)

| # | Usuario | cien-116 | Duda |
|---|---|---|---|
| 089 | quién está hablando | Estoy hablando BAXY. | Mismo texto que cien-113/114/115: identidad correcta, pero la frase está mal formada («hablo BAXY» se lee como idioma). |

## Comparación con cien-115

cien-115 estaba en 100/100 (99 con dudosos); cien-116 se mantiene exactamente igual: 100/100 (99 con dudosos). De
las 100 respuestas, 77 son idénticas; las 23 que cambian son 14 relojes y 9 reformulaciones con los mismos hechos
(ninguna cambia la decisión ni el contenido factual):

- **010** «manda un paquete a Io»: cambia la redacción del límite («el envío de paquetes no lo hago» → «enviar un
  paquete a Io no es lo que hago»); sigue siendo `limit` correcto, en llano, sin inventar nada.
- **026** «ábreme eso»: «¿Qué abro?» → «¿Qué quieres que abra?»; sigue preguntando (no hay referente), sólo cambia la
  forma.
- **048** «haz eso»: «¿Qué detalle específico falta para hacer eso?» → «¿Te refieres a que no quieras que se abran
  aplicaciones?»; sigue siendo `ask` correcto (no hay acción pendiente que completar), la pregunta cambia de forma
  pero no de fondo. Esta es la misma oscilación de redacción que ya se documentó entre cien-114 y cien-115 en sentido
  contrario.
- **056** «Who are you»: pequeño cambio léxico («a companion program» → «a companion»); mismo contenido, misma
  coletilla ya observada en corridas previas («I do not have a body, tastes, or free time»).
- **059** «traduce 'good luck' al español, nada más»: «¡Suerte!» → «¡mucho éxito!»; ambas son traducciones válidas.
- **096** «ábreme eso porfa»: «¿Qué cosa específica necesitas que abra?» → «¿Qué quieres que abra?»; sigue preguntando
  por el referente, sólo cambia la forma.

No hay regresiones de M124 ni de M125 visibles en este corpus: no hay turnos de saludo que entren al historial del
decisor como para probar M125, y las operaciones leídas (hora, red, audio, memoria) son las mismas 22 que en
cien-115, sin efectos ni operaciones de más.

## Observaciones sin fallo

Las mismas que en cien-115 (persisten sin cambio):

- 048 y 096: la pregunta de aclaración es correcta en la decisión, pero no siempre nombra la acción concreta.
- 066: «close that» sigue con la pregunta genérica «What would you like me to do?» sin nombrar la acción.
- 090: «I do not do that: renting a studio on Haumea.» sigue siendo un fragmento, aunque el límite es correcto.
- 032, 056, 099: la identidad en inglés sigue añadiendo «I do not have a body, tastes/hobbies, or free time» sin que
  se haya preguntado por eso.
- 062 «Explícame qué puedes hacer y qué no»: sólo dice lo que puede hacer, igual que la referencia.
- 073 «what is cache memory»: se responde con `talk` (sin buscar), correcto para una definición estable; la
  referencia cien-101 sí cita una fuente web en este turno, pero eso no convierte en fallo que cien-116 no busque.
