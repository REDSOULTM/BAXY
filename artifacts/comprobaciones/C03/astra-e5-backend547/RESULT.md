# astra-e5-backend547

Primera comparación secuencial del mismo E5 sobre742 entradas de encuesta. Torch848,918MiB; ONNX FP32833,344MiB; INT8494,547MiB. Diagnóstico de throughput, no latencia de producto. FP32 mínimo coseno0,998346; cero cambios de vecino del banco congelado. INT8 cambia108 vecinos, sin que ese banco tenga autoridad de ejecución.548 identifica exactamente dos diferencias de tokenización(H0166/H0704): AutoTokenizer agrega WhitespaceSplit y modifica el normalizador del tokenizer.json; se exporta su backend efectivo.549 corrige esta diferencia sin cambiar modelo ni corpus. No adoptar desde547.

Fuentes: [eficiencia de Sentence Transformers](https://www.sbert.net/docs/sentence_transformer/usage/efficiency.html), [cuantización ORT](https://onnxruntime.ai/docs/performance/model-optimizations/quantization.html).
