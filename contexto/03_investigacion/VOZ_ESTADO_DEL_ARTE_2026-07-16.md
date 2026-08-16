# Voz local: Carter → BAXY y estado del arte (2026-07-16)

## Resultado

BAXY dispone de una tubería local funcional con dos entradas: escucha directa
por botón y escucha continua activada por «Baxy». Ambas desembocan en la misma
`MissionInput` tipada que el texto. La salida se habla con una voz instalada en
Windows y puede cancelarse al detectar una interrupción.

La implementación no incorporó sin más los artefactos anteriores: el wake y
el TTS históricos tienen restricciones incompatibles con la condición de que
el producto pueda venderse.

## Genealogía comprobada

| Generación | Qué aportó | Evidencia útil | Problema que no se hereda |
|---|---|---|---|
| Carter | captura, VAD por energía y STT | primer loop físico y vocabulario de comandos | acoplamiento amplio y poca prueba de ciclo de vida |
| BAXY Python 1 | LiveKit/openWakeWord, Parakeet, corrector y Piper | wake real, español/inglés/spanglish, anti self-hearing | wake con falsos positivos y procedencia no comercial; entidades 81 % |
| BAXY Tool Ecosystem v2 | loopback, NLMS AEC, ducking, barge-in y TTS durable | ~10,9 dB de ERLE histórico y cierres robustos | AEC acústico humano y soak 24 h no quedaron demostrados |
| BAXY actual | shell .NET + sidecar local tipado | una sola puerta de misión, fail-closed, planner durable | antes de este corte solo tenía micrófono directo, sin wake ni TTS de producto |

Los módulos revisados fueron `legacy/voice`,
`legacy/legacy_export/voice_pipeline`, `legacy/core/durable_tts*`, sus pruebas y
los registros R-019/R-020/R-021/R-022/R-033.

## Contraste actual

### VAD y STT

Silero VAD 6.2.1 es streaming, ONNX, MIT, soporta 8/16 kHz y declara menos de
1 ms por bloque en un hilo CPU, con entrenamiento multilingüe. Se usa el
paquete oficial, no `silero-vad-lite`. Parakeet TDT 0.6B v3 int8 permanece por
haber ganado las pruebas locales anteriores en latencia, silencio y
code-switching. [Silero VAD](https://github.com/snakers4/silero-vad)

### Wake word

El estado del arte favorece KWS pequeño + VAD + verificador de segunda etapa.
Sherpa-onnx ya ofrece KWS de vocabulario abierto con boost y umbral por palabra,
pero los modelos oficiales disponibles están centrados en inglés/chino; no se
asume que resuelvan el nombre inventado español «Baxy» sin corpus físico.
[Sherpa-onnx KWS](https://k2-fsa.github.io/sherpa/onnx/kws/index.html)

El modelo histórico no se distribuye. Los modelos incluidos por openWakeWord
son CC BY-NC-SA y el servicio licencia por defecto sus modelos generados solo
para uso personal/no comercial. [openWakeWord](https://github.com/dscripka/openWakeWord),
[términos del servicio](https://openwakeword.com/terms)

Decisión vigente: LiveKit WakeWord entrega la ruta local Apache-2.0 para un
clasificador ONNX propio; el runtime de BAXY usa ventana rodante de 2 s,
pre-roll y antirrebote, y no alimenta Parakeet ni Nemotron mientras espera el
hit acústico. El matcher cerrado «Baxy/Baxi» queda limitado a limpiar el texto
posterior o a una compatibilidad explícita; no es el detector. El manifiesto
exige hash y un informe FAR/FRR promocionable antes de habilitar el activo.
No existe aún un peso Baxy aprobado: hasta entrenarlo y medirlo, la ruta
honesta es botón directo, no anunciar un wake de producto.

La promoción actual no toma una tasa observada de 0 falsos positivos como
riesgo cero: el informe `baxy-wake-corpus-gate-v3` usa el límite superior
unilateral de Poisson al 95 %. Para el objetivo de 0,1 FPPH se necesitan al
menos 30 h de negativos si no hay activaciones falsas, además de FRR ≤5 % y la
vinculación SHA-256 entre ONNX, parámetros e informe.

### TTS

Piper sigue siendo una buena referencia de naturalidad/streaming, pero el
runtime oficial actual es GPL-3.0. Por eso no se enlaza ni se importa desde el
producto. [Piper actual](https://github.com/OHF-Voice/piper1-gpl)

La salida vigente usa SAPI de Windows y las voces ya instaladas. Es totalmente
local, no agrega un modelo redistribuido y expone las flags asíncrona y purge
para cancelación real. [Flags SAPI](https://learn.microsoft.com/en-us/previous-versions/windows/desktop/ms720892(v=vs.85))

### AEC, ducking y barge-in

WASAPI loopback existe precisamente, entre otros usos, para alimentar AEC y
funciona aunque el hardware no exponga un dispositivo loopback. BAXY captura
esa referencia, estima retardo/ganancia, cancela el camino directo y aplica
NLMS a las reflexiones. [WASAPI loopback](https://learn.microsoft.com/en-us/windows/win32/coreaudio/loopback-recording)

Windows define además modos Speech/Communications y efectos AEC/NS/AGC, pero
su presencia depende del driver. BAXY no los da por existentes: conserva su
referencia propia y degrada con `aec=false` si WASAPI no abre.
[Modos de procesamiento de audio](https://learn.microsoft.com/en-us/windows-hardware/drivers/audio/audio-signal-processing-modes)

El barge-in combina inicio de habla por VAD, correlación contra loopback para
rechazar la propia voz de BAXY y purge de SAPI. El ducking conserva y restaura
el volumen exacto incluso al fallar.

## Medición de este equipo

- Pila completa precalentada: ~2,3 s.
- Micrófono físico abierto: `USB PnP Audio Device`.
- Loopback WASAPI físico: activo y cerrado correctamente.
- TTS SAPI: reproducción física observada y cancelada.
- AEC determinista: 61,01 dB ERLE en el caso directo sintético del gate.
- Clip hablado histórico del usuario: STT no vacío y entidad Spotify reparada.
- Wake/VAD/STT/SAPI sintético: 6/6 segmentaciones y 6/6 rutas tras el ajuste.

Artefactos: `artifacts/product/voice_system_gate.json` y
`artifacts/product/mind_voice_gate.json`.

## Límite honesto

El sistema está implementado y el hardware abre, pero ningún test automático
puede atribuir una voz al usuario ausente. La calibración final de FRR/FAR del
wake personal y el barge-in humano sobre parlantes fuertes requiere que el
usuario pronuncie el corpus. No se confunde esa calibración con un defecto de
wiring ni se inventa un resultado.

## Actualización técnica — 2026-07-23

Se añadió un primer pase local de **Nemotron 3.5 ASR Streaming 0.6B int8,
560 ms** mediante el export oficial de sherpa-onnx. Sus hipótesis parciales
llegan por una cola separada del hilo del micrófono, solo después de un wake
acústico o micrófono directo; si esa cola se atrasa, se descarta únicamente el
preview. Parakeet int8 conserva el texto final, la AEC y el corrector. De ese
modo ningún parcial puede convertirse en activación o acción. La documentación
del export confirma stream por idioma/`auto` y las variantes de tamaño de
bloque. [Nemotron Streaming en sherpa-onnx](https://k2-fsa.github.io/sherpa/onnx/nemo/nemotron-streaming.html)

La compuerta sintética actual mantiene 6/6 rutas finales con Parakeet y la
compuerta de hardware abre micrófono/loopback y aprueba AEC, ducking y el clip
histórico. El preview se registra como evidencia separada: no se promueve como
transcriptor final hasta superar un corpus de micrófono ES/EN/spanglish y
entidades. La implementación ya separa KWS y ASR, pero el estado de wake no se
presenta como aprobado hasta instalar un ONNX Baxy cuyo SHA-256 coincida con un
gate acústico FAR/FRR. LiveKit ofrece la ruta Apache-2.0 para
entrenar/exportar ese ONNX, no un modelo Baxy listo para distribuir, y advierte
que el rendimiento multilingüe requiere más diversidad y evaluación propia.
[LiveKit Wakeword](https://github.com/livekit/livekit-wakeword)
