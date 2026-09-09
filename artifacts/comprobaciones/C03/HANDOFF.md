# Handoff C03 — fuente626 publicada — 2026-09-09

## Objetivo y estado
Completar las ocho rutas de respuesta veraz en producto real, encuesta742 con variantes, UI/voz y recursos conjuntos; no sólo los paneles de conversación. Goal activo; ninguna decisión pendiente del dueño. Autorización536 para históricos/nuevos/encuesta vigente. BAXY manual cerrado. No procesos de campaña ni build activos.

Fuente626 publicada en `67085974c69c60034cba2ad95d156ddb096de6f6`, HEAD=origin verificado; main intacto. Cambia sólo la política de salida de progreso mixed a español permitido, conservando inglés explícito, fases/pasos y reintentos. La conversación conserva spanglish. `astra-progress-source626/RESULT.json` y `astra-conversation-regression627/RESULT.json` fijan evidencia. Encuesta25 cubiertos/717 abiertos/0 no aplicables;742/rev1248 intacta.

## Validación
`pytest tests/test_c03_request_preservation.py -q`:200pass. Dueñas ampliadas (ese fichero, compose_contract, first_signal, turn_policy, price_v8 y stt_quality_evaluators):1363pass/1skip ambiental (archivos de campaña STT ausentes),8,30s. `scripts/test_source_quality.ps1`:Fast verde, Release20,29s,0advertencias/errores.33pines de6campañas verificados también en staging. Full626 no ejecutado: sólo Python; Full final sigue pendiente. Full606 es línea base histórica, no prueba de626.

627 conserva33/35 finales; H0012 y Atlas fallan. Avisos boot_stage emitidos ya no narran el análisis del idioma; conservan tercera persona española pendiente. No hay prueba de pantalla/voz. Pico3499,559MiB GPU/2361,191MiB RAM, sin UI/voz juntas; no mínimo global acreditado.

## No repetir sin evidencia nueva
619 se rechazó por regresión de tono Qwen aunque mejoraba Gemma.615–617 no calificaron el subtipo social.622–624 no promovieron Ministral: guardia14/20original y11/20subtipo; se aisló user-user incompatible, prosa compatible4/12; nativo8/12 e identidad mínima0/12 con1corte. Todo sellado.565 ya rechazó cambiar el destinatario de la fase;625 no lo reabre.

## Siguiente acción
Inspeccionar el caso `missing-value` de `%LOCALAPPDATA%/BAXY/C03-effect-controls608-private/turn-audit.jsonl` y `compose-audit.jsonl`: «Pon el volumen a...» termina en `missing_literal_fact`/reintentos agotados en vez de preguntar el valor. Localizar el primer campo erróneo antes de inferir o editar; empezar en el owner de composición `src/baxy_mind/llm.py` y el traspaso de aclaración en `__main__.py`. Es un bloqueo de aclaración C03 distinto de los barridos de identidad/estilo descartados.

Pendientes:717requisitos, identidad/tono/progreso y otras rutas, recuperación de errores, UI real, loopback completo/AEC separados, VRAM conjunta mínima, registroCPU si se califica, Full final y publicación. No cerrar filas de otros owners ni el goal por esta reparación parcial.
