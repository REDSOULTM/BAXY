# C03 — captura WASAPI en su hilo dueño — 2026-09-07

EN_CURSO.143 integra cursor continuo y captura WASAPI;148tests/0skips/13,12s,
Fast17999exit0/Release2,85s/0avisos/errores.144 físico falla antes de hablar:
capture_failed:PortAudioError. Captura62385exit0,24,08s,0overflows y endpoint
0/muted=true restaurado exactamente. Driverexit1. No resultado acústico favorable.

145 aísla WasapiCaptureStream con loopback activo, sin reproducir ni cambiar
volumen: hilo principal abre/lee10frames; worker falla al start. Error−9999 con
texto WDM-KS del backend, conservado entero en astra-capture145/RESULTS.json;
ese texto por sí solo no prueba que se esté seleccionando WDM-KS.

146 cambia sólo el contexto COM del worker: el _com_apartment existente de
voice_aec.py rodea la vida de captura. Tres aperturas consecutivas leen10frames
cada una, ADC válido, mismo dispositivo12 aquí. Sin PCM guardado ni reproducción.
Exit0. Se adopta inicialización por hilo, no se cambia el algoritmo de AEC.

Herencia: _com_apartment ya mantiene COM para AudioDucker en el producto.
Consulta acotada evidencia-baxy/índice e inventario de voz; no se atribuye al
histórico una prueba de esta captura WASAPI en worker. Contraste2026-09-07:
[PortAudio WASAPI](https://raw.githubusercontent.com/PortAudio/portaudio/master/src/hostapi/wasapi/pa_win_wasapi.c)
requiere COM antes de abrir y prepara interfaces COM para el callback. Es fuente
actual, no prueba de identidad de DLL instalada. La reproducción145/146 decide.
[Issue546 de sounddevice](https://github.com/spatialaudio/python-sounddevice/issues/546)
afecta ASIO: no se adopta como evidencia causal de WASAPI.

147 mueve apertura al __enter__ de WasapiCaptureStream: ExitStack conserva el
contexto COM hasta después del cierre; start fallido cierra dispositivo; fallo
de selección/construcción también libera COM. Reutiliza _com_apartment, sin otra
capa COM. Tests verifican orden y cierre, además de continuidad/bursts/overflow.
148pass/0skips/11,29s, TEMP/c03-source147-owner.log. Fast en curso; físico148
pendiente, misma frase/direct/volumen que138/144, sin wrappers ni VAD en sombra.
No Full ni promoción; C03 completo sigue EN_CURSO.

Fast77674exit0, Release1,39s/0avisos/errores.148 driver45941/captura53932exit0,
pero habla1,609s y1barge: **fallo acústico**, aunque arranque y cierre ya funcionen.
33,62s de captura, cero overflows, restaura0/muted=true. No atribuir la causa a
COM ni asumir que la continuidad por sí sola resolvió el problema.

149 tap de observación retorna AEC/VAD/guard originales sin segundo VAD ni cambios
de fuente.264pares crudo/referencia/limpio privados, índice de huellas público.
92688/89757exit0,5,282s/0barge; captura38,05s, restauración exacta.150 verifica
historial continuo bit a bit entre frames y correlación global0,331 con desfase
mic−ref835muestras/52,19ms. Correlación global no prueba calidad local en cada frame.
151 prueba ocho fases de bloque prefijadas0–448step64 con mismo mic/ref149 y nuevos
estados DSP:0barge en8/8; fase0 reproduce PCM limpio bitidéntico. Es componente
offline, no toda la segmentación ni aceptación física. Límites en su PREREG.

152 fija tres inicios de captura con stop entre ellos, todos con tap149 y copia
única del resultado Piper.59589/12976exit0; speaking5,391/5,562/5,219s,0barge en3.
Captura56,80s, cero overflows, restaura0/muted=true. Los tres PCM generados tienen
97082/101434/93754muestras a22050Hz (4,403/4,600/4,252s), huellas distintas en
GENERATED_INDEX.json. Por ello repetir el texto no controla la señal sintetizada;
**no atribuir diferencias entre corridas sólo al coste de observación**. Estados
AEC sí nuevos por captura; Silero pertenece al engine cargado y no se recrea por
phase: no afirmar tres arranques fríos completos de todos los componentes.

153 en curso: mismos tres inicios, sin taps por frame, sólo copia del PCM devuelto
por Piper una vez por frase. Captura48562/driver11839. No elegir el mejor pase.
Fuente147 intacta y snapshot14ficheros/logs en astra-source147-snapshot/INDEX.json.

153 terminó11839/48562exit0,5,375/5,109/5,422s,0barge en3;49,45s/restauración exacta.
154 añadió seis fixtures consumidos ES/EN:58440/25526exit0,0barge en6,75,01s/
restauración exacta.156 ASR34732exit0;157 ASR del corte148exit0 confirma truncamiento.
Resultados, límites y siguiente acción en PRUEBAS_CAPTURA143_157.md. Sin procesos
propios activos. C03 y el corte148 siguen abiertos; no Full/promo/publicación aún.
