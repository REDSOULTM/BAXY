# 431 — aclaración de aplicación genérica incorporada

Se amplió la rama de aplicación incompleta que ya existía en
`effect_intent.resolve_explicit_clarification_intent`. El objeto genérico completo
usa ClarificationIntent(application), la pregunta redactada por el modelo y la
continuación del producto. No cambia el catálogo, el control de appId, el modelo,
los permisos ni el prompt. No añade otra etapa de inferencia.

La gramática reutiliza los verbos de apertura y el tratamiento de prefijos;
consume la petición completa. Conserva nombres concretos, negación, preguntas,
hipótesis, otro dispositivo y órdenes añadidas fuera de esta rama. No autoriza
una apertura ni escoge una aplicación por el usuario.

Baseline:15 fallos/20 pass/0 skips; doce peticiones no obtienen ClarificationIntent,
tres recorridos entran indebidamente en composición en vez de aclaración.
Primera edición:32 pass/3 fallos por cierre «por favor»; se completó la gramática
del cierre sin cambiar etiquetas ni retirar controles.

- Focal final:35 pass/0 skips,1,20s.
- Owners (test_effect_intent, test_turn_policy, test_current_catalog_review,
  test_catalog_operation_aliases):2714 pass/0 skips,48,67s.
- `scripts/test_source_quality.ps1`: Fast entero verde; build3,86s,
  0 advertencias y 0 errores.

La conducta de producto aún requiere432: repetir los ocho turnos426 con el
mismo perfil diagnóstico en memoria privada nueva. La aceptación humana fresca
no se consume. Full queda para el candidato final de C03.
