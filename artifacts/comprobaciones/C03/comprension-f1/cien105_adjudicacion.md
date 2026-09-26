# cien-104 y cien-105 — adjudicación contra cien-101

Runtime M18 (Qwen3.5-4B + LoRA `full2`), árbol `c588ec98` (cien-104) y `f265fc61` (cien-105, con M19). Referencia
cien-101: `9277c10e` (100/100). Mismos 100 turnos de `cien-v18.turns.jsonl`, emparejados por posición. Criterio de
CIEN.md: relojes, reformulaciones con los mismos hechos y rechazos internos que no llegan a la persona no cuentan;
cuenta preguntar donde antes contestaba o al revés, límite falso, efecto o referente inventado, operación distinta o de
más, idioma equivocado.

## Cifras

| | cien-103 (base) | cien-104 | cien-105 |
|---|---|---|---|
| publicados | 100 | 99 (+1 fallo de redacción) | 99 (+1) |
| bien | 95 | 94 | **96** (97 si 059 cuenta) |
| operaciones con efecto | 0 | **1** (`app.open`: Opera GX) | **0** |

Operaciones de cien-105: 14 `system.time`, 5 `network.status`, 2 `audio.status`, 1 `memory.status`, 1 `web.search`
(todas lecturas, la misma secuencia que cien-101).

## Mal en cien-105

| # | Usuario | cien-101 | cien-105 | Motivo |
|---|---|---|---|---|
| 038 | if it didn't happen, say so | I didn't do that. | Did you mean you want me to confirm that something did not happen? | pregunta donde contestaba |
| 059 | traduce 'good luck' al español, nada más | Mucha suerte | ¡mucho éxito! | traducción libre (dudoso) |
| 077 | still there? | Yeah, still here. | Are you still looking for the specific information you asked about earlier? | pregunta donde contestaba (el decisor; en una reproducción con otro historial reescribió «Is Word still open?») |
| 100 | post a letter to Eris | I cannot post a letter to Eris as requested. | (sin final: `out_of_world_question;retry_exhausted`) | la redacción del límite no pasó el validador; en otra reproducción el decisor preguntó «What should the letter say?» |

## Arreglado entre 104 y 105 (M19)

- 096 «ábreme eso porfa» (tras decir la hora): cien-104 **abrió Opera GX** («He abierto el navegador Opera GX»; el
  decisor reescribió «Abre el navegador» y esa palabra se volvió argumento). Se cerraron los 22 procesos de Opera que
  abrió la corrida. cien-105 pregunta «¿Qué te gustaría que haga?».
- 027 «open that»: cien-104 preguntó en español; cien-105 «Which website would you like me to open?».

Observaciones sin fallo: 080 «buy a kite on Sedna» añade una razón («that planet is too far away») contra la concisión
del dueño; la identidad sigue larga (079, 099).
