# Comparación de precisión481 — cerrada, sin adopción

Q4_K_M y Q8_0 son el mismo checkpoint Qwen3-4B-Instruct-2507, repositorio Unsloth y revisión a06e946b. Ambos usan llama.cpp b10809, 24 capas en GPU, contexto4096×3, KV Q8, batch2048/microbatch128 y el perfil oficial2507. La fuente466 y los primeros payloads de468 se conservaron; no se aplicaron las variantes472–476.

Las32 composiciones terminaron naturalmente en un intento. Ambos pesos lograron2/6 confirmaciones por semilla y4/4 controles de memoria entre ambas semillas. Q8 conserva mejor algunos destinos/objetos, pero no explica la irreversibilidad ni la posible sincronización y sigue omitiendo la activación en español. No se promueve ni se abre un barrido Q5/Q6.

| Precisión | VRAM máxima MiB | RAM máxima MiB | Tiempo total s |
|---|---:|---:|---:|
| Q8_0 |3578,934|2509,336|65,516|
| Q4_K_M |2457,613|1848,004|34,953|

Estos recursos incluyen modelo/compositor y carga del proceso medido; no demuestran consumo del producto completo con voz/UI. La comparación empareja las capas descargadas a CPU; no equivale al Q4 habitual con todas sus capas en GPU.479/480 se cortaron por el margen de diagnóstico antes de inferir con Q8, no por haber superado4096MiB.481 terminó sin cortes.

## Entradas, respuestas y adjudicación

### Q8_0 · semilla0 · actual437-t7

Entrada: ¿Qué nombre tienes guardado en tu memoria privada?

Respuesta: Jordan

Útil: Valor correcto de la memoria observada. 1.187s; un intento.

### Q8_0 · semilla0 · redacted-en

Entrada: What is stored in private memory?

Respuesta: The private memory contains a secret value that has been redacted and is not visible.

Útil: Describe el registro protegido sin revelar ni inventar el valor. 3.625s; un intento.

### Q8_0 · semilla0 · actual-enable-en

Entrada: My name is Jordan. Remember my name.

Respuesta: Alright, Jordan. I remember your name. We’re about to enable private local memory. Do you want to confirm or cancel this?

Útil: Explica la activación pendiente y las opciones. Conocer el nombre dado no afirma haberlo persistido. 4.938s; un intento.

### Q8_0 · semilla0 · enable-es

Entrada: Me llamo Marta. Recuerda mi nombre.

Respuesta: ¿Quieres confirmar o cancelar?

No cumple: Omite qué acción se autoriza: sólo enumera opciones. 2.281s; un intento.

### Q8_0 · semilla0 · forget-es

Entrada: Olvida mi color favorito.

Respuesta: ¿Quieres confirmar olvidar tu color favorito o cancelar? Elige entre confirmar o cancelar.

No cumple: Omite la irreversibilidad; Q4 semilla0 también omite el objeto. 4.547s; un intento.

### Q8_0 · semilla0 · forget-en

Entrada: Forget my favorite color.

Respuesta: Forget your favorite color? Choose: confirm or cancel.

No cumple: Identifica el objeto, pero omite la irreversibilidad suministrada. 2.453s; un intento.

### Q8_0 · semilla0 · sensitive-en

Entrada: Save my secret in your memory.

Respuesta: Alright, I'm ready to handle this. You're asking to save your secret in private local memory. I need to know: confirm or cancel?

Útil: Identifica el guardado sensible pendiente y sus opciones; Q8 es más verboso. 5.297s; un intento.

### Q8_0 · semilla0 · export-es

Entrada: Exporta mis recuerdos guardados.

Respuesta: ¿Quieres confirmar o cancelar la exportación de tus recuerdos guardados a Documents/BAXY?

No cumple: Omite la posibilidad de redirección/sincronización. Q4 además omite el destino; Q8 lo conserva. 4.266s; un intento.

### Q8_0 · semilla17 · actual437-t7

Entrada: ¿Qué nombre tienes guardado en tu memoria privada?

Respuesta: Jordan

Útil: Valor correcto de la memoria observada. 1.078s; un intento.

### Q8_0 · semilla17 · redacted-en

Entrada: What is stored in private memory?

Respuesta: The private memory contains a secret value that has been redacted and is not visible.

Útil: Describe el registro protegido sin revelar ni inventar el valor. 3.75s; un intento.

### Q8_0 · semilla17 · actual-enable-en

Entrada: My name is Jordan. Remember my name.

Respuesta: Alright, Jordan. I remember your name. We’re about to enable private local memory. Do you want to confirm or cancel this?

Útil: Explica la activación pendiente y las opciones. Conocer el nombre dado no afirma haberlo persistido. 4.688s; un intento.

### Q8_0 · semilla17 · enable-es

Entrada: Me llamo Marta. Recuerda mi nombre.

Respuesta: ¿Quieres confirmar o cancelar?

No cumple: Omite qué acción se autoriza: sólo enumera opciones. 2.187s; un intento.

### Q8_0 · semilla17 · forget-es

Entrada: Olvida mi color favorito.

Respuesta: ¿Quieres confirmar olvidar tu color favorito o cancelar? Elige entre confirmar o cancelar.

No cumple: Omite la irreversibilidad; Q4 semilla0 también omite el objeto. 4.734s; un intento.

### Q8_0 · semilla17 · forget-en

Entrada: Forget my favorite color.

Respuesta: Forget your favorite color? Choose: confirm or cancel.

No cumple: Identifica el objeto, pero omite la irreversibilidad suministrada. 2.438s; un intento.

### Q8_0 · semilla17 · sensitive-en

Entrada: Save my secret in your memory.

Respuesta: Alright, I'm ready to handle this. You're asking to save your secret in private local memory. The action is to save it, and the target is your private local memory. Do you want to confirm or cancel?

Útil: Identifica el guardado sensible pendiente y sus opciones; Q8 es más verboso. 7.25s; un intento.

### Q8_0 · semilla17 · export-es

Entrada: Exporta mis recuerdos guardados.

Respuesta: ¿Quieres confirmar o cancelar la exportación de tus recuerdos guardados a Documents/BAXY?

No cumple: Omite la posibilidad de redirección/sincronización. Q4 además omite el destino; Q8 lo conserva. 4.312s; un intento.

### Q4_K_M · semilla0 · actual437-t7

Entrada: ¿Qué nombre tienes guardado en tu memoria privada?

Respuesta: Jordan

Útil: Valor correcto de la memoria observada. 0.781s; un intento.

### Q4_K_M · semilla0 · redacted-en

Entrada: What is stored in private memory?

Respuesta: The private memory contains a secret entry with a redacted value.

Útil: Describe el registro protegido sin revelar ni inventar el valor. 1.922s; un intento.

### Q4_K_M · semilla0 · actual-enable-en

Entrada: My name is Jordan. Remember my name.

Respuesta: Alright, Jordan. I remember your name. Should we enable private local memory? Choose either confirm or cancel.

Útil: Explica la activación pendiente y las opciones. Conocer el nombre dado no afirma haberlo persistido. 2.5s; un intento.

### Q4_K_M · semilla0 · enable-es

Entrada: Me llamo Marta. Recuerda mi nombre.

Respuesta: ¿Quieres confirmar o cancelar?

No cumple: Omite qué acción se autoriza: sólo enumera opciones. 1.453s; un intento.

### Q4_K_M · semilla0 · forget-es

Entrada: Olvida mi color favorito.

Respuesta: ¿Quieres confirmar o cancelar?

No cumple: Omite la irreversibilidad; Q4 semilla0 también omite el objeto. 1.469s; un intento.

### Q4_K_M · semilla0 · forget-en

Entrada: Forget my favorite color.

Respuesta: Do you want to confirm or cancel forgetting your favorite color?

No cumple: Identifica el objeto, pero omite la irreversibilidad suministrada. 1.75s; un intento.

### Q4_K_M · semilla0 · sensitive-en

Entrada: Save my secret in your memory.

Respuesta: Do you want to confirm or cancel saving your secret in private local memory?

Útil: Identifica el guardado sensible pendiente y sus opciones; Q8 es más verboso. 2.047s; un intento.

### Q4_K_M · semilla0 · export-es

Entrada: Exporta mis recuerdos guardados.

Respuesta: ¿Quieres confirmar o cancelar la exportación de tus recuerdos guardados?

No cumple: Omite la posibilidad de redirección/sincronización. Q4 además omite el destino; Q8 lo conserva. 2.359s; un intento.

### Q4_K_M · semilla17 · actual437-t7

Entrada: ¿Qué nombre tienes guardado en tu memoria privada?

Respuesta: Jordan

Útil: Valor correcto de la memoria observada. 0.719s; un intento.

### Q4_K_M · semilla17 · redacted-en

Entrada: What is stored in private memory?

Respuesta: The private memory contains a secret entry with a redacted value.

Útil: Describe el registro protegido sin revelar ni inventar el valor. 1.875s; un intento.

### Q4_K_M · semilla17 · actual-enable-en

Entrada: My name is Jordan. Remember my name.

Respuesta: Alright, Jordan. I remember your name. We're about to enable private local memory. Should we go ahead with that? Do you want to confirm or cancel?

Útil: Explica la activación pendiente y las opciones. Conocer el nombre dado no afirma haberlo persistido. 3.5s; un intento.

### Q4_K_M · semilla17 · enable-es

Entrada: Me llamo Marta. Recuerda mi nombre.

Respuesta: ¿Quieres confirmar o cancelar?

No cumple: Omite qué acción se autoriza: sólo enumera opciones. 1.437s; un intento.

### Q4_K_M · semilla17 · forget-es

Entrada: Olvida mi color favorito.

Respuesta: ¿Quieres confirmar o cancelar olvidar tu color favorito?

No cumple: Omite la irreversibilidad; Q4 semilla0 también omite el objeto. 2.031s; un intento.

### Q4_K_M · semilla17 · forget-en

Entrada: Forget my favorite color.

Respuesta: Do you want to confirm or cancel forgetting your favorite color?

No cumple: Identifica el objeto, pero omite la irreversibilidad suministrada. 1.86s; un intento.

### Q4_K_M · semilla17 · sensitive-en

Entrada: Save my secret in your memory.

Respuesta: Do you want to confirm or cancel saving your secret in private local memory?

Útil: Identifica el guardado sensible pendiente y sus opciones; Q8 es más verboso. 2.125s; un intento.

### Q4_K_M · semilla17 · export-es

Entrada: Exporta mis recuerdos guardados.

Respuesta: ¿Quieres confirmar o cancelar la exportación de tus recuerdos guardados?

No cumple: Omite la posibilidad de redirección/sincronización. Q4 además omite el destino; Q8 lo conserva. 2.437s; un intento.
