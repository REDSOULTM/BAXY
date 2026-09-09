# C03 —230: conservar el inicio antes de admitir la interrupción

## Cambio vigente

El audio candidato se conserva en la lista utterance existente, con sus límites
de duración y finalización. Durante TTS un primer bloque elegible puede empezar
ese búfer, pero no inicia ducking, streaming ni transcripción. Se admite al
cumplir los tres bloques consecutivos ya exigidos para interrumpir, o al detectar
voz cuando la salida ya terminó. Si la frase termina sin admisión, se descarta.

No hay otra cola ni capturador, ni se modifica un umbral. admit_utterance reúne
el inicio de ducking/streaming que antes estaba duplicado en la apertura normal
y en la autorización de wake provisional; ambos reutilizan el mismo camino.
La captura RAW220 y la dependencia baxy.2 permanecen sin cambios.

## Por qué se rechazó228

227 mostró el dato real de apertura: barge_frames=1 en los cuatro controles,
antes del comienzo humano.228 esperaba tres bloques antes de empezar a guardar
la frase, pero el pre-roll no cubría la espera intermitente del humano0: perdió
«Se».229 conserva ese fallo.230 mantiene la frase provisional completa mientras
espera la admisión; no aumenta pre-roll para ajustar un caso conocido.

## Validación230–231

- Dos pruebas de prefijo fallan antes del cambio230 por pérdida de muestras,
  tanto si la salida sigue activa como si termina antes de confirmar.
- `pytest tests/test_mind_voice_runtime.py tests/test_voice_capture_clock.py tests/test_speex_aec.py -q`:
  **127passed in5.37s**, sin skips. Prueban también que un candidato de1/2bloques
  no provoca ducking, streaming ni ASR, y que se conserva el prefijo al admitir.
- Ruff de los archivos fuente/test modificados: verde.
- `scripts/test_source_quality.ps1`: **Fast exit0**, Release1.14s,0avisos/errores.
- Replay230 sobre los1316frames físicos221: **cero segmentos/cancelaciones**;
  siete guardas iguales, cambio máximo VAD0.00906166 por los resets de turno.
-231: ocho controles humanos213 con código225/230 y reconocedor baxy.2 iguales.
  Los ocho segmentos humanos mantienen exactamente sus muestras, rangos y
  transcripciones. Se eliminan únicamente los segmentos espurios separados
  «Tola» y «Hola, aquí Bas» de humano0/1 RAW. Los otros seis casos son idénticos
  completos; las solicitudes de cancelación coinciden en8/8. «Se recomienda…»
  conserva su inicio88576 y texto; no hay la pérdida de229.

La máscara de salida de231 sigue siendo la aproximación fija212: no cambia el
audio tras una cancelación contrafactual. No es una prueba física simultánea
humana. Las transcripciones humanas conservan sus errores previos, incluido
30→3años en el humano2 sin eco; no se declaran8/8pases semánticos.

## Verificación física232

Sesión acotada del VoiceEngine directo con fuente230, RAW/Speex/Silero/Piper
y baxy.2, los mismos cuatro textos187. Sin UI/LLM ni bypass de wake. El script
conserva señales y decisiones, con el coste de observación declarado.
Terminó con1316frames/42.112s, cuatro síntesis y sin errores de dispositivo.
El cliente real declaró efectos[]. Volumen restaurado exactamente a0/mutedtrue,
todos los workers cerrados. **Hubo dos barge_in y una transcripción publicada
espuria «Toll.»**. La segunda decodificación dio «S» y el producto la descartó
por dudosa. El diagnóstico completó su recorrido, pero la calidad física falla.

233 reproduce ambos cortes en frames135/442, dos segmentos1.248s, VAD1316/1316
idéntico y diez guardas idénticas.235 reproduce el mismo resultado exacto sobre
fuente225 anterior: la nueva admisión no origina estos fallos en la señal232.
234 verifica el DSP y caracteriza la correlación; véase DIAGNOSTICO_ECO233_235.md.

## Alcance

C03 íntegro sigue activo: errores de contenido ASR, activación calibrada,
voz humana física, ocho rutas,100humanos frescos aún sin congelar y100/100,
averías/recuperación,UI/audio final,4GB conjuntos,runtime/instalación,
continuidad C04–C09,Full verde y publicación fuera de main.
