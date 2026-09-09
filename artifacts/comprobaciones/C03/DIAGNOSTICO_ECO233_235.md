# C03 —233–235: eco físico232 reproducible, admisión230 no lo causa

232 interrumpe dos salidas a103476.906 y103486.734, y publica «Toll.». El
conductor restauró volumen/mute exactamente y cerró captura, salida y workers.
No hubo habla humana simultánea controlada. El parecido al TTS y los segmentos
conservados justifican investigar eco, sin convertir una prueba de sala en un
certificado de ausencia de cualquier sonido ambiental.

233 reproduce la captura por la segmentación productiva230 con la señal limpia,
estado speaking y pares de guarda grabados. Resultado: cancelaciones135/442;
segmentos125–163 y432–470 (fin exclusivo164/471),1.248s cada uno; «Toll.» y«S».
Todas las probabilidades VAD y las diez guardas coinciden exactamente. La API
transcribe_pcm conserva«S»; en la sesión física _decode_utterance lo descarta
con transcript_doubtful, por eso sólo hay una publicación.

235 carga la fuente225 sellada, anterior a la admisión provisional, y repite
los mismos1316frames232. Obtiene cancelaciones, muestras, rangos y textos
idénticos233. Esto descarta atribuir esos dos cortes al cambio230 sobre esta
señal fija; no simula el audio que habría producido un ducking distinto en vivo.

234 vuelve a ejecutar Speex desde cero sobre micrófono/referencia de221 y232:
**2632/2632frames limpios exactamente iguales**, diferencia máxima0.0. No hay
nondeterminismo del cálculo DSP que explique los cortes al reproducir las
entradas. Esto no demuestra por sí solo que todos los relojes físicos sean
perfectos: conserva la secuencia de referencia realmente recibida.

En los seis frames que confirman las dos interrupciones, la guarda de512
muestras da correlaciones0.522/0.466/0.446 y0.482/0.521/0.470, todas bajo0.55.
La energía limpia es0.00877/0.01165/0.00927 y0.00454/0.01019/0.00710, suficiente
para barge. La referencia no falta: RMS1017–1520PCM. Ventanas de1024/2048/4096
con el mismo margen250ms tampoco alcanzan0.55 (máximo0.547). Los máximos de
ventana larga se sitúan cerca de313–318muestras (~20ms), dentro del margen.
No se baja el umbral ni se amplía la historia para forzar un pase.

Próxima comparación acotada: revisar el adaptador DTLN128 ya existente182 y
evaluarlo sobre la señal RAW232 fallida y los controles humanos con baxy.2.
Las causas nuevas respecto a sus rechazos previos son RAW sin AEC/NS Windows
y la normalización nativa corregida218. Esto justifica una comparación fija,
no una búsqueda de ganancias/umbrales ni adoptar por cero eco sin voz humana.
Usar221 como control y los cuatro humanos195 con la construcción RAW213,
congelando condiciones antes del reconocedor. No instalar aún otra dependencia.

Fuente230 continúa porque resuelve la incoherencia de admisión y preserva los
ocho segmentos humanos231; el bloqueo acústico separado sigue abierto. No se
declara C03 terminado ni se ejecuta Full durante la reparación.
