# C03 — tramo 21: contexto descartado y adaptador heredado preparado

2026-09-06. EN_CURSO, sin bloqueo externo. No se cambió fuente del producto,
registro del runtime, política de evidencia ni umbrales. No se ejecutó Full.

## Diagnóstico de contexto: dos variantes sin mejora

`astra-history-ablation-ready`: sesión 87935 terminal 0, 12 respuestas,
15,47 s, pico GPU 3497,56 MiB. Se compararon seis preguntas de corpus-warm
con historial completo y con sólo mensajes de usuario. Payloads reconstruidos
con el límite de 12 mensajes del shell y el método chat, no capturados del HTTP
original. PREREG conserva payloads, modelo, sampler y huellas de fuente.
Sin mensajes del asistente, t10 responde sobre backup en vez de gravedad y t13
cambia del inglés al español. t15 sigue circular y no obedece spanglish.

`astra-history-isolated`: sesión 48134 terminal 0, seis respuestas, 11,03 s,
pico GPU 3497,56 MiB. Sólo pregunta actual, instrucciones de sistema conservadas.
t13 es pertinente; t14 añade una exclusividad falsa, t15 es circular y sólo español,
t10 usa una analogía sin sentido. No se propone quitar memoria del producto.

Conclusión: no adoptar ninguna poda del historial. RequestReading sí reconoce
mixed; el fallo persiste sin historia. No más variantes de poda sin evidencia nueva.
`astra-history-ablation` fue un intento previo sin respuestas: faltaba la variable
del servidor; se preservó el log y se corrigió sólo el lanzador diagnóstico.

Las 18 preguntas, respuestas y evaluaciones individuales están en
[PRUEBAS_CONTEXTO_C03.md](<D:/Perfil/Escritorio/ETC/Programacion/BAXY DEFINITIVO/artifacts/comprobaciones/C03/PRUEBAS_CONTEXTO_C03.md>).
Son inferencias directas, separadas de los 1822 turnos del informe del producto.

## Herencia preparada: Gemma 4 E2B LoRA

La evidencia histórica localizada en `biblioteca/gemma4-agent/documentacion/09_finetune/`
describe mejoras de vocabulario de herramientas, no aceptación C03 multilingüe.
El GGUF fusionado histórico falta; sí existe el adaptador local en
`../Probando Gemma 4/dataset_finetune/out/lora/`. Se copió sin escribir allí.

Destino: `D:/BAXYRuntime/experiments/models/gemma4-e2b-inherited-d3b0fed4/`.

| Pieza | SHA256 |
|---|---|
| adapter/adapter_model.safetensors (original) | d3b0fed4c0a6806fdcc48754cfe40483015c7b796b7cb5b45b0e10d9aeddc3ec |
| adapter-f32.gguf (convertido, 101385024 bytes) | aa03467549368b5fef8af29c8782eac968cdb7f5634e0a40af78b5800c56b33d |
| base/config.json | 1b28f3d2c3100f6c594754b81107428bd7b822a7f48272ca681dae9d2ec38330 |
| base-gguf/gemma-4-E2B-it-Q4_K_M.gguf (3106738272 bytes) | 740185b21d22ceb83a11c3aa62ad5842ef32c70f6096d756bbee85a1e4ec34b8 |

Conversión oficial llama.cpp b9980: sesión 20323 terminal 0, arquitectura Gemma4,
`scratchpad/llama-c03-b9980/convert_lora_to_gguf.py --base <destino>/base
--outfile <destino>/adapter-f32.gguf --outtype f32 <destino>/adapter`.
Log: `scratchpad/c03-lora-convert.log`. Herramientas externas usadas sin modificarlas.

Base descargada de `unsloth/gemma-4-E2B-it-GGUF`, revisión
`0314792d7f1f7e229411f620751375812bb9faf2`, SHA verificado en streaming.
Sesión 21234 terminal 0, 86,61 s, log `scratchpad/c03-inherit-gemma-base-download.log`.
Primer intento falló por HF_HUB_OFFLINE; sólo el proceso descargador lo desactivó.
Proveniencia: INHERITANCE.json, BASE_DOWNLOAD.json y BASE_VERIFIED.json en destino.

**Limitación:** el adaptador original no conserva la revisión exacta de su base
de entrenamiento. Esta base estándar sin QAT es de la misma familia, pero todavía
no se ha demostrado compatibilidad ni calidad conjunta. La base QAT anterior era
distinta. Convertir y descargar no acredita que el candidato funcione.

## Reanudación concreta

Prerregistrar una comparación corta de base estándar frente a base+adaptador usando
las mismas preguntas fallidas y narración con hechos verificados. Un modelo a la vez,
medición GPU atribuible y techo 4096 MiB. Heredar el Recorder de los scripts de contexto
y usar una subclase diagnóstica de LlmRuntime._server_command para añadir --lora;
sin editar fuente ni registro. BAXY_MIND_LLAMA_SERVER debe declararse en el lanzador.
Verificar compatibilidad al cargar antes de inferir. No repetir el diagnóstico QAT.

Siguen pendientes panel de desarrollo verde, 100 nuevos, UI real, runtime registrado,
Full final y publicación propia fuera de main. La preparación del modelo no cuenta
como respuesta útil ni como aceptación. No hay proceso de descarga pendiente.
