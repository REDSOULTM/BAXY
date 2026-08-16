# LLM_FIRST_BLOCKERS

Fecha: 2026-05-05

## Estado

No hay blockers abiertos para el cierre `LLM_FIRST_READY`.

## Riesgos no bloqueantes

| Riesgo | Estado | Mitigación |
|---|---|---|
| Emergency fallback determinístico si el LLM devuelve vacío/placeholder/`OK.` | Aceptado como safety fallback | Documentado; ruta normal llama LLM y tests verifican llamada |
| Templates en `response_composer.py` | Aceptado como scaffold interno | Tool/policy/capability final pasa por `generate_result_reply(...)` |
| Modelo local puede variar estilo/idioma | Riesgo live | `build_messages(...)`, verbalizer prompt y guards |
| Live Ollama strict no re-ejecutado en esta fase | No bloqueante para unit/smoke mock | `audit/smoke_manual_equivalent.py` cubre criterio manual-equivalent; re-ejecutar live si se requiere evidencia real |
