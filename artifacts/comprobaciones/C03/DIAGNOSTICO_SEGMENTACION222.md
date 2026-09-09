# C03 —222: la segmentación admite audio rechazado para interrumpir

Reproducción íntegra de los1316frames limpios221 por VoiceEngine._capture_loop,
con Silero real, estado speaking registrado y echo guard real sobre los pares
micrófono/referencia retrasados por Speex. Dispositivo, salida y ducking son
inertes; no se altera la señal ni se ejecuta cancelación acústica una segunda vez.

Se reproduce el único segmento físico exactamente: frames162–195 incluidos,
1.088s, transcripción nativa instalada «Let's see.». Diferencia máxima de VAD
respecto221:0.0; siete llamadas a echo guard, cero diferencias. No cancelaciones.

En170/172/173/174 Silero supera0.5 y el guard de correlación no detecta eco,
pero la energía0.001850/0.001810/0.000761/0.000425 es inferior al umbral vigente
0.004. La rama de VoiceEngine limpia barge_frames pero deja speech=True: el
mismo bloque que no admite una interrupción abre/prolonga una transcripción.
Los otros tres positivos están rechazados por el guard. La reproducción
establece el camino causal antes de modificarlo.

Corrección propuesta: en esa rama conservar el rechazo también en speech, con
el mismo umbral, sin filtrar texto reconocido. Deben permanecer intactos los
primeros bloques humanos que sí cumplen y la voz baja cuando BAXY no habla.
Se verificará con tests de segmento/cancelación y los mismos1316frames. No se
afirma que esto arregle todos los defectosASR217 ni la activación calibrada.
