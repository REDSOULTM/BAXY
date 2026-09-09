# C03 — controles humanos y búsqueda local —195–199

Sin cambios de producto, AEC, umbrales, modelo o registro. Fuente192 y prueba
UI194 siguen intactas. C03 EN_CURSO; no Full durante reparación.

## Grabaciones públicas195

Cuatro WAV originales de Google FLEURS, dos es_419 y dos en_us, test,
revisión70bb2e84b976b7e960aa89f1c648e09c59f894dd. Atribución: Conneau et al.,
FLEURS (2022), licencia CC-BY-4.0. [Dataset](https://huggingface.co/datasets/google/fleurs)
y [paper](https://arxiv.org/abs/2205.12446). No datos locales enviados.

Primer acceso falló por imports requests/soundfile ausentes, sin instalar nada.
La API rows y first-rows devolvió500 por grupo Parquet de703MB y límite300MB.
Se conservó ese intento y se fijó PREREG-TAR antes de obtener audio: dos IDs de
transcripción distintos por idioma, en orden del tar del autor, duración<=20s.
Lectura acotada a100miembros/64MiB comprimidos. No elección según acierto de ASR.
Se guardaron cuatro WAV float32/16k originales, sin normalizar ni recodificar;
dos TSV y hashes, 12,84/9,72/10,56/8,76s. Nunca son reserva Carter→BAXY.

## Búsqueda local196, autorizada por el dueño

Se priorizaron Probando Gemma4, BAXY, Carter OS AI y FunctionGemma y se amplió
a C:/ y D:/. Inventario de nombres/metadatos; ningún audio subido ni proyecto
anterior modificado. Se excluyó el árbol actual, Windows, papelera, junctions,
cachés indicadas y capturas C03 ya conocidas. Duración300s, sesión88361exit0.
1.615.235 archivos examinados,471.912 archivos con extensión de audio en3.252
carpetas; la mayoría de esa cifra no acredita grabación humana. Hubo7 errores
de acceso y quedaron61 directorios en la frontera privada. No es búsqueda
completa de todo el disco. El inventario y sus rutas personales quedan privados.

Hallazgos en Probando Gemma4:1.012 archivos de audio del registro de voz de
23–25junio,338 muestras en wake_positives_real,454 en wake_false_positives y
la grabación de292,842854s en gemma4_agent/voice/tests. Un sidecar de captura
confirma16kHz,3,872s, razón eos_silence y event_id; esto prueba captura, no quién
habló ni que fuera voz humana en lugar de reproducción. Los manifests históricos
real_mic/real_es buscados en las dos raíces candidatas no existen allí.

«Grabación (2).m4a» tiene metadato creation_time2026-05-18T16:44:35Z. El reporte
asociado atribuye su transcripción a faster-whisper large-v3: el rótulo ground
truth no la convierte en anotación humana. Reporte y JSON alineado incluso
discrepan en algunos textos. v2_expected contiene105wakes/103marcas de comando.
Se preguntó al dueño si es una grabación suya; respuesta pendiente al registrar.
No se necesita esa respuesta para continuar diagnósticos públicos. No ampliar
su admisión previa de tres turnos ingleses a este audio ni a otras capturas.

Los WAV Grabación(2) y testaudio_full son idénticos por SHA256: True.

## Baseline197 y comparación198–199

197:8 lecturas completas, cuatro originales sin cambio de ganancia, Parakeet
CPU6/beam8 y Nemotron CPU6/greedy/flush0,66s. Sin pistas textuales; errores del
original conservados. Sesión46684exit0. El baseline no declara4/4 perfectos.

198: cada grabación se escala una vez a RMS0,01 y se inserta un segundo después
del primer bloque de referencia187 RMS>=20PCM: muestra31872. Se conserva el
micrófono y referencia exactos de187; referencia continua. Una condición sólo
voz usa referencia cero; otra suma el eco físico grabado. Raw/Speex/DTLN128,
estado nuevo por condición, sin barrido de ganancia/retardo.24señales conservadas;
sesión1037exit0. El VAD y máscara speaking son controles offline, no la captura
con resets de segmentación o la reproducción posterior a una interrupción real.

199:48lecturas, ambos reconocedores sobre las24ventanas fijadas antes. Sin
normalización adicional ni texto esperado. Sesión27801exit0. Tabla de errores
superficiales de palabra; puntuación/caja ignoradas, números y homófonos no
normalizados. No es una tabla de pass/fail semántico.

| Audio | Motor AEC | Parakeet sólo voz | Parakeet mezcla | Nemotron sólo voz | Nemotron mezcla |
|---|---|---:|---:|---:|---:|
| es_419 ID2001 | raw | 1/29 | 1/29 | 6/29 | 8/29 |
| es_419 ID2001 | speex | 2/29 | 1/29 | 4/29 | 2/29 |
| es_419 ID2001 | dtln128 | 2/29 | 2/29 | 4/29 | 2/29 |
| es_419 ID1764 | raw | 0/22 | 0/22 | 5/22 | 13/22 |
| es_419 ID1764 | speex | 2/22 | 0/22 | 4/22 | 2/22 |
| es_419 ID1764 | dtln128 | 1/22 | 1/22 | 5/22 | 4/22 |
| en_us ID1904 | raw | 1/19 | 10/19 | 4/19 | 18/19 |
| en_us ID1904 | speex | 19/19 | 4/19 | 3/19 | 14/19 |
| en_us ID1904 | dtln128 | 1/19 | 1/19 | 7/19 | 4/19 |
| en_us ID1675 | raw | 1/21 | 8/21 | 2/21 | 21/21 |
| en_us ID1675 | speex | 1/21 | 1/21 | 5/21 | 8/21 |
| en_us ID1675 | dtln128 | 2/21 | 8/21 | 2/21 | 7/21 |

Lecturas literales completas y orden en astra-human197/RESULTS.json y
astra-observe-human199/RESULTS.json; datos/ventanas/payloads de referencia en sus
PREREG. No se descarta ningún intento ni se elige el observador más favorable.

Hallazgo decisivo: DTLN128 no domina a Speex. En el segundo audio inglés mezclado,
ambos observadores pierden parte del inicio con DTLN; Parakeet con Speex conserva
el inicio. En el primer inglés DTLN sí mejora la mezcla. En voz sola, Parakeet
devuelve vacío con Speex para ese primer inglés, pero Nemotron recupera la frase:
no afirmar borrado físico de audio a partir de una transcripción vacía.
Persisten degradaciones y desacuerdos. No promover DTLN por estos controles ni
repetirlos buscando otra combinación favorable. El fallo físico183 permanece.

## Continuación

Cambia la siguiente acción: ya hay candidatos de grabación local con registros y
cuatro controles humanos públicos fijados; no hacen falta más descargas para
diagnosticar. Verificar procedencia de Grabación(2) y sus segmentos sin dar por
humanos sus ground-truth automáticos. Para el eco, localizar en los mismos PCM
conocidos qué parte de habla/eco conserva cada salida antes de otro cambio de
motor o detector. Contrastar un mecanismo concreto, no acumular tamaños/modelos.

Pendientes íntegros: fallo acústico183, activación/entrada humana aprobadas,
ocho rutas finales,100humanos reservados congelados y100/100, averías/recuperación,
UI/runtime/4GB, promoción/regresión/instalación/continuidadC04–C09, Full/publicación.
Ningún proceso propio queda pendiente en195–199. No commit/push/main/subagentes.
