# 1011 — aclarar el objeto sin intercambiar roles

Base: c42ddbe02f07ce38949a1f9cbb9df6a87ff04234. Worktree: `C:/Users/usuario/AppData/Local/BAXY/C03-deictic1011-worktree`, rama codex/c03-deictic1011. Único archivo: src/baxy_mind/llm.py.

1009 confirma el enrutamiento corregido: H0216/H0531/H0534 y variante EN (índices0/1/2/5; t1/t2/t3/t6; requests8/13/18/34) terminan deictic_referent_clarification con cero efectos. Sin composición de aclaración intermedia, publican respectivamente «¿Puedes abrir este?», «¿qué abriste?», «¿Puedes abrir este?» y «Can you open that one for me?». La primera pérdida está en la pregunta generada y aceptada, no en selección unsupported, provider o transporte.
El lector de clarify_missing_referent valida JSON/question, puntuación, igualdad literal e información interna; eso no distingue una pregunta por el objeto de una orden interrogativa o un intercambio de sujeto/tiempo. No se captura aquí el JSON crudo del helper, por lo que su aceptación se establece por el flujo y el audit, sin inventar el contenido completo de respuesta.
H0619/t4 sí tiene compose clarification publicado; su final útil no se atribuye directamente a la misma generación. La variante ES/t5 tiene final útil. No se amplía el diagnóstico a los límites.

Se sustituye únicamente el párrafo del system prompt del helper: BAXY realiza la acción ya solicitada; el usuario identifica el objeto faltante; la acción todavía no ocurrió. Pide el dato, sin asumir tipo de objeto, repetir la orden como pregunta, reconfirmar intención, encargar ejecución al usuario o preguntar por una acción pasada.
No hay ejemplo de respuesta visible, vocabulario literal de casos, nuevo veto, operación, modelo, backend, parámetros ni presupuesto. Idioma/trato, estructura de mensajes, schema y verificadores permanecen intactos. No se atribuye causalidad a la plantilla ni a la separación de system messages.
Revisión manual y git diff --check limpios. Sin tests/imports/AST/build/GPU/producto por instrucción explícita. Eficacia funcional y créditos pendientes de raíz.

Evidencia SHA256, en `C:/Users/usuario/AppData/Local/BAXY/C03-deictic1009-private/run/`:
- turn-audit.jsonl: 21e6eec6cf56e4cc417b5a4cbb48addfb44ab3cf0f78173537c48a4cf1cb2a75.
- shell-trace.jsonl: 46089909d5f48f008ea3d11cfc3035329dcfa95edb9114e1fde8585009b2e350.
- compose-audit.jsonl: 964b2db1588c090182f4974c0f1f27762ac79de07ea53e7b05512307e1a0868e.
- capture/events.jsonl: 2b8bcad3cfd702dc0f211a51e7bfab2889fd13d8349d5db1ce95e10f6f9c3bf7.
