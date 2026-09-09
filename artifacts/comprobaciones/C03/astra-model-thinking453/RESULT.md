# 453 — reasoning sin corte intermedio, sin solución completa

33 peticiones HTTP locales directas, un intento y timeout120s real.
Qwen3.5:5 útiles,2 fallos completos y4 censuradas al agotar3072 tokens.
Gemma base:5/11 útiles; Gemma publicado:9/11 útiles. Los cuatro agotamientos
no se adjudican como errores semánticos de respuestas completas.

Gemma publicado resuelve nombres y secretos, pero expone memory.save y en el
caso mixto sólo habla del idioma. No supera todas las condiciones. Qwen tarda
18–46s por petición y Gemma varios segundos. No se adopta thinking global
ni se amplían límites de producto. Recursos en resources.json; el arnés
sí respeta el timeout previsto, a diferencia de452.

La auditoría454 y descarga455 pudieron afectar duraciones: no es benchmark
aislado. Las respuestas y las cuatro censuras permanecen válidas como registro.
No promoción; no familia descartada globalmente.

## Respuestas finales literales

### qwen35-4b · actual437-t7

(Sin respuesta final)

censored: Agotó3072 tokens sin respuesta final; no juzgar contenido incompleto como fracaso semántico.

### qwen35-4b · actual437-t4

The name I have saved in my private memory is Jordan.

useful: Conserva datos y alcance solicitados.

### qwen35-4b · name-marta

(Sin respuesta final)

censored: Agotó3072 tokens sin respuesta final; no juzgar contenido incompleto como fracaso semántico.

### qwen35-4b · compound-name

El nombre que tengo guardado en mi memoria privada es Ana María.

useful: Conserva datos y alcance solicitados.

### qwen35-4b · third-person

Hola, el nombre de tu hermana que tengo guardado es Nina.

useful: Conserva datos y alcance solicitados.

### qwen35-4b · two-records

(Sin respuesta final)

censored: Agotó3072 tokens sin respuesta final; no juzgar contenido incompleto como fracaso semántico.

### qwen35-4b · memory.enable

Memory configuration is active. The enable operation completed successfully with no errors detected. Nothing needs replaying right now.

fail: Añade que no hace falta replay; replayed=false no prueba esa necesidad futura.

### qwen35-4b · memory.save

Confirmed. The memory has been updated and saved successfully.

useful: Conserva datos y alcance solicitados.

### qwen35-4b · redacted-es

Solo tengo un registro secreto en mi memoria privada, pero su valor aparece como redactado.

fail: Redactado no explica inequívocamente ocultamiento en español.

### qwen35-4b · redacted-en

I found one secret record in private memory, but its content is currently marked as [REDACTED].

useful: Conserva datos y alcance solicitados.

### qwen35-4b · mixed-es

(Sin respuesta final)

censored: Agotó3072 tokens sin respuesta final; no juzgar contenido incompleto como fracaso semántico.

### gemma-base · actual437-t7

Mi nombre guardado es Jordan.

fail: Nombre atribuido a BAXY.

### gemma-base · actual437-t4

I have saved the name Jordan in private memory.

useful: Conserva datos y alcance solicitados.

### gemma-base · name-marta

Mi nombre guardado es Marta.

fail: Nombre atribuido a BAXY.

### gemma-base · compound-name

Mi nombre guardado es Ana María.

fail: Nombre atribuido a BAXY.

### gemma-base · third-person

Tu hermana se llama Nina.

useful: Conserva datos y alcance solicitados.

### gemma-base · two-records

Tengo guardados los nombres Jordan y Nina.

useful: Conserva datos y alcance solicitados.

### gemma-base · memory.enable

The memory configuration operation was completed. It has been enabled.

useful: Conserva datos y alcance solicitados.

### gemma-base · memory.save

The memory save operation is completed. The memory state has been updated.

useful: Conserva datos y alcance solicitados.

### gemma-base · redacted-es

Tengo guardado un registro etiquetado como secreto.

fail: Omite la protección del valor.

### gemma-base · redacted-en

The memory recall showed a record labeled as secret.

fail: Omite la protección del valor.

### gemma-base · mixed-es

Tengo guardada tu color favorito, que es turquesa, y un secreto que está redactado.

fail: Redactado no explica inequívocamente ocultamiento en español.

### gemma-published · actual437-t7

El nombre que tengo guardado es Jordan.

useful: Conserva datos y alcance solicitados.

### gemma-published · actual437-t4

I found Jordan.

useful: Conserva datos y alcance solicitados.

### gemma-published · name-marta

Marta.

useful: Conserva datos y alcance solicitados.

### gemma-published · compound-name

Te lo tengo guardado: Ana María.

useful: Conserva datos y alcance solicitados.

### gemma-published · third-person

Nina.

useful: Conserva datos y alcance solicitados.

### gemma-published · two-records

Listo, te listo los nombres que tengo guardados: Jordan y Nina.

useful: Conserva datos y alcance solicitados.

### gemma-published · memory.enable

Confirmed, memory enablement is now enabled.

useful: Conserva datos y alcance solicitados.

### gemma-published · memory.save

Confirmed: memory.save completed successfully and the memory was updated.

fail: Expone el identificador interno memory.save.

### gemma-published · redacted-es

Tenía guardado un registro secreto, pero su valor está oculto por seguridad. Eso es todo.

useful: Conserva datos y alcance solicitados.

### gemma-published · redacted-en

The retrieved item was labeled "secret" and its value is redacted.

useful: Conserva datos y alcance solicitados.

### gemma-published · mixed-es

Listo, lo devolví en español.

fail: Meta-respuesta sobre idioma; no informa valores ni protección.
