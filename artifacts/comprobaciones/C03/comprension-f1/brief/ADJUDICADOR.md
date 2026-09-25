# Encargo: resolver desacuerdos del oro de decisión de BAXY

Dos personas escribieron, por separado, qué debería decidir BAXY en unos mensajes y no coinciden. Tú decides el oro
final de cada uno según `REGLAS_ORO.md` (léelo entero) y `CATALOGO.md` (misma carpeta).

## Sala limpia (obligatorio)

Lee **sólo**: `REGLAS_ORO.md`, `CATALOGO.md` y los ficheros de desacuerdo que te indique el encargo. No abras, busques
ni listes nada más (ni el repositorio de BAXY, ni los conjuntos). No uses Grep ni Glob.

## Entrada

Una línea por desacuerdo: `{"key", "id", "label_id", "text", "history", "gold", "audit_gold", "audit_note"}`. `gold`
es el oro del primer autor; `audit_gold` el del auditor; `history` la conversación previa (si la hay).

## Salida

Una línea por desacuerdo, mismo orden: `{"label_id": "...", "gold": [...], "choice": "first"|"audit"|"union"|"new",
"why": "una frase"}`. Elige la lista de decisiones aceptables que cumple las reglas del dueño: puede ser la del primero,
la del auditor, la unión de ambas (si las dos son aceptables) o una nueva. No aceptes lo que las reglas prohíben.
Responde con 2 líneas: cuántos por cada `choice`.
