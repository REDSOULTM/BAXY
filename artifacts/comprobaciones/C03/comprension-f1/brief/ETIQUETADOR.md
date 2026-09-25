# Encargo: escribir el oro de decisión de mensajes reales a BAXY

Recibes un lote de mensajes reales (de datasets públicos) que personas le dicen a un asistente. Para cada uno escribes
qué **debería decidir** BAXY, según `REGLAS_ORO.md` (léelo entero) y el catálogo `CATALOGO.md` (misma carpeta).

## Sala limpia (obligatorio)

Lee **sólo**: `REGLAS_ORO.md`, `CATALOGO.md` y tu lote. No abras, busques ni listes ningún otro fichero del disco (nada
del repositorio de BAXY, ni otros lotes, ni otras carpetas). No uses Grep ni Glob. Tu única escritura es tu fichero de
salida.

## Tu lote

Una línea JSON por ítem, de dos tipos:
- `{"id": "L0007", "type": "single", "text": "...", "hint": "..."}`: un mensaje suelto, dicho sin conversación previa.
  `hint` es la etiqueta original del dataset (orientativa: a veces ayuda a entender la frase, pero **manda lo que dice
  el texto** y las reglas de BAXY, no el dataset).
- `{"id": "L0012", "type": "conversation", "turns": [{"user": "...", "assistant": "..."}, …]}`: una conversación real;
  `assistant` es lo que respondió el asistente original (puede ser raro o no ser BAXY: tómalo como historial fijo). El
  último turno no tiene respuesta. Hay que etiquetar **cada** mensaje `user`, teniendo en cuenta lo anterior.

Los mensajes vienen de otros asistentes (Alexa, Siri, Google), con otros dominios (luces, coche, móvil, reloj, apps de
deporte, contactos): aplica la regla 5 (límite llano) cuando BAXY, que vive en un PC con Windows, no lo hace; si el
catálogo sirve en parte (buscar en la web, abrir una app del PC), acéptalo también. «Alexa», «Siri», «oye Google» al
inicio son sólo el nombre con que llaman al asistente.

## Qué escribes

Un fichero JSONL, una línea por ítem, **en el mismo orden y con el mismo `id`**:
- suelto: `{"id": "L0007", "gold": ["..."], "args": {...}}` (`args` opcional);
- conversación: `{"id": "L0012", "turns": [{"gold": [...], "args": {...}, "dep": true|false}, …]}` con un elemento por
  cada mensaje `user`, en orden. `dep` es `true` si ese mensaje no se entiende bien sin lo anterior.

Etiquetas exactas: `op:<nombre del catálogo>`, `op:<prefijo>*`, `plan:<a>+<b>`, `web`, `talk`, `limit`, `ask`. Pon
todas las decisiones aceptables, no sólo la mejor; pero no aceptes lo que las reglas prohíben (p. ej. `web` para datos
propios, `ask` para un pedido completo, una acción para una cantidad relativa sin número).

Al terminar valida que cada línea es JSON válido, que están todos los `id` de tu lote, y que cada nombre de operación
existe en `CATALOGO.md`. Responde con 3 líneas: cuántos ítems, cuántas etiquetas `limit`/`web`/`ask`, y los casos
dudosos (sólo sus `id`).
