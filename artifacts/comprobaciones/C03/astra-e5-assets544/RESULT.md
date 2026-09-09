# E5 ONNX544 — adquisición verificada

Se descargaron los dos grafos oficiales del mismo checkpoint614241f622f53c4eeff9890bdc4f31cfecc418b3: FP32(470268510bytes) e INT8(118346824bytes). Tamaños y SHA256 coinciden con los objetos LFS del autor. Permanecen en D:/BAXYRuntime/experiments/models/e5-onnx-614241f6; no se añadió nada al snapshot E5 firmado de10 archivos.

El modelo generador, runtime registrado, encoder de producción y cachés siguen intactos. Falta comparar valores, ranking, RAM y latencia. El grafo INT8 publicado lleva perfil AVX512_VNNI; no se presupone que sea la mejor configuración para Ryzen AVX2 ni se descarta cuantización por ese perfil. Fuentes primarias, límites e hipótesis enPREREG.json. Sólo se solicitaron assets públicos: ninguna conversación salió del PC.
