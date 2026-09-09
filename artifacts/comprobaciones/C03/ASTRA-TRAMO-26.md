# C03 — tramo26: modelo desnudo y capas

Petición del dueño: aislar LLM y añadir ecosistema. Informe y evidencia completa:
[DIAGNOSTICO_POR_CAPAS_C03.md](DIAGNOSTICO_POR_CAPAS_C03.md).

144respuestas conversacionales+144compositor+6replays+21App=315observaciones.
No aceptación ni tasa de acierto global. Granite registrado intacto; Qwen base
experimental sin adaptador. Todo bajo4096MiB. App72,14s incluye38,11s preparación;
21publicados, tres falsedades inequívocas, ventana propia sólo cerrada tras confirmar.

Arreglo mínimo heredado del lector existente: clasificación de la pregunta dentro
del prefijo de idioma. Preserva literal y no añade capa/frases visibles.130tests
pass; Fast verde, build0errores/0advertencias; Full final pendiente.

V1 invalida último contraste por error de instrumento; V2 preserva historial.
Compositor: seed no siempre explícito, usar antes/después de la misma llamada
para causalidad de validadores. Todo documentado, sin ocultar intentos inválidos.

Hallazgos y siguiente acción en CHECKPOINT: corregir narración/guardas con hechos,
no nueva ronda LoRA. Entrenamiento/evaluación v4 terminados y pausados, no promoción.
C03 EN_CURSO; no bloqueo externo ni procesos pendientes; main sin publicar.
