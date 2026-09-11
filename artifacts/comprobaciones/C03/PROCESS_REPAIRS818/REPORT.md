# Reparaciones 816–818 de respuestas de procesos

Se corrigen dos rechazos falsos y la selección del plazo de composición de listas cortas con varias filas. Las tres causas tienen reproducciones independientes; el siguiente panel medirá el conjunto. No cambia el prompt, modelo, perfil, proyección de hechos, rúbrica ni casos.

| Causa demostrada | Cambio mínimo | Prueba que limita la afirmación |
|---|---|---|
| Una expresión normal, «current context», se clasificaba como código interno. | Retirar esa única condición de la regla existente. | Baseline raíz:4fallos/6pass. Después:284pass/0omitidas. Los conteos de prueba explicitan alcance limitado; el borrador813 también exageraba la observación y no se acredita. |
| «complete» se confundía con un corte de «completeness», palabra descriptiva de los metadatos. | El detector existente deja fuera los descriptores observationScope/unit. Mantiene nombres, títulos y capacidades observados. | 696pruebas raíz/0omitidas/7,54s. Replay privado del primer borrador t15 sin inferencia: mismo texto y payload, una llamada Recorder. No corrige la omisión de145observados ni regrada815. |
| Cinco filas cortas recibían sólo4segundos de composición, aunque requieren una lista. | Las observaciones verificadas y exitosas con más de una fila de procesos seleccionan el presupuesto denso existente:9segundos internos/10externos enGPU. | Dueñas aisladas158pass/0omitidas; raíz integrada289pass/0omitidas/17s. Controles0/1fila,2/5/7,8/50,512caracteres, datos inválidos, fallo, CPU y protocolo. No se amplían valores de presupuesto, tokens ni reintentos. |

815 sigue39/50. Sus seis intentos de resultado de t31 no publicaron borrador; esto demuestra el presupuesto aplicado y los reintentos, pero no mide cuánto habría tardado una inferencia nativa aislada. La tanda819 podrá acreditar recuperación de respuestas, sin atribuir por sí sola cada ganancia a un componente individual.

Fast pasó y Full acumulado repetición1 quedó verde: .NET4.657pass/1omisión agregada; Python12.898pass/3omisiones/466subpruebas/620,88s. Las16optativas impresas de .NET no son disjuntas ni se suman.33pins intactos. El primer Full rojo y la reparación exclusiva de tres referencias actuales están conservados en FULL_RESULT, FULL_FAILURES y FULL_RETRY1/IDENTITY_REPAIR. No hay nuevos datos ni campañas de audio.

Encuesta28/742cubiertos,714abiertos,0NA; matriz3/11cumplidas; ninguna categoría nueva cerrada. Full final, aceptación100, ocho rutas, UI y audio siguen pendientes. Los worktrees816/817/818 se retiraron tras verificar snapshots exactos; WORKTREE_CHECK y WORKTREE_RELEASE conservan la prueba. La tanda819 preparada exige los sellos verdes de FULL_RETRY1 antes de arrancar. BAXY permanece cerrado para uso manual.
