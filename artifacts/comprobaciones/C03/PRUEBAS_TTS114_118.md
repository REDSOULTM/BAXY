# C03 — voz inglesa y contrato Piper — 2026-09-07

La implementación manual sigue incompleta tras112: corregir PAD recuperó los
controles españoles, pero el adaptador CLI de eSpeak pierde puntuación y límites
de oración. El Piper oficial para Windows recupera el contenido de los seis
controles técnicos ES/EN con las voces adecuadas. Es evidencia nativa de PCM,
**no aceptación acústica física, reserva100 ni promoción del runtime**.

## Herencia y comparación

`biblioteca/carter/legacy/Carter_v2/MODEL_TTS_TOURNAMENT_REPORT.md:69-73`,
2026-05-02, señala voces Piper por idioma. Su torneo era scaffold y sus cifras
de latencia no acreditaban una implementación completa. Configuración registrada:
`es_MX-claude-high`, espeak es-419. Native113 conserva ese modelo/PAD y cambia
sólo espeak a en-us: recupera el reloj; altera read/heal y UTF-8. No adoptar
únicamente esa sustitución ni afirmar que una transcripción imperfecta demuestra
por sí sola pronunciación incorrecta.

Los candidatos configurados de activos sólo ofrecían baxy-es; no existían los
directorios alternativos de Piper bajo `.gemma4`. Se descargó una sola voz
inglesa masculina, `en_US-john-medium`, 63.531.379 bytes, CPU. Su ficha oficial
declara dataset LibriVox de dominio público. Se consultaron ryan/hfc_male, cuyas
fichas declaran CC BY-NC-SA; no se descargaron. Lessac enlaza otra licencia;
no se eligió. No colección de modelos ni cambio del LLM.

[Ficha John](https://huggingface.co/rhasspy/piper-voices/resolve/1162a9173d0ce503555aed757976b7a9912eae4c/en/en_US/john/medium/MODEL_CARD),
consultada2026-09-07 vía endpoint público, copia exacta en DOWNLOAD.json.
Revisión1162a9173d0ce503555aed757976b7a9912eae4c.
ONNX SHA789c6c875726e627ddee93d51d8727859abe9c091c3d141591f4b83c2072e988.
Config SHAaf60f177b6b550f3d7a302720c0fb89e7f94a82b5dca464775ef63b1c69ba09a.
La config usa `en`, no `en-us`: se compara el paquete completo entrenado.
Descarga local experimental, sin contenidos privados enviados fuera.

## Native114 y observadores115/116

Tres respuestas ya consumidas en110/104; no reserva humana. Mismo engine112,
modelo/config John, Parakeet CPU sin hints. Ejecución final exit0; registros de
dos interrupciones técnicas conservados: assert de preparación antes de síntesis
(en frente a en-us), y codificación de consola después del primer WAV. El primer
WAV y su resultado se reutilizaron por hash; no se regeneró para buscar un pase.

| Entrada literal | Parakeet114 |
|---|---|
| It is 07:14. | It is 714. |
| The file read failed because the content is invalid UTF-8. | The file read failed because the content is invalid to TF8. |
| I couldn't read the file because it wasn't found in the sandbox. | I couldn't read the file because it wasn't found in the sandbox. |

11569715exit0 usa el Nemotron3.5 streaming ya instalado, CPU/greedy/auto, sobre
los mismos seis WAVs preservados de113/en-us y114. El helper del ensayo no daba
silencio final y truncaba tokens: no adjudicar sus finales como error del TTS.
11613894exit0 cambia sólo el flush:0,66s de silencio según el
[ejemplo primario Sherpa](https://raw.githubusercontent.com/k2-fsa/sherpa-onnx/master/python-api-examples/online-decode-files.py),
líneas383–387, consultado2026-09-07. No cambia audio de entrada ni sintetiza otra
vez. Recupera en114 «It is seven fourteen», «File read failed because the content
is inval UTF eight», y toda la tercera respuesta. Eso confirma que Parakeet
puede errar en UTF-8; no convierte115/116 en prueba auditiva humana ni3/3 exacto.
No se modifica el helper de producto: streaming es opcional/off y este uso era
observación técnica; no se promueve como verificador final.

## Native117: primera transformación que falta

El [fonemizador primario Piper](https://raw.githubusercontent.com/rhasspy/piper-phonemize/master/src/phonemize.cpp),
líneas31–119, consultado2026-09-07, aplica NFD, retira flags de idioma y conserva
puntuación/segmentación mediante el terminador de cláusula. Nuestro adaptador
lee `espeak-ng --ipa=3` y colapsa espacios: no son contratos equivalentes.
La DLL local eSpeak no exporta TextToPhonemesWithTerminator. PyPI
piper-phonemize1.1.0 no ofrece wheel Windows; no se instala una wheel incompatible.

117exit0 aísla solamente el punto final real en estos tres textos de una sola
oración, conservando fonemas/voz/escalas/engine112. Parakeet recupera literalmente
los tres contenidos (reloj como seven fourteen). WAVs1,440/4,063/4,133s.
No semilla ONNX fija: no se atribuye igualdad de ondas. Esto respalda el defecto
del frontend; **no se adopta un parche que añada puntos a todo**.

## Reference118: contrato completo, seis controles

Se descarga [Piper Windows2023.11.14-2](https://github.com/rhasspy/piper/releases/tag/2023.11.14-2),
referencia archivada MIT correspondiente a estos exports, no paquete actual
instalado ni implementación BAXY. ZIP22.477.236bytes,
SHAf3c58906402b24f3a96d92145f58acba6d86c9b5db896d207f78dc80811efcea.
DLLs/exe/config/modelos por hash en PREREG118; debug conserva fonemas/IDs.
Incluye los PAD de su export C++ (también tras BOS), puntuación y oraciones.
La referencia Python usada en112 no añadía PAD tras BOS: no confundir ambos
contratos ni afirmar que112 había alcanzado paridad completa.

Un proceso CLI por texto, CPU, escalas por defecto y0,2s entre oraciones;
Parakeet sin hints.1187916exit0, seis contenidos recuperados:

| Entrada literal | Transcripción | CLI+s síntesis |
|---|---|---:|
| It is 07:14. | It is 714 |0,844s|
| The file read failed because the content is invalid UTF-8. | The file read failed because the content is invalid UTF-8. |1,078s|
| I couldn't read the file because it wasn't found in the sandbox. | I couldn't read the file because it wasn't found in the sandbox. |1,110s|
| ¡Hola! Aquí BAXY. ¿En qué te puedo ayudar hoy? | Hola, aquí Baxi. ¿En qué te puedo ayudar hoy? |1,218s|
| Son las 07:13. | Son las 7.13. |0,922s|
| Son las 07:15. | Son las 7.15. |0,969s|

Es comparación de implementación completa: también cambia el ONNX Runtime
incluido y el framing C++. La causalidad del punto se aisló en117; no atribuir
toda diferencia118 a un solo detalle. La carga de la voz ocupa ~0,6s por proceso.

Decisión de siguiente implementación: sustituir el frontend manual por el Piper
completo probado, retirar lo que sustituye, conservar un solo propietario de
reproducción/cancelación y seleccionar voz por idioma real del texto hablado.
Medir ese coste integrado antes de aceptar; no mantener dos motores alternativos.
Assets/registro/hashes y regresión de instalación deben incluir ambos idiomas
antes de promoción. No código/selector nuevo adoptado en114–118; fuente112 y
UI108 permanecen. No App, servidor, captura ni inferencia activos; volumen sigue
restaurado0/muted=true. C03 EN_CURSO, Full sólo al cierre íntegro.
