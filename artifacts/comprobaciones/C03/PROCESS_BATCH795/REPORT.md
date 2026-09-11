# Procesos795: baseline de producto

50 respuestas completas, 4 correctas y 46 fallidas según el criterio congelado; no acredita cobertura de encuesta. Las cuatro válidas son H0169, H0669, memory_rank-01 y memory_rank-06. Nombres distintos en un top no exigen añadir PIDs ni cifras que el usuario no pidió. Para instancias homónimas se conserva el criterio congelado de identidad.

Los fallos se concentran en lectura fresca, conteo/alcance, identidad y CPU actual. El modelo registrado sigue siendo Qwen; esta prueba no reabre su elección ni representa modelo nativo. El bruto, las transformaciones, los hechos y los finales están en el informe privado RESPUESTAS.md; ADJUDICATION.json registra cada turno sin publicar sus datos del PC.

Recursos del árbol conductor: 3499.55859375 MiB VRAM, 2445.0625 MiB RAM; 258.594 s; violaciones: []. No incluye certificación de UI o voz.

Reparación796 en curso: lectura CPU por intervalo con identidad estable y normalización por procesadores lógicos de la máquina; proyección de conteo separado de filas; conservación de PID en la operación de inventario; reconocimiento de preguntas y límites hablados. Sin promoción ni nueva cobertura hasta validar y repetir la categoría.

Herencia: WindowsSystemStatusProvider usa muestreo150ms y WindowsSystemStatusProbe obtiene GetActiveProcessorCount de todos los grupos. La biblioteca ya consultada no aportó otra implementación vigente. Referencias primarias revisadas2026-09-10: [Process.TotalProcessorTime](https://learn.microsoft.com/en-us/dotnet/api/system.diagnostics.process.totalprocessortime?view=net-10.0) documenta tiempo CPU acumulado; [Environment.ProcessorCount](https://learn.microsoft.com/en-us/dotnet/api/system.environment.processorcount?view=net-10.0) puede reflejar afinidad/cuota del proceso y no sirve como denominador físico global. Se reutiliza la sonda Windows existente.
