# Candidato837 — captura en píxeles físicos

Raíz integró los dos archivos de la propuesta DPI835, tras revisar todo el diff. No cambia el compositor, modelo ni datos de los paneles. Fuente aún **sin adoptar**: Full acumulado pendiente.

- Dueñas raíz: **47 pass / 0 fail / 0 skips**,186ms; WindowsScreenshotProviderTests y CaptureOcrLayoutTests. Sesión97344 recogida0(fb3ea7).
- Fast: exit0, Release15,82s,0errores;46pins intactos SHA`b0ea5aeae1792f1d0ef8fea8a66c071f30c1ec41e3f004e90df859ddb78aaaf5`.
- Probe nativo837: exit0(19ea01),20checks pass/0fail. Ventana y BMP2564×1320, recorte idéntico, `isClipped=false`; escritorio físico2800×1840. HWND/PID/creación coinciden con postlectura independiente. Proveedor y postlectura permanecieron en el mismo hilo y restauraron el contexto DPI original.
- El probe anterior829 producía1108×694 para esa geometría, porque comparaba DWM físico con escritorio virtualizado1244×818. DPI835 había aislado la causa con una comparación antes/durante/después y contexto restaurado. Los recibos anteriores quedan intactos.

El resultado prueba dimensiones, identidad, hash y restauración. No prueba ausencia de oclusión, tabla completa, frescura de valores, H0675, UI, voz ni ejecución de la petición original. La imagen real permanece privada; NATIVE_RESULT.json enlaza su recibo y SHA.

Antes del Full se reproduce un bloqueo adicional descubierto al preparar834: el handler externo exige `EffectObserved` a toda operación cuyo riesgo no sea ReadOnly; `ocr.read` conserva riesgo PrivacySensitive y devuelve una lectura verificada sin mutación. No falsear `EffectObserved` ni rebajar privacidad para eludirlo. Diagnóstico839 con prueba roja en preparación; Full no iniciado para incorporar, si procede, la reparación mínima de este recorrido.

OCR8326/8,8361/8 y8384/8 se conservan como diagnósticos independientes. Ningún control nativo mejora el conjunto; framing cerrado y compositor intacto. Encuesta36cubiertos/706abiertos/0NA; H0675 abierto; C03 EN_CURSO.
