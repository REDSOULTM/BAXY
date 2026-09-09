# 659 — ONNX y pesos nativos coinciden

Se descargaron los pesos safetensors originales de la misma revisión y se verificó su SHA. PyTorch2.13.0+cpu/Transformers5.14.1, FP32/eval/inference_mode, atención eager y2/1hilos reproducen las31 etiquetas ONNX. Token IDs y máscara del tokenizer nativo coinciden exactamente; diferencia máxima de probabilidad0,000001848, por debajo de0,001 predefinido. La mala clasificación de658 no se explica por esos caminos de backend ni por truncamiento.

Pico RSS1006,707MiB y21,781s de proceso nativo, sin infracciones. No se presenta como perfil óptimo ni consumo conjunto del producto. Esta comprobación valida la comparación, no la calidad: el candidato sigue sin cualificar para este contrato. No se cambia el modelo de BAXY ni se introduce un juez adicional. Fuente654 y encuesta26/716/0 intactas.
