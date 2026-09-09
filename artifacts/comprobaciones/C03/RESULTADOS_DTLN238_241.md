# C03 —238–241: candidata DTLN512 y límite del reconocimiento

## Decisión

DTLN512 queda como candidata a integrar para la cancelación de eco. Supera a
128 en conservación de cláusulas y elimina el fallo acústico observado en la
prueba física240. **No está integrada ni se declara cerrada la fidelidad ASR**.
Speex sigue siendo el backend productivo de fuente230. La candidata utiliza
el adaptador182 y dependencias ya aisladas; no se cambia el runtime registrado.

##238–239: mismas señales, mayor capacidad

238 calcula sólo512 sobre las diez entradas236. Se reutilizan los resultados
Speex/128 anteriores. CPU1hilo, media9.23–10.11ms por512muestras, p99máximo
22.34ms y pico38.25ms aislado; no se presenta como presupuesto conjunto.

239 usa la segmentación real230 y baxy.2 sobre los diez resultados y las ocho
ventanas humanas fijas.221/232dan cero cancelaciones y cero segmentos espurios.
Los ocho recorridos humanos producen una frase cada uno.128 perdía una cláusula
del humano1 RAW y fragmentaba el humano2;512 conserva esas cláusulas. Además
recupera30años en el humano2 solo, donde Speex daba3años.

Quedan diferencias de palabras: en humano1 solo el segmento da«pudier acceder»
frente a«pudieron acceder»; en humano3 RAW da«world» en lugar de«word»; en el
humano2 RAW cambia«could» a«can». Las ventanas fijas pueden tener más errores
que los segmentos productivos (p.ej., humano1 pierde«acceder» en la ventana).
Los literales completos se conservan en COMPARACION_LITERAL239_241.md. No se
cuentan estos recorridos como ocho pases semánticos ni se ignoran regresiones.

##240: física con candidata, sin modificar el producto

VoiceEngine230 directo con sustitución explícita del backend por DTLN512,
captura RAW real, Silero/Piper/baxy.2 y los cuatro textos187. Duración42.112s,
1316bloques, cuatro síntesis, **cero barge_in, cero transcripciones y cero errores**.
Windows declara efectos[]. Todos los workers terminan y el volumen/mute se
restaura exactamente a0/mutedtrue. La calibración de wake no se elude: continúa
unavailable/wake_verifier_manifest_missing.

En vivo el DSP consumió media10.80ms, p9916.59ms y máximo31.78ms por bloque.
La métrica pertenece sólo al DSP observado; no sustituye la medición conjunta
con UI/LLM. TRACE_METRICS.json conserva además energía de micrófono, referencia
y señal limpia para comprobar que no se está acreditando una entrada vacía.

Es una prueba física de eco con síntesis, sin voz humana simultánea controlada,
UI o LLM. La grabación y todos sus límites se conservan. El resultado no prueba
un presupuesto conjunto ni basta para la aceptación final de C03.

##241: reconocedor independiente

Se conservan los ocho segmentos y ocho ventanas512, y se añaden los cuatro
originales humanos195 exactos ya transcritos219. Nemotron local usa su camino
existente, lenguaje auto y cola de0.66s, sin pistas ni cambios de parámetros.
El propósito es aislar el reconocimiento; no introducir otro filtro.

Nemotron no resuelve de forma fiable las diferencias: omite palabras y partes
de palabras, incluso en los originales sin AEC. Por ejemplo, en humano1 RAW
ventana transforma«no todos» en«nos», y en humano1 solo segmento omite«funeral».
En el original humano0 da«Se recomie…» y pierde palabras. Por tanto,241 no
acredita que las palabras ausentes se hayan destruido en DTLN y tampoco
justifica sustituir Parakeet por esta ruta streaming.

## Continuación

Preparar integración reproducible de DTLN512 como candidata acústica: una sola
implementación de AEC, hashes/licencias/activos/dependencias y pruebas de su
propietario; retirar el backend que sustituya. Medir después el producto completo
y conservar los controles humanos/errorASR. No presentar la candidata como una
promoción de C03 ni ocultar los límites239/241. El objetivo íntegro incluye aún
wake/voz humana física,8rutas,100frescos y100/100,averías/UI/audiofinal,4GB,
instalación/continuidadC04–C09,Full verde y publicación fuera main.
