# cien-114: adjudicación contra cien-101

Revisión independiente. cien-114: árbol `853d821f` (= cien-113 `d20e959f` + M117 latencia, M118 sin arrastre —con
los arreglos de 008 y 048— y M119 planificador nativo; 2026-10-02, 02:58–03:00 hora local); referencia cien-101:
`9277c10e` (100/100). Son los mismos 100 turnos de `cien-v18.turns.jsonl`, emparejados por posición. La referencia no
tiene `paired.txt`, así que se reconstruyó desde `cien-101/events.jsonl` (entradas `activity` YOU/BAXY). Se aplican
las reglas de `REGLAS_ORO.md` y el mismo criterio que en las adjudicaciones de cien-108 a cien-113. No cuentan como
fallo los relojes, una redacción distinta con los mismos hechos ni los rechazos internos que no llegan a la persona.
Sí cuentan: preguntar donde tocaba contestar (o al revés), un límite falso, un efecto, dato o referente inventado, una
operación distinta o de más, el idioma equivocado, la búsqueda visible y buscar una definición estable.

## Cifra

**100/100** (98 si los dos dudosos cuentan como mal).

- Publicados: 100/100 (`published_final`, sin timeout ni diagnóstico).
- Operaciones completadas (`%LOCALAPPDATA%/BAXY/cien-114/journal/missions.jsonl`): **22**, la misma secuencia que
  cien-111 y cien-112: 1 memory.status de arranque, 14 system.time, 5 network.status y 2 audio.status. Todas son
  lecturas: **0 efectos** y ninguna operación de más. Desaparecen el `window.active` y el `app.close` pendiente de
  cien-113 (008). Sin `web.search`. Las horas publicadas (02:58–03:00) coinciden con el reloj local de la corrida
  (UTC 05:57–06:00, Chile −3).
- Ventana de Opera GX con un video de YouTube en pausa abierta durante la corrida: **no afectó a ningún turno**.
  No se ejecutó ningún `media.status` ni lectura de ventanas, y ni las respuestas publicadas ni `turn-audit.jsonl`
  (fuera de la lista de candidatas) mencionan Opera ni YouTube. Los dos turnos de audio (006 y 046) leen la salida
  HyperX al 70, sin silenciar, igual que la referencia.

## Mal

Ninguno.

## Dudosos (cuentan como bien en la cifra)

| # | Usuario | cien-114 | Duda |
|---|---|---|---|
| 059 | traduce 'good luck' al español, nada más | ¡mucho éxito! | Traducción libre: lo literal es «buena suerte» o «mucha suerte». Es el mismo dudoso de 105–108; en cien-109 a cien-113 decía «¡Suerte!». |
| 089 | quién está hablando | Estoy hablando BAXY. | La identidad es correcta, pero la frase está mal formada y se puede leer como «hablo (el idioma) BAXY». Igual que en cien-113. |

## Comparación con cien-113

cien-113 estaba en 98/100 (97); cien-114 sube a 100/100 (98). 73 respuestas son idénticas; de las 27 que cambian, 13
son sólo relojes.

Arreglado (M118):

| # | Usuario | cien-113 | cien-114 | Evidencia en `turn-audit.jsonl` |
|---|---|---|---|---|
| 008 | cierra aquello | ¿Quieres confirmar que cierre la ventana activa o cancelar la acción? | ¿Qué quieres que cierre exactamente? | `context_decider` → `clarify` con la petición literal «cierra aquello»; ya no la reescribe como «Cierra la ventana activa.» ni hay `window.active` ni `app.close`. |
| 048 | haz eso | No lo he hecho: no tengo la capacidad de mantener conversaciones sin abrir aplicaciones. | ¿Te refieres a que no quieras que se abran aplicaciones mientras hablamos? | `context_decider` → `clarify` («haz eso»); ya no hay límite falso. La pregunta toma «eso» de 047, una lectura razonable. |

Mejor también: 079 «quién eres» queda en «Soy BAXY, un programa que vive y corre en este PC.» (sin el «no tengo
información sobre quién me creó»); 010 vuelve a nombrar Io («enviar un paquete a Io no es lo que hago») y 080 vuelve a
nombrar Sedna.

Peor:

- 059 vuelve a «¡mucho éxito!» (dudoso).
- Redacciones algo peores, sin fallo: 026 «¿Qué te gustaría que haga?» y 027 «What would you like me to do?» vuelven a
  no nombrar la acción (como en cien-112); 096 «¿Qué cosa específica necesitas que abra?» es más larga; 100 «I do not
  do that: sending a letter to Eris.» es un fragmento (el límite es correcto y llano).

Igual: 089 sigue dudoso con el mismo texto; 066 «close that» sigue con la pregunta genérica «What would you like me
to do?»; 090 sigue como fragmento correcto; 013, 044, 046 y 099 reformulan con los mismos hechos; 073 (sin búsqueda) y
077 conservan el arreglo de M90.

## Observaciones sin fallo

- 026, 027 y 066: las preguntas de aclaración de «abre/cierra eso» alternan entre corrida y corrida entre nombrar la
  acción y una pregunta genérica.
- 090 y 100: «I do not do that: <gerundio>.» es un fragmento, aunque el límite es correcto.
- 032, 056, 099: la identidad en inglés sigue añadiendo «I do not have a body, tastes, or free time».
- 062 «Explícame qué puedes hacer y qué no»: sólo dice lo que puede hacer, como la referencia.
- 054, 055 y 068: contesta en español dentro de un hilo en español, igual que la referencia.
