#460 — compositor real10/11→11/11 con un dato público requerido

Once composiciones con guardas y reintentos existentes: diez útiles; el mixto
no informaba datos. El segundo intento de memory.save eliminó el identificador
interno que la guarda ya rechazaba. No se añadió ninguna guarda nueva.

Sólo en el mixto, transportar su único valor público corto por requiredFacts
existente produce una respuesta con color y secreto oculto. El contrato sigue
acotado a un valor: no obliga a copiar listas, secretos o datos largos.
No se altera representación de registros ni se afirma que todo dato sea del usuario.

11/11 en este diagnóstico del compositor, no aceptación fresca ni producto
completo. thinking Gemmapublicado/b10809 documentado; ver recursos.json.
No fuente ni runtime promovidos. Siguiente: producto privado con override
de los dos cambios propuestos, conservar controles y adjudicar todo.

## Respuestas literales

### actual437-t7 · baseline

El nombre que tengo guardado es Jordan.

Útil; 1 llamadas nativas; 3.359s.

### actual437-t4 · baseline

I found Jordan.

Útil; 1 llamadas nativas; 2.688s.

### name-marta · baseline

Marta.

Útil; 1 llamadas nativas; 2.64s.

### compound-name · baseline

Te lo tengo guardado: Ana María.

Útil; 1 llamadas nativas; 3.828s.

### third-person · baseline

Nina.

Útil; 1 llamadas nativas; 3.797s.

### two-records · baseline

Tenés guardados los nombres Jordan y Nina. Eso es lo que encontré en mi memoria privada.

Útil; 1 llamadas nativas; 4.11s.

### memory.enable · baseline

Confirmed, memory enablement is now enabled.

Útil; 1 llamadas nativas; 2.937s.

### memory.save · baseline

Confirmed, the memory has been saved.

Útil; 2 llamadas nativas; 6.235s.

### redacted-es · baseline

Tenía guardado un registro secreto, pero su valor está oculto por seguridad. Eso es todo.

Útil; 1 llamadas nativas; 2.422s.

### redacted-en · baseline

The retrieved item was labeled "secret" and its value is redacted.

Útil; 1 llamadas nativas; 4.062s.

### mixed-es · baseline

Listo, lo devolví en español.

Fallo; 1 llamadas nativas; 3.469s.

### mixed-es · single-public-value

Te mostré tus recuerdos guardados: tu color favorito es turquesa y mantuve el secreto oculto.

Útil; 1 llamadas nativas; 4.281s.
