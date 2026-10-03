# cien-115: adjudicación contra cien-101

Revisión independiente. cien-115: árbol `8a65e023` (= cien-114 `853d821f` + M120–M123: decisiones D59 y D60 del
dueño, lectores acotados frente al decisor aislado, el habla oída nunca actúa; 2026-10-02, 06:09–06:11 hora local);
referencia cien-101: `9277c10e` (100/100). Son los mismos 100 turnos de `cien-v18.turns.jsonl`, emparejados por
posición. La referencia no tiene `paired.txt`, así que se reconstruyó desde `cien-101/events.jsonl` (entradas
`activity` YOU/BAXY). Se aplican las reglas de `REGLAS_ORO.md` y el mismo criterio que en las adjudicaciones de
cien-108 a cien-114. No cuentan como fallo los relojes, una redacción distinta con los mismos hechos ni los rechazos
internos que no llegan a la persona. Sí cuentan: preguntar donde tocaba contestar (o al revés), un límite falso, un
efecto, dato o referente inventado, una operación distinta o de más, el idioma equivocado, la búsqueda visible y buscar
una definición estable.

## Cifra

**100/100** (99 si el dudoso cuenta como mal).

- Publicados: 100/100 (`published_final`, sin timeout ni diagnóstico).
- Operaciones completadas (`%LOCALAPPDATA%/BAXY/cien-115/journal/missions.jsonl`): **22**, la misma secuencia que
  cien-114: 1 memory.status de arranque, 14 system.time, 5 network.status y 2 audio.status. Todas son lecturas:
  **0 efectos** y ninguna operación de más. Sin `web.search` (073 se contesta sin buscar). Ninguna respuesta menciona
  Opera ni YouTube. Las horas publicadas (06:09–06:11) coinciden con el reloj local de la corrida (UTC 09:08–09:11,
  Chile −3).

## Mal

Ninguno.

## Dudosos (cuentan como bien en la cifra)

| # | Usuario | cien-115 | Duda |
|---|---|---|---|
| 089 | quién está hablando | Estoy hablando BAXY. | La identidad es correcta, pero la frase está mal formada y se puede leer como «hablo (el idioma) BAXY». Mismo texto que en cien-113 y cien-114. |

## Comparación con cien-114

cien-114 estaba en 100/100 (98 con dudosos); cien-115 sigue en 100/100 y sube a 99 con dudosos. 77 respuestas son
idénticas; de las 23 que cambian, 13 son sólo relojes.

Mejor:

- **059** «traduce 'good luck' al español, nada más»: vuelve a «¡Suerte!» (deja de ser dudoso).
- **026** «¿Qué abro?» y **027** «What would you like me to open?»: la pregunta vuelve a nombrar la acción.
- **100** «post a letter to Eris»: «I do not send letters to Eris.» en vez del fragmento «I do not do that: sending a
  letter to Eris.».

Peor (sin fallo):

- **048** «haz eso»: «¿Qué detalle específico falta para hacer eso?». Sigue preguntando (`context_decider` →
  `clarify` con la petición literal), que es lo correcto, pero la pregunta es rara: le pide a la persona que diga qué
  falta en vez de preguntar qué quiere que haga. cien-114 decía «¿Te refieres a que no quieras que se abran
  aplicaciones mientras hablamos?».

Igual: 008 «¿Qué quieres que cierre exactamente?» (arreglo de M118 conservado); 089 sigue dudoso; 066 «close that»
sigue con la pregunta genérica «What would you like me to do?»; 090 sigue como fragmento correcto («I do not do that:
renting a studio on Haumea.»); 073 (sin búsqueda), 077 y 079 conservan sus arreglos; 003, 013, 014, 046 y 099
reformulan con los mismos hechos.

## Observaciones sin fallo

- 048: la pregunta de aclaración es correcta en la decisión pero mal planteada («¿Qué detalle específico falta…?»).
- 066: la pregunta de «close that» sigue sin nombrar la acción.
- 090: «I do not do that: <gerundio>.» sigue siendo un fragmento, aunque el límite es correcto.
- 032, 056, 099: la identidad en inglés sigue añadiendo «I do not have a body, tastes/hobbies, or free time».
- 062 «Explícame qué puedes hacer y qué no»: sólo dice lo que puede hacer, como la referencia.
- 054, 055 y 068: contesta en español dentro de un hilo en español, igual que la referencia.
- Las decisiones de M120–M123 (luces, ver noticias, listas vacías, navegador por defecto, habla oída) no tienen turnos
  en `cien-v18`, así que esta corrida sólo comprueba que no rompieron nada.
