# 528 — actualizar expectativas de contratos preservados

Baseline Full526 sobre 892c506: 15 fallos de `test_c03_request_preservation.py`: tres por la procedencia de hechos añadida a conversación en512; nueve por el scope de la operación en errores anidados; tres por ese mismo scope en efectos anteriores a una cancelación.

La identidad exige no atribuir como hechos personales lo que dijo el asistente y no cambiar qué operación falló. `llm.py` conserva la operación recibida sin inferirla, y `test_operation_scope_reaches_first_composition_and_recovery` ya demuestra la regresión corregida. No se cambia producto, resultado de modelo ni sello histórico. Se actualizan tres expectativas exactas para conservar también esos contratos; siguen las aserciones de petición literal, causa, cancelación, hechos y ausencia de windowId opaco.

Validación: fichero dueño completo con pytest, seguido de ruff del fichero. No reejecutar Full por esta edición de tests. Aceptar sólo con todos sus tests verdes y sin nuevas omisiones. Los otros10fallos de Full526 se diagnostican por separado.
