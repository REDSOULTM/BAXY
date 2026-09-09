# C03 — captura RAW209–214 — investigación terminada, producto sin promoción

La fuente207 y sherpa-onnx1.13.4+baxy.1 siguen vigentes. No se cambió el producto,
el registro, el volumen permanente, el modelo ni los umbrales. C03 continúa activo.

## Hallazgo y comparación causal acotada

209 consulta seis flujos WASAPI inicializados, sin arrancar audio: tres roles de
dispositivo predeterminado × categorías Other/Communications. Todos resuelven al
mismo endpoint48kHz estéreo. IAudioEffectsManager devuelve reducción de ruido ON,
beamforming OFF y cancelación acústica ON. IAcousticEchoCancellationControl devuelve
E_NOINTERFACE(80004002). La ausencia del control de referencia NO significa ausencia
de AEC; la lista de efectos demuestra lo contrario.

210 cambia únicamente AudioClientProperties.Options a RAW. Los seis flujos se
inicializan y sus listas de efectos quedan vacías. Cambiar sólo la categoría a
Communications no alteró los efectos209. No se modificaron ajustes globales.

211 comprueba además los efectos sobre los IAudioClient reales de PortAudio
obtenidos con PaWasapi_GetAudioClient: el flujo normal tiene AEC/NS ON; RAW no
declara efectos. Así se verifica que la biblioteca instalada aplica streamOption=1,
sin inferirlo sólo del campo solicitado. Es instrumentación privada del experimento,
no una API nueva incorporada al producto.

Se capturan simultáneamente ambos flujos16kHz/mono/512, con la misma referencia
WASAPI y el anclaje ADC del producto. Una sola reproducción de los cuatro PCM
Piper187 originales, sin regenerarlos: comienzos2/9/16/23s, duración total30s.
Captura normal1020frames, RAW1021frames. Sin errores de callback/cola/loopback ni
reproducción. Volumen antes/después exactamente0 y muted=true. Hilo y loopback
cerrados. La captura física211 no ejecuta BAXY completo ni cancela su reproducción.

212 procesa las dos entradas conservadas con/sin Speex, Silero nuevo y los mismos
guardas/umbrales. Máscara temporal fija de reproducción; no reproduce resets de
segmentación ni la parada contrafactual tras una interrupción. Sus eventos son
**candidatas offline**, no eventos barge_in reales del producto.

| Captura | Speex | Frames VAD durante voz reproducida | Candidatas a interrupción |
|---|---|---:|---:|
| Normal | No | 229 | 10 |
| Normal | Sí | 26 | 1 |
| RAW | No | 226 | 10 |
| RAW | Sí | 27 | 0 |

La candidata normal+Speex aparece a2,377s de la reproducción. RAW+Speex mejora este
control conservando algoritmos y umbrales, pero no demuestra resolución general.
Ambos caminos conservan todavía actividad VAD de eco. La hipótesis de procesamientos
encadenados merece evaluación; no se ha probado que explique por completo el fallo183.

## Conservación humana y nuevo límite del reconocedor

213 añade las cuatro voces humanas195, escaladas una sola vez a RMS0,01 e insertadas
a los3s de la reproducción, alineadas al ADC de cada flujo. Cuatro condiciones por
voz: sola sin Speex, sola con Speex, mezcla normal+Speex y mezcla RAW+Speex.
Se procesa toda la señal y se transcribe una ventana fija con1s de margen usando
VoiceEngine.transcribe_pcm y la dependencia instalada. Salida TTS inerte.

Son16 lecturas completas. No son16 pases. En RAW+Speex, los dos españoles devuelven
texto vacío; el segundo también queda vacío con Speex sobre voz aislada. Las
correlaciones con la onda humana alineada son0,939/0,941/0,954 respectivamente,
con ganancias de proyección0,893/0,897/0,927. No se interpreta texto vacío como
voz borrada. Hay además errores menores en transcripciones no vacías, incluidos
«pueda» por «puede», pérdida de «acceder» y homófonos ingleses.

La mezcla se hace después del procesamiento Windows de la captura: NO acredita
cómo trata ese procesamiento a un humano físico simultáneo.

214 aísla las tres ventanas vacías y un control positivo. El resultado nativo de
Parakeet ya está vacío antes del corrector en las tres; applied_decoding_method
confirma greedy_search. El corrector no causa estos vacíos. Nemotron recupera
contenido humano de las tres mismas ventanas, con errores de palabras conservados.
No se adopta como sustituto ni se presenta como transcripción perfecta.

Ejemplos literales del resultado alternativo:

- Español2001 RAW+Speex: «Se recomienda enfáticamente a los viajeros que informen
  sobre cualquier riesgo del clima extremo en el área que visitan, dado queda
  afectar sus planes de viaje.»
- Español1764 RAW+Speex y voz sola+Speex: «Fue tanta la cantidad de gente que se
  concentró que nos pudieron acceder al funeral en laza de San Pedro».

La reparación207 continúa acreditada para los47 controles208 y los cuatro casos
recuperados. Los nuevos controles213–214 demuestran que **no resuelve todos los
vacíos de Parakeet**. No volver a afirmar una reparación general del ASR.

## Decisión y siguiente paso

No promover RAW todavía, ni descartarlo atribuyendo los vacíos a borrado de voz.
Investigar la primera pérdida dentro del reconocedor nativo con las cuatro ventanas
214 fijas: entrada/features/salida del encoder/decodificador, incluyendo el control
positivo. Conservar la evidencia de mejora acústica212. No añadir un segundo modelo
al producto ni hacer barridos de ganancias, umbrales o filtros.

No se repitieron Fast/Full porque no hubo cambio de fuente del producto. Los procesos
211(10218),213(70723),214(45944) se recogieron exit0;209/210/212 terminaron directamente.
No quedan procesos propios activos. Scripts/entradas/resultados quedan sellados en
TRAMO209_214_PINS.json. El registro y snapshot207 se verifican al sellar.

Todos los pendientes del objetivo siguen vigentes: audio/activación, ocho rutas,
100humanos frescos congelados y adjudicados, averías/recuperación, UI/audio físico
final, recursos conjuntos, runtime/instalación/continuidadC04–C09, Full y publicación.

## Fuentes primarias

- [Ejemplo oficial AEC de Microsoft](https://github.com/microsoft/Windows-classic-samples/blob/main/Samples/AcousticEchoCancellation/cpp/AECCapture.cpp): inicialización y consulta separada de efectos/control.
- [Estado de efectos](https://learn.microsoft.com/en-us/windows/win32/api/audioclient/ne-audioclient-audio_effect_state): OFF=0, ON=1.
- [Opciones RAW](https://learn.microsoft.com/en-us/windows/win32/api/audioclient/ne-audioclient-audclnt_streamoptions): exclusión del procesamiento salvo el permanente del endpoint.
- [Modos de procesamiento](https://learn.microsoft.com/en-us/windows-hardware/drivers/audio/audio-signal-processing-modes): contrato de captura RAW y procesamiento adaptativo.
- [PortAudio WASAPI](https://github.com/PortAudio/portaudio/blob/master/include/pa_win_wasapi.h): acceso al cliente y opción RAW. La conducta de la DLL instalada se comprueba directamente en211.
- SDK local10.0.26100.0: shared/ksmedia.h8570–8584 identifica GUIDs AEC, NS y beamforming; um/audioclient.h define interfaces y estados.
