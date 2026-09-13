# TIME1139 — sondas de precisión del Programador de tareas

Tres sondas de raíz sin producto, sin GPU y sin tocar las910 tareas BAXY-Alarm preexistentes (conteo igual antes y después). Las dos tareas sonda usaron nombres propios únicos, acción `cmd /c exit0`, fecha2027 y se eliminaron por identidad exacta con ausencia verificada.

1. `New-ScheduledTaskTrigger -Once -At` con22:00:44.2708220-03:00 devuelve StartBoundary `2026-09-13T01:00:44Z`: pierde fracciones. Asignar StartBoundary al objeto CIM conserva `…44.270822-03:00` en memoria.
2. Registrar ese trigger con fracciones (cmdlet): el servicio persiste StartBoundary `…09:34:56-03:00`, NextRunTime `…56.0000000`, XML exportado sin fracciones.
3. Registrar por XML con StartBoundary fraccional: mismo resultado, sin fracciones.

Demostrado: el servicio normaliza a segundos enteros por ambas vías. El criterio sellado (due fraccional igual a NextRun, tolerancia0) es insatisfacible en esta plataforma por cualquier parche del provider. No se propone parche ni se reinterpreta el criterio: decidir requiere al dueño (ver ESTADO_PARA_DUENO_2026-09-13.md). La composición TIME1133 ya publica el NextRun verificado; el éxito de respuesta sigue separado del fallo de precisión.

Reanudación exacta en TIME1139/PROBES.json.
