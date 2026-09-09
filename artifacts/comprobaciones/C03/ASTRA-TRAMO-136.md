# C03 — integración del AEC en captura — 2026-09-07

EN_CURSO. Fuente anterior119/124 fijada por TRAMO119_128_PINS y evidencia129–135
por TRAMO129_135_PINS. Prototipo134 físico:0barge frente a1en sombra sobre mismos
bloques;135 recupera frase completa. PRUEBAS_AEC129_134.md fija límites/alternativas.

136 sustituye NLMS de clips por SpeexDSP por sesión, antes del VAD/segmentación.
Retira transporte de referencias a ASR y conserva indicador AEC aplicado. El guard
recibe par crudo alineado con la latencia de un bloque, sin cambios de umbral.
Asset por resolvedor existente; estado nativo creado/usado/liberado por captura.
No cambia backend TTS, modelo LLM ni registro.

Pruebas:127pass/0skips/12,43s iniciales, más3 pruebas de captura/propiedad en
éxito/fallo. Suite integrada final130pass/0skips/10,64s, sesión50884exit0:
test_speex_aec,test_mind_voice_runtime,test_piper_tts,test_neural_speech_output,
test_goal06_voice,test_asset_resolution. No algoritmos nativos simulados como
aceptación: las fixtures verifican limpieza, sesiones y alineación del par.

Native137exit0:265pares exactos del físico134 alimentados al dueño integrado;
PCM limpio bit a bit idéntico y todos los pares crudos alineados. Media0,134ms/
p990,162ms offline; estado nativo destruido. Asset de desarrollo staged por hash
bb683ab3c50f66f777f0d2eb570b57c0ef5c71cb7e45535f9625a3f2ab56d9f1 en
D:/BAXYRuntime/assets/aec/speexdsp-1.2.1/speexdsp.dll, con COPYING y receta.
Manifest de runtime no promovido. Native137 no es otra prueba de audio físico.

Fast inicial encontró __all__ obsoleto en voice_aec; retirado. Fast39832exit0,
Release3,14s,0avisos/errores. No Full.

138 integrado físico sin wrappers:10271/20182exit0, pero speaking1,578s y2barge_in;
no error del proveedor. No aceptación acústica ni entrega cerrada. La paridad DSP137
no prueba la temporización de referencia en vivo. Investigar los bloques realmente
consumidos de latest512 y latencias de captura, sin ajustar umbrales ni repetir hasta
pasar. Prototipo134 añadía un VAD en sombra; no atribuir su pase a integración idéntica.

Revisión de callers localizó scripts/run_voice_system_gate.py importando aún el
NLMS retirado. Se actualiza su componente AEC a la misma secuencia de frames con
el nuevo dueño; mantiene semilla, señal, retardo y umbral6dB. Componente aislado
ejecutado:15,99dB/pass; no se ejecutó la compuerta física completa. Actualizados
el mapa de ownership y docstring de flujo. Fast posterior29493exit0 (ver log fijado).
139–142 localizan discontinuidad de referencia y falta de reloj ADC en MME;
PRUEBAS_REFERENCIA138_142.md. Fuente136 aún no resuelve aceptación física.
