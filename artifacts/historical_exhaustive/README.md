# Evidencia exhaustiva histórica

Los archivos `runtime_fast_gate*.json` son evidencia histórica de una auditoría
determinista retirada. No representan la arquitectura vigente, no deben
regenerarse y no autorizan efectos. Su productor,
`scripts/audit_exhaustive_runtime_cases.py`, dependía de decidores por frases
que ya no forman parte de BAXY.

La auditoría exhaustiva vigente es
`scripts/run_exhaustive_runtime_model_gate.py` —o su coordinador paralelo—,
que reproduce los casos contra el sidecar y el modelo semántico reales sin
despachar operaciones al core. Sus salidas `runtime_model_gate*` son las que
deben usarse para nuevas mediciones. Esta distinción conserva los artefactos
anteriores como procedencia sin reintroducirlos como código activo.
