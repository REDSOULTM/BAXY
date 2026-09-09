# 362 — contexto transportado por sus roles originales

_post_native_tool_selection reemplaza el envoltorioJSON por el diálogo saneado
y acotado en sus roles user/assistant; el mensaje actual sigue como último user
literal. System sólo contiene la instrucción propia del selector. No se añaden
prompts, descripciones ni límites nuevos. El recorte extra359 retirado sigue
retirado:362 se debe evaluar junto con él, porque359 solo regresó en producto360.

Baseline del transporte nuevo:4fail0pass0skip1,96s. Después:

`runtime Python -m pytest tests/test_turn_policy.py tests/test_compose_contract.py tests/test_llm_transport.py -q -x --tb=short`

1091pass0fail0skip5,32s. Incluye integridad del diálogo, mensaje actual único,
no mutación, roles no autorizados descartados y límites de12mensajes/6000chars.
`.\scripts\test_source_quality.ps1`: verde, build1,40s,0warnings/errors.
`git diff --check` sobre las dos fuentes modificadas: correcto. No Full.

361 aislado11/11 frente a9/11 justifica esta prueba de integración, no su aceptación.
Producto363 preparado, mismos siete pedidos/modelo360, sólo362 difiere. Registro2507
intacto; Qwen3.5 diagnóstico. El candidato final y las otras rutas siguen pendientes.
