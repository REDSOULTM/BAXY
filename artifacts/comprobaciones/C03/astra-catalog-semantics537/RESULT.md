# C03 — catalog-semantics537

No adoptado. Las descripciones canónicas no reparan el guardado ni la capacidad. El resultado de capacidad añade el límite no demostrado «Solo tengo acceso a la información que se me proporciona en cada interacción».

El watchdog heredado lanzó TypeError al comparar la primera lectura GPU None con3800. El proceso terminó y fue cerrado, y el muestreador registró3497,56MiB; esta corrida NO acredita vigilancia activa ni cumplimiento continuo del límite. Se corrigió la espera acotada de telemetría en538–540, sin alterar537 ni repetirlo.

Son diagnósticos nativos locales, no producto completo, UI, voz ni cobertura individual de la encuesta. No cambia la fuente120713be. Encuesta:0cubiertos/742abiertos/0no aplicables.

Recursos del servidor: GPU3497.559MiB, RAM722.238MiB, 13.375s. No es el consumo conjunto de BAXY.

## Entradas y salidas literales

### disabled-save-error — baseline

Entrada nativa:

```text
My name is Jordan. Remember my name.
situation: {"outcome": "failed", "cause": "memory disabled", "operation": "memory.save"}
Mandatory language: English. Outside literal contract items, do not introduce Spanish words such as «Listo» or «encontré».
English only. Name the failure cause in prose.
```

Respuesta:

The memory save operation failed because memory was disabled.

Fin: stop; latencia0.484s.

### disabled-save-error — catalog-description

Entrada nativa:

```text
My name is Jordan. Remember my name.
situation: {"outcome": "failed", "cause": "memory disabled", "operation": "memory.save", "operationDescription": "Guarda una memoria explícita local no secreta."}
Mandatory language: English. Outside literal contract items, do not introduce Spanish words such as «Listo» or «encontré».
English only. Name the failure cause in prose.
```

Respuesta:

The memory save operation failed because memory was disabled.

Fin: stop; latencia0.407s.

### enable-confirmation — catalog-description

Entrada nativa:

```text
My name is Jordan. Remember my name.
situation: {"kind": "confirmation", "pendingAction": {"operation": "memory.enable", "target": "private local memory"}, "cause": "memory enable", "choices": ["confirm", "cancel"]}
Mandatory language: English. Outside literal contract items, do not introduce Spanish words such as «Listo» or «encontré».
Request a decision about the pending action and its target in everyday language, so the person knows what they authorize. Ask which choice the person wants, naming every available choice explicitly in the question: confirm, cancel. Do not claim the action already happened.
Contrato literal de salida: conserva todas las acciones, palabras y hechos enumerados; no los sustituyas ni los omitas.
Acciones: (ninguna)
Palabras: confirm, cancel
Hechos: (ninguno)
```

Respuesta:

Alright, Jordan. I remember your name. We're about to enable private local memory. Should we go ahead with that, or should we cancel? Choose: confirm or cancel.

Fin: stop; latencia0.937s.

### enable-confirmation — baseline

Entrada nativa:

```text
My name is Jordan. Remember my name.
situation: {"kind": "confirmation", "pendingAction": {"operation": "memory.enable", "target": "private local memory"}, "cause": "memory enable", "choices": ["confirm", "cancel"]}
Mandatory language: English. Outside literal contract items, do not introduce Spanish words such as «Listo» or «encontré».
Request a decision about the pending action and its target in everyday language, so the person knows what they authorize. Ask which choice the person wants, naming every available choice explicitly in the question: confirm, cancel. Do not claim the action already happened.
Contrato literal de salida: conserva todas las acciones, palabras y hechos enumerados; no los sustituyas ni los omitas.
Acciones: (ninguna)
Palabras: confirm, cancel
Hechos: (ninguno)
```

Respuesta:

Alright, Jordan. I remember your name. We're about to enable private local memory. Should we go ahead with that, or should we cancel? Choose: confirm or cancel.

Fin: stop; latencia0.844s.

### enable-result — baseline

Entrada nativa:

```text
confirm
situation: {"kind": "status", "outcome": "completed", "seen": {"enabled": true, "replayed": false}, "state": "memory configuration", "operation": "memory.enable"}
Mandatory language: English. Outside literal contract items, do not introduce Spanish words such as «Listo» or «encontré».
Report the verified results. English only.
```

Respuesta:

Memory configuration enabled successfully. Operation completed.

Fin: stop; latencia0.265s.

### enable-result — catalog-description

Entrada nativa:

```text
confirm
situation: {"kind": "status", "outcome": "completed", "seen": {"enabled": true, "replayed": false}, "state": "memory configuration", "operation": "memory.enable", "operationDescription": "Habilita la memoria privada local con confirmación explícita."}
Mandatory language: English. Outside literal contract items, do not introduce Spanish words such as «Listo» or «encontré».
Report the verified results. English only.
```

Respuesta:

Memory private local enabled with explicit confirmation.

Fin: stop; latencia0.297s.

### save-result — catalog-description

Entrada nativa:

```text
confirm
situation: {"kind": "status", "outcome": "completed", "seen": {"saved": true, "corrected": false, "sensitive": false, "replayed": false}, "state": "memory updated", "operation": "memory.save", "operationDescription": "Guarda una memoria explícita local no secreta."}
Mandatory language: English. Outside literal contract items, do not introduce Spanish words such as «Listo» or «encontré».
Report the verified results. English only.
```

Respuesta:

The memory was saved successfully. No corrections were made. The operation updated the local memory state.

Fin: stop; latencia0.516s.

### save-result — baseline

Entrada nativa:

```text
confirm
situation: {"kind": "status", "outcome": "completed", "seen": {"saved": true, "corrected": false, "sensitive": false, "replayed": false}, "state": "memory updated", "operation": "memory.save"}
Mandatory language: English. Outside literal contract items, do not introduce Spanish words such as «Listo» or «encontré».
Report the verified results. English only.
```

Respuesta:

Memory saved successfully. No corrections made. Status confirmed as completed.

Fin: stop; latencia0.359s.

### app-clarification — baseline

Entrada nativa:

```text
Abre una aplicación.
situation: {"kind": "clarification", "cause": "unclear request"}
Idioma obligatorio: español. Fuera de los literales del contrato, no introduzcas palabras inglesas.
Ask one short question that disambiguates. Do not guess.
```

Respuesta:

¿De qué aplicación te refieres?

Fin: stop; latencia0.250s.

### app-clarification — catalog-description

Entrada nativa:

```text
Abre una aplicación.
situation: {"kind": "clarification", "cause": "unclear request"}
Idioma obligatorio: español. Fuera de los literales del contrato, no introduzcas palabras inglesas.
Ask one short question that disambiguates. Do not guess.
```

Respuesta:

¿De qué aplicación te refieres?

Fin: stop; latencia0.235s.

### stored-name-en — catalog-description

Entrada nativa:

```text
What name have you saved in private memory?
situation: {"kind": "status", "outcome": "completed", "seen": {"shown": 1, "total": 1, "records": [{"label": "name", "value": "Jordan"}], "replayed": false}, "state": "listed memories", "operation": "memory.recall", "operationDescription": "Recupera memorias locales visibles para la sesión actual."}
Mandatory language: English. Outside literal contract items, do not introduce Spanish words such as «Listo» or «encontré».
Report the verified results. English only.
Contrato literal de salida: conserva todas las acciones, palabras y hechos enumerados; no los sustituyas ni los omitas.
Acciones: (ninguna)
Palabras: (ninguna)
Hechos: Jordan
```

Respuesta:

Jordan

Fin: stop; latencia0.188s.

### stored-name-en — baseline

Entrada nativa:

```text
What name have you saved in private memory?
situation: {"kind": "status", "outcome": "completed", "seen": {"shown": 1, "total": 1, "records": [{"label": "name", "value": "Jordan"}], "replayed": false}, "state": "listed memories", "operation": "memory.recall"}
Mandatory language: English. Outside literal contract items, do not introduce Spanish words such as «Listo» or «encontré».
Report the verified results. English only.
Contrato literal de salida: conserva todas las acciones, palabras y hechos enumerados; no los sustituyas ni los omitas.
Acciones: (ninguna)
Palabras: (ninguna)
Hechos: Jordan
```

Respuesta:

Jordan

Fin: stop; latencia0.187s.

### stored-name-es — baseline

Entrada nativa:

```text
¿Qué nombre tienes guardado en tu memoria privada?
situation: {"kind": "status", "outcome": "completed", "seen": {"shown": 1, "total": 1, "records": [{"label": "name", "value": "Jordan"}], "replayed": false}, "state": "listed memories", "operation": "memory.recall"}
Idioma obligatorio: español. Fuera de los literales del contrato, no introduzcas palabras inglesas.
Report the verified results.
Contrato literal de salida: conserva todas las acciones, palabras y hechos enumerados; no los sustituyas ni los omitas.
Acciones: (ninguna)
Palabras: (ninguna)
Hechos: Jordan
```

Respuesta:

Jordan

Fin: stop; latencia0.188s.

### stored-name-es — catalog-description

Entrada nativa:

```text
¿Qué nombre tienes guardado en tu memoria privada?
situation: {"kind": "status", "outcome": "completed", "seen": {"shown": 1, "total": 1, "records": [{"label": "name", "value": "Jordan"}], "replayed": false}, "state": "listed memories", "operation": "memory.recall", "operationDescription": "Recupera memorias locales visibles para la sesión actual."}
Idioma obligatorio: español. Fuera de los literales del contrato, no introduzcas palabras inglesas.
Report the verified results.
Contrato literal de salida: conserva todas las acciones, palabras y hechos enumerados; no los sustituyas ni los omitas.
Acciones: (ninguna)
Palabras: (ninguna)
Hechos: Jordan
```

Respuesta:

Jordan

Fin: stop; latencia0.187s.

### progress — catalog-description

Entrada nativa:

```text
situation: {"kind": "status", "state": "reviewing the person's request"}
Idioma obligatorio: español. Fuera de los literales del contrato, no introduzcas palabras inglesas.
```

Respuesta:

Estoy revisando la solicitud del usuario. Aún no se han obtenido los resultados solicitados.

Fin: stop; latencia0.657s.

### progress — baseline

Entrada nativa:

```text
situation: {"kind": "status", "state": "reviewing the person's request"}
Idioma obligatorio: español. Fuera de los literales del contrato, no introduzcas palabras inglesas.
```

Respuesta:

Estoy revisando la solicitud del usuario. Aún no se han obtenido los resultados solicitados.

Fin: stop; latencia0.375s.

### disable-result — baseline

Entrada nativa:

```text
Desactiva la memoria privada.
situation: {"kind": "status", "outcome": "completed", "seen": {"enabled": false, "replayed": false}, "state": "memory configuration", "operation": "memory.disable"}
Idioma obligatorio: español. Fuera de los literales del contrato, no introduzcas palabras inglesas.
Report the verified results.
```

Respuesta:

La memoria privada ha sido desactivada. El estado actual indica que está deshabilitada.

Fin: stop; latencia0.437s.

### disable-result — catalog-description

Entrada nativa:

```text
Desactiva la memoria privada.
situation: {"kind": "status", "outcome": "completed", "seen": {"enabled": false, "replayed": false}, "state": "memory configuration", "operation": "memory.disable", "operationDescription": "Deshabilita nuevas lecturas y escrituras de memoria local."}
Idioma obligatorio: español. Fuera de los literales del contrato, no introduzcas palabras inglesas.
Report the verified results.
```

Respuesta:

La memoria privada ha sido desactivada. No se permiten nuevas lecturas ni escrituras en la memoria local.

Fin: stop; latencia0.688s.

### clock-result — catalog-description

Entrada nativa:

```text
Dime la hora.
situation: {"clock": "21:24", "operation": "system.time", "operationDescription": "Lee la fecha y hora actuales, la hora UTC y el desfase local mediante dos observaciones coherentes."}
Idioma obligatorio: español. Fuera de los literales del contrato, no introduzcas palabras inglesas.
Preserve the 24-hour clock, or state AM/PM when converting to 12-hour time.
State the time in clock. Do not set the clock. Do not introduce yourself. Do not describe presence.
State the time in clock.
```

Respuesta:

21:24

Fin: stop; latencia0.234s.

### clock-result — baseline

Entrada nativa:

```text
Dime la hora.
situation: {"clock": "21:24", "operation": "system.time"}
Idioma obligatorio: español. Fuera de los literales del contrato, no introduzcas palabras inglesas.
Preserve the 24-hour clock, or state AM/PM when converting to 12-hour time.
State the time in clock. Do not set the clock. Do not introduce yourself. Do not describe presence.
State the time in clock.
```

Respuesta:

21:24

Fin: stop; latencia0.266s.

### memory-capability-disabled — baseline

Entrada nativa:

```text
¿Tienes memoria local?
situation: {"kind": "status", "outcome": "completed", "seen": {"enabled": false, "totalRecords": 1, "persistentRecords": 1, "sessionRecords": 0, "temporaryRecords": 0, "maximumRecords": 512, "replayed": false}, "state": "memory status", "operation": "memory.status"}
Idioma obligatorio: español. Fuera de los literales del contrato, no introduzcas palabras inglesas.
Report the verified results.
```

Respuesta:

No, no tengo memoria local. El estado actual indica que la memoria local está deshabilitada.

Fin: stop; latencia0.468s.

### memory-capability-disabled — catalog-description

Entrada nativa:

```text
¿Tienes memoria local?
situation: {"kind": "status", "outcome": "completed", "seen": {"enabled": false, "totalRecords": 1, "persistentRecords": 1, "sessionRecords": 0, "temporaryRecords": 0, "maximumRecords": 512, "replayed": false}, "state": "memory status", "operation": "memory.status", "operationDescription": "Informa el estado y los límites de la memoria local."}
Idioma obligatorio: español. Fuera de los literales del contrato, no introduzcas palabras inglesas.
Report the verified results.
```

Respuesta:

No, no tengo memoria local activa. Solo tengo acceso a la información que se me proporciona en cada interacción.

Fin: stop; latencia0.625s.
