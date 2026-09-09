# Fuente119 — proveedor Piper completo y voz por idioma — 2026-09-07

Herencia/contraste/mismo control: [PRUEBAS_TTS114_118](PRUEBAS_TTS114_118.md).
La referencia Windows recuperó los seis contenidos ES/EN; el frontend manual
perdía puntuación, segmentación y detalles del contrato de fonemas. Se sustituye
por el Piper completo medido. No se conserva un motor alternativo manual ni
se añade una colección de reglas de puntuación.

`piper_tts.py` es dueño del proveedor y sus activos: JSON UTF-8 con un único
pedido, Piper local sin shell/ventana, PCM firmado16bits, plazo30s y cancelación
que mata y recoge exclusivamente el hijo propio. Un proceso por síntesis evita
otro protocolo persistente;118 midió0,844–1,218s incluido cargar el modelo.
El coste integrado sigue pendiente. No envío externo de texto ni inferenciaGPU.

`voice_output.py` conserva su hilo, cola, generación de cancelación y OutputStream
propio. Se retiran el fonemizador CLI manual, la llamada ONNX manual y sus
resolvedores de eSpeak. El proveedor completa las oraciones; la cola elige voz
por texto ya compuesto, reutilizando la evidencia de idioma de request_reading.
Las instrucciones citadas dentro de una respuesta no se interpretan como pedidos
de idioma. Idioma de texto mixto: voz de la evidencia predominante; empate español.
No clasificador adicional ni cambio del contrato mente/kernel.

La cola informa nombre/hash/frecuencia de la voz seleccionada. Se corrige
voice.status, que antes informaba siempre el hash español aunque cambiara la
salida. Los callers de tooling Goal09 usan el proveedor sustituto. La prueba
del antiguo framing manual se retira porque ese código ya no existe; la entrada
del proveedor, cancelación, PCM y los resultados nativos quedan comprobables.

Assets declarados: piper_runtime y neural_tts_english_voice. Copias verificadas
del runtime118 y John114 en D:/BAXYRuntime/assets/piper-2023.11.14-2 y
D:/BAXYRuntime/assets/voice/baxy-en; no se sobrescribió un directorio existente.
La voz española se conserva. Registro mind-runtime-v1 intacto: esto es candidato
de desarrollo, no promoción. Antes de promover faltan hashes/configs/runtime
de ambos idiomas en registro/preflight y regresión de instalación correspondiente.

Validación dueña con Python del runtime:
`python -m pytest tests/test_piper_tts.py tests/test_neural_speech_output.py tests/test_mind_voice_runtime.py tests/test_goal06_voice.py tests/test_request_reading.py tests/test_asset_resolution.py -q`
→311pass/0skips,10,36s,8132exit0. Primer ensayo:308pass/1fallo por mock de Popen
que interfería con la carga perezosa de numpy.testing; se comprueba PCM exacto
sin esa importación. No se relaja la expectativa. Retest1pass/13deselected.
Tests de selección ES→EN→ES, frecuencia/hash reales de la cola, Unicode/newlines,
fallo del hijo, PCM inválido, cancelación y plazo con recolección.

Fast inicial detectó un import numpy sin uso tras retirar el motor; eliminado.
Fast60843exit0: Release2,96s,0avisos/errores. Native12011445exit0: cola/proveedor
reales y sink PCM explícito; seis controles alternados con contenido recuperado
por ASR local e identidad de voz correcta. PCM listo en0,891–1,187s tras el primer
saludo (2,329s, incluye inicialización). Hijo Piper38440 observado durante
síntesis, cancelado/recogido en94ms; InterruptedError y worker finalizado.
Ese sink no es dispositivo físico ni UI; no aceptarlo como tal.

UI/audio121 tuvo tres finales fieles y3513,418MiB de GPU, pero el audio físico
no se recupera.123 localiza interrupción real al activar micrófono;124 corrige
el detector de eco.125 mejora a3,938s pero todavía emite barge_in antes del
final (off5,562/5,359s).126 sobre capturas existentes recupera la frase completa
off/off y pierde UTF-8 en direct, tanto micrófono como loopback. Véase
PRUEBAS_VOZ119_125.md; no confundir la mejora nativa con cierre acústico.

Fuente108/UI109 y todos los pendientes del CHECKPOINT siguen vigentes. C03
EN_CURSO: no reserva100, promoción, audio físico ni Full final acreditados aquí.
