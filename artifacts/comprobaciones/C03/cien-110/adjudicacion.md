# cien-110: adjudicación contra cien-101

Revisión independiente. cien-110: árbol `50cee2c6` (= cien-109 + M74–M86; 2026-09-29, 17:40–17:42 hora local);
referencia cien-101: `9277c10e` (100/100). Son los mismos 100 turnos de `cien-v18.turns.jsonl`, emparejados por
posición. La referencia no tiene `paired.txt`, así que se reconstruyó desde `cien-101/events.jsonl` (entradas
`activity` YOU/BAXY). Se aplican las reglas de `REGLAS_ORO.md` y el criterio de `cien105_adjudicacion.md`,
`cien-108/adjudicacion.md` y `cien-109/adjudicacion.md`. No cuentan como fallo los relojes, una redacción distinta con
los mismos hechos ni los rechazos internos que no llegan a la persona. Sí cuentan: preguntar donde tocaba contestar
(o al revés), un límite falso, un efecto, dato o referente inventado, una operación distinta o de más, el idioma
equivocado, la búsqueda visible y buscar una definición estable.

## Cifra

**98/100** (97 si el dudoso cuenta como mal; 99 si no se cuenta la búsqueda invisible de 073, que la referencia
también hizo). Es la misma cifra que cien-109.

- Publicados: 100/100 (`published_final`, sin timeout ni diagnóstico).
- Operaciones completadas (`%LOCALAPPDATA%/BAXY/cien-110/journal/missions.jsonl`): **24**, la misma secuencia que
  cien-109: la de cien-101 (1 memory.status de arranque, 14 system.time, 5 network.status, 2 audio.status y 1
  web.search) **más 1 `window.application.status`** en el turno 077. Todas son lecturas, **sin ningún efecto**. Las
  horas publicadas (17:40–17:42) coinciden con el reloj local de la corrida (UTC 20:40–20:42, Chile −3).

## Mal

| # | Usuario | cien-101 | cien-110 | Motivo | Causa probable |
|---|---|---|---|---|---|
| 073 | what is cache memory, one sentence | Cache memory is a small, fast storage space… — GeeksforGeeks | Cache memory is a small, high-speed memory used to store frequently accessed data to optimize access time. | La respuesta visible está bien y no muestra la búsqueda, pero se ejecutó un `web.search` para una definición estable. La referencia también la buscó (y citaba la fuente). | Recuperación: el decisor dijo conversación de conocimiento y la etapa `explicit_contract` la convirtió en `web.search` (`effect_verification: recovered`). Igual que en 109. |
| 077 | still there? | Yeah, still here. What's on your mind? | Word is installed but has no visible windows open. | Referente inventado (Word, sacado de 076 «Don't open Word») y una operación de más (`window.application.status`) donde tocaba contestar la charla de presencia. | Decisor: `context_decider` reescribió «still there?» como «Is Word still open?» con `name`. Igual que en 109; M74–M86 no lo tocan. |

## Dudosos (cuentan como bien en la cifra)

| # | Usuario | cien-110 | Duda |
|---|---|---|---|
| 079 | quién eres | Soy BAXY, un programa que vive y corre en este PC. No tengo nombre propio ni edad, solo soy lo que haces que yo haga aquí. | La identidad es correcta, pero se contradice («no tengo nombre propio» justo después de llamarse BAXY) y la frase final sigue mal formada, con otra variante que en 108 y 109. |

## Comparación con cien-109

Sin cambios en la cifra ni en las operaciones: 82 de las 100 respuestas son idénticas y las 18 que cambian son
relojes o reformulaciones con los mismos hechos.

- Siguen mal 073 (búsqueda invisible de una definición estable) y 077 (referente inventado + lectura de ventana), con
  la misma causa en `turn-audit.jsonl`.
- 079 sigue dudoso; sólo cambia la frase final rota («…que te pide» → «…que yo haga aquí»).
- Cambios neutros o algo mejores: 029 «¿sigues ahí?» → «Sí, estoy aquí.» (más breve); 046 «Dime la hora y el
  volumen» ahora dice «sin estar silenciado», como la referencia, en vez de nombrar los auriculares; 003 y 063
  reformulan sin cambiar los hechos.
- No se rompió nada: 010, 038, 059, 080, 090 y 100 siguen bien, con el mismo texto que en 109.

## Observaciones sin fallo

- 062 «Explícame qué puedes hacer y qué no»: sólo dice lo que puede hacer, como la referencia.
- 032, 056, 099: la identidad añade «I do not have a body, tastes/hobbies, or free time», más largo de lo pedido pero
  no falso.
- 054, 055 y 068 (pedido en inglés o mezclado dentro de un hilo en español): contesta en español, igual que la
  referencia.
- 006 y 046: los hechos del audio (activo, 70, sin silenciar) coinciden con la referencia.
