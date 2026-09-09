# C03 — contador de interrupción sostenida — fuente172

Defecto observado en código: si VAD no declara habla, el contador anterior no
se reinicia. Acumula candidatos separados por silencio o por salida detenida.
Además, >=3 emite nuevas cancelaciones en cada frame mientras el output aún
está cerrándose.168 mostró eventos separados por31ms dentro de un mismo corte.
Esto no prueba que el PRIMER corte169 fuera por acumulación; se conserva ese límite.

Prueba del capture_loop original: cinco secuencias, VAD/stream aislados;
4fallos/1pase/81deselected en1,42s. Capturaba [3,4,5,6] en vez de un solo [3]
y cancelaba al sumar tres frames no consecutivos. Incluye control positivo de
tres frames consecutivos que ya pasaba; no se cambia la duración exigida.

172 añade reinicio cuando no hay voz o no está hablando, y cambia >=3 por ==3.
No modifica modelo, DSP, duración3frames, umbrales, ventanas ni política wake.
Suites dueñas voz/captura/Speex/output/goal06:130pass,0skips,7,36s.
Fast55364 en curso al preparar este informe; recoger antes del ensayo173.

Herencia: biblioteca/gemma4-agent/documentacion/01_arquitectura/design/barge_in.md
exige actividad consecutiva, pero es DESIGN ONLY: no acredita una implementación
ni se adopta su duración propuesta de500ms. El código actual conserva96ms.
Contraste primario Speex consultado2026-09-07:
https://www.speex.org/docs/manual/speex-manual/node7.html
El manual advierte sobre adaptación, reloj y distorsión. mdf.c1.2.1:1124–1170
calcula adaptación mínima; no se midió todavía ese estado nativo en169.
No se atribuye el corte a adaptación sólo por esa lectura ni se modifica el filtro.

173 preparado: mismo fullsidecar168 y cuatro textos, mismo observador de estado
(sin taps porframe ni snapshot169), nueva fuente172. Registrar todos los cortes;
si siguen, no aumentar duración ni retocar correlación para aprobar la corrida.

## Resultado posterior

Fast55364 exit0, Release2,73 s, 0 avisos/errores. 173 terminado: dos cortes en cuatro salidas; contador reparado, separación acústica aún insuficiente. Ver astra-sidecar173 y nuevo experimento174.
