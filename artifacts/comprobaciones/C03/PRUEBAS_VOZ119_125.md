# C03 — Piper integrado, audio físico e interrupción — 2026-09-07

Fuente119 integra el proveedor completo, con311tests/Fast verdes. Native120
recupera seis contenidos ES/EN por la cola real; el sink sustituye únicamente
el dispositivo. Identidad de voz, cancelación de hijo real y snapshots de fuente
en astra-native-voice120. Los contenidos son los seis controles118, no reserva100.
Native120 no acreditaba acústica. UI/audio121 confirma que faltaba otra frontera.

## UI/audio121: producto real, contenido físico no acreditado

`py main.py`, fuente119, App38776, Qwen3.5 override, wake1, sin hooks/sink ni
inyección de texto generado. Launcher/monitor21410exit0, captura32330exit0.
Misma sesión de escritorio, capturas00–03 en astra-audio121; lectura directa
por Computer Use. Texto de entrada literal y final visible:

| Hora local | Pedido | Respuesta |
|---|---|---|
|08:10:56|bienvenida de arranque|¡Hola! Aquí BAXY. ¿En qué te puedo ayudar hoy?|
|08:12:11–12|Dime la hora.|Son las 08:12.|
|08:12:47–48|What time is it?|It is 08:12.|
|08:13:30–31|Dime la hora, please.|Son las 08:13.|

Micrófono MME Realtek1/16kmono y loopback WASAPI13/48kstereo reales,267,42s,
cero overflows. Datos privados en LOCALAPPDATA/BAXY/C03-audio121-private.
Volumen0,30 temporal;0/muted=true restaurado exactamente al finalizar. App y
descendientes terminados por ruta/PID propios, no procesos ajenos. PicoGPU
3513,41796875MiB; RAM5964,01953125MiB,257,75s. Sampler adjunto al App nuevo
antes de readiness,12,219s tras lanzar py (incluye espera al build/creación del
App); no atribuir al App consumo anterior a existir. Registro intacto.

Análisis85289exit0, ParakeetCPU sin hints/hotwords sobre ventanas13s ancladas
aproximadamente a creaciónApp+ms de voice.speak. Todas completas: esta vez no
hay truncamiento por fin de captura. Micrófono no recupera texto; loopback sólo
«Yeah.» en t2 crudo, resto vacío (normalizado también vacío). Energía/correlación
no sustituyen contenido. ASR es observador imperfecto: tampoco se afirma que
esta transcripción vacía sea por sí sola la causa del problema.
TRANSCRIPTION_INDEX.json apunta al informe privado con hash. No aceptación física.

El manifest confirma python_path=src de este repositorio: no otra instalación.
VoiceEngine conserva VAD y barge-in al hablar; la primera frontera siguiente
que podía cortar audio era esa interrupción o la reproducción real.

## 122/123: aislamiento físico de la activación del micrófono

Herencia: biblioteca/gemma4-agent/documentacion/01_arquitectura/design/barge_in.md,
2026-06-04, **diseño solamente**. Propone actividad sostenida pero no demuestra
supresión de eco; no se adopta un umbral suyo para conseguir un pase.

122 intentó off-before/wake/off-after con VoiceEngine real, sin App/LLM ni efectos.
Off-before produjo5,171s de estado speaking. Wake se rechazó por
wake_verifier_manifest_missing; driver12205exit1, captura26286exit0/restauración.
Se conserva el fallo; no es comparación completada ni fallo de Piper.

Se comprobó una diferencia con App: MindRuntimeDiscovery.cs:188–208 publica el
manifiesto registrado de wake, calibration.approved=false, y establece
BAXY_VOICE_WAKE_ALLOW_UNCALIBRATED=1. Es una seam preexistente, no permiso para
aceptar wake sin calibrar. No se replica esa excepción para forzar la prueba.
123 usa modo directo: el bloque barge-in es compartido y se ejecuta antes de la
distinción de modos (voice.py:2348–2360 en fuente119). Aísla esa frontera; no
acredita wake. No guard relajado, PCM inyectado, efecto Core ni transcripción
enrutada. Las posibles transcripciones se guardan sólo en el directorio privado.

12362079exit0/captura97658exit0: un VoiceEngine, misma frase ya consumida,
«The file read failed because the content is invalid UTF-8.», misma voz John,
flujo público start/stop y mismos dispositivos. Captura39,64s, volumen restaurado.

| Fase | Estado speaking | Eventos barge_in | Error del proveedor |
|---|---:|---:|---|
|off-before|5,234s|0|ninguno|
|direct|1,469s|1|ninguno|
|off-after|5,391s|0|ninguno|

La activación normal también inicia loopback/ducking: no es únicamente un cambio
de bit. Lo demostrado es la cancelación real al activar escucha, no una avería
de síntesis. El propio eco es hipótesis apoyada por el defecto siguiente, pendiente
de confirmar con el contraste físico125 y el contenido capturado.

## Fuente124: comparar todos los retardos sin relajar el umbral

`_looks_like_echo` decía tolerar250ms, pero muestreaba el retardo de128 en128
muestras (8ms). El eco exactamente atenuado a retardos1,73,127,513,3999 y4000
muestras se clasificaba como distinto. Antes:6fail/2pass/70deselected,1,19s.
Los controles antiguos sólo cubrían eco sin retardo y ruido independiente.

Se conserva ventana250ms, energía mínima, umbral0,55 y reglas de interrupción.
La correlación normalizada ahora examina cada retardo, con norma centrada por
ventana. Implementación vectorizada con el NumPy1.26.4 ya instalado;
[referencia primaria1.26](https://numpy.org/doc/1.26/reference/generated/numpy.correlate.html),
consultada2026-09-07. No nueva dependencia, clasificador ni capa de AEC.
Se mantiene el control negativo de voz cercana independiente mezclada con eco.

`python -m pytest tests/test_mind_voice_runtime.py tests/test_piper_tts.py tests/test_neural_speech_output.py tests/test_goal06_voice.py -q`
→109pass/0skips,7,78s. Mil evaluaciones del control retrasado reconocidas;
media0,328ms por frame frente a ventana de32ms. Es microbenchmark, no recursos
del producto completo. Fast90073exit0: Release3,36s,0avisos/errores. No Full.

125 prerregistrado como el mismo off/direct/off de123, fuente124 como diferencia.
Driver10575/captura66170 terminaron con exit0. Off-before:5,562s/0barge;
direct:3,938s/1barge; off-after:5,359s/0barge. Ningún error del proveedor.
Captura47,86s, cero overflows, threadsStopped=true y volumen restaurado
exactamente a0/muted=true. Fuente124 prolonga la reproducción respecto de123,
pero aún ocurre una cancelación anticipada: no acredita aceptación acústica.
El siguiente diagnóstico compara las capturas privadas123/125 y sus eventos,
sin repetir reproducción ni cambiar el umbral. Fuente119/124 son
candidatos, runtime no promovido. UI/audio final, entrada hablada, reserva100,
promoción/regresión, continuidadC04–C09 y Full/publicación siguen pendientes.
