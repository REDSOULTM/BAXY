# LIVE_RUNTIME_CYCLE_6_REPAIR_PLAN

Fecha: 2026-05-05

## Cambio 1/3 — Fortalecer contrato persona/arquitectura/capabilities en system prompt

- Archivo: `src/carter_v3/turn_support.py`
- Idea universal:
  - Instrucciones explícitas y generales para respuestas de identidad/arquitectura:
    - describir Carter como asistente local;
    - arquitectura por componentes reales (tools, policy, verifier, memory, modelo local);
    - evitar respuestas genéricas tipo chatbot.
  - Instrucción general de empatía técnica para dudas/frustración: reconocer preocupación y proponer pasos verificables.
- Por qué NO es hardcode:
  - no hay ramas por `user_text`;
  - no se agregan listas de apps ni frases concretas;
  - se modifica comportamiento de alto nivel del LLM, derivado del contrato de sistema.
- Tests:
  - `tests/test_runtime_persona_and_capabilities.py` (ampliar cobertura de arquitectura/capability honesty)
- Smoke cases:
  - `S05`, `S06`, `S07`
- Rollback:
  - revertir bloque de instrucciones nuevas en `build_messages`.

## Cambio 2/3 — Guardrail universal de capability honesty cuando no hay herramienta adecuada

- Archivos: `src/carter_v3/turn_support.py`, `src/carter_v3/agent.py` (mínimo)
- Idea universal:
  - reforzar salida honesta “capability missing in current tool catalog” cuando el runtime no ejecuta tools y la petición es de acción, evitando respuestas ambiguas inútiles.
- Por qué NO es hardcode:
  - se basa en ausencia/presencia de herramientas reales;
  - no usa palabras específicas de prompts.
- Tests:
  - `tests/test_runtime_no_fake_success_live_cases.py`
  - `tests/test_live_regressions_from_user_log.py` (si aplica)
- Smoke cases:
  - `S21` (y robustez general en capability-missing)
- Rollback:
  - revertir rama de fallback capability-missing.

## Cambio 3/3 — Ajuste de tests para contratos estructurales (sin literalismo)

- Archivos:
  - `tests/test_runtime_persona_and_capabilities.py`
  - `tests/test_runtime_no_fake_success_live_cases.py`
  - `tests/test_live_regressions_from_user_log.py` (solo si necesario)
- Idea universal:
  - asegurar que los asserts validen señales estructurales (localidad, arquitectura real, no fake success, capability missing honesto), no texto exacto.
- Por qué NO es hardcode:
  - no obliga frases específicas;
  - valida comportamientos contractuales.
- Smoke cases:
  - cobertura indirecta de `S05`, `S06`, `S07`, `S21`.
- Rollback:
  - revertir tests nuevos/ajustados si introducen acoplamiento.
