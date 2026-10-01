# cien-112: adjudicación contra cien-101

Revisión independiente. cien-112: árbol `38d03aa2` (= cien-111 `30861483` + M91b, M93, M94–M98; 2026-10-01,
04:01–04:03 hora local); referencia cien-101: `9277c10e` (100/100). Son los mismos 100 turnos de
`cien-v18.turns.jsonl`, emparejados por posición. La referencia no tiene `paired.txt`, así que se reconstruyó desde
`cien-101/events.jsonl` (entradas `activity` YOU/BAXY). Se aplican las reglas de `REGLAS_ORO.md` y el mismo criterio
que en las adjudicaciones de cien-108 a cien-111. No cuentan como fallo los relojes, una redacción distinta con los
mismos hechos ni los rechazos internos que no llegan a la persona. Sí cuentan: preguntar donde tocaba contestar (o al
revés), un límite falso, un efecto, dato o referente inventado, una operación distinta o de más, el idioma equivocado,
la búsqueda visible y buscar una definición estable.

## Cifra

**100/100** (también 100 con los dudosos como mal: no hay dudosos).

- Publicados: 100/100 (`published_final`, sin timeout ni diagnóstico).
- Operaciones completadas (`%LOCALAPPDATA%/BAXY/cien-112/journal/missions.jsonl`): **22**, la misma secuencia que
  cien-111: 1 memory.status de arranque, 14 system.time, 5 network.status y 2 audio.status. Todas son lecturas:
  **0 efectos**, ninguna operación de más y ningún `web.search` (073 se contesta sin buscar). Las horas publicadas
  (04:01–04:03) coinciden con el reloj local de la corrida (UTC 07:00–07:03, Chile −3).

## Mal

Ninguno.

## Dudosos

Ninguno.

## Comparación con cien-111

Mejor: ninguno (cien-111 ya estaba en 100/100). Peor: ninguno. 76 respuestas son idénticas; de las 24 que cambian, 13
son sólo relojes y 11 son redacciones distintas con la misma decisión y los mismos hechos:

| # | Usuario | cien-111 | cien-112 | Nota |
|---|---|---|---|---|
| 026 | ábreme eso | ¿Qué abro? | ¿Qué te gustaría que haga? | Sigue preguntando (decisor `clarify`, `argument_fields: appId`), pero la pregunta pierde «abrir» y suena más genérica. |
| 027 | open that | What would you like me to open? | What would you like me to do? | Igual que 026: pregunta correcta, menos precisa. |
| 096 | ábreme eso porfa | ¿Qué quieres que abra? | ¿Qué cosa específica necesitas que te abra? | Pregunta correcta, algo más larga. |
| 014, 044, 063, 083, 084 | (seguimientos y definiciones) | — | — | Mismos hechos con otras palabras. 063 pasa a «a legacy standard… widely supported», correcto aunque menos explicativo. |
| 046 | Dime la hora y el volumen. | …sin estar silenciados. | …con el sonido activo en los auriculares HyperX. | Mismo dato (70, activo); omite «sin silenciar», que «activo» ya implica. |
| 080, 099 | Sedna / describe yourself | — | — | «I don't buy kites on Sedna.»; «tastes» en vez de «hobbies». |

Se mantienen los arreglos de M90: 073 sin `web.search`, 077 «Yeah, I'm still here. What's up?» sin operación y 079
sin autocontradicción, con el mismo texto que en cien-111.

## Observaciones sin fallo

- 026 y 027: la pregunta de aclaración ya no nombra la acción («abrir» / «open»). No cuenta, porque la decisión
  (preguntar) es la correcta, pero es una pérdida de precisión frente a cien-111 y conviene vigilarla.
- 079: sigue añadiendo «no tengo información sobre quién me creó ni cuándo», que nadie preguntó.
- 032, 056, 099: la identidad en inglés sigue añadiendo «I do not have a body, tastes, or free time».
- 062 «Explícame qué puedes hacer y qué no»: sólo dice lo que puede hacer, como la referencia.
- 054, 055 y 068: contesta en español dentro de un hilo en español, igual que la referencia.
