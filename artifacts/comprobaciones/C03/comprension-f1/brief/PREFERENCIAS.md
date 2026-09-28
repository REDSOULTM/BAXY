# Encargo: pares de preferencia para el decisor (la frontera entre decisiones)

Lee primero `ENTRENAMIENTO.md` (misma carpeta): sala limpia, reglas del dueño, catálogo y formato del `target` son los
mismos. Aquí no escribes una decisión por mensaje sino **pares**: para un mismo contexto, la decisión correcta
(`chosen`) y la equivocada que más tienta (`rejected`). El decisor aprende la frontera, no a hablar más ni a actuar más.

## Formato (una línea JSON por par)

```json
{"id": "P<escritor>-<n>", "speaker": "rioplatense", "kind": "action_vs_limit",
 "history": [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}],
 "user": "...",
 "chosen":   {"request": "...", "decision": "action", "operations": ["app.open"], "question": ""},
 "rejected": {"request": "...", "decision": "limit",  "operations": [], "question": ""},
 "why": "una frase: por qué la elegida es la correcta según REGLAS_ORO"}
```

`history` puede ir vacío (mensaje suelto, la mitad de los pares) o traer 1–4 mensajes. `chosen` y `rejected` usan el
mismo `request` salvo cuando la reescritura misma es el error.

## Tipos (reparto **simétrico**: cada tipo con su inverso, en igual cantidad)

| kind | chosen | rejected | forma |
|---|---|---|---|
| action_vs_limit | la operación del catálogo | limit | lo que el PC sí hace dicho con palabras raras, coloquiales o que suenan a otra cosa |
| limit_vs_action | limit | una operación parecida | lo que el PC no hace aunque se parezca a una operación (apps del celular, servicios ajenos, aparatos de la casa) |
| talk_vs_search | talk | web.search | conocimiento estable, definiciones, consejos, cálculos |
| search_vs_talk | web.search | talk | datos del día, fechas concretas, precios, resultados, lo que cambia |
| action_vs_clarify | la operación | clarify | pedido completo que no hace falta preguntar |
| clarify_vs_action | clarify | una operación | falta de verdad algo que cambia el resultado |
| talk_vs_clarify | talk | clarify | comentarios, gustos, quejas o preguntas sobre la conversación después de que BAXY hizo algo |
| sister_ops | la operación correcta | la hermana | operaciones hermanas del catálogo (ver ENTRENAMIENTO.md, punto 1) |

Nunca un `rejected` que sea correcto también: si dudas de que el `chosen` gane por las reglas, no escribas el par.

## Cantidad

150 pares por escritor en 10 partes de 15 (`<nombre>-pNN.jsonl`), los 8 tipos repartidos por igual, hablantes
variados (chileno, rioplatense, mexicano, colombiano, España, inglés, spanglish). Valida al terminar: JSON válido,
operaciones del catálogo y no internas, `decision`/`operations` coherentes en los dos lados, `chosen` ≠ `rejected`.
