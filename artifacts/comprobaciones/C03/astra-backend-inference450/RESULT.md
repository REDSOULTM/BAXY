# 450 — la actualización sola no resuelve memoria

44 primeras respuestas; todas terminaron por stop, sin cortes ni errores.

| Modelo | Backend | Útiles/11 | Segundos de peticiones | Máximo tokens salida |
|---|---|---:|---:|---:|
| qwen35-4b | b9980 | 6/11 | 5.078 | 26 |
| qwen35-4b | b10809 | 6/11 | 4.734 | 26 |
| gemma-published | b9980 | 9/11 | 3.61 | 52 |
| gemma-published | b10809 | 8/11 | 4.156 | 66 |

Qwen conserva once respuestas idénticas entre versiones. Gemma cambia cinco,
pero persisten los fallos de datos protegidos. El tiempo de una corrida corta
no acredita una mejora estable de rendimiento. Recursos completos en resources.json;
no VRAM/RAM del producto entero. Manifest intacto; fuente436.

451 compara perfiles documentados por modelo. Esta comparación T0 sólo aísla
el backend: no permite descartar una familia por sus resultados. Todas las
respuestas literales y razones de adjudicación están en ADJUDICATION.json.
