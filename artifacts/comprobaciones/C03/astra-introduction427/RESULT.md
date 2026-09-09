# 427 — se reproduce el error AUTO; guardia genérica descartada

El payload nativo exacto426T5 vuelve a seleccionar system.identity para
«Me llamo Álvaro.». También ocurre con Nina y Ana María. El clasificador de
acto sin catálogo devuelve no_effect en los tres; no basta para adoptarlo:
acierta9/13controles y falla aplicaciones incompletas(complete) y guardar/leer
memoria privada(no_effect). Reintroducirlo como filtro general queda descartado.
Esto coincide con la advertencia de llm._decide_turn:7215 de pérdida de lecturas
y conocimiento al reinterpretar AUTO con el clasificador antiguo. La prueba
aporta una reproducción nueva, no permiso para ignorar esos contraejemplos.

NativeAUTO usa el mismo catálogo426T5 en todas las variantes; faltan operaciones
de otros dominios, por lo que las selecciones window.active/media.status de los
controles de app/volumen no describen una recuperación normal del producto.
«No guardes mi nombre» obtiene un falso borrado en la prosa nativa: guardia0no
valida veracidad de esa prosa. No usar conteo del acto como adjudicación de frase.
No efectos reales.13pares,16,906s,GPU3175,56MiB/RAM1349,19MiB,sinviolaciones,
manifiesto intacto. No nueva fuente ni aceptación. Modelos cerrados.

428 estudia otra vía: el parser privado ya reconoce una declaración de nombre
con DeclaredNameInputPattern y separa la cláusula pública. Reutilizar ese dato
sólo si ocupa todo el mensaje, sin guardar nombre ni saltarse pedidos compuestos.
Primero composición aislada con el estado ya existente session_context_only,
frente al payload erróneo426T5. Si funciona, validar límites con nombres Unicode,
terceras personas, guardado explícito, preguntas y acciones añadidas antes de fuente.
No regex nueva por nombre ni caché de identidad ni nuevo prompt/operación.
Llama b9980 documenta tools nativas y --jinja; capacidad de formato no acredita
que AUTO elija bien el acto: https://github.com/ggml-org/llama.cpp/blob/b9980/docs/function-calling.md
Herencia inmediata: NaturalMemoryRequestParser.TryBindSaveInput/DeclaredNameInputPattern
y MainWindow.SessionContextOnly. Fuente actual425 y comportamiento418 se conservan.

- Me llamo Álvaro. — guardia ['no_effect', 'zero'], esperado no_effect.

- My name is Nina. — guardia ['no_effect', 'zero'], esperado no_effect.

- Me llamo Ana María. — guardia ['no_effect', 'zero'], esperado no_effect.

- My brother is called Omar. — guardia ['no_effect', 'zero'], esperado no_effect.

- No guardes mi nombre. — guardia ['no_effect', 'zero'], esperado no_effect.

- What is my Windows username? — guardia ['complete', 'one'], esperado complete.

- Dime la cuenta de Windows actual. — guardia ['complete', 'one'], esperado complete.

- Abre una aplicación. — guardia ['complete', 'one'], esperado not_complete.

- Open an app. — guardia ['complete', 'one'], esperado not_complete.

- Set the volume to 30. — guardia ['complete', 'one'], esperado complete.

- Me llamo César. Pon el volumen al 30. — guardia ['complete', 'one'], esperado complete.

- My name is Maya. Save my name. — guardia ['no_effect', 'zero'], esperado complete.

- What name have you saved in private memory? — guardia ['no_effect', 'zero'], esperado complete.
