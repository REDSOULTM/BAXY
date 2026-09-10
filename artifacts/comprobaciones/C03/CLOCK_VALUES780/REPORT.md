# Los50valores de fecha y hora se conservan

25capturas UTC con offsets explícitos producen25respuestas de hora y25de fecha. Las50cumplen: incluyen cambio de año, febrero bisiesto/no bisiesto, cambios de mes, medianoche, mediodía y offsets de30/45minutos. Entradas, observaciones sintéticas, expectativas y respuestas literales figuran en CASOS_SINTETICOS.md.

Es el compositor local de BAXY con instrucciones, validadores y reintentos activos.49borradores iniciales coinciden con sus finales. El caso35 produjo Son las12del mediodía, correcto para12:00, y BAXY lo rechazó como missing_name; el reintento publicó Son las12:00, también correcto. Se retiene el veto falso como defecto de integración.51peticiones reales, todas con T0/max_tokens256, thinking desactivado y cache_prompt false; ninguna truncada o fallida. Modelo y comando del servidor conservados respecto de779. La primera preparación se detuvo antes de inferencia porque el fixture omitía reconocer la clave version: se preservó version1 y sólo se variaron UTC/offset. Hubo una sola pasada de50casos, con el reintento incluido.

16,281s incluyendo arranque;3497,56MiB VRAM y757,52MiB RSS sumada en el árbol del compositor. Todas las guardas intactas, sesión21475 terminal0 recogida. No prueba selector, provider, UI, voz ni reserva; tampoco arregla los dos fallos de779 ni concede cobertura automática.
