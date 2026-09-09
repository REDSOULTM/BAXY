# 531 — declaraciones actuales verificadas

Las seis suites dueñas dieron **37 pass,0 fail,1 skip ambiental**,121,32s; sesión19647exit0. La omisión existente es la comprobación de resultados de una campaña STT ciega cuyos ficheros no están disponibles; no cuenta como certificación de audio. Fast: aprobado, build Release23,44s,0warnings/errors; sesión15663exit0.

Se conservan los sellos y resultados históricos de r277/V8/wake. Se actualizaron las expectativas del contrato vivo (abstención permitida y recuperación ante misión incompleta) y las declaraciones actuales de programas/runtime. Los únicos campos de identidad de runtime que diferían eran el nombre y SHA-256 del GGUF: Granite antiguo frente al Qwen registrado. GGUF y llama-server fueron rehasheados en disco y coinciden con el manifiesto, que no se modificó.

Un template se restauró a su hash LF publicado: c979e0e71a3e21b8f208e6ab120d5cb29327885f29d2a8b18fda67a723798e18. La prueba r278 verifica que ya no quedan ficheros restaurables por daño de fin de línea. Las copias previas privadas y los deltas están en DECLARATIONS.json.

Junto con528 y530, las dueñas de los25fallos de Full526 están resueltas. No se ha repetido Full ni se declara cierre. C03, UI/audio, reserva, cobertura y aceptación siguen pendientes. Encuesta0cubiertos/742abiertos/0no aplicables.
