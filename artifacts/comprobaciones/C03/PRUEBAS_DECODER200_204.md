# C03 — diagnóstico de decodificación 200–204

No hay cambio de producto ni promoción de runtime/AEC. Fuente192 sigue vigente.
200 conserva comparación de onda sobre las24 señales198. 201 usa la segmentación
real del producto/Silero:42 segmentos, cada uno idéntico a un rango de entrada.
El primer intento201 falla en el arnés antes de ingerir frames; se conserva.
202 completa42 lecturas con helper real y modified_beam_search, CPU6/paths8.
203 cambia sólo a greedy_search:42 segmentos +4 originales +silencio =47 lecturas.
Tres segmentos humanos vacíos (casos15,21,23) recuperan contenido, y caso3 pasa
de «Hola.» a la frase humana. Existen omisiones menores y texto procedente del
eco; no son47 pases. Silencio puro vacío. No acredita reparación acústica183.

204 mide el coste de dos reconocedores CPU: greedy751,99MiB incrementales,
6,453s de construcción; beam adicional729,19MiB y6,204s. RSS conjunto1525,50MiB.
El mismo segmento23 con beam y aliases wake sigue vacío; greedy lo recupera.
El primer lanzamiento204 falló por import incorrecto antes de crear outputs;
reintento completo, proceso79058 recogido exit0. No segundo modelo adoptado.

Decisión: probar reparación nativa acotada antes de aceptar dos copias del modelo.
En curso205: fuente sherpa-onnx v1.13.4 commit142807252687d81b40d6315f23470a1512a00de3,
compilación aislada Windows. PR3657 abierta, head867762892495a6bf1a2b031699906aaa73217e90.
La fuente1.13.4 ya avanza al menos un frame en blank: el cambio efectivo propuesto
es puntuación de duración/límite de símbolos. No atribuirlo a añadir ese guard.
Se comparará primero compilación sin parche, después mismo build con parche,
sobre los controles congelados. No modifica el registro ni instala en el runtime.
SetConfig de Nemo no reconstruye el decoder; no usarlo para fingir cambio dinámico.

Fuentes: [reporte3267](https://github.com/k2-fsa/sherpa-onnx/issues/3267),
[propuesta3657](https://github.com/k2-fsa/sherpa-onnx/pull/3657), herencia en
biblioteca/gemma4-agent/documentacion/03_voz_stt/research/parakeet_v3_uso_correcto_2026-06-10.md.
Todos los controles200–204 terminados;205 es trabajo posterior sin resultado aún.
C03 EN_CURSO: se mantienen íntegros los pendientes de CHECKPOINT.md.
