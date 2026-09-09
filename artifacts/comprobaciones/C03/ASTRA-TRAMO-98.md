# C03 — progreso desde actividad real — candidato98

97 comprueba ocho combinaciones de fase/idioma sin anticipar acciones cuando
el narrador recibe sólo actividad actual. Se conserva modelo, sampler e instrucción
originales;93–95 no se adoptan. PRUEBAS_PROGRESO93_97.md fija contraste y límites.

App deriva fase con el FieldBridgeContract existente, sin otro clasificador.
CreateMilestoneDraft incluye paso/total sólo durante actuación y con posición
válida. ComposeMilestoneAsync captura también StatusDescription; TryApplyMilestone
descarta resultado si el turno terminó, cambió o está en otra fase/paso. Un cambio
de estado retira el label anterior sin borrar el reloj de hitos.

Python proyecta fase a actividad, conserva posición válida y no manda el objetivo
futuro al narrador. El pedido original sigue entrando a compose_user_message,
lectura de idioma y validadores, y no cambia el input del planner. Se aplica a
primera composición, reconstrucción específica de progreso y ambos reintentos.
No se introduce respuesta visible fija ni se describe una acción sin empezarla.

Pruebas iniciales localizaron reconstrucción tardía que reinsertaba texto y una
proyección genérica que retenía step durante comprensión: corregidas. Dos tests
antiguos fijaban que el progreso recibiera el pedido; ahora fijan idioma conservado
y ausencia del objetivo no ejecutado. Las demás rutas siguen conservándolo.
Cuatro suites completas:1155pass/0skips/5,66s. Integración C03FactPreservation,
PlannerAppBoundary,Goal06VisibleVoice,FieldProgressContract:203pass/0skips/15s.
Formato .NET acotado aplicado. Logs TEMP/c03-progress98-{python-final,dotnet}.log.
Fast en ejecución49118, TEMP/c03-progress98-fast.log.

scratchpad/c03-progress-pipeline99.py preparado, no ejecutado: ocho fixtures97
con compose_user_message real, incluidos guardas/reintentos. No acredita fase
observada ni UI; después hará falta producto y UI con casos reales.
Fuente92 recupera4/4, no se ha vuelto a ejecutar ese panel sin causa nueva.
Modelo Qwen3.5 sólo override; C03 EN_CURSO. Sin Full.
