# C03 — publicación real de avisos de voz — 194

Tres casos diagnósticos en la aplicación de escritorio, iniciada con `py main.py`.
Fuente192 sin cambios; modelo Qwen3.5 con override, registro intacto. Un hook
externo emite eventos de diagnóstico; no inyecta respuestas redactadas.

| Caso | Salida visible | Evaluación |
|---|---|---|
| Evento wake | Estoy listo para ayudarte con lo que necesites. | Acuse útil sin afirmar ejecución. |
| Transcripción dudosa | ¿Podrías repetir lo que dijiste? | Pide repetir sin inventar lo escuchado. |
| Nueva pregunta durante composición del acuse | Son las 13:05. | Nuevo resultado fiel; el segundo acuse queda descartado. |

La tercera prueba entrega «¿Qué hora es?» mientras el compositor redacta un
acuse, con pausa diagnóstica de 0,5 s en esa invocación. El historial final tiene
cinco entradas: bienvenida, primer acuse, aclaración, pregunta y hora. La marca
published del audit del compositor describe su etapa, no acredita publicación
posterior en UI. UI-supersede.txt demuestra ausencia del segundo acuse.

Core: utc `2026-09-07T16:05:01.2546992+00:00`, localUtcOffsetMinutes `-180`.
El resultado local 13:05 coincide con la respuesta visible. Los textos se
inspeccionaron en la ventana real mediante Computer Use y quedaron conservados.

Monitor51134 recogido exit0. Fin mediante STOP_APP del propio lanzador;
cleanupExit0 y launcherExit0. Duración540,41s; GPU3480,15234375MiB,
RAM5326,40625MiB. No promoción ni cambio de AEC: el producto conserva Speex.

Estos son tres casos técnicos, no entrada humana ni reserva. La activación usa
la costura de wake aún no aprobada. No hubo captura acústica ni ajuste de volumen;
no se acredita audio físico ni ocho rutas completas. Fallo183 y mezcla129 siguen
abiertos. Las pruebas113Python/16.NET/Fast corresponden a fuente192/193.

Siguiente: incorporar controles humanos públicos con transcripción conocida al
diagnóstico de conservación del habla, antes de otra sustitución de AEC. Separados
de la reserva Carter→BAXY. C03 íntegro EN_CURSO, sin Full final ni publicación.
