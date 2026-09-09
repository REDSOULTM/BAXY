# Fuente112 — contrato de fonemas Piper — 2026-09-07

Audio110 no acredita contenido audible fiel. Native111 aísla la pérdida antes
del dispositivo: el generador ONNX recibía fonemas sin el PAD que espera el
modelo. Herencia, contraste primario, pares y límites en
[PRUEBAS_AUDIO110_NATIVE111](PRUEBAS_AUDIO110_NATIVE111.md).

Se corrige únicamente `_PiperOnnxEngine.generate` en voice_output.py: después
de cada fonema conocido se añade su separador PAD; se siguen omitiendo los
caracteres desconocidos, como el joiner IPA. Se conservan modelo, fonemizador,
parámetros, framing BOS/EOS, normalización de PCM y propietario de reproducción.
No otra capa ni paquete Piper. El modelo no cambia ni se promueve.

La prueba dueña fija una entrada canónica del modelo con fonemas de uno y
varios IDs, carácter desconocido y longitud real. Detecta la regresión que
las pruebas de reproducción/cancelación no podían ver al sustituir la síntesis
por PCM de prueba. No se relajan guards ni criterios de aceptación.

Comando con Python del runtime:
`python -m pytest tests/test_neural_speech_output.py tests/test_mind_voice_runtime.py tests/test_goal06_voice.py -q`:
**85pass/0skips,7,76s**, exit0. TEMP/c03-tts112-tests.log.
`.\scripts\test_source_quality.ps1`:33691 exit0, **Fast verde**,
Release3,37s,0avisos/errores; TEMP/c03-tts112-fast.log. No Full.

Native111 recupera tres controles españoles; el inglés sigue sin transcribirse
fielmente con es-419. Native11358330 exit0: tres respuestas inglesas consumidas
del producto, misma voz ONNX, sólo eSpeak es-419/en-us con PAD corregido.
en-us recupera el reloj, pero altera UTF-8 (you'll be the fake) y read (heal).
No resuelve3/3; no adoptar sólo fonemizador ni llamar fiel a una transcripción
que cambia hechos. No semilla ONNX fija: comparación de contenido, no igualdad
de ondas. RESULTS/PREREG en astra-native-tts113. Siguiente hipótesis: voz
entrenada en inglés, mismo motor y textos; no selector/modelo adoptados.

La verificación acústica posterior, entrada hablada real, reserva100, promoción,
continuidadC04–C09, Full final y publicación siguen pendientes. C03 EN_CURSO.
