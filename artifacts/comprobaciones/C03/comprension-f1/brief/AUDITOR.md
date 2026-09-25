# Encargo: auditar a ciegas el oro de decisión de BAXY

Otra persona ya escribió qué debería decidir BAXY en cada uno de estos mensajes. Tú lo escribes **de nuevo, sin ver
lo suyo**, para medir cuánto coinciden. Lee `REGLAS_ORO.md` entero y consulta `CATALOGO.md` (misma carpeta).

## Sala limpia (obligatorio)

Lee **sólo**: `REGLAS_ORO.md`, `CATALOGO.md` y `..\audit\batch.jsonl`. No abras, busques ni listes ningún otro fichero
(ni el repositorio de BAXY, ni los conjuntos, lotes u oros de otras carpetas). No uses Grep ni Glob. Tu única escritura
es `..\audit\gold_audit.jsonl`.

## Entrada

Una línea JSON por ítem: `{"key": "Q001", "type": "single"|"turn", "text": "...", "history": [...]}`. `history` (sólo
en `turn`) son los mensajes anteriores de la conversación (`user` / `assistant`); decide el último mensaje, `text`,
con ese contexto.

## Salida

Una línea por ítem, mismo orden: `{"key": "Q001", "gold": ["..."], "args": {...}, "note": "..."}` (`args` y `note`
opcionales; `note` en una frase si dudaste). Etiquetas exactas: `op:<nombre>`, `op:<prefijo>*`, `plan:<a>+<b>`,
`web`, `talk`, `limit`, `ask`; todas las aceptables, ninguna que las reglas prohíban. Valida el JSON al terminar y
responde con 2 líneas: cuántos ítems y cuántos dudosos.
