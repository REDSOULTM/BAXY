# K2 Horizon y BAXY

Revisión del 9 de septiembre de 2026. Alcance: documentación, implementación del backend, archivos publicados y estimación de memoria. No se han descargado pesos ni ejecutado K2 en este PC; el modelo activo de BAXY sigue intacto.

**Mi recomendación es evaluar primero K2 Horizon 0.9B.** Tiene un tamaño prometedor para reducir recursos, pero todavía debe demostrar español, uso correcto del catálogo y respuestas veraces. El 3.7B merece una prueba condicionada a un perfil de memoria distinto. Ninguno está aprobado para sustituir al modelo actual.

K2 Horizon es una familia de IFM/MBZUAI presentada el 3 de septiembre, con variantes 0.9B, 3.7B, 7B, 32B, 36B-A4B y 375B-A23B. La familia ofrece pesos abiertos; las fichas pequeñas declaran licencia Apache-2.0. El uso local encaja con la privacidad de BAXY. [Presentación de IFM](https://ifm.ai/blog/k2/), [ficha 0.9B](https://huggingface.co/IFM/K2-Horizon-0.9B), [ficha 3.7B](https://huggingface.co/IFM/K2-Horizon-3.7B).

## ¿Cabe en los 4 GB de VRAM?

**El nombre comercial no equivale a todos los parámetros almacenados.** Los metadatos publicados contabilizan 1.078.285.824 parámetros para 0.9B y 5.058.255.360 para 3.7B; en este último, la denominación describe el núcleo. Por eso calcular memoria multiplicando simplemente «3,7 mil millones × 4 bits» sería demasiado optimista. [Metadatos oficiales 0.9B](https://huggingface.co/api/models/IFM/K2-Horizon-0.9B), [metadatos oficiales 3.7B](https://huggingface.co/api/models/IFM/K2-Horizon-3.7B).

La tabla usa el tamaño exacto de GGUF publicado y estima la caché de atención del perfil actual de BAXY: tres secuencias de 4.096 tokens, 12.288 en total, con caché Q8_0. Se expresa en GiB: 1 GiB = 1.073.741.824 bytes. El presupuesto aquí es 4 GiB = 4.096 MiB, siguiendo las mediciones de C03.

| Variante | Archivo de pesos | Caché estimada | Suma orientativa pesos + caché | Valoración inicial |
|---|---:|---:|---:|---|
| 0.9B Q4_K_M | 0,620 GiB | 357 MiB | 0,969 GiB | Mayor margen; comprobar pérdida por cuantización |
| 0.9B Q8_0 | 1,070 GiB | 357 MiB | 1,418 GiB | Primer candidato práctico |
| 0.9B BF16 | 2,011 GiB | 357 MiB | 2,360 GiB | Referencia de calidad potencialmente viable |
| 3.7B Q4_K_M | 2,940 GiB | 918 MiB | 3,836 GiB | Margen insuficiente para asumir que BAXY completo cabe |
| 3.7B Q8_0 | 5,016 GiB | 918 MiB | 5,913 GiB | Supera el presupuesto con todos los pesos en GPU |

Los BF16 proceden de los repositorios de IFM; los Q4/Q8 citados son conversiones comunitarias, con procedencia y hashes archivados. Un archivo descargable no acredita una prueba de BAXY. [GGUF oficial 0.9B](https://huggingface.co/IFM/K2-Horizon-0.9B-GGUF/tree/main), [conversión 0.9B](https://huggingface.co/NANI-Nithin/K2-Horizon-0.9B-GGUF), [conversión 3.7B](https://huggingface.co/abenzerps/K2-Horizon-3.7B-GGUF).

**Estas sumas no son el consumo real ni un mínimo garantizado.** Faltan buffers de cálculo, contexto CUDA, asignaciones del backend y el resto de BAXY. El archivo también contiene metadatos y no se traduce byte por byte en VRAM residente. La caché se calcula como `2 × capas × cabezas KV × dimensión de cabeza × tokens × 34/32 bytes`, suponiendo K y V Q8_0 y atención densa convencional. Los tamaños arquitectónicos provienen de los [config oficiales 0.9B](https://huggingface.co/IFM/K2-Horizon-0.9B/resolve/main/config.json) y [3.7B](https://huggingface.co/IFM/K2-Horizon-3.7B/resolve/main/config.json). Debe confirmarse que el backend aplica ese formato de caché.

Con una sola secuencia de 4.096 tokens, 3.7B Q4 baja a unos **3,239 GiB de pesos más caché**, antes de los demás gastos. Reducir concurrencia y buffers podría hacerlo viable; trasladar capas o caché a CPU también reduce VRAM, pero aumenta RAM y puede empeorar latencia. Es una posibilidad técnica pendiente de medir.

Las variantes mayores quedan fuera de la primera tanda: tienen peor encaje inicial con 4 GiB de VRAM y los 16 GiB instalados en este PC. En las variantes de expertos, los parámetros activos no representan todos los pesos que hay que almacenar.

**BAXY seguirá usando RAM aunque el LLM quepa en VRAM.** Python, .NET, interfaz, audio y otras estructuras usan memoria del sistema. No hay evidencia para prometer una cifra de RAM de K2 ni para decir que todo BAXY puede vivir exclusivamente en VRAM.

## Compatibilidad técnica

La arquitectura de BAXY admite cambiar su mente local manteniendo el catálogo, la autorización del kernel y la verificación de los providers. Sin embargo, el cambio no consiste simplemente en elegir otro GGUF.

El runtime registrado usa llama.cpp b9980 y Qwen3-4B-Instruct-2507 Q4_K_M. K2 necesita implementación específica: IFM mantiene la rama `model/K2Horizon`; se identificó el commit `35999d101cf2233fc54f09c3c8d599da7303ce02`. [Implementación de IFM](https://github.com/MBZUAI-IFM/llama.cpp/commit/35999d101cf2233fc54f09c3c8d599da7303ce02).

Existe además un reporte abierto en llama.cpp, etiquetado como no confirmado, donde una compilación posterior falla al cargar el 0.9B por arquitectura desconocida. Es una reproducción de otro usuario en Linux/CUDA, no una medición nuestra ni prueba de que toda versión posterior falle. No encontré evidencia suficiente para declarar compatible el ejecutable actual de BAXY o recomendar una actualización genérica como solución. [Incidencia de carga](https://github.com/ggml-org/llama.cpp/issues/28361), [discusión de integración](https://github.com/ggml-org/llama.cpp/discussions/28308).

| Requisito de BAXY | Resultado de esta revisión |
|---|---|
| Inferencia local y privada | Compatible en principio mediante pesos locales |
| Windows y CUDA del PC | Falta compilar/cargar y verificar el backend específico |
| Máximo conjunto de 4 GiB | 0.9B prometedor; 3.7B condicionado; sin medición K2 |
| Español, inglés y mezcla natural | Falta evaluación de nuestras conductas e idiomas |
| Catálogo tipado y confirmación exacta | Deben conservarse; probar formato, argumentos y límites |
| Nada afirmado sin verificar | Los benchmarks externos no lo acreditan |
| Respuesta rápida y señal antes de 3 segundos de silencio | Falta medir turno completo, no sólo tokens/segundo |
| Voz, interfaz y recuperación de errores | Falta prueba integrada con los recursos conjuntos |

Cambiar el modelo tampoco crea por sí solo una operación ausente del catálogo ni corrige datos mal proyectados por el programa. Esos bloqueantes siguen teniendo su propio dueño en el código.

## Qué dicen sus resultados y cómo probarlo justamente

Los autores publican para 3.7B un 68,6 en SWE-bench Verified, frente a 41,2 de su referencia Qwen3.5-4B. En llamadas a funciones BFCL v4, los valores son 50,9 y 55,7 respectivamente, y advierten que los protocolos de las referencias pueden diferir. Por tanto, la ventaja en programación no demuestra superioridad general como mente de BAXY. Nuestro Qwen3-4B-Instruct-2507 tampoco es ese Qwen3.5 de la tabla. [Resultados 3.7B](https://huggingface.co/IFM/K2-Horizon-3.7B).

El 0.9B publica 28,0 en BFCL v4 frente a 43,6 de la referencia Qwen3.5-2B. Su atractivo principal para esta evaluación es su tamaño. No identifiqué en lo consultado una evaluación específica de órdenes de escritorio en español y spanglish que sustituya nuestras pruebas; eso no demuestra incapacidad en esos idiomas. [Resultados 0.9B](https://huggingface.co/IFM/K2-Horizon-0.9B).

| Configuración | Referencia 0.9B | Referencia 3.7B |
|---|---|---|
| Esfuerzo | `high` | `high` |
| Temperatura / top-p | 0,6 / 0,95 | 1,0 / 0,95 |
| Presupuesto de salida recomendado | Al menos 32.768 tokens | Al menos 32.768 tokens |
| Formato | Separar razonamiento y respuesta; parser K2 para herramientas | Igual |

Son las recomendaciones publicadas; permitir 32.768 tokens no obliga a generarlos todos. Los autores advierten de la pérdida de calidad al reducir esfuerzo o cortar razonamiento. Sus recetas validadas con SGLang usan BF16 y FlashAttention-3; no equivalen a una validación del fork de llama.cpp en nuestro Windows. [Perfil 0.9B](https://huggingface.co/IFM/K2-Horizon-0.9B), [perfil 3.7B](https://huggingface.co/IFM/K2-Horizon-3.7B).

BAXY utiliza actualmente razonamiento desactivado y presupuestos breves por función. Reutilizarlos sin comprobar la plantilla y el comportamiento real daría una comparación injusta. La propuesta es medir dos perfiles explícitos: una referencia fiel a los autores y un perfil interactivo optimizado para BAXY. Si este último pierde calidad, se registra la pérdida; no se rebaja el criterio para hacerlo pasar.

El perfil largo también cuesta memoria: para 3.7B, una sola secuencia de 32.768 tokens ya requiere aproximadamente 2.448 MiB de caché Q8_0, además de los pesos. Necesita aún espacio para la entrada. No cabe en 4 GiB completamente en GPU con ese Q4; un ensayo así exige registrar qué se mueve a RAM.

## Prueba propuesta y criterio de decisión

1. **Compatibilidad aislada:** fijar revisión del backend y del modelo, comprobar carga en Windows, plantilla efectiva, separación de respuesta y razonamiento, JSON estructurado, cancelación y errores. Mantener disponible el runtime registrado para volver a él.
2. **0.9B primero:** comparar BF16 o Q8 como referencia y después Q4, variando una configuración por comparación. Medir RAM, VRAM, tiempo hasta señal y respuesta completa, incluidos arranque y recuperación.
3. **Conductas completas:** tandas de al menos 50 casos o categorías enteras con variantes españolas, inglesas y mixtas; selección de operación, números, referencias, ambigüedad, límites, conversación y narración de resultados reales. Separar fallos nativos del modelo de los introducidos por BAXY.
4. **3.7B sólo si aporta una ventaja:** ensayar menor concurrencia y buffers, con el coste de RAM y latencia explícito. No descargar primero modelos grandes que no resuelvan un bloqueo relevante.
5. **Promoción únicamente con evidencia:** comprobar las ocho rutas de C03, regresiones, recursos con voz e interfaz y validación completa que corresponda. Una mejora aislada de benchmark no autoriza sustituir el modelo.

La decisión actual es **candidato de investigación, sin promoción**. No conocemos todavía su consumo real en este PC ni si mejora al Qwen registrado. El reporte deja una prueba concreta para resolverlo respetando identidad, catálogo, privacidad y presupuesto de BAXY.

## Evidencia conservada

En esta carpeta están los metadatos oficiales, configuraciones y listados de GGUF consultados. Las revisiones de pesos examinadas son `02d0da0fefe5a2f8dc3db091cad29b15c9d8e4fa` (0.9B) y `633f52ad28b17edeabd82afc61d2d13b4c59a561` (3.7B). `MEMORY_ESTIMATE.json` conserva los cálculos y `PINS.json` sus hashes de archivo. Los enlaces a `main` pueden cambiar; las copias fijadas permiten revisar esta conclusión a fecha de hoy.
