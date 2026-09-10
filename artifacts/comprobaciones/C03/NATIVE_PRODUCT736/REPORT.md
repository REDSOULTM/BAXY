# K2 y Qwen: capacidad del modelo e integración con BAXY

La preocupación del dueño está confirmada en casos concretos: BAXY puede retirar una operación correcta o rechazar una respuesta verdadera por su formulación. Eso debe separarse del rendimiento nativo del modelo.

## Resultados y alcance

El ensayo nativo699 ya comparó seis perfiles con los mismos50 casos, sin reglas ni catálogo de BAXY:300 respuestas. Qwen práctico obtuvo40/50 y K2 high práctico38/50. La prueba731 mostró además que forzar `enable_thinking=False` a K2 bajaba ese control a19/50; esa imposición no se usa aquí.

La comparación736 conserva código, adaptadores, App y Core idénticos, con el perfil propio de cada modelo. K2 se interrumpió por RAM libre global tras50 finales; Qwen completó73. Las23 peticiones restantes de K2 siguen sin evaluar.

| Medida del producto | K2 high práctico | Qwen práctico |
|---|---:|---:|
| Finales completados / previstos |50/73|73/73|
| Respuestas correctas entre los50 comunes |11/50|35/50|
| Correctas en todo lo completado |11/50|48/73|
| Mediana hasta terminal, mismos50, incluidos fallos |30,39 s|1,06 s|
| Pico VRAM del árbol medido |3,37 GiB|3,10 GiB|
| Pico RAM residente, servidor y producto observados |2,27 GiB|2,34 GiB|
| Pico memoria privada comprometida, mismo alcance |6,50 GiB|6,14 GiB|

En los50 comunes hay11 aciertos compartidos,24 sólo de Qwen y15 fallos compartidos. Esto describe **estas integraciones**: no demuestra que K2 sólo pueda responder11 de50 preguntas sin BAXY. El panel nativo699 es distinto y no permite restar puntuaciones como medida de regresión.

La adjudicación es conservadora: Qwen falla cuando añade que la GPU es principal sin observación o que la batería ya terminó de cargarse. Sus resultados son sensibles a tres formulaciones anotadas en ADJUDICATION.json (47–50/73 según esas interpretaciones). No cambia la conclusión de que ninguna integración cumple C03.

## Dónde se pierde la respuesta

- **BAXY retira propuestas correctas.** En H0023, H0103 y disk-used-es, K2 recibe y elige la operación pertinente. El replay del veto de dominio convierte las tres en conversación sin operaciones. El timeout posterior no fue la primera pérdida.
- **BAXY rechaza prosa correcta.** En H0104 la ventana y su foco están observados y bien descritos. El validador no reconoce la formulación «Activa está…» y también restringe cómo se identifica el sujeto. Reordenar sólo la cópula no basta.
- **El modelo/servidor también puede entregar un defecto.** H0207 y H0384 ya llegan con `</ifm|think>` en el content HTTP; BAXY lo publica. No se ha aislado su origen entre generación, prompt y parser. En H0359 K2 propone una cifra de batería sin lectura; después el guardia se agota. Ese error previo tampoco se atribuye a BAXY.
- **Los presupuestos de BAXY pesan mucho.** Hay llamadas de prosa con unos4s efectivos y reparaciones con el remanente. K2 registra292 fallos de transporte y40 respuestas completas en333 llamadas; una quedó abierta al corte. Qwen registra193 respuestas y1 fallo en194. Esos son contadores de llamadas, no de casos ni de errores semánticos.

Los logs distinguen el input de BAXY de la petición efectiva. Todas las llamadas K2 usaron T1/max4096/high y las Qwen T0,7/max4096; no se envió `enable_thinking=False`. Los guardias antiguos no intervienen en todas las rutas: se observaron3 llamadas en K2 y14 en Qwen, incluidos caminos posteriores a la selección nativa.

## Recursos y diferencias del entorno

K2 se cortó cuando la RAM **global** disponible cayó a747,49MiB, bajo el umbral768MiB. No superó el límite de VRAM propio. Sus muestras no identifican qué proceso causó la caída. Después se cerró el capturador AMD PresentMon (unos788MiB) y se solicitó cerrar Steam; Qwen arrancó con más RAM libre. No se presenta la diferencia de tiempos como un experimento de entorno perfectamente idéntico.

La RAM residente y la memoria privada comprometida no son equivalentes: esta última no implica que toda esa cantidad esté ocupando RAM física. Los observadores adicionales comenzaron después de aparecer la App y excluyen compiladores. Estas ejecuciones no acreditan ventana visible, voz física ni todo el consumo conjunto de BAXY en uso normal.

## Decisión y continuación

No se promueve K2 ni se cambia el runtime registrado. Tampoco se descarta K2 por la puntuación global del producto. El siguiente diagnóstico debe aislar la redacción de hechos con payloads congelados y un perfil apropiado para ese rol, y medir las pérdidas de los filtros compartidos antes de otra campaña general. No repetir la misma tanda con la misma configuración ni ampliar plazos para contar passes.

La categoría K2 sigue incompleta (23 pendientes). C03 sigue activo: encuesta26 cubiertos/716 abiertos/0 no aplicables; Full5 conserva sus dos fallos originales. No se adopta fuente ni se acredita cobertura con este informe.

[Método y atribuciones detalladas](METODO_Y_HALLAZGOS.md) · [comparación y controles](COMPARISON.json) · [juicios K2](k2/ADJUDICATION.json) · [juicios Qwen](qwen/ADJUDICATION.json).

Las entradas, respuestas literales, payloads y borradores completos permanecen localmente en:

- [K2 — respuestas](<C:/Users/usuario/AppData/Local/BAXY/C03-native-product736-k2-private/RESPUESTAS.md>)
- [Qwen — respuestas](<C:/Users/usuario/AppData/Local/BAXY/C03-native-product736-qwen-private/RESPUESTAS.md>)
