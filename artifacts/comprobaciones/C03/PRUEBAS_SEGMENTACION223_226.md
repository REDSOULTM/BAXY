# C03 —225: admisión de voz durante salida, conservando la frase humana

## Resultado vigente

La rama que rechaza energía insuficiente para interrumpir ahora usa
`speech = speech_started`: no abre un turno a partir de esos bloques mientras
BAXY habla, pero conserva la continuidad de una frase ya admitida. No cambia
VAD, correlación, umbral de energía, duración de interrupción ni texto ASR.
Cuando no hay salida, la voz de baja energía conserva su comportamiento.

Captura RAW220 y runtime baxy.2 continúan integrados. La versión vigente es
fuente225; fuente223 es una candidata intermedia rechazada, conservada como
evidencia. No se afirma que este arreglo resuelva toda la fidelidad de voz.

## Evidencia y regresión

222 estableció la causa sobre los1316frames físicos221: VAD idéntico en todos
los bloques, siete guardas de eco idénticas, un segmento162–195 de1.088s que
produce «Let's see.». Cuatro positivos de VAD bajo la energía exigida mantenían
speech=True y abrían el turno. No hubo un barge_in real en esa sesión.

223 primero reproduce el fallo en una prueba de contrato:1failed/2passed,
91deselected. Poner speech=False incondicional en esa rama elimina el segmento
falso al reproducir221, con122tests correspondientes verdes. Sin embargo,224
detecta que también fragmenta voces humanas en presencia de salida. Se rechaza
esa candidata; no se cuentan sus pruebas unitarias como aceptación.

225 añade una prueba de continuidad con24bloques de voz baja entre dos grupos
de voz más fuerte. Falla sobre223: dos segmentos en lugar de uno. La corrección
final limita el rechazo al inicio de turno; la frase conserva todos sus bloques.

- `pytest tests/test_mind_voice_runtime.py tests/test_voice_capture_clock.py tests/test_speex_aec.py -q`:
  **123passed in5.37s**, sin skips, Python registrado. Los logs rojo y verde
  están en astra-segmentation225. Se comprueban voz baja sin salida, rechazo
  inicial durante salida, primeros bloques antes de cancelar y continuidad.
- `scripts/test_source_quality.ps1`: Fast exit0; Release1.17s,0avisos/errores.
  Log íntegro en astra-segmentation225/Fast.log. No se ejecutó Full durante
  esta reparación.
- Replay225 sobre todos los1316frames221: **cero segmentos, cero cancelaciones**.
  Siete guardas coinciden con221. La diferencia máxima de VAD0.00906166 aparece
  en una ejecución cuyo reinicio de VAD ya no ocurre al cerrar el turno espurio;
  no se afirma paridad completa de VAD después del cambio de segmentación.
  El campo histórico `unrejectedBelowBargeEnergyWhileSpeaking` cuenta rechazos
  pendientes sólo de la guarda de correlación; no significa admisión en225.
-226 compara fuente220 frente225 con ocho controles213 congelados:
  cuatro voces humanas solas+Speex y cuatro con eco RAW+Speex. **8/8 idénticos
  en rangos, muestras, transcripciones y decisiones de interrupción**. Había
 4/8paridades de segmento en la candidata223; esa regresión ya no está.

Los16 recorridos de226 son con el código real de segmentación, Silero real y
el mismo reconocedor instalado. El par micrófono/referencia de213 se reconstruye
con su ganancia/onset originales para la guarda, sin procesar Speex otra vez.
La máscara de salida es la aproximación fija212, sin apagar el altavoz
contrafactual tras cancelar. No son interrupciones físicas ni reserva humana.

## Límites que siguen abiertos

8/8paridades no son8/8textos correctos. En el control humano2 solo+Speex sigue
«25 to3years» donde la referencia dice25–30; aparecen otras diferencias de
palabras ya existentes. Algunos controles con eco todavía generan un saludo
espurio antes de la frase humana. Véase COMPARACION_LITERAL226.md para los
textos completos, sin ocultar estos errores.

La sesión física221 se hizo antes de la corrección225. El replay demuestra el
arreglo sobre su grabación, no una nueva aceptación física del candidato final.
Wake sigue no disponible por wake_verifier_manifest_missing. Siguen pendientes
voz humana física, ocho rutas,100frescos y100/100,averías/UI/audio final,4GB
conjuntos,instalación/continuidad C04–C09,Full verde y publicación fuera de main.
