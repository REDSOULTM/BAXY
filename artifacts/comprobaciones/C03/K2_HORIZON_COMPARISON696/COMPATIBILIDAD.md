# K2 Horizon: compatibilidad inicial comprobada

La compilación original del fork IFM `35999d101cf2233fc54f09c3c8d599da7303ce02` terminó correctamente en Windows, CUDA 13.0.88 y SM86. La carga inicial de K2 0.9B Q8 falló antes de generar por una expresión Unicode no admitida por la ruta `std::regex` de Windows. Ese intento se conserva en `smoke-q8-auto` y no cuenta como un fallo de calidad del modelo.

Se corrigió la ruta privada de pretokenización para conservar letras, marcas y controles de unión U+200C/U+200D según la expresión oficial. La siguiente carga funcionó, pero sólo coincidieron 261 de 285 casos con el tokenizador oficial. Las 24 diferencias desaparecieron al desactivar NFC en el tokenizador de referencia: la causa era la normalización NFC ausente en el backend, no una diferencia de los pesos.

Se añadió NFC mediante la API de Windows, exclusivamente para K2, antes de pretokenizar. La compilación incremental terminó con código 0. `BACKEND_BUILD_NFC.json` fija fuentes, parche y todos los DLL/EXE; `k2-unicode-nfc-windows.patch` reproduce el cambio. Es una modificación local para Windows, sin publicación al fork y sin promoción al runtime de BAXY.

El smoke `q8-nfc1` terminó con código 0 y estos resultados:

| Comprobación | Resultado |
|---|---|
| Tokenización oficial 0.9B | 285/285 secuencias de IDs idénticas; 0 diferencias |
| Dato observado en español | Devuelve 4 GiB libres, coherente con el dato entregado |
| JSON Schema en inglés | `audio.status` con argumentos vacíos, JSON válido |
| Herramienta nativa en inglés | Propone `audio_status` con `{}`; terminal `tool_calls` |
| Separación de razonamiento | `reasoning_content` separado de `content` y llamadas |
| VRAM máxima del servidor | 2285,56 MiB |
| RAM máxima del servidor | 1370,47 MiB |
| Manifiesto productivo | SHA256 idéntico antes y después |

La prueba utilizó los pesos Q8 verificados, contexto 36864, una ranura, caché KV Q8, Flash Attention, `reasoning_effort=high`, salida máxima de 32768 tokens, temperatura 0,6 y top-p 0,95. Las tres respuestas tardaron aproximadamente 0,92, 3,75 y 0,84 segundos. Es un diagnóstico pequeño del servidor aislado: no demuestra superioridad sobre Qwen ni consumo conjunto de BAXY con interfaz y voz.

La caché KV Q8 es una configuración a contrastar, no una recomendación específica de IFM. Los autores validan BF16 y FlashAttention-3 y recomiendan `high` para evaluación. Los modos `medium` y `low` son válidos, pero su uso para medir interacción breve debe declararse como un perfil experimental posterior a la referencia. [Tarjeta oficial 0.9B](https://huggingface.co/IFM/K2-Horizon-0.9B), [tarjeta oficial 3.7B](https://huggingface.co/IFM/K2-Horizon-3.7B).

El panel común de 50 peticiones está fijado en `PANEL_PLAN.json`. Sus entradas se conservarán idénticas entre candidatos; muestreo, plantilla, precisión, contexto, concurrencia y ubicación de la caché se declararán por perfil. Reutilizar un dato histórico cuando se pide una lectura nueva, inventar un efecto, emitir una herramienta incorrecta o no terminar son fallos que deben conservarse. Ninguno de estos replay nativos ejecuta efectos ni concede cobertura automática a los 742 requisitos de C03.
