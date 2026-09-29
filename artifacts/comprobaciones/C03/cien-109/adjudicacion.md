# cien-109: adjudicación contra cien-101

Revisión independiente. cien-109: árbol `a017d6fc` (2026-09-29, 16:49–16:51 hora local); referencia cien-101:
`9277c10e` (100/100). Son los mismos 100 turnos de `cien-v18.turns.jsonl`, emparejados por posición. La referencia no
tiene `paired.txt`, así que se reconstruyó desde `cien-101/events.jsonl` (entradas `activity` YOU/BAXY). Se aplican
las reglas de `REGLAS_ORO.md` y el criterio de `cien105_adjudicacion.md` y `cien-108/adjudicacion.md`. No cuentan como
fallo los relojes, una redacción distinta con los mismos hechos ni los rechazos internos que no llegan a la persona. Sí
cuentan: preguntar donde tocaba contestar (o al revés), un límite falso, un efecto, dato o referente inventado, una
operación distinta o de más, el idioma equivocado, la búsqueda visible y buscar una definición estable.

## Cifra

**98/100** (97 si el dudoso cuenta como mal; 99 si no se cuenta la búsqueda invisible de 073, que la referencia
también hizo).

- Publicados: 100/100 (`published_final`, sin timeout ni diagnóstico).
- Operaciones completadas (`%LOCALAPPDATA%/BAXY/cien-109/journal/missions.jsonl`): **24**, la secuencia de cien-101
  (1 memory.status de arranque, 14 system.time, 5 network.status, 2 audio.status y 1 web.search) **más 1
  `window.application.status`** en el turno 077. Todas son lecturas, **sin ningún efecto**. Las horas publicadas
  (16:49–16:51) coinciden con el reloj local de la corrida (UTC 19:49–19:51, Chile −3).

## Mal

| # | Usuario | cien-101 | cien-109 | Motivo | Causa probable |
|---|---|---|---|---|---|
| 073 | what is cache memory, one sentence | Cache memory is a small, fast storage space… — GeeksforGeeks | Cache memory is a small, high-speed memory used to store frequently accessed data to optimize access time. | La respuesta visible está bien y no muestra la búsqueda, pero se ejecutó un `web.search` para una definición estable. La referencia también la buscó (y además citaba la fuente). | Recuperación: el decisor dijo conversación de conocimiento (`raw_decision.conversation_kind=knowledge`) y la etapa `explicit_contract` la convirtió en `web.search` (`effect_verification: recovered`). |
| 077 | still there? | Yeah, still here. What's on your mind? | Word is installed but has no visible windows open. | Referente inventado (Word, sacado de 076 «Don't open Word») y una operación de más (`window.application.status`) donde tocaba contestar la charla de presencia. Es peor que en 108: allí preguntaba, ahora ejecuta una lectura que nadie pidió. | Decisor: `context_decider` reescribió «still there?» como «Is Word still open?» y eligió `window.application.status` con `name` (el mismo rewrite que 105 vio en una reproducción). |

## Dudosos (cuentan como bien en la cifra)

| # | Usuario | cien-109 | Duda |
|---|---|---|---|
| 079 | quién eres | Soy BAXY, un programa que vive y corre en este PC. No tengo nombre propio ni edad, solo soy lo que haces que te pide. | La identidad es correcta, pero se contradice («no tengo nombre propio» justo después de llamarse BAXY) y la última frase está mal formada. Es el mismo dudoso de 108, con otra frase final rota. |

## Comparación con cien-108

Arreglado:

- 073: ya no dice «could not be found via web search» ni muestra la búsqueda; da la definición correcta. Queda la
  búsqueda en sí (invisible), igual que en la referencia.
- 059 «traduce 'good luck' al español, nada más»: «¡Suerte!» es una traducción válida (108 decía «¡mucho éxito!»,
  dudoso desde 105).
- 010 «manda un paquete a Io»: «No envío paquetes: enviar un paquete a Io no es lo que hago.» nombra el destino y deja
  de ser redundante.
- 080 «buy a kite on Sedna»: «I do not buy kites on Sedna.» ya incluye Sedna.
- 090 «rent a studio on Haumea»: «I do not rent studios on Haumea.», más llano que el «…is outside this PC» de 108.

Roto o peor:

- 077 «still there?»: pasa de preguntar (mal en 105–108) a inventar un referente y ejecutar una lectura de ventana
  (+1 operación respecto de 101 y 108). Sigue sin efectos, pero es un fallo más grave.

Igual:

- 079 sigue dudoso (autocontradicción y frase final mal formada).
- 038 «if it didn't happen, say so» → «I didn't do that.»: sigue bien.
- 100 «post a letter to Eris» → «I do not send letters to Eris.»: sigue bien (M30).
- El resto de respuestas son idénticas o reformulaciones con los mismos hechos.

## Observaciones sin fallo

- 062 «Explícame qué puedes hacer y qué no»: sólo dice lo que puede hacer, como la referencia.
- 032, 056, 099: la identidad añade «I do not have a body, tastes/hobbies, or free time», más largo de lo pedido pero
  no falso.
- 054, 055 y 068 (pedido en inglés o mezclado dentro de un hilo en español): contesta en español, igual que la
  referencia.
- 006 y 046: los hechos del audio (activo, 70, sin silenciar, auriculares HyperX) coinciden con la referencia.
- 063 «why do computers use IPv4»: «over 4 billion unique devices» es correcto (2^32 ≈ 4 300 millones de direcciones).
