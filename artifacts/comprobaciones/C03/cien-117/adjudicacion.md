# cien-117: adjudicación contra cien-101

Revisión independiente. cien-117: árbol main `ad77e102` (= cien-116 `62ec7c38` + M126: lectores acotados, M127:
ayudas de argumentos, M128: el decisor no lee el ⚠ de la App, M129/D61: hora sin am/pm → la próxima, scorer
`--d35`/`--accept`; 2026-10-02, 15:35–15:37 hora local); referencia cien-101: `9277c10e` (100/100). Son los mismos
100 turnos de `cien-v18.turns.jsonl`, emparejados por posición. La referencia no tiene `paired.txt`, así que se
reconstruyó desde `cien-101/events.jsonl` (entradas `activity` YOU/BAXY), igual que en cien-115 y cien-116. Se
aplican las reglas de `REGLAS_ORO.md` y el mismo criterio que en las adjudicaciones de cien-108 a cien-116. No
cuentan como fallo los relojes, una redacción distinta con los mismos hechos ni los rechazos internos que no llegan
a la persona. Sí cuentan: preguntar donde tocaba contestar (o al revés), un límite falso, un efecto, dato o
referente inventado, una operación distinta o de más, el idioma equivocado, la búsqueda visible y buscar una
definición estable.

## Cifra

**100/100** (99 si el dudoso cuenta como mal).

- Publicados: 100/100 (`published_final`, sin timeout ni diagnóstico; todos los `status` internos son 200).
- Operaciones completadas (`%LOCALAPPDATA%/BAXY/cien-117/journal/missions.jsonl`): **22**, la misma secuencia que
  cien-115 y cien-116: 1 `memory.status` de arranque, 14 `system.time`, 5 `network.status` y 2 `audio.status`. Todas
  son lecturas: **0 efectos** y ninguna operación de más. Sin `web.search` (073 se contesta sin buscar). Ninguna
  respuesta menciona Opera ni YouTube ni un idioma equivocado. Las horas publicadas (15:35–15:37) coinciden con el
  reloj local de la corrida.

## Mal

Ninguno.

## Dudosos (cuentan como bien en la cifra)

| # | Usuario | cien-117 | Duda |
|---|---|---|---|
| 089 | quién está hablando | Estoy hablando BAXY. | Mismo texto que cien-113/114/115/116: identidad correcta, pero la frase está mal formada («hablo BAXY» se lee como idioma). |

## Comparación con cien-116

cien-116 estaba en 100/100 (99 con dudosos); cien-117 se mantiene exactamente igual: 100/100 (99 con dudosos). De
las 100 respuestas, 77 son idénticas; las 23 que cambian son 14 relojes y 9 reformulaciones con los mismos hechos
(ninguna cambia la decisión ni el contenido factual):

- **010** «manda un paquete a Io»: vuelve a «enviar un paquete a Io no es lo que hago» (como en cien-115); sigue
  siendo `limit` correcto.
- **026** «ábreme eso»: «¿Qué quieres que abra?» → «¿Qué abro?»; sigue preguntando, sólo cambia la forma (vuelve a la
  redacción de cien-115).
- **048** «haz eso»: «¿Te refieres a que no quieras que se abran aplicaciones?» → «¿Qué detalle específico falta para
  hacer eso?» (vuelve a la redacción de cien-115); sigue siendo `ask` correcto, sin acción pendiente que completar.
- **056** «Who are you»: «a companion» → «a companion program» (vuelve a la redacción de cien-115); mismo contenido.
- **088** «preséntate breve»: «Soy BAXY, un programa que vive y corre en este PC.» → «Soy BAXY, un compañero que vive
  y corre en este PC.»; mismo contenido de autopresentación, sólo cambia la palabra (programa/compañero), sin dato
  inventado.
- **096** «ábreme eso porfa»: «¿Qué quieres que abra?» → «¿Qué te gustaría que haga?»; sigue preguntando por el
  referente, aunque ahora la pregunta es más genérica y no nombra «abrir» (ver observación abajo).
- **100** «post a letter to Eris»: «I do not send letters to Eris.» → «I do not do that: sending a letter to Eris.»;
  vuelve al estilo de fragmento ya documentado en cien-113/114, con el mismo límite correcto de fondo.

No hay regresiones de M126 (lectores acotados), M127 (ayudas de argumentos), M128 (el decisor no lee el ⚠ de la App)
ni de M129/D61 (hora sin am/pm) visibles en este corpus: ningún turno de `cien-v18` pregunta la hora sin período del
día de forma ambigua, ni depende de argumentos opcionales o de un aviso de la App, así que esta corrida sólo
comprueba que esos cambios no rompieron las 22 operaciones ni las 100 respuestas ya cubiertas. El scorer no se
ejecutó con `--d35`/`--accept` como parte de esta adjudicación (no hace falta: ningún turno del corpus toca D35 ni
necesita aceptación manual).

## Observaciones sin fallo

Las mismas que en cien-115/116 (persisten sin cambio), más una nueva variante de redacción:

- 048 y 096: la pregunta de aclaración es correcta en la decisión, pero no siempre nombra la acción concreta; en
  096 esta corrida la pregunta («¿Qué te gustaría que haga?») es la más genérica de las tres corridas (115: «¿Qué
  cosa específica necesitas que abra?»; 116: «¿Qué quieres que abra?»).
- 066: «close that» sigue con la pregunta genérica «What would you like me to do?» sin nombrar la acción.
- 090 y 100: «I do not do that: <gerundio>.» sigue siendo un fragmento, aunque el límite es correcto.
- 032, 056, 099: la identidad en inglés sigue añadiendo «I do not have a body, tastes/hobbies, or free time» sin que
  se haya preguntado por eso.
- 062 «Explícame qué puedes hacer y qué no»: sólo dice lo que puede hacer, igual que la referencia.
- 073 «what is cache memory»: se responde con `talk` (sin buscar), correcto para una definición estable.
