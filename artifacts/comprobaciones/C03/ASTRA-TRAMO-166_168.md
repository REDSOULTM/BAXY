# C03 — UI166 vuelve a responder; salida física aún falla

Fuente164191pass/0skips19,14s. Fast49634exit0, Release3,56s0warnings/errors.
166 App36988, launcher7728, monitor30244; py main.py real. Captura7514 y launcher65506
exit0/propios cerrados. Sin nuevas ediciones de producto tras164.
Tres preguntas consumidas en UI: «Dime la hora.» -> «Son las10:55.»;
«What time is it?» -> «It is10:56.»; «Dime la hora, please.» -> «Son las10:56.».
Payloads Core verificados y composición first/stop en idioma es/en/mixed.
Latencias submit.received->visible.text:1325,475/1045,566/1043,858ms.
Un solo catalog.configure, voiceon durante toda la observación, sin reinicios.
Recursos246,77s:3499,50390625MiBVRAM, atribución disponible;5964,53125MiBRAM.
Audio263,89s,0overflows, threadsStopped y restauración exacta0/mutedtrue.

167 ASR local Parakeet CPU sobre mic/loopback crudo y normalizado, cuatroventanas
de voice.speak-0,5s a+15s. NO recupera las frases completas: mic vacío cuatro;
loop saludo/EN vacío, ES «Yeah.» sólo crudo, mixto «Gracias.»/«Thank you.».
Hay señal capturada, no es el silencio de158, pero no acreditar audio útil.
No afirmar aún que sean cortes por barge:166 no guardó ese evento interno.
Fuente164 corrige bloqueo161 y latencia158; NO cierra audio148 ni C03.

168 siguiente: fullsidecar/catálogo/modelo, mismos cuatrotextos publicados166,
captura física. Registra eventos JSONL y sólo añade observación de last_error
al cambiar speaking; no taps porframe ni modifica DSP. Distinguir cancelación
barge_in de error/deadline de reproducción antes de cualquier ajuste.


168 terminado: driver81611 y captura99840 exit0, cierre propio69,266s;
captura91,31s con restauración exacta. Greeting4,781s sinbarge; ES10:55 dura1,516s
con1barge; EN10:56 dura2,907s sinbarge; ES10:56 dura0,938s con2eventosbarge.
Todos cambios a speakingFalse reportan errorTTS null. La interrupción, no un
deadlineTTS observado, explica dos de cuatro salidas en esta reproducción.
No extender esa atribución a todas las salidas166 sin su evento interno.
169 prepara snapshot sólo tras la primera decisión de cancelar: arrays locales,
ring y relojes. Evita los taps porframe que antes coincidían con desaparición
del fallo. Producto164 intacto; sin procesos propios antes del arranque169.
