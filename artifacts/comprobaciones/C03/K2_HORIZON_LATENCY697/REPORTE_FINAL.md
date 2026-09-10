> **Rectificación posterior del dueño (699): la elección de modelo queda provisional.** Este documento conserva el informe histórico de pruebas condicionadas por instrucciones de BAXY. Su recomendación de retomar Qwen queda suspendida hasta aislar el modelo original. Véase [método vigente](../K2_HORIZON_NATIVE699/METODO.md).

# K2 Horizon y BAXY: velocidad, memoria y calidad real

Investigación cerrada sobre las pruebas 696–698 · equipo Windows con Ryzen 7 5800H y RTX 3060 Laptop · fuentes consultadas 9–10 de septiembre de 2026.

**Conservar Qwen como runtime actual y retomar los bloqueantes compartidos de BAXY.** K2 se descargó, compiló, corrigió y probó realmente con perfiles documentados. Tiene opciones rápidas y con menos memoria, pero ninguna ofrece una mejora suficientemente estable de calidad y latencia que justifique sustituir ahora el runtime. El diagnóstico de lentitud queda resuelto en sus causas observadas; C03 todavía no está terminado.

La sospecha sobre la lentitud tenía fundamento: el pequeño K2 sí puede generar rápido en esta máquina. El benchmark fijo midió **171–173 tokens/s en 0.9B Q8**, **unos 112 en 0.9B BF16** y **unos 72 en 3.7B Q4**. Las esperas extremas procedían de perfiles concretos: muchos tokens de razonamiento, trabajo trasladado a CPU, reservas grandes de contexto y defectos de compatibilidad. Esas causas se investigaron por separado y se conservaron también los intentos fallidos.

## La decisión para BAXY

El mejor recuento K2 fue el pequeño BF16 high: **33/50**, frente a **30/50** del Qwen registrado. Acertó 10 entradas que Qwen falló y falló 7 que Qwen acertó; dos de esas siete son el mismo fixture repetido. Sus pérdidas incluyen una secuencia de operaciones, aclaración de aplicación, cantidades GPU y conocimiento sencillo. Su mediana fue 1,33 s frente a 0,65 s, y su máximo 37,80 s frente a 2,24 s. El menor uso de memoria es atractivo, pero no compensa todavía esas regresiones para un compañero general. El 3.7B Q4 low alcanzó 32/50 en 1,11 s de mediana, con errores de identidad, estado de memoria, cifras y prosa. El 0.9B Q8 low llegó a 0,33 s y unos 1,36 GiB de VRAM, pero sólo cumplió 20/50. Medium 0.9B mejoró a 32/50, aunque tuvo dos errores de parsing y propuso cambiar una conexión cuando sólo se pedía observarla. Son conclusiones de este panel de desarrollo y backend experimental; no un descarte universal de K2 ni una aceptación de Qwen, que también necesita correcciones.

Esta es una decisión sobre los perfiles locales medidos. No demuestra una superioridad universal de una familia de modelos, ni certifica que cualquiera de ellos ya cumpla todo C03. El criterio de BAXY sigue siendo conservar calidad y resultados verificables con el menor consumo que cumpla, respetando español, inglés y mezcla natural.

## Cuánto tarda una respuesta real

Estas filas usan el mismo panel de 50 entradas: 20 selecciones de operaciones y 30 respuestas basadas en hechos o conversación. Los perfiles K2 de esta tabla ya incluyen la corrección de kwargs y delimitadores efectivos; parser 698 añade además la transición de pensamiento a herramientas documentada por SGLang.

| Perfil | Cumplen | Selección /20 | Prosa /30 | Mediana final s | Máximo s | VRAM / RAM GiB |
|---|---:|---:|---:|---:|---:|---:|
| [Qwen Q4 actual, tres ranuras](<D:/Perfil/Escritorio/ETC/Programacion/BAXY DEFINITIVO/artifacts/comprobaciones/C03/K2_HORIZON_COMPARISON696/run-qwen-registered1/ADJUDICATION.json>) | 30/50 | 7 | 23 | 0.65 | 2.24 | 3.42 / 0.71 |
| [Qwen Q4, muestreo oficial, una ranura](<D:/Perfil/Escritorio/ETC/Programacion/BAXY DEFINITIVO/artifacts/comprobaciones/C03/K2_HORIZON_COMPARISON696/run-qwen-documented1/ADJUDICATION.json>) | 29/50 | 7 | 22 | 0.69 | 2.17 | 3.10 / 0.71 |
| [K2 0.9 BF16 high, parser697](<D:/Perfil/Escritorio/ETC/Programacion/BAXY DEFINITIVO/artifacts/comprobaciones/C03/K2_HORIZON_COMPARISON696/run-09-bf16-high-practical-parser697-1/ADJUDICATION.json>) | 33/50 | 9 | 24 | 1.33 | 37.80 | 2.23 / 0.69 |
| [K2 3.7 Q4 high, parser698](<D:/Perfil/Escritorio/ETC/Programacion/BAXY DEFINITIVO/artifacts/comprobaciones/C03/K2_HORIZON_COMPARISON696/run-37-q4-high-parser698-1/ADJUDICATION.json>) | 31/50 | 10 | 21 | 3.41 | 48.45 | 3.37 / 0.79 |
| [K2 3.7 Q4 low, parser698](<D:/Perfil/Escritorio/ETC/Programacion/BAXY DEFINITIVO/artifacts/comprobaciones/C03/K2_HORIZON_COMPARISON696/run-37-q4-low-parser698-1/ADJUDICATION.json>) | 32/50 | 11 | 21 | 1.11 | 2.83 | 3.37 / 0.79 |
| [K2 3.7 Q4 medium, parser698](<D:/Perfil/Escritorio/ETC/Programacion/BAXY DEFINITIVO/artifacts/comprobaciones/C03/K2_HORIZON_COMPARISON696/run-37-q4-medium-parser698-1/ADJUDICATION.json>) | 17/50 | 9 | 8 | 1.98 | 11.16 | 3.37 / 0.78 |
| [K2 0.9 Q8 low, parser698](<D:/Perfil/Escritorio/ETC/Programacion/BAXY DEFINITIVO/artifacts/comprobaciones/C03/K2_HORIZON_COMPARISON696/run-09-q8-low-parser698-1/ADJUDICATION.json>) | 20/50 | 3 | 17 | 0.33 | 1.31 | 1.36 / 0.48 |
| [K2 0.9 Q8 medium, parser698](<D:/Perfil/Escritorio/ETC/Programacion/BAXY DEFINITIVO/artifacts/comprobaciones/C03/K2_HORIZON_COMPARISON696/run-09-q8-medium-parser698-1/ADJUDICATION.json>) | 32/50 | 12 | 20 | 1.05 | 9.03 | 1.36 / 0.47 |

Los tiempos empiezan al enviar la petición al servidor listo y terminan al recibir su resultado. Incluyen procesar el contexto, generar pensamiento, generar respuesta y transferirla por la API local. **No incluyen arrancar BAXY ni reproducir la voz.** Tampoco se equipara un token de pensamiento al momento en que el usuario recibe una respuesta útil. Los recibos `READY.json` conservan por separado la carga del servidor; `MEASUREMENTS.json` conserva primer token, primer contenido y tiempo final.

La RAM es el máximo de memoria residente del árbol del servidor. La VRAM es la memoria dedicada atribuida a ese mismo árbol mediante los contadores de Windows. No son la RAM total del PC, un incremento respecto al reposo ni el consumo conjunto de BAXY. Los picos se muestrean cada 250 ms y pueden omitir un pico más breve. 1 GiB=1024 MiB; el presupuesto del producto es 4096 MiB, aunque la GPU de pruebas tiene 6 GiB físicos.

## Por qué un modelo pequeño podía parecer tan lento

**La longitud del pensamiento importa tanto como la velocidad por token.** El perfil inicial 0.9B Q8, high y salida máxima 32768, consumió 434,06 s en una negación y agotó el presupuesto sin entregar un final completo. Un modelo puede generar rápido y aun así tardar minutos si produce miles de tokens antes de responder. La tarjeta IFM recomienda high y un presupuesto amplio para evaluación; el apéndice distingue esos ensayos de los límites que conviene medir para una aplicación. [IFM0.9](https://huggingface.co/IFM/K2-Horizon-0.9B), [apéndice técnico](https://huggingface.co/IFM/K2-Horizon-0.9B/blob/main/APPENDIX.md).

**Parte del modelo grande trabajaba fuera de la GPU.** K2 comercial 3.7B contiene aproximadamente 5,06 mil millones de parámetros incluyendo embeddings. El GGUF Q8 ocupa unos 5 GiB antes de caché y buffers. El intento con 28 capas GPU llegó a 4154,707 MiB durante la carga y se detuvo sin generar: ese perfil excede el techo. Con 24 capas y offload adicional desactivado, quedó bajo el límite, pero sus logs mostraron alrededor de 20 s de prefill y 5 tokens/s. Completó 20 selectores en 1123,47 s de servidor, y se interrumpió adaptativamente antes de los 30 casos de prosa. [Intento que excedió el techo](<D:/Perfil/Escritorio/ETC/Programacion/BAXY DEFINITIVO/artifacts/comprobaciones/C03/K2_HORIZON_COMPARISON696/run-37-q8-high-native-gpu28-1/RESOURCES.json>), [parada documentada](<D:/Perfil/Escritorio/ETC/Programacion/BAXY DEFINITIVO/artifacts/comprobaciones/C03/K2_HORIZON_COMPARISON696/run-37-q8-high-native-gpu24-noop1/OPERATOR_STOP.json>).

Esa parada no estaba preregistrada. Los 30 registros posteriores de cancelación/conexión se conservan, pero se excluyen del puntaje; no son 30 fallos del modelo. El perfil anterior también cambió offload y número de capas, por lo que no se atribuye toda la diferencia a cuantización.

**El contexto tiene coste aunque la pregunta sea corta.** Reservar 36864 tokens de caché no equivale a reservar 8192. En 3.7B Q4, mover la caché de CPU/contexto 36 k a GPU/contexto 8 k redujo el tiempo mediano observado de 10,50 a 3,91 s en aquellas corridas; la RAM residente bajó de 3,51 a 0,82 GiB, mientras la VRAM subió de 3,00 a 3,37 GiB. Cambiaron varias condiciones y el presupuesto de salida: son perfiles de despliegue, no una estimación causal aislada del efecto de cada flag.

La literatura de FlashAttention explica por qué reducir transferencias entre niveles de memoria ayuda a la atención; no promete una aceleración universal para cualquier GPU o longitud. El backend compilado ya usa FlashAttention y CUDA Graphs, de modo que no había un interruptor básico omitido que multiplicara por diez la velocidad. [FlashAttention, Dao etal.](https://arxiv.org/abs/2205.14135), [NVIDIA sobre CUDA Graphs](https://developer.nvidia.com/blog/optimizing-llama-cpp-ai-inference-with-cuda-graphs/).

## Los errores de compatibilidad que sí se corrigieron

El soporte utilizado es el fork IFM `model/K2Horizon`, commit `35999d101cf2233fc54f09c3c8d599da7303ce02`. La consulta remota no encontró una revisión posterior en esa rama. El anuncio original lo presenta como soporte preliminar y reconoce fricción de versiones en 3.7B/7B. Un reporte de otro usuario también documenta que el upstream probado no reconocía la arquitectura; ese caso es de Linux y no mide la latencia de este Windows. [Anuncio del soporte](https://github.com/ggml-org/llama.cpp/discussions/28308), [reporte de carga](https://github.com/ggml-org/llama.cpp/issues/28361).

1. **Unicode en Windows.** La expresión de división de tokens fallaba al cargar. Corregida esa incompatibilidad, aparecieron 24 discrepancias entre 285 entradas: faltaba normalización NFC. Con ambas correcciones se obtuvo 285/285 frente al tokenizer oficial para las dos tallas. La misma comprobación se repite antes de cada panel K2. Esto acredita los tokens de esas entradas; no una igualdad de logits entre llama.cpp y Transformers.
2. **Opciones de plantilla ignoradas por el analizador.** El parser analizaba la plantilla con valores por defecto aunque la petición seleccionara otro formato de herramientas. Ahora recibe los kwargs efectivos, de modo que JSON y XML se analizan según la petición real.
3. **Delimitador incorrecto para low/medium.** El historial de la plantilla renderiza pensamiento con marcas high, mientras el prefijo de la nueva generación cambia según el esfuerzo. El analizador ahora usa ese prefijo efectivo. La fuga sistemática de `think_faster` en las respuestas low quedó corregida.
4. **Transición implícita a herramientas.** La implementación oficial permite que una apertura de herramientas termine el pensamiento sin un cierre explícito previo. Se incorporó esa regla. Los cierres de esfuerzos distintos siguen sin convertirse en prosa visible: varias generaciones medium emiten cierres incompatibles y quedan registradas como fallos del perfil, sin presentar su pensamiento como respuesta. [Parser oficial SGLang](https://github.com/sgl-project/sglang/blob/main/python/sglang/srt/parser/reasoning_parser.py#L440-L491).

El último cambio tiene un caso de reproducción anterior con 36 fallos. Después: **121 tests y 4539 aserciones del autoparser; 39 tests y 210 aserciones PEG; cero fallos, excepciones y skips**. Se prueban los tres esfuerzos, prosa/XML/JSON, herramientas, delimitadores y fragmentos de streaming. El compilación Release usa CUDA 13 y SM86. Los 15 EXE/DLL están fijados individualmente: el hash del pequeño `llama-server.exe` por sí solo no identifica la implementación que vive en las DLL. [Recibo y validación del backend final](<D:/Perfil/Escritorio/ETC/Programacion/BAXY DEFINITIVO/artifacts/comprobaciones/C03/K2_HORIZON_LATENCY697/BACKEND_BUILD698.json>).

Las correcciones están en un backend experimental aislado y su parche es reproducible. El manifiesto productivo de BAXY conserva su hash. No se han trasladado automáticamente esas modificaciones al runtime de uso habitual.

## Comprobación independiente de la GPU

Se ejecutó `llama-bench` con prompt 512/generación 128, tres repeticiones, 8 hilos, batch 512/ubatch 128, capas GPU 99, FlashAttention y caché Q8. Se comparó `GGML_CUDA_GRAPH_OPT=0/1` de forma secuencial, sin dos modelos simultáneos.

| Pesos | PP 512 tokens/s, graph 0 / graph 1 | TG 128 tokens/s, graph 0 / graph 1 | VRAM pico MiB |
|---|---:|---:|---:|
| 0.9B Q8 | 5794.5 / 6231.4 | 170.77 / 173.21 | 1177.7 |
| 0.9B BF16 | 5769.0 / 5870.4 | 111.66 / 111.47 | 2067.9 |
| 3.7B Q4 | 2379.4 / 2364.1 | 72.04 / 72.10 | 2956.2 |

`GRAPH_OPT` aportó aproximadamente 1,4% en generación del pequeño Q8 y prácticamente nada en BF16/Q4. Es una optimización distinta de CUDA Graphs, que ya estaban activados. La documentación del desarrollador presenta beneficios dependientes de arquitectura/carga; los resultados en MoE y otras GPU no se pueden prometer para este modelo denso en una 3060. [Análisis CUDA del desarrollador](https://github.com/ggml-org/llama.cpp/discussions/17621).

El benchmark fijo excluye tokenización, muestreo y la conversación completa. Sus contextos efectivos son mucho menores que los 8192 reservados por el servidor, por eso sus números de memoria y velocidad son distintos. No se usa su pico de 2956 MiB para afirmar que BAXY 3.7B consume sólo esa memoria. Los logs de servidor incluyen además tasas reales de prefill/generación, y los últimos perfiles guardan el prefijo renderizado por `/apply-template` antes de inferir. [Método de llama-bench](https://github.com/ggml-org/llama.cpp/blob/master/tools/llama-bench/README.md), [mediciones locales completas](<D:/Perfil/Escritorio/ETC/Programacion/BAXY DEFINITIVO/artifacts/comprobaciones/C03/K2_HORIZON_LATENCY697/bench-fixed/RESULTS.json>).

Se investigó también `--backend-sampling`: en este fork es experimental e incompatible con el muestreador de gramática y con el de presupuesto de razonamiento. Las peticiones de herramientas usan gramática, por lo que activarlo indiscriminadamente no era una optimización válida. No se retiró esa restricción para obtener un número de velocidad mejor.

## Lo que enseñan las reproducciones de otros usuarios

La reproducción de answ_kaz, del 4 de septiembre, usa un MacBook Air M5 de 16 GB y el mismo commit IFM. Reporta unos 111 tokens/s en 0.9B Q4 y problemas de naturalidad/conocimiento y bucles con ciertos ajustes. También compara cuantización con y sin matriz de importancia. Apoya investigar tokenizer, cuantización y longitud de razonamiento; sus cifras de Metal y japonés no acreditan velocidad en Windows ni calidad en español. [Experiencia y mediciones del usuario](https://note.com/answ_kaz/n/naf5011d5ff5d).

Otra reproducción documenta el arranque local en Apple Silicon con el fork adecuado y los formatos de razonamiento; sirve para contrastar el procedimiento, no como benchmark de esta GPU. [Guía de Farshid Pirahansiah](https://pirahansiah.com/notes/docs/llm/k2-horizon-local/).

Se priorizaron código del backend, tarjetas de autores, trabajos originales y relatos con configuración reproducible. Los resultados anunciados de matemáticas o programación no sustituyen las pruebas de un compañero de escritorio que debe respetar hechos, identidad, confirmaciones y operaciones actuales. Tampoco una puntuación de perplexity equivale por sí sola a calidad de BAXY.

## Cómo se evitó una comparación injusta

Se descargaron cinco archivos verificados: 0.9 Q8/Q4/BF16 y 3.7 Q4/Q8. **0.9 Q4 sólo se descargó; no tiene evaluación aquí.** El BF16 de 0.9B del distribuidor NANI y el oficial IFM comparten el mismo objeto y SHA-256; los metadatos locales de Q8/BF16 coinciden en arquitectura, dimensiones y RoPE. Eso reduce una duda de procedencia, pero no permite atribuir toda diferencia de una semilla a la cuantización.

Para K2 0.9 se utilizó temperatura 0,6 y para 3.7 temperatura 1,0; top-p 0,95, sin recorte top-k/min-p, repetición 1 y semilla 0. High con 32768 tokens se midió como referencia; luego se midieron 8192 de contexto/4096 de salida y esfuerzos más bajos como opciones de interacción. Los niveles low/medium no se presentan como reproducción de los benchmarks high publicados. Los formatos JSON y Markdown/XML están identificados en cada preregistro. [Tarjeta3.7B](https://huggingface.co/IFM/K2-Horizon-3.7B).

Qwen tiene dos controles: su perfil registrado y otro con temperatura 0,7, top-p 0,8, top-k 20, min-p 0 y sin pensamiento, siguiendo su documentación. El segundo usa una ranura y 8192 de contexto; el actual tiene tres ranuras de 4096. El control práctico limitó salida a 4096 frente a 16384 recomendados, sin truncar respuestas. El ahorro de memoria al reducir ranuras no demuestra la misma capacidad concurrente. [Qwen3-4B-Instruct-2507](https://huggingface.co/Qwen/Qwen3-4B-Instruct-2507).

Los 50 casos se fijaron antes de inferir. Uno está repetido literalmente, por lo que hay 49 fixtures distintos; varios contienen historial y no son una muestra aleatoria de todos los usuarios. Se adjudicaron argumentos, selección, hechos y lenguaje contra el criterio de cada caso; acertar el nombre de una función no da crédito automático. La revisión es manual y no ciega, con una sola semilla. Las diferencias pequeñas no son una prueba estadística de superioridad.

El panel de selección representa una fase que propone operaciones con argumentos vacíos deliberadamente. No prueba extracción completa de argumentos, autorización del kernel ni efectos sobre el PC. Un paquete carece de la herramienta de Internet: abstenerse es el límite correcto del modelo, pero no satisface la capacidad que BAXY debe implementar. Los históricos de hardware son evidencia suministrada para prosa; reutilizarlos al pedir una lectura nueva falla el criterio de frescura.

## Todas las corridas anteriores, incluidas las fallidas

Estas filas conservan resultados de la investigación y ayudan a explicar las correcciones. Los resultados de backend 696/697 afectados por parsing **no se usan como una clasificación de capacidad intrínseca del modelo**.

| Perfil | Cumplen | Selección /20 | Prosa /30 | Mediana final s | Máximo s | VRAM / RAM GiB |
|---|---:|---:|---:|---:|---:|---:|
| [0.9 Q8 high, contexto36k, backend696](<D:/Perfil/Escritorio/ETC/Programacion/BAXY DEFINITIVO/artifacts/comprobaciones/C03/K2_HORIZON_COMPARISON696/run-q8-high-reference1/ADJUDICATION.json>) | 21/50 | 4 | 17 | 1.05 | 434.06 | 2.23 / 1.35 |
| [0.9 BF16 high, contexto36k, backend696](<D:/Perfil/Escritorio/ETC/Programacion/BAXY DEFINITIVO/artifacts/comprobaciones/C03/K2_HORIZON_COMPARISON696/run-09-bf16-high-reference1/ADJUDICATION.json>) | 32/50 | 9 | 23 | 1.58 | 37.70 | 3.10 / 2.35 |
| [3.7 Q4 high, contexto36k, KV CPU](<D:/Perfil/Escritorio/ETC/Programacion/BAXY DEFINITIVO/artifacts/comprobaciones/C03/K2_HORIZON_COMPARISON696/run-37-q4-high-cpu-kv1/ADJUDICATION.json>) | 31/50 | 9 | 22 | 10.50 | 104.62 | 3.00 / 3.51 |
| [3.7 Q4 high, contexto8k, JSON, backend696](<D:/Perfil/Escritorio/ETC/Programacion/BAXY DEFINITIVO/artifacts/comprobaciones/C03/K2_HORIZON_COMPARISON696/run-37-q4-high-gpu8k1/ADJUDICATION.json>) | 31/50 | 10 | 21 | 3.91 | 49.36 | 3.37 / 0.82 |
| [3.7 Q4 high, XML, sólo20 selectores](<D:/Perfil/Escritorio/ETC/Programacion/BAXY DEFINITIVO/artifacts/comprobaciones/C03/K2_HORIZON_COMPARISON696/run-37-q4-high-native-selectors1/ADJUDICATION.json>) | 10/20 | 10 | No medida | 1.71 | 6.91 | 3.37 / 0.79 |
| [3.7 Q8 high,24capas GPU, parcial20](<D:/Perfil/Escritorio/ETC/Programacion/BAXY DEFINITIVO/artifacts/comprobaciones/C03/K2_HORIZON_COMPARISON696/run-37-q8-high-native-gpu24-noop1/ADJUDICATION.json>) | 10/20 | 10 | No medida | 28.88 | 183.41 | 3.58 / 2.67 |
| [0.9 BF16 high, XML, sólo20 selectores](<D:/Perfil/Escritorio/ETC/Programacion/BAXY DEFINITIVO/artifacts/comprobaciones/C03/K2_HORIZON_COMPARISON696/run-09-bf16-high-native-selectors1/ADJUDICATION.json>) | 7/20 | 7 | No medida | 1.45 | 25.20 | 3.10 / 2.32 |
| [3.7 Q4 low, backend696 con etiquetas visibles](<D:/Perfil/Escritorio/ETC/Programacion/BAXY DEFINITIVO/artifacts/comprobaciones/C03/K2_HORIZON_COMPARISON696/run-37-q4-low-native-gpu8k1/ADJUDICATION.json>) | 11/50 | 11 | 0 | 1.05 | 2.77 | 3.37 / 0.80 |
| [3.7 Q4 low, parser697](<D:/Perfil/Escritorio/ETC/Programacion/BAXY DEFINITIVO/artifacts/comprobaciones/C03/K2_HORIZON_COMPARISON696/run-37-q4-low-parser697-1/ADJUDICATION.json>) | 32/50 | 11 | 21 | 0.98 | 2.50 | 3.37 / 0.81 |
| [3.7 Q4 medium, parser697](<D:/Perfil/Escritorio/ETC/Programacion/BAXY DEFINITIVO/artifacts/comprobaciones/C03/K2_HORIZON_COMPARISON696/run-37-q4-medium-parser697-1/ADJUDICATION.json>) | 8/50 | 0 | 8 | 1.79 | 9.24 | 3.37 / 0.78 |
| [0.9 Q8 medium, parser697](<D:/Perfil/Escritorio/ETC/Programacion/BAXY DEFINITIVO/artifacts/comprobaciones/C03/K2_HORIZON_COMPARISON696/run-09-q8-medium-parser697-1/ADJUDICATION.json>) | 28/50 | 8 | 20 | 0.94 | 9.91 | 1.36 / 0.47 |

En total se conservaron **860 resultados evaluables** de esas repeticiones del panel, además de smokes y el intento de carga rechazado. No son 860 mensajes únicos ni requisitos de C03 completados. [Resumen estructurado y diferencias por caso frente a Qwen](<D:/Perfil/Escritorio/ETC/Programacion/BAXY DEFINITIVO/artifacts/comprobaciones/C03/K2_HORIZON_LATENCY697/SUMMARY698.json>).

## Qué queda demostrado sobre RAM y VRAM

Varios servidores caben bajo 4 GiB. El pequeño Q8 con contexto 8 k ronda 1,36 GiB de VRAM y medio GiB de RAM residente; BF16 ronda 2,23 GiB de VRAM y 0,69 GiB de RAM. Esos ahorros se miden junto a sus fallos de calidad y no bastan para adoptarlos.

**Todavía no está demostrado el mínimo de memoria de BAXY completo con calidad suficiente.** Windows, la interfaz, Python, buffers y voz usan RAM; colocar capas de inferencia en GPU no elimina esa memoria. Incluso el benchmark con todas las capas principales en GPU conserva un buffer de embeddings en memoria host. La medición conjunta debe incluir simultáneamente las piezas que el producto mantiene activas y la latencia hasta la voz.

Para una eventual promoción K2 faltan la validación del paquete completo de DLL en el manifiesto, el ajuste del runtime a su contexto/razonamiento, argumentos y kernel reales, salidas visibles, voz y consumo conjunto. Ningún resultado nativo de este informe sustituye esas comprobaciones. El ahorro de VRAM no autoriza bajar calidad ni convertir un estado incompleto en éxito.

El diagnóstico de lentitud y la comparación aquí descrita quedan documentados. **C03 sigue activo: 26 casos cubiertos, 716 abiertos, 0 no aplicables.** La campaña no ha añadido cobertura a la encuesta. La siguiente intervención debe actuar sobre los bloqueantes compartidos de frescura, alcance y presentación de hechos, con el modelo elegido y pruebas reales de producto.

## Evidencia reproducible

- [Plan común de50casos](<D:/Perfil/Escritorio/ETC/Programacion/BAXY DEFINITIVO/artifacts/comprobaciones/C03/K2_HORIZON_COMPARISON696/PANEL_PLAN.json>): criterios anteriores a las generaciones.
- [Plan de controles finales](<D:/Perfil/Escritorio/ETC/Programacion/BAXY DEFINITIVO/artifacts/comprobaciones/C03/K2_HORIZON_LATENCY697/CONTROLS698_PLAN.json>): perfiles y ejecución secuencial.
- [Backend697](<D:/Perfil/Escritorio/ETC/Programacion/BAXY DEFINITIVO/artifacts/comprobaciones/C03/K2_HORIZON_LATENCY697/BACKEND_BUILD.json>) y [backend698](<D:/Perfil/Escritorio/ETC/Programacion/BAXY DEFINITIVO/artifacts/comprobaciones/C03/K2_HORIZON_LATENCY697/BACKEND_BUILD698.json>): parches, hashes, compilación y pruebas.
- [Métricas y adjudicaciones consolidadas](<D:/Perfil/Escritorio/ETC/Programacion/BAXY DEFINITIVO/artifacts/comprobaciones/C03/K2_HORIZON_LATENCY697/SUMMARY698.json>): resultados completos, errores y diferencias por caso.
- Los prompts, respuestas completas y logs con contexto histórico permanecen en almacenamiento local privado; la evidencia pública conserva IDs, causas y hashes.

Validación: compilación Release y suites completas dueñas del parser verdes, paridad de tokenizer, prefijos efectivos en los controles 698, recursos y manifiesto verificados por corrida. No es una aceptación integrada de BAXY ni un Full nuevo. Full 693 permanece como evidencia de la fuente anterior, sin extenderlo a este backend experimental.
