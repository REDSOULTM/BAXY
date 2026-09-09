# Recuperación106 — candidato actual, 2026-09-07

Se heredan literalmente los doce comandos finales de routes-regression46:
tres averías del compositor, cada una con restauración y repetición de la
petición en el mismo proceso, perfil y sesión. [Prerregistro](astra-recovery106/PREREG.json).
Fuente103/Qwen3.5 override. No borradores escritos a mano, hook de cable,
pruebas normales de reserva, UI ni aceptación acústica.

| Inyección | Petición literal, repetida tras restaurar | Terminal de avería | Respuesta tras restaurar |
|---|---|---|---|
| reject | ¿Qué hora es? | composition_failed: unsafe_language;recovery:unsafe_language;retry_exhausted | Son las 06:29. |
| timeout | What time is it? | composition_failed: composer_request_failed;retry_exhausted | It is 06:30. |
| exhaust | Dime la hora, please. | composition_failed: no_response;recovery:no_response;retry_exhausted | Son las 06:30. |

Todas las inyecciones y restauraciones registran PID30524. Cada avería deja
hasCompositionError=true, causa concreta, controles habilitados, isBusy=false,
cero composición pendiente y sin plan pendiente. Cada petición posterior produce
published_final, limpia el error y conserva los controles utilizables.
Las tres horas son compatibles con su reloj observado; no se afirma prosa de
error ni seis respuestas normales correctas. Son tres estados de avería y tres
recuperaciones útiles. El deadline exterior no se agotó; mode=timeout inyecta
la avería de composición, no una caída real de red ni un bloqueo físico del LLM.

[Eventos](astra-recovery106/events.jsonl), [auditoría](astra-recovery106/compose-audit.jsonl),
[resultado](astra-recovery106/RESULT.json). Handle57526exit0;31,55s,
GPU3173,5625MiB,RAM4510,03125MiB,atribución disponible,registro intacto.
Proceso y descendientes propios finalizados; sin parada forzada ni otro modelo.

Límite pendiente de UI: FieldProductChannel emite composition_failed tipado y
actividad SYSTEM con ese mismo código; useEventStream no tiene un caso específico
para el evento. El conductor acredita estado/recuperación, pero no que esa señal
sea entendible en una ventana real. Inspeccionar esa ruta físicamente antes de
decidir cambios; no confundir UI104 errores de archivos con agotamiento total del
compositor. Tampoco equivale a fallo físico del servidor y restauración.

No cambia source ni requiere repetir las97pruebas/Fast verdes de103. No Full;
C03 EN_CURSO: confirmación actual, avería visible/recuperación, voz, cien humanos,
runtime sin override, continuidad y validación/publicación finales pendientes.
