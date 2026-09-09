# 525 — retirar la pregunta no mejora las lecturas de memoria

Revisión de cierre, sin repetir el experimento ya completado: nueve respuestas nativas, todas con finish_reason=stop y sin errores de transporte. Qwen3.5-4B/b10865, los mismos perfiles registrados/documentados de524; únicamente se retiró la pregunta inicial de tres payloads de lectura ya resuelta. Se conservaron hechos, idioma y contratos.

| Caso | Greedy | Documentado seed0 | Documentado seed17 |
|---|---|---|---|
| Nombre guardado, inglés | I found the memory for Jordan. | I recalled a memory about Jordan. | I recalled a memory about Jordan. |
| Nombre guardado, español | Jordan ha visto la memoria. | Jordan fue visto en un registro de memoria. | Jordan fue visto en la lista de memorias. |
| Memoria desactivada | El estado de la memoria muestra que hay un registro persistente activo y que la capacidad máxima disponible es de 512 registros. | Todo el historial se ha guardado en memoria persistente y la sesión está lista para ser usada. | El estado del sistema muestra que se han completado las operaciones de memoria y que el registro total es de 1 entrada persistente. |

Las salidas españolas confunden actor/observación y ninguna del estado comunica que la memoria está desactivada; una inventa que todo el historial está guardado. Las inglesas no justifican perder la pregunta. Se rechaza el tratamiento y no se adopta fuente ni modelo. Esto no demuestra incapacidad universal del modelo.

Sólo servidor: GPU3174,54MiB, RAM1123,73MiB,6,5s. Manifiesto intacto, sin violaciones; el servidor se cerró deliberadamente tras la prueba (exit15). No es medición de UI/voz ni aceptación fresca. Requests/responses completos permanecen en C03-native-compose-profile525-private.
