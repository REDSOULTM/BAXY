# C03 — fallo de arranque de voz integrado — 2026-09-07

EN_CURSO. Fuente147 intacta, pruebas/huellas previas en TRAMO143_157_PINS.json.
158 ejecuta `py main.py` real con misma configuración121 y Qwen3.5 override,
sin taps de audio ni hooks. App35432, launch/sampler79424, captura65681.

Dos de tres turnos previstos enviados por Computer Use:

-«Dime la hora.» entra a10:24:00. Core verifica10:24; visible «Son las10:24.»
a10:24:54, ~54s. Captura y screenshot01-clock-es conservados.
-«What time is it?» entra a10:26:21. Core observa10:26:51; visible «It is10:26.»
a10:28:16, ~116s. Screenshot02-clock-en conserva vozoff. La hora es fiel al hecho
verificado pero ya está anticuada al publicarse. No considerarlo útil por literal.
-Mezcla no enviada: la reproducción ya demostró fallo de integración; no completar
la lista como si la captura física siguiera activa después de su plazo.

Voiceoff permanece en UI. Shell-trace muestra nuevos catalog.configure/id1 y
timeouts de message.compose; no declarar fallo nativo sin stack. La captura llegó
a300,14s y restauró exactamente0/muted=true,0overflows. Loopbackpeak1/32768:
no salida audible en la ventana capturada, incluido saludo y primera respuesta.
La segunda respuesta llega fuera de la grabación; no adjudicar su audio.

App cerrada por marcador STOP_APP y dueño validado: cleanupExit0, launcherExit0,
400,81s de monitor, GPU3508,0859375MiB (atribución disponible), RAM5864,33203125MiB.
Sampler comenzó tras detectar la App13,219s después del launcher; creación App
1788787372,8509917, no13s de App sin medir. Ambos procesos de prueba recogidosexit0.
Snapshot privado de comandos y variables seleccionadas en process158.json;
confirma aplicación/sidecar con mismos manifests wake y allow_uncalibrated1.
No aprobación de wake ni promoción del runtime.

159 inicia VoiceEngine.start(wake) sin preload con esa configuración observada:
readyTrue en8,187s, AEC activo, cierre completo.160 añade saludo real en cola antes
de start, orden de App: readyTrue8,312s/cierre. Ningún cambio de volumen; endpoint
seguía silenciado. Ambosexit0 y sin dumps del temporizador12s. Esto descarta que
ese arranque de voz aislado falle siempre; no descarta carga/contención integrada.
Continúan wakeCascadeManifestInvalid/wakeVerifierMissing: seam histórico, no cierre.

161 en curso: sidecar original por JSONL, catálogo autenticado del Core actual,
Qwen3.5 y entorno observado; secuencia catálogo/status/saludo/startwake. Entrada
runpy sólo habilita faulthandler cada15s, sin monkeypatches. Logs/protocolo privados,
sin ejecutar operaciones del catálogo. Sesión16017; consultar resultado y stacks
antes de tocar timeouts o repetir UI. Driver garantiza cierre de árbol propio.

161 terminado: voice.start agota 60 s; driver exit1 tras ~68 s. Stack repetido:
request_dispatch -> VoiceEngine._start (lock de voz retenido) -> LoopbackReference.start
-> scipy.signal -> scipy.linalg.blas -> carga nativa _fblas. TTS espera ese lock
en _on_tts_state. Cleanup del root exit0 NO prueba cierre cooperativo: stderr
registra request_dispatch_thread y voice_engine_shutdown timed_out; descendientes
propios recogidos. Sin procesos de esta prueba pendientes.
162 prepara una única diferencia experimental: importar scipy.signal en el hilo
principal antes de runpy/lector JSONL. Fuente147 sigue intacta. OpenBLAS documenta
un bloqueo de inicialización gfortran/pipes en Windows para Java; es hipótesis
análoga, todavía no demostración de la causa nativa de BAXY.
https://github.com/OpenMathLib/OpenBLAS#considerations-for-using-the-library-from-java
