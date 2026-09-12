# Dos rutas publican texto visible sin pasar por el filtro de defectos

CLOCK1034 acreditó diez filas y, de paso, dejó al descubierto algo que vale más que los créditos: no
todo lo que la persona lee pasa por `compose_visible_defect`. Hay tres rutas de texto visible y sólo una
está filtrada.

## Las tres rutas, con la evidencia de cada una

| Ruta | Quién genera | ¿Filtro de defectos visibles? | Evidencia |
|---|---|---|---|
| Resultado tipado | `compose_user_message` | **sí** | 45 filas publicadas en `compose-audit.jsonl` de CLOCK1034 |
| Aclaración | campo `question` de la decisión | no; sólo `_recovery_question_is_valid` | los cuatro `kind: clarify` de CLOCK1034 |
| Conversación | `llm.chat` | no | los dos `kind: conversation` que publicaron «SIEMPRE» |

El `turn-audit` lo dice sin ambigüedad. Los cuatro que preguntaron en vez de contestar salieron con
`final.kind = clarify` e `intent_operations = ["system.time"]`; los dos de «SIEMPRE» con
`final.kind = conversation`, `conversation_kind = knowledge`. Ninguno de los seis aparece entre las filas
publicadas del diagnóstico de composición.

## «SIEMPRE» era vocabulario del prompt

`llm.py:107` instruye «Hablas español, inglés y spanglish; responde SIEMPRE en el idioma del…». El
modelo devolvió esa palabra sola como respuesta conversacional y el producto la publicó, porque la ruta
de `llm.chat` sólo comprobaba que la respuesta no estuviera vacía y que una explicación no fuera sólo
preguntas.

**Reparado, con la regla más estrecha que sirve:** una respuesta conversacional que sea **una sola
palabra en mayúsculas** no se publica; se convierte en fallo de contrato, que al menos es honesto y
además dispara el reintento del turno. Verificado contra los **125 terminales publicados** de las seis
tandas de esta sesión: rechaza exactamente los dos «SIEMPRE» y conserva las 123 respuestas reales,
incluidas «03:01», «Sí» y «OK» —una cifra o un monosílabo sí pueden ser respuesta—
(`scratchpad/c03-bare-token-check.py`).

## La aclaración innecesaria es otra cosa, y es más grande

Los cuatro fallos de variante de CLOCK1034 no son leakage: son preguntas bien formadas —terminan en
«?», sin vocabulario de prompt, así que `_recovery_question_is_valid` las acepta— que **no había que
hacer**. Y el propio audit muestra que la decisión ya sabía qué operación era:
`intent_operations: ["system.time"]` con `effect_operations: []`.

Es decir: el turno identifica la lectura, no necesita ningún dato de la persona para hacerla, y aun así
pregunta «¿Quieres que te diga la hora actual?». Cinco literales de la encuesta han fallado ya por esto
en tres tandas distintas: H0532 en SYSTEM1028, H0497 en APPS1029 y las cuatro variantes de aquí.

**No se repara a ciegas.** La regla honesta —si la operación identificada es de sólo lectura y su
esquema no exige argumentos, no se pregunta: se lee— toca la capa de decisión, que es la que gobierna
todas las categorías, y necesita sus propios controles: hay conductas donde preguntar **sí** es lo
correcto (destino ausente, referente deíctico, confirmación de efecto). El siguiente paso es medir
cuántos abiertos dependen de ella y sellar la reparación con controles de las dos clases, no adivinar.

## Lo que esto cambia en el orden de trabajo

La reparación de la aclaración innecesaria es transversal: afecta a `clarification_unresolved_input` (31
abiertos, ninguno llegando al reconocedor), a `conversation` (22) y a las variantes de cualquier
categoría cuya conducta se resuelve con una lectura sin argumentos. Es el candidato más grande que queda
después de la de apps, y por eso encabeza la continuación en `RELEVO_ACTIVO.json`.
