# Sonda 717: plazo agotado durante la preparación de audio

Mismo script literal y plazo de 3 segundos que 716. El observador identifica después del vencimiento al intérprete hijo del launcher por parentesco y fecha de creación. py-spy 0.4.2 logra capturar la pila sin variables locales.

La pila muestra `main -> prepare_resampler -> _resample -> scipy.signal -> interpolate -> optimize -> _trlib`. Todavía no se había emitido `hello` ni ejecutado el fallo forzado del dispatcher. Esto localiza la fase que consumía el plazo en esta ejecución; no demuestra que toda lentitud histórica tenga una causa única.

Los dos procesos propios fueron retirados comprobando sus fechas de creación. El script conserva el hash de la prueba original. `deadline_passed=false`; el código 0 del conductor no es un pass del test. Los datos crudos de la pila permanecen en la ruta privada registrada en RESULT.json. Sin cambios productivos, adopción o cobertura.

La repetición aislada de ambos owners también terminó: 0 pass, 2 fail, 57,96 s. Sus logs están archivados en `../astra-catalog-source712/FULL5_OWNER_REPRO.log` y `FULL5_OWNER_REPRO_EXIT.json`.
