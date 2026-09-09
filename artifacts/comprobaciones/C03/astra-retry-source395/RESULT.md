# 395 — reintento con su mismo historial

LlmRuntime.chat ahora conserva presentation_history en el reintento
bounded_chat_answer: mantiene roles, hechos y correcciones, respeta la exclusión
de temas anteriores y no duplica el pedido actual. No cambia prompt, schema,
sampler, límites, guardias ni autoridad. El pin de programa actual de V8 se
actualiza por esta edición; sus seis artefactos, aritmética y veredicto no cambian.

- Focal antes de fuente: 2 failed, 1 passed, 964 deselected, 1,80s.
- Focal después de fuente: 3 passed, 0 skips, 964 deselected, 0,67s.
- `python -m pytest tests/test_turn_policy.py tests/test_compose_contract.py
  tests/test_llm_transport.py tests/test_request_reading.py
  tests/test_price_v8_veto_damage_by_cause.py -q`: 1343 passed, 0 skips, 6,00s.
- `scripts/test_source_quality.ps1`: Fast verde entero; build Release 1,52s,
  cero advertencias y errores. No Full durante reparación.

394 demuestra 2/5→4/5 más un parcial en averías sintéticas;396 confirma la
implementación real y sus payloads, con 5/5 en esa corrida. La variación de
Álvaro con payload idéntico se conserva explícita en ambos RESULT.md.
No se declara resuelto el compositor de memoria, el idioma del caso393bT4,
la ruta genérica de nombres ni el goal completo.
