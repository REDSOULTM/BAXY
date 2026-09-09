# C03 — disponibilidad y cancelación, 2026-09-06

La traza del tramo 3 mostraba decisión no disponible a los tres segundos y
ambiguous_request como hecho de recuperación. El único plazo de tres segundos
en esa entrada es VoiceCancelAsync, enviado al registrar cada mensaje de usuario.
Un test con petición de modelo en curso y acuse tardío de voz reprodujo que
IsReady pasaba a false y el siguiente pedido quedaba inutilizable. Otro test
reprodujo que una decisión ausente acusaba de ambigüedad a la petición.

Se conserva IsReady sólo ante timeout del acuse de voice.cancel: sigue devolviendo
false, no afirma haber cancelado, descarta el acuse tardío por correlación y
mantiene recuperaciones por fallo de IO/inferencia. La causa de una decisión
ausente ahora es mind_unavailable. Tipo/id/plazo se añaden a la traza con etiquetas
permitidas por el logger existente. No se relajó su protección de datos.

Antes: 2 fail. Después: 69 pass/0 skips de MindShellEndToEndTests y
PlannerAppBoundaryTests. `astra-voice-cancel-isolation`: 1/3 correctos; dispone
de decisiones reales, pero pide un nombre ya presente y reinterpreta cancelar.
Su adjudicación y fixture comprobado/limpiado están conservados.

La cancelación de una aclaración pendiente se resuelve ahora con el parser de
control existente: limpia el objetivo y entrega el hecho clarification_cancelled,
sin otra decisión ni reinterpretación del pedido. La nueva regresión falló antes.
Después: 70 pass. astra-clarification-cancel dio 3/6 correctos: el control
español limpia el pendiente, pero la prosa es imperativa; cancel that no era
reconocido. Se amplió el parser existente con referencias a la petición pendiente
(that/it/eso), sin aceptar órdenes compuestas ni autorizar una acción nueva.
Antes: 6 fail/14 pass; después: 101 pass/0 skips de MemoryOperationProtection,
MindShellEndToEnd y PlannerAppBoundary.

La proyección de status descartaba el resultado completado y llamaba cause al
estado resultante. astra-cancel-completed subió a 5/6 correctos; aún inventaba
un motivo en español. Se conserva ahora el estado en state, y se excluye acting
de completed. El contraste de progreso falló antes. Después: 369 pass y 101
subtests de los cuatro owners Python; ruff verde y V8 5 pass. La corrida
astra-cancel-state terminó exit 0 con **4/6 plenamente correctos**: la relación
causal queda corregida y el control ES/EN funciona, pero vuelve la aclaración
agramatical y la cancelación española usa metadiscurso artificial. Adjudicación
guardada. STT: 12 pass/1 skip ambiental; no es aceptación nueva de voz. No seguir
retocando el mismo prompt ni añadir vetos por esas frases. Sin procesos activos.
Full sigue reservado para el cierre de C03. No se cambió ni descargó un modelo.
