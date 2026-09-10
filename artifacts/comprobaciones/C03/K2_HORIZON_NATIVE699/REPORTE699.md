# Modelos antes de BAXY: referencia independiente

La objeción del dueño era válida: llamar a la API nativa no elimina las instrucciones de BAXY. Las 860 respuestas previas las conservaban. Esta fase añade 300 respuestas sin system de BAXY, herramientas ni schema, con plantilla nativa y muestreo específico por modelo. La conclusión conjunta está en la comparación emparejada de instrucciones700; ningún modelo queda promovido por esta tabla.

Son las mismas50 tareas nuevas en cada perfil:20 de hechos suministrados,10 de conocimiento sencillo,10 de instrucciones y10 de contexto;30 español,15 inglés y5 mezcla. Rúbricas congeladas antes de inferencia y respuestas completas leídas manualmente. Es diagnóstico de desarrollo dirigido a veracidad, no un benchmark general, prueba ciega ni cobertura de los742 requisitos humanos.

| Perfil | Cumple | Primer texto p50 | Final p50 / máximo | VRAM pico | RAM pico |
|---|---:|---:|---:|---:|---:|
| K2 0.9 BF16 high · referencia | 33/50 | 3.515s | 4.586s / 511.109s | 3.10GiB | 0.67GiB |
| Qwen Q4 · referencia | 40/50 | 0.078s | 3.328s / 25.890s | 2.58GiB | 2.19GiB |
| K2 3.7 Q4 high · referencia | 39/50 | 14.922s | 21.914s / 233.297s | 2.99GiB | 3.46GiB |
| Qwen Q4 · GPU 8k | 40/50 | 0.047s | 1.352s / 9.719s | 3.09GiB | 0.70GiB |
| K2 3.7 Q4 low · GPU 8k | 28/50 | 0.265s | 1.899s / 16.015s | 3.36GiB | 0.77GiB |
| K2 3.7 Q4 high · GPU 8k | 38/50 | 6.078s | 8.828s / 74.782s | 3.36GiB | 0.77GiB |

Picos medidos sólo en el árbol del servidor, con muestras cada250ms; no son el consumo conjunto de BAXY ni garantizan capturar picos más breves. El tiempo de primer texto corresponde al stream HTTP, no a pantalla/voz. La mediana del primer texto excluye finales ausentes, que se declaran abajo. No se interpreta el primer token de razonamiento oculto como una respuesta visible.

Las referencias usan el margen de salida recomendado: Qwen16384, K2 high32768. Qwen y K2 grande desplazan KV a RAM para reservar ese margen bajo el techo local; K2 pequeño BF16 mantiene KV en GPU. Los perfiles prácticos usan contexto8192/salida4096 y KV q8 en GPU. Por eso comparar referencia y práctico cambia varias condiciones; no identifica por sí solo cuál ajuste causa la diferencia.

K2 grande high y low prácticos sí mantienen idénticos los50 cuerpos enviados salvo reasoning_effort, verificado en SUMMARY699.json. El high práctico se añadió al observar degradación en low: escogerlo únicamente por las pruebas anteriores con BAXY habría repetido el sesgo señalado.

IFM recomienda high, T0.6/p0.95 para0.9 y T1/p0.95 para3.7, con32768tokens de margen; low/medium sacrifican precisión y no son su receta de evaluación. Aquí se rotulan como perfiles prácticos. [K2 pequeño](https://huggingface.co/IFM/K2-Horizon-0.9B), [K2 grande](https://huggingface.co/IFM/K2-Horizon-3.7B).

Qwen2507 es no-thinking; su tarjeta no requiere enable_thinking=false y recomienda su propio muestreo. La referencia usaT0.7/p0.8/k20/minp0 y el práctico conserva ese muestreo. [Ficha Qwen](https://huggingface.co/Qwen/Qwen3-4B-Instruct-2507).

Los resultados pertenecen a los perfiles locales medidos: K2 pequeño BF16, grandes Q4_K_M y sus backends fijados por hash. El fork llama.cpp de K2 tiene correcciones Windows/tokenizador/parser probadas; no es la ejecución BF16/SGLang/H200 validada por IFM. La paridad del tokenizador285/285 y las plantillas no acreditan paridad completa de logits o calidad con Transformers. No se atribuye automáticamente al modelo original todo defecto del perfil local.

Las fichas identifican inglés para K2 grande e inglés/chino para el pequeño. Eso no prueba que no puedan responder español; sí obliga a medirlo directamente antes de elegirlos para un producto que prioriza español. [K2 grande](https://huggingface.co/IFM/K2-Horizon-3.7B), [K2 pequeño](https://huggingface.co/IFM/K2-Horizon-0.9B).

**Finales ausentes y cortes:**

- K2 0.9 BF16 high · referencia: knowledge-08 (length, 511.109s), context-06 (stop, 4.328s)
- Qwen Q4 · referencia: ninguno.
- K2 3.7 Q4 high · referencia: ninguno.
- Qwen Q4 · GPU 8k: ninguno.
- K2 3.7 Q4 low · GPU 8k: facts-17 (stop, 0.750s)
- K2 3.7 Q4 high · GPU 8k: ninguno.

**Comparaciones por la misma pregunta:**

- 37-q4-high-practical699 frente a qwen-q4-practical699: 6 mejoras, 8 regresiones, 4 fallos compartidos. IDs en SUMMARY699.json.
- 37-q4-high-practical699 frente a 37-q4-low-practical699: 16 mejoras, 6 regresiones, 6 fallos compartidos. IDs en SUMMARY699.json.

No hay ganador universal por una diferencia de uno o dos casos. Las discrepancias interpretativas con el segundo lector están escritas: Qwen referencia/práctico39–40, K2 low27–28 según los fronterizos; la tabla usa el criterio final documentado del revisor principal. Una apertura correcta seguida de hechos materialmente falsos falla. Se toleran redacción torpe y alternativas que no cambian el significado; no se exigen frases literales.

**Entradas, respuestas y decisiones completas:**

- [K2 0.9 BF16 high · referencia](run-09-bf16-high-reference699/RESPUESTAS.md)
- [Qwen Q4 · referencia](run-qwen-q4-reference699/RESPUESTAS.md)
- [K2 3.7 Q4 high · referencia](run-37-q4-high-reference699/RESPUESTAS.md)
- [Qwen Q4 · GPU 8k](run-qwen-q4-practical699/RESPUESTAS.md)
- [K2 3.7 Q4 low · GPU 8k](run-37-q4-low-practical699/RESPUESTAS.md)
- [K2 3.7 Q4 high · GPU 8k](run-37-q4-high-practical699/RESPUESTAS.md)

El contraste700 conserva las herramientas e historias y quita exactamente un mensaje system sobre los mismos 20 selectores previos. Mide ese mensaje, no todas las capas del producto. Consulta su informe para la conclusión conjunta. C03 y la encuesta continúan en 26 cubiertos / 716 abiertos / 0 no aplicables; estos controles no conceden cobertura.
