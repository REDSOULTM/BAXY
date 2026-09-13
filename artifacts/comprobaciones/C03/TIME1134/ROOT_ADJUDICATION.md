## TIME1134 v6 — alarma creada y respondida, precisión fallida

203/742 cubiertos,539 abiertos,0 no aplican;0/35 categorías cerradas,C03 formal3/11. Una variante ejecutada (índice10, alarm-panel978-dev-04, «In eight minutes, sound an alarm for me.»):0pass1fail,24sin ejecutar,0créditos.

La tarea se creó y verificó (invocación cc4eec73-1179-42ab-8592-0fe7ee62e443, tarea BAXY-Alarm-ec23c8961bec423696b25b52dc7441c4). La reparación TIME1133 sí produjo final útil y fiel: «Alarm scheduled for 01:00 UTC.», sin missing_name. Falla igualmente por el criterio sellado de tolerancia0: dueUtc01:00:44.270822Z frente a NextRun01:00:44Z; StartBoundary registrado22:00:44-03:00 también sin fracciones. Éxito de respuesta y fallo de precisión se conservan separados; ninguno acredita.

Raíz canceló sólo la tarea propia por identidad exacta y verificó su ausencia; EXIT0, pins intactos, sin violaciones. 29,265s; pico GPU3495,56MiB; pico RAM del árbol1732,04MiB. Sin tests por orden del dueño. Juicio tomado por Codex raíz antes de la pausa (FABLE_PAUSE_STATE.json) y registrado aquí por Fable sin repetir la ejecución. Evidencia: TIME1134/ROOT_ADJUDICATION.json; privado en C03-time1134-instrument-v6/private.

Siguiente: TIME1139 aísla dónde se pierden las fracciones antes de cualquier nueva medición; no repetir índice10 con este candidato.

---
