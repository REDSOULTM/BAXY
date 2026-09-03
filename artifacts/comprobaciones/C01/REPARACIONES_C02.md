# Reparaciones mínimas de base hechas en C01 — C02 debe verificarlas

C01 no puede cerrar con Full rojo. Estas no son el trabajo de C02; C02
revalida linaje, clon limpio y sellos históricos.

| Pieza | Qué había | Qué hizo C01 | Qué debe verificar C02 |
|---|---|---|---|
| `experiments/stt_quality/evaluate_reserved_stt.py` `EXPECTED_PROGRAM_TREE_SHA256` | Pin `08300d7c…`; árbol actual `1d3a69df…` por `scripts/goal095_09512_integrate.py` posterior al sello | Re-selló al árbol medido `1d3a69df31ac1ce1a75517f3f988b25a0d701b29667c89dd015d55956889bdac` | Que el sello coincide con el árbol del clon limpio; no reescribir hashes a ciegas otra vez; campañas históricas que pinchan `08300d7c…` quedan como sellos viejos, no como expectativa del árbol actual |
| `experiments/stt_quality/audit_fresh_postweight_stt_sources.py` | Mismo pin desactualizado | Mismo re-sello | Igual |
| `tests/test_wakeword_runtime_resources.py` | Sin rastrear; exigía un único objeto `SessionOptions` para tres `InferenceSession` | Se versiona. Aserción: cada sesión queda con 1 hilo, `ORT_SEQUENTIAL` y spinning desactivado. No se cambió `src/baxy_mind/onnx_runtime.py` (eso mutaría el árbol) | Incluir el archivo en el linaje; no interpretarlo como prueba de consumo de CPU |
| `test_goal09_voice_engines.py::test_voice_engine_pcm_source_wakes_on_injected_wav` | Intermitente en Full (`open up pad please` vs `notepad`); aislado pasó | No se tocó | Reproducir en Full limpio; no bajar umbral |

No se eliminó cobertura ni se añadió skip/xfail.
