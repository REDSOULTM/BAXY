# C03 — tramo45 — diagnóstico en curso

La confirmación «Son turnos validos» queda adjudicada para los tres turnos
ingleses preguntados en ADMISIBILIDAD_DUENO_2026-09-06.md. La reserva sigue sin
congelar ni ejecutar. Las auditorías de procedencia/exposición dejan239candidatos
no descartados de742, no239humanos independientes certificados.

## UI real: fallo nuevo

`astra-scoped-reader-ui45`: lanzamiento normal `py main.py`, sin cambiar fuente44
ni runtime. Windows registró caída Python23360 con0xc0000005 a22:49:27−03 el
6septiembre. Evento1000 conservado. El turno «hola quien eres» entró externamente;
el agente no lo había tecleado. Antes de morir:voice.cancel y turn.decide. El
compositor produjo la causa mind_unavailable, pero no se certificó su visualización.
RESULT:516,16s,GPU3800,19140625MiB,RAM5154,8203125MiB,registro intacto.
STOP controlado, sesión39958 exit0. No acredita audio físico ni UI aprobada.
La captura observed-window-0.png corresponde a Codex por selección/oclusión
anómala y queda excluida como evidencia de BAXY/publicación.

## Aislamiento, sin editar producto

- `astra-native-voice45`: VoiceEngine registrado con saludo neural, wake,
  espera15s,cancelación,espera15s y parada. Exit0,53,907s. STT y micrófono activos,
  TTS SHA coincidente. No caída. `native-stderr.log` recoge snapshot programado,
  que no es excepción ni bloqueo. No hay LLM en este control.
- `astra-native-sidecar45`: añade mente registrada y catálogo auténtico del core,
  conserva saludo/wake; espera40s,cancela y solicita «hola quien eres». Exit0,
  71,218s,GPU3497,55859375MiB,RAM4953,5625MiB,registro intacto. Respuesta local:
  «Hola, soy BAXY, tu compañero en el PC. ¿En qué puedo ayudarte? 😎».
  Micrófono sigue activo. No caída. No es UI ni aceptación fresca.
- `astra-native-ui45`: reproducción en ventana real EN_CURSO,sesión6331,
  app34904,sidecar2740. Única instrumentación:PythonPath añade
  scratchpad/c03-native-hook45/sitecustomize.py para faulthandler en archivo local.
  Registro/modelo/instalación sin editar. Se envió mediante skill Windows
  «hola quien eres» a23:03:21. Detención:crear STOP dentro de la carpeta de corrida.

Herencia:REGISTRO_DE_MANTENIBILIDAD.md:785–833 describe ownership/cancelación
no bloqueante ya reparada. No reabrirla ni atribuir causa a SAPI sin stack.
El etiquetado request_timeout del shell también cubre TCS cancelado al morir
stdout (MindSidecarClient.cs:1325); no prueba agotamiento del presupuesto.

Diagnóstico nativo según [Python3.12 faulthandler](https://docs.python.org/3.12/library/faulthandler.html):
handler Windows y archivo abierto durante la vida del proceso. Se consultó
[CoUninitialize de Microsoft](https://learn.microsoft.com/en-us/windows/win32/api/combaseapi/nf-combaseapi-couninitialize)
para evaluar lifetimes COM; todavía no hay evidencia que atribuya la caída aCOM.
## Reparación adoptada45

`NATIVE_DUMP45.json` resume los dos dumps privados de Windows con hashes, sin
copiar memoria del proceso al repositorio. El original23360 intentó ejecutar
0x24525f60700,fuera de módulos,con retorno inmediato a
libportaudio64bit.dll+0xd492. El dump2740 captura una segunda violación durante
faulthandler. Es evidencia de callback nativo inválido; no un timeout LLM.

El helper heredado sd.play usa contexto global y su finished_callback libera
sus callbacks CFFI antes de que el owner cierre el stream (sounddevice.py:2650).
Se sustituyó por OutputStream sin callbacks, escrito en bloques30ms desde el
mismo worker que abre/aborta/cierra. Se retiran play/get_stream/stop globales;
no capa nueva,parámetros del modelo ni cambios C#. Un timeout de reproducción
se declara como error,ya no termina silenciosamente como si hubiera completado.
API primaria consultada el7septiembre2026:
[streams sounddevice](https://python-sounddevice.readthedocs.io/en/latest/api/streams.html),
[uso y recomendación de streams para aplicaciones](https://github.com/spatialaudio/python-sounddevice/blob/master/doc/usage.rst).
El issue365 fue sólo testimonio sin solución demostrada; no fundamenta adopción.

Antes `astra-native-ui45`:saludo produjo error visible de mente no disponible,
capturado en visible-failure.png.146,98s,GPU3792,2734375MiB,RAM5555,48046875MiB.
STOP y sesión6331 exit0. Después `astra-owned-stream-ui45`:mismo hook diagnóstico,
registro y saludo; respuesta correcta y sin caída ni reinicio del sidecar33108.
Además pregunta negativa de audio y hora con prohibición independiente responden
en pantalla.245,31s,GPU3822,51171875MiB,RAM5790,02734375MiB,registro intacto.
Sesión58140 detenida por STOP exit0. Native-fault33108 sólo contiene enabled.
Tres capturas válidas; entradas/respuestas en PRUEBAS_VOZ_UI_C03.md.
No equivale a reserva100 ni a certificación acústica por micrófono/loopback.

Pruebas dueñas:runtime Python -m pytest tests/test_neural_speech_output.py
tests/test_mind_voice_runtime.py tests/test_goal06_voice.py -q:
83pass,0skips,7,88s. Tres casos verifican PCM completo,abort/cierre tras cancelación
y cierre tras desaparición del dispositivo,con un único hilo propietario.
Prueba de hardware heredada:tests/test_goal09_voice_engines.py
-k 'product_tts_is_neural or neural_speak_starts' -q:
2pass,5deselected,0skips,4,85s; TTS neural y cancelación real a media frase.
Logs %TEMP%/c03-tranche45-voice-{owners,native-tests}.log.
Fast final verde:build1,93s,0avisos/errores,log voice-fast-final.log.
Primer Fast falló porque BAXY abierto bloqueaba la copia de baxy-core.exe:
10avisos/2errores MSB3027/MSB3021,conservado en voice-fast.log. Se cerró la prueba
propia antes de repetir. No Full todavía. Fuente:TRAMO45_PINS.json.
C03 permanece EN_CURSO,con reserva/rutas/averías/validación final pendientes.
