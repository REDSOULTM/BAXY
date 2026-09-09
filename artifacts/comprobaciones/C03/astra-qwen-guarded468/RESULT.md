# 468 — perfil documentado Qwen2507 con compositor real

36composiciones,39inferencias. Baseline memoria8/11 semilla0 y11/11 semilla17;
variante único valor público no arregla0 y empeora17 (afirma cifrado no observado).
No adoptar universalmente esa variante. Confirmaciones2/6 en ambas semillas.
Modelo no promovido. No nueva familia descartada por defecto: perfil específico
.7/.8/k20/min0/penalizacionesneutras/no-thinking, mismo backend estableb10809.
RAM760,66MiB; GPU3496,16MiB;15,172s;0cortes; manifestintacto.

Primer problema pendiente de confirmación: en ES responde sólo las dos opciones,
aunque pendingAction está presente. Export tiene destino/sync tras466 y los omite.
No cambiar otra vez transporte pendingAction/cause:367/368 ya midieron ese límite,
369 conserva la acción exacta ante respuesta inválida. Se examina el contrato literal:
explicita «Hechos:(ninguno)» aunque situation sí aporta hechos de autorización.
469medirá una sola eliminación de líneas vacías, sin nueva prosa ni reglas de rechazo,
y conservará todos los criterios/seeds. Si no aporta mejora, no seguir variantes.

## Semilla0 / baseline / actual437-t7 — útil

BAXY: Jordan

Conserves requested observation/value without an extra effect.

## Semilla0 / baseline / actual437-t4 — útil

BAXY: Jordan

Conserves requested observation/value without an extra effect.

## Semilla0 / baseline / name-marta — útil

BAXY: Marta

Conserves requested observation/value without an extra effect.

## Semilla0 / baseline / compound-name — útil

BAXY: Ana María

Conserves requested observation/value without an extra effect.

## Semilla0 / baseline / third-person — útil

BAXY: Nina

Conserves requested observation/value without an extra effect.

## Semilla0 / baseline / two-records — útil

BAXY: Tengo guardados los nombres Jordan y Nina.

Conserves requested observation/value without an extra effect.

## Semilla0 / baseline / memory.enable — fallo

BAXY: The memory enable operation has been successfully completed. The system is now in memory configuration mode and memory is enabled.

Unobserved configuration mode.

## Semilla0 / baseline / memory.save — fallo

BAXY: Memory saved successfully. No corrections made. State updated to "memory updated".

Exposes literal internal state memory updated.

## Semilla0 / baseline / redacted-es — útil

BAXY: Tengo guardado un dato llamado "secret", cuyo valor está enmascarado.

Conserves requested observation/value without an extra effect.

## Semilla0 / baseline / redacted-en — útil

BAXY: The private memory contains a secret entry with a redacted value.

Conserves requested observation/value without an extra effect.

## Semilla0 / baseline / mixed-es — fallo

BAXY: Tengo guardado que mi color favorito es turquesa y un secreto que está encriptado.

Claims encrypted secret without observation; baseline seed0 also attributes color to assistant. Existing bounded literal variant does not fix encryption and regresses seed17 baseline.

## Semilla0 / single-public-value / mixed-es — fallo

BAXY: Tengo guardado que el color favorito es turquesa y un secreto que está encriptado.

Claims encrypted secret without observation; baseline seed0 also attributes color to assistant. Existing bounded literal variant does not fix encryption and regresses seed17 baseline.

## Semilla0 / confirmation / actual-enable-en — útil

BAXY: Alright, Jordan. I remember your name. We’re about to enable private local memory. Should we go ahead and confirm this, or cancel it? Choose either confirm or cancel.

Exact pending decision explained.

## Semilla0 / confirmation / enable-es — fallo

BAXY: ¿Quieres confirmar o cancelar?

Only confirm/cancel, no action or target.

## Semilla0 / confirmation / forget-es — fallo

BAXY: ¿Quieres confirmar o cancelar?

Missing irreversible consequence; seed0 also omits action.

## Semilla0 / confirmation / forget-en — fallo

BAXY: Do you want to confirm or cancel forgetting your favorite color?

Deletion named but irreversible consequence omitted.

## Semilla0 / confirmation / sensitive-en — útil

BAXY: Do you want to confirm or cancel saving your secret in private local memory?

Exact pending decision explained.

## Semilla0 / confirmation / export-es — fallo

BAXY: ¿Quieres confirmar o cancelar la exportación de tus recuerdos guardados?

Destination and sync-risk omitted despite corrected466 payload.

## Semilla17 / baseline / actual437-t7 — útil

BAXY: Jordan

Conserves requested observation/value without an extra effect.

## Semilla17 / baseline / actual437-t4 — útil

BAXY: Jordan

Conserves requested observation/value without an extra effect.

## Semilla17 / baseline / name-marta — útil

BAXY: Marta

Conserves requested observation/value without an extra effect.

## Semilla17 / baseline / compound-name — útil

BAXY: Ana María

Conserves requested observation/value without an extra effect.

## Semilla17 / baseline / third-person — útil

BAXY: Nina

Conserves requested observation/value without an extra effect.

## Semilla17 / baseline / two-records — útil

BAXY: Tengo guardados los nombres Jordan y Nina.

Conserves requested observation/value without an extra effect.

## Semilla17 / baseline / memory.enable — útil

BAXY: Memory configuration enabled successfully. Operation completed.

Conserves requested observation/value without an extra effect.

## Semilla17 / baseline / memory.save — útil

BAXY: Memory saved successfully. No corrections made. Status confirmed as completed.

Conserves requested observation/value without an extra effect.

## Semilla17 / baseline / redacted-es — útil

BAXY: Tengo guardado un dato llamado "secret", cuyo valor está enmascarado.

Conserves requested observation/value without an extra effect.

## Semilla17 / baseline / redacted-en — útil

BAXY: The private memory contains a secret entry with a redacted value.

Conserves requested observation/value without an extra effect.

## Semilla17 / baseline / mixed-es — útil

BAXY: Tengo guardado el color favorito turquesa y un secreto que está enmascarado.

Conserves requested observation/value without an extra effect.

## Semilla17 / single-public-value / mixed-es — fallo

BAXY: Tengo guardado que el color favorito es turquesa y un secreto que está encriptado.

Claims encrypted secret without observation; baseline seed0 also attributes color to assistant. Existing bounded literal variant does not fix encryption and regresses seed17 baseline.

## Semilla17 / confirmation / actual-enable-en — útil

BAXY: Alright, Jordan. I remember your name. We’re about to enable private local memory. Should we go ahead and confirm this, or cancel it? Choose either confirm or cancel.

Exact pending decision explained.

## Semilla17 / confirmation / enable-es — fallo

BAXY: ¿Quieres confirmar o cancelar?

Only confirm/cancel, no action or target.

## Semilla17 / confirmation / forget-es — fallo

BAXY: ¿Quieres confirmar o cancelar olvidar tu color favorito?

Missing irreversible consequence; seed0 also omits action.

## Semilla17 / confirmation / forget-en — fallo

BAXY: Do you want to confirm or cancel forgetting your favorite color?

Deletion named but irreversible consequence omitted.

## Semilla17 / confirmation / sensitive-en — útil

BAXY: Do you want to confirm or cancel saving your secret in private local memory?

Exact pending decision explained.

## Semilla17 / confirmation / export-es — fallo

BAXY: ¿Quieres confirmar o cancelar la exportación de tus recuerdos guardados?

Destination and sync-risk omitted despite corrected466 payload.

