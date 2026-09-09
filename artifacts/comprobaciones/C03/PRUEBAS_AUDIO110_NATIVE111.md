# Audio110 y síntesis111 — 2026-09-07

La prueba de escritorio obtuvo tres respuestas visibles fieles y presupuesto
menor de4GB con voz activada, pero **no acreditó audio inteligible**. La
comparación nativa posterior localizó la omisión de PAD entre fonemas al formar
la entrada de Piper. Añadirlo recupera el contenido de tres controles españoles;
el inglés continúa fallando con la configuración española.

## Audio110: producto y captura física

[Prerregistro](astra-audio110/PREREG.json): fuente108, `py main.py`, mismo
override Qwen3.5, wake1 y pila de voz registrada. Sin hook, inyección de borradores
o PythonPath alternativo. Los controles son técnicos consumidos, no reserva100.

| Entrada | Respuesta visible | Captura |
|---|---|---|
| Dime la hora. | Son las 07:13. | [ES](astra-audio110/01-es-visible.jpg) |
| What time is it? | It is 07:14. | [EN](astra-audio110/02-en-visible.jpg) |
| Dime la hora, please. | Son las 07:15. | [Mixto](astra-audio110/03-mixed-visible.jpg) |

Bienvenida: «¡Hola! Aquí BAXY. ¿En qué te puedo ayudar hoy?».
App28040, Sky856508. La primera captura estaba ocluida por otra aplicación y no
se guardó como evidencia de BAXY; se activó la ventana y se observó de nuevo.

Captura87021/PID38376:180,09s, terminó por límite180s, exit0. Micrófono Realtek
MME1,16kHz/mono, y loopback WASAPI13,48kHz/estéreo, en streams independientes.
No overflows y ambos hilos terminaron. Se elevó temporalmente el endpoint
predeterminado a0,30/unmuted y se restauró **exactamente** a0/muted=true.
[Resultado](astra-audio110/AUDIO_RESULT.json). WAVs privados fuera del repositorio:
LOCALAPPDATA/BAXY/C03-audio110-private, con rutas y hashes en ese resultado.
No subida de audio ni transcripciones a servicios externos.

Se heredó el mecanismo de streams con propietario de tramo45 y se contrastó
con [sounddevice0.5.5](https://python-sounddevice.readthedocs.io/en/0.5.5/api/streams.html),
misma versión instalada. Lectura sin callbacks en un hilo propietario por stream;
consulta de disponibilidad antes de leer y restauración del endpoint en finally.
La captura observa dispositivos reales; el loopback no se presenta como micrófono.

Monitor/launcher76726 exit0:200,45s, GPU3502,296875MiB, RAM6015,91796875MiB,
atribución disponible; captura desde1,032s después de lanzar, antes de readiness.
Launcher py main.py exit0, limpieza exclusiva del árbol propio exit0.
[Recursos](astra-audio110/RESOURCES.json). No reinicio ni caída nativa observada.
No incluye los1,032s iniciales ni acredita ejecución con el modelo promovido.

## Lo que revelan las grabaciones

Análisis2169 exit0, sólo CPU y STT registrado Parakeet0.6b-v3-int8, después de
terminar App/servidor. Cuatro ventanas alrededor de voice.speak:1s previo y12s
posteriores, usando creación de App + tiempo relativo de trace, sin afirmar
timestamp DAC exacto. Transcripción cruda y normalizada al pico, sin prompt de
texto esperado ni hotwords. [Índice privado](astra-audio110/TRANSCRIPTION_INDEX.json).

Saludo y dos primeros relojes no se recuperan por ASR en ninguna de las dos
señales. En el último, loopback crudo produce «Solo se gira.»; normalizado,
«Susegira.». Micrófono normalizado produce «So I'm saying he.». Ninguna conserva
la hora. Esa última ventana tiene4,6s disponibles por el límite de captura y
no se presenta como reproducción completa demostrada.

Correlación de ventanas mic/loopback:0,237 en saludo,0,009 en primer reloj,
0,225 en segundo y0,212 en tercero. Son señales de trayecto, **no** prueba de
contenido inteligible. Un reloj casi no tiene energía en loopback. Esto impide
adjudicar aceptación física aunque la pantalla y las llamadas voice.speak existan.

## Native111: primera transformación incorrecta

Fuente voice_output.py seguía byte a byte igual al tramo45,
SHA d123946278b2e70d897216e6a44ba24c5f0b505d138732e7cb31e0898d9f4afa.
Las83pruebas citadas de voz eran el conteo del tramo45, no el tramo83 de búsquedas.
Aquellas pruebas acreditaban propietario/cancelación y reproducción, sin decodificar
el PCM producido por la tokenización del modelo.

`_PiperOnnxEngine.generate` enviaba BOS/fonemas/EOS sin PAD. El
[código primario de Piper](https://raw.githubusercontent.com/rhasspy/piper/master/src/python_run/piper/voice.py)
consultado2026-09-07 inserta el ID PAD tras cada fonema conocido. Se contrasta
el contrato del export usado, sin instalar el paquete Piper ni sustituirlo todo.

[Prerregistro111](astra-native-tts111/PREREG.json): mismas cuatro respuestas,
ONNX/config registrados, fonemas CLI eSpeak, escalas, proveedor CPU y ASR local;
única diferencia de entrada: PAD tras fonemas conocidos. Se conservan ambos
WAVs, secuencias de IDs, fonemas, tiempos, hashes y decodes en
[RESULTS](astra-native-tts111/RESULTS.json). Sin reproducción física ni LLM.
Sesión89823 exit0. La variación de ruido propia de ONNX no se fijó por semilla;
no se comparan formas de onda idénticas, sino conservación de contenido.

| Texto de entrada | ASR sin PAD | ASR con PAD | Duración sin/con PAD |
|---|---|---|---|
| ¡Hola! Aquí BAXY. ¿En qué te puedo ayudar hoy? | Paketajik pordaron. | Hola aquí Baxi en que te puedo ayudar hoy. |1,637/2,485s|
| Son las 07:13. | So say this. | Son las 7.13. |0,720/1,184s|
| It is 07:14. | vacío | И ти сите 14. |0,801/1,335s|
| Son las 07:15. | Solo se gira. | Son las 7.15. |0,766/1,289s|

Se adopta la corrección del contrato en fuente112; el inglés permanece como
bloqueo separado, no un4/4. La voz/config es es_MX-claude-high/es-419; el
fonemizador trata también la frase inglesa como español. Investigar esa frontera
con pruebas nativas antes de añadir modelos o cambiar la interfaz. Queda por
demostrar físicamente la corrección y resolver inglés, entrada hablada,
reserva100, promoción, continuidad y cierre final. C03 EN_CURSO.
