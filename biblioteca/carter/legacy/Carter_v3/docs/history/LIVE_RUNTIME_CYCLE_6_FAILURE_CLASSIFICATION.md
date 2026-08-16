# LIVE_RUNTIME_CYCLE_6_FAILURE_CLASSIFICATION

Fecha: 2026-05-05  
Fuente: `LIVE_SAFE_RUNTIME_SMOKE_RESULTS_STRICT.md`

| ID | Prompt | Respuesta exacta | Motivo FAIL actual | ¿Bug de harness? | ¿Bug de runtime? | Fix permitido | Riesgo hardcode | Test requerido |
|---|---|---|---|---|---|---|---|---|
| S04 | sos iron man? | "…soy tu asistente local Carter…" | `UNMAPPED` en harness (sin oráculo asignado) | Sí | No | `HARNESS_ORACLE_MISSING` | Bajo | test del harness estricto (oráculo persona para identidad negativa) |
| S05 | cual es tu arquitectura? | "…no tengo architectural description…" | oráculo A detecta respuesta genérica sin elementos estructurales | No | Sí | `RUNTIME_PERSONA_BUG` | Medio | `tests/test_runtime_persona_and_capabilities.py` |
| S06 | puedes ver tu codigo? | "no puedo ver directamente mi código…" | respuesta niega capability local útil / muy genérica | No | Sí | `RUNTIME_CAPABILITY_BUG` | Medio | `tests/test_runtime_persona_and_capabilities.py` |
| S07 | tengo miedo de que fracasemos con Carter | respuesta empática + `UNMAPPED` | `UNMAPPED` en harness (sin oráculo asignado) | Sí | No | `HARNESS_ORACLE_MISSING` | Bajo | test del harness estricto (oráculo empatía técnica) |
| S08 | Me llamo red | "Intenté actualizar la memoria local, pero no pude confirmar…" + recall posterior correcto | evaluación write-turn aislada; debe evaluarse en par write+recall | Sí | Parcial (mensaje write mejorable) | `MEMORY_PAIR_EVALUATION_BUG` | Bajo | `tests/test_live_regressions_from_user_log.py` / memoria pair oracle |
| S21 | pausala | "No estoy seguro a cuál te refieres..." | media/capability missing no se expresa de forma honestamente específica | No | Sí | `CAPABILITY_MISSING_HONESTY_BUG` | Medio | `tests/test_runtime_no_fake_success_live_cases.py` |
| S23 | para cuando tengo una alarma? | "no puedo programar alarmas directamente..." | mission status/text todavía cae en respuesta conversacional débil para capability missing | No | Sí | `CAPABILITY_MISSING_HONESTY_BUG` | Medio | `tests/test_runtime_no_fake_success_live_cases.py` |

## Clasificación consolidada

- Harness-only:
  - `S04` -> `HARNESS_ORACLE_MISSING`
  - `S07` -> `HARNESS_ORACLE_MISSING`
  - `S08` -> `MEMORY_PAIR_EVALUATION_BUG`
- Runtime real:
  - `S05` -> `RUNTIME_PERSONA_BUG`
  - `S06` -> `RUNTIME_CAPABILITY_BUG`
  - `S21` -> `CAPABILITY_MISSING_HONESTY_BUG`
  - `S23` -> `CAPABILITY_MISSING_HONESTY_BUG`
