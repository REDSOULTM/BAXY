# 359 — se retira el segundo recorte del selector nativo

El selector conserva el historial que ya saneó y acotó a12mensajes/6000caracteres.
Se elimina únicamente [-6:] de previous_dialogue_for_references_only en
_post_native_tool_selection. El catálogo, formato, roles, modelo, prompt y límites
siguen iguales. La comparación nativa358 mejora selección6/8→7/8 y conserva una
variante fallida de ambas identidades, todavía pendiente de reparar.

Baseline de transporte:2fail1pass0skip1,71s. Los casos ES/EN perdían la declaración;
el control de privacidad/límites ya pasaba. Tras la edición:

`runtime Python -m pytest tests/test_turn_policy.py tests/test_compose_contract.py tests/test_llm_transport.py -q -x --tb=short`

1091pass,0fail,0skip5,32s. Los tests comprueban que el contexto humano no desaparece,
que el mensaje actual no se duplica, que el historial no muta y sigue siendo dato
sin autoridad, con roles y tamaño limitados.

`.\scripts\test_source_quality.ps1`: verde, build1,72s,0warnings/errors. No Full.
Producto360 preparado: mismos siete pedidos/modelo/perfil aislado357; sólo359
cambia. Esta reparación no acredita aún la respuesta pública ni cierra C03.
