# C03 — captura RAW integrada y verificación física220–221

## Cambio de producto220

WasapiCaptureStream solicita eStreamOptionRaw sobre la estructura WASAPI de
sounddevice0.5.5. Conserva auto_convert, entrada predeterminada WASAPI, bloques
mono512 a16kHz, reloj ADC, cola acotada, detección de pérdidas y propietario COM.
El campo CFFI se utiliza porque la versión fijada no ofrece un argumento RAW
en WasapiSettings. No se añade otro capturador ni se modifican Speex, VAD,
umbrales o decodificadores. La dependencia instalada sigue siendo baxy.2.

La API de PortAudio puede aceptar la apertura aun si un endpoint no aplica RAW;
por ello esta prueba verifica los efectos del IAudioClient real. La evidencia
corresponde a este endpoint y runtime, no a todos los controladores Windows.

## Validación220

- `pytest tests/test_voice_capture_clock.py tests/test_speex_aec.py tests/test_goal09_voice_engines.py -q`:
  **35 passed in53.05s**, sin skips, Python registrado. La prueba de captura
  comprueba RAW y auto_convert junto al reloj, copia de frames y cierre COM.
- Ruff de voice_capture.py y test_voice_capture_clock.py: verde.
- `scripts/test_source_quality.ps1`: Fast exit0; log íntegro en astra-capture220/Fast.log.
- `scratchpad/c03-capture220.py`: componente productivo real,250frames/8s,
  efectos Windows declarados `[]`, sin desbordamiento ni datos no finitos.
  ADC inicial101709.8674698, final101717.8352363; intervalo mínimo0.0293378s,
  máximo0.0342619s, siempre creciente. No se conserva PCM ni se cambia volumen.

## Diagnóstico221

PREREG y script definen una sesión física del VoiceEngine productivo en modo
directo, RAW/Speex/Silero/Piper/baxy.2, con los cuatro textos fijos187. Se observa
después de ejecutar el DSP real; se conservan micrófono/referencia/salida y
decisiones para poder estudiar cualquier corte sin repetir grabaciones a ciegas.
No hay modelo alternativo, UI, LLM ni excepción a la calibración de wake.

Terminó exit0:1316frames/42.112s, cuatro síntesis y admisiones, cero barge_in,
cero errores de voz/conductor. El cliente real declaró efectos `[]`. Captura,
decodificación y salida terminaron; volumen restaurado exactamente a0/mutedtrue.
Fast compiló Release en7.06s,0avisos/errores.

Hay una transcripción inesperada durante el saludo: «Let's see.». Por tanto,
cero interrupciones no significa ausencia de capturas espurias. El diagnóstico
222 conserva y reproduce el segmento; no se presenta221 como aceptación de voz.
No hubo habla humana simultánea controlada ni UI/LLM, y wake sigue no disponible.

## Alcance pendiente

Siguen abiertos los controles217 con palabras perdidas, eco y30→3años, la
activación calibrada y la aceptación física humana. No se ejecutó Full durante
esta reparación. C03 conserva las ocho rutas,100turnos humanos frescos aún sin
congelar,100/100 útiles/fieles,averías/recuperación,UI/audio final,4GB conjuntos,
runtime/instalación,continuidad C04–C09 y publicación fuera de main.
