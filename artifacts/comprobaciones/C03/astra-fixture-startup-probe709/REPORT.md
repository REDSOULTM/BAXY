# Arranque del Core: timeout reproducido

El fixture real produjo cinco arranques listos y falló en el sexto, antes de enviar una petición. Las cinco inicializaciones completas tardaron 8,17–9,40 segundos. La prueba diagnóstica NUnit cuenta como **0 pass, 1 fail, 0 skips**; no son seis casos de aceptación.

Se capturó la excepción exacta de saludo del Core a los 10,059 segundos desde InitializeAsync. El proceso seguía vivo. dotnet-stack terminó con exit0 y sin errores diagnósticos; su captura posterior muestra al Core leyendo stdin. Esto confirma que llegó a avanzar, pero no identifica por sí solo su espera exacta cuando venció el plazo.

El hijo PowerShell del inventario seguía presente 9,753 segundos después de crear Core y había salido a los 10,305. El timeout cayó dentro de ese intervalo. Se medirá el script por fases para distinguir Get-StartApps, metadatos Shell y sobrecarga de lanzamiento; no se atribuye todavía una causa única. La observación tuvo cadencia efectiva aproximada de 550 ms cerca del fallo y pudo añadir carga.

Se restauró el fixture byte por byte y se retiró el helper temporal. Todas las fuentes de CANDIDATE4 permanecen idénticas. El binario de tests contiene la instrumentación hasta el siguiente build; no se debe reutilizar con --no-build como validación de fuente restaurada.

La sonda no usó LLM, turnos, UI ni voz. No aumentó cobertura ni aprobó Full705. RESULT.json conserva conteos y huellas; procesos, excepciones y pila completos permanecen privados en LOCALAPPDATA/BAXY/C03-fixture-startup709-private.
