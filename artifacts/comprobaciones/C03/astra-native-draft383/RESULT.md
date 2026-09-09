# Borrador nativo383 — fuente validada, generalización pendiente

Se conserva conversation_reply sólo de la primaria sin funciones y finish_reason stop. La autoridad sigue en la decisión tipada; __main__ separa el borrador antes de validarla y sólo lo entrega si termina en knowledge sin efectos. Chat usa initial_reply bajo sus guardas/reintentos; no guarda borradores entre turnos ni los pone en speculative_chat_handoff. No cambia prompt, modelo, sampler, ejecución ni parser privado.

- Baseline inicial:5fail3pass958deselected2,07s. Prueba de prosa sin funciones tenía un hunk en otro test; se corrigió en la preparación, no contarla como baseline rojo.
- Primer focal:4fail4pass1,86s. Detectó message no inicializado para borrador aceptado y la aserción mal ubicada. Un control español muy corto no activa la guarda de idioma existente; reemplazado por español inequívoco para comprobar esa guarda, sin tocarla. Guardas de idioma de frases muy cortas siguen como límite.
- Replay focal:9pass0skip957deselected1,32s.
- Dueñas turn_policy/compose_contract/llm_transport/request_reading/price_v8:1342pass0skip6,01s.
- Fast verde, build1,52s0warnings/0errors. Handle94587 recogidoexit0.

V8 actualiza sólo pins de __main__/llm actuales con causa documentada; seis artefactos y aritmética/veredicto intactos. Sigue sin Full.384 está ejecutando la misma población5 sin hook de sustitución; falta generalización de borradores antes de extender despacho App.
