# astra-e5-retrieval549

Comparación con tokenizador efectivo548 y PlannerCatalog real, query/passage correctos. FP32 y no-arena: equivalencia numérica(errores de componente≤1,94e-7), cero cambios de inclusión o primera operación entre742 mensajes; dos cambios de orden enH0183/H0258. RAM pico1226,387 y1225,820MiB frente a832,992MiB deTorch. No-arena no ahorra RAM en esta carga. INT8491,789MiB pero cambia206 primeras operaciones e inclusión en742/742; no significa206 errores demostrados, sí ausencia de equivalencia y de prueba de calidad suficiente. Consultas individuales calientes: Torch16–39ms, FP327–23ms, INT83–15ms; no son latencia extremo a extremo ni presupuesto UI/voz. Ningún backend adoptado.

Fuentes: [eficiencia de Sentence Transformers](https://www.sbert.net/docs/sentence_transformer/usage/efficiency.html), [cuantización ORT](https://onnxruntime.ai/docs/performance/model-optimizations/quantization.html).
