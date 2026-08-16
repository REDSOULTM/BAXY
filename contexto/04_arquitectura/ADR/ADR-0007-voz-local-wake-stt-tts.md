# ADR-0007 — Voz local, wake verificable y salida cancelable

- Estado: Aceptado
- Fecha: 2026-07-16
- Actualizado: 2026-07-23
- Depende de: ADR-0001 y ADR-0005

## Contexto

El sidecar actual solo ofrecía micrófono directo, Silero-lite y Parakeet. Los
BAXY preservados tenían wake, Piper, loopback, NLMS, ducking y salidas
durables, pero no cerraron licencias ni la prueba acústica humana. El producto
se vende y solo admite componentes redistribuibles con licencias permisivas.

## Decisión

1. Mantener una sola entrada tipada: voz y texto convergen en `MissionInput`.
2. Usar Silero VAD 6.2.1 ONNX y Parakeet TDT int8 local como transcripción
   final con AEC. Cuando esté instalado el export oficial local, Nemotron 3.5
   Streaming int8 produce hipótesis parciales de baja latencia en un trabajador
   acotado, nunca en el hilo de captura; solo recibe un turno abierto por KWS
   acústico o por el botón directo.
3. Ofrecer modo `direct` y modo continuo `wake`, ambos visibles en la UI.
4. Detectar el wake con un clasificador acústico ONNX propio de LiveKit
   WakeWord, una ventana rodante de 2 s, pre-roll y antirrebote. El ASR puede
   quitar el prefijo del texto ya autorizado, pero jamás activa BAXY. No
   distribuir el modelo openWakeWord histórico.
5. Requerir manifiesto con SHA-256 y un informe FAR/FRR promocionable antes de
   habilitar el KWS. El informe `baxy-wake-corpus-gate-v3` vincula por hash el
   ONNX y los parámetros de decisión; exige FRR ≤5 % y un límite unilateral
   Poisson FAR al 95 % ≤0,1/h (30 h negativas si no hay falsos positivos).
   Sin modelo calibrado, `wake` queda no disponible; el fallback STT léxico
   exige una variable explícita de migración.
6. Usar SAPI y voces instaladas en Windows; no importar ni empaquetar Piper.
7. Capturar referencia WASAPI, cancelar camino directo + NLMS y reportar si no
   existe AEC en vez de simularlo.
8. Ducking siempre reversible y barge-in por VAD + rechazo correlacional de eco
   + purge asíncrono de SAPI.
9. No persistir audio ni transcripciones en los gates físicos.
10. La escucha al inicio es opt-in por entorno; `run_baxy.ps1` la activa porque
   el propietario la pidió explícitamente, mientras la UI mantiene indicador.

## Consecuencias

- Con un modelo validado, BAXY escucha solo KWS en reposo; al disparar, entrega
  2 s de pre-roll a VAD/ASR para conservar «Baxy, abre Spotify» como una sola
  locución. El ASR no se ejecuta continuamente para decidir el wake.
- El KWS corre en una cola CPU acotada y puede descartar frames obsoletos sin
  bloquear la captura. Una discontinuidad reinicia su ventana; nunca mezcla
  audio no contiguo.
- La cola de Nemotron puede descartar parciales bajo carga; nunca bloquea la
  captura ni descarta el audio final que llega a Parakeet.
- SAPI es menos natural que las mejores voces neurales, a cambio de eliminar
  redistribución y copyleft del runtime.
- El AEC es medible y degradable, no equivalente a WebRTC AEC3.
- La voz del usuario y su sala todavía deben calibrar FAR/FRR y barge-in físico.

## Criterio de reapertura

Reabrir el umbral, frase o backend KWS solo si un modelo propio/permisivo para
«Baxy» supera en corpus separado: FRR ≤5 %, límite unilateral de FAR al 95 %
≤0,1/h, latencia de activación p95 medida y cero regresión de
privacidad/licencias. La frase «Baxy» aislada
debe competir con «Oye Baxy» en ese mismo corpus antes de cambiar la UX.
Reemplazar SAPI solo con TTS español local que tenga runtime y pesos
comercialmente permisivos, cancelación acotada y una escucha humana A/B
documentada.
