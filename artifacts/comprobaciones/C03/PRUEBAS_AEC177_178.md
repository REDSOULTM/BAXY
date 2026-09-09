# C03 — inicio acústico y estimación de eco —177/178

177 terminado exit0. En el control127/129, speaking empieza en24,4738125s;
la referencia supera RMS20PCM en25,59s y la voz cercana sintética empieza
en25,5548125s. Por tanto no existe el segundo de adaptación que sugeriría
medir desde speaking: la voz cercana empieza35,1875ms antes del umbral de
referencia. Alineación de streamReadyUtc aproximada; no precisión acústica ADC.

Las salidas near-only176 dan retardo63muestras lineal y127residual. Se fija ese
retardo antes de proyectar la mezcla sobre la voz cercana conocida por ventanas
de300ms. La ventana25,8548s conserva proyección~0,731 en lineal pero~0 en final;
26,1548s pasa~0,508 a~0,031. No es una separación exacta ni un criterio de calidad,
pero respalda la pérdida adicional residual observada con ASR176. Véanse todos
los valores en astra-timing177/RESULTS.json; no inferir conservación sólo por RMS.

## Contraste178 prerregistrado

El extracto usado define ep_strength.default_gain=1. Antes de una estimación
lineal usable, residual_echo_estimator.cc calcula R2 con potencia de referencia
por el cuadrado de esa ganancia. No estima aquí la ganancia desde cada grabación.

La [fuente actual de WebRTC](https://webrtc.googlesource.com/src/+/refs/heads/main/modules/audio_processing/aec3/residual_echo_estimator.cc),
consultada2026-09-07, blob29776e88e941905af90d88011488fba25aa0dbc2, expone variantes
de campo con0,1 para ganancias de reflexiones tempranas/tardías. Se contrasta
esa hipótesis en el extracto, que tiene una sola ganancia común. No equivale al
WebRTC actual completo ni es una recomendación de su configuración por defecto.

Sólo se cambia esa estimación en la clase experimental. Se mantienen criterios
de VAD/energía/correlación/interrupción de BAXY. Mismos cinco controles174; no
adopción si eliminar eco vuelve a perder habla cercana. Si es insuficiente,
no barrido de ganancias para elegir un pase.

Se reutiliza por hash la biblioteca estática176 y se compila sólo el binding.
Primer build18707 exit1: faltaban los includes/defines públicos de la biblioteca
importada. Se copiaron los mismos requisitos de su CMake upstream (abseil,
WEBRTC_WIN/NOMINMAX y winmm); sin cambio del algoritmo. Reintento84605 en curso,
log TEMP/c03-gain178-build-retry.log. Evaluador preparado c03-evaluate178.py.

No cambio de fuente de producto/runtime, no audio físico ni Full. C03 EN_CURSO.

## Resultado178

Reintento84605 exit0; evaluación55442 exit0, diez filas (cinco controles/dos etapas).
La referencia menor mantiene0bloques de habla residual en ambos ecos y silencio,
pero la mezcla sigue «Exactly.» en Parakeet crudo/normalizado. No cumple palabras
cercanas; no adoptada y no barrido de ganancias. La fuente CMake178 y ambas
salidas de build quedan conservadas; la biblioteca nativa176 no se recompiló.
Cambio de estrategia179: contraste neuronal DTLN, no otra configuración AEC3.
