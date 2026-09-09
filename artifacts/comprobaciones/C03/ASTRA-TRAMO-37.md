# Tramo 37 — prohibiciones y cantidad de volumen

2026-09-06. C03 EN_CURSO/ACTIVE, sin bloqueo externo. Goal-c03.
El tramo anterior fue progreso: corrigió evaluación y dejó una representación
útil para integrar. Este tramo edita fuente y la mide en el producto.

## Resultado

PRUEBAS_RESTRICCIONES_INTEGRADAS_C03.md conserva **70 entradas y respuestas**:
37 de producto y 33 de sondas, con errores, controles y mensajes completos.
No son casos independientes ni reserva de aceptación. No se cambió el modelo,
registro, sampler, main ni se publicó. No hay procesos propios pendientes.

- astra-real-constraints12: ocho prohibiciones útiles sin invocaciones Core,
  lectura inicial correcta, un control sintético fallido y dos restauraciones/
  lecturas correctas. 69,06s; GPU3497,56MiB; RAM4915,48MiB; registro intacto;
  26478 terminal0. «Nunca» en el reconocimiento no se penaliza por sí solo.
- astra-real-users-constraints22: diecinueve de veinte casos conocidos útiles;
  una aclaración sobre alcance del dispositivo queda pendiente de continuidad.
  Dos restauraciones/lecturas correctas aparte. 92,08s; GPU3499,56MiB;
  RAM5082,68MiB; registro intacto; 40944 terminal0. Fecha, negación, volumen
  contextual e identidad correctos. «Turn up the volume» pregunta sólo cuánto.
- astra-air-device-followup3: sesión limpia. La respuesta del aire acierta la
  conclusión, pero añade una explicación imprecisa de H₂O/humedad. La pregunta
  de dispositivo sólo obtiene volumen/silencio. El tercer turno era una respuesta
  sintética a una aclaración que aquí NO ocurrió; no usarla como prueba de
  continuidad de la otra corrida. 66,12s; GPU3497,56MiB; RAM4865,65MiB;
  registro intacto; 17509 terminal0. La lectura de audio fue100,muted:false.

## Cambios y herencia

1. effect_intent.explicit_negative_constraint reutiliza el vocabulario existente
   _COVERAGE_ACTION_HEAD y la flexión del imperativo negativo español. Es una
   lectura conservadora para presentar prohibiciones aisladas, nunca autoridad
   de ejecución. No transforma todo prefijo «no» en prohibición; dudas,
   observaciones, compuestos y verbos no reconocidos conservan la ruta normal.
2. llm reutiliza el prompt de alcance del tramo36 en constraint_ack. Recibe el
   pedido literal y su idioma como datos. No añade decodes ni vetos por frases;
   la salida sigue siendo generada. Las instrucciones e idioma llegan una vez.
3. __main__ ya no fuerza cero efectos sólo por una negación al principio de una
   petición compuesta. Conserva explicaciones tras «no abras X; solo/just ...».
   El control sintético muestra que la primaria todavía puede perder el pedido
   positivo: no atribuir al cambio una reparación completa de esa familia.
4. La aclaración explícita existente de volumen reconoce turn up/down volume y
   raise/lower/increase/decrease sin cantidad. Conserva las guardas de negación,
   otro dispositivo y cantidad explícita. Sustituye la extracción especulativa
   de esos pedidos por la ruta que ya sabe que sólo falta amount.

Se reutiliza INVESTIGACION_MODELO_C03.md: modelo2507 no-thinking, template y
llama.cpp b9980 inspeccionados, muestreo oficial ya contrastado. La evidencia
local decide, no una receta de otra variante. No se reabre la descarga de modelos
por diferencias de estilo. Ningún cambio de instrucciones de extracción se adoptó.

## Hipótesis comprobadas y descartadas

- astra-negative-conversation-purpose:12 llamadas,7,78s. Mezclar prohibición,
  dificultad y conocimiento en un solo propósito vuelve a invertir bajar/subir
  y confunde «no sé qué es Steam». Descartado; no ampliar a todas las negaciones.
- astra-clarification-operation-ids:6 llamadas,5,09s. El formateador explícito
  ya pide sólo cantidad en tres textos reales. Retirar identificadores también
  funciona, pero no repara la ruta que producía el fallo; no se adopta.
- La traza previa t15 demuestra turn.decide55→action→arguments56. No usaba el
  formateador explícito. extract_direct_arguments solicita una pregunta por todos
  los campos requeridos y, en la sonda, inventa amount1 cuando está ausente.
  La guarda independiente posterior rechaza ese valor: no se ejecutó en producto.
- astra-direct-missing-fields:10 llamadas,8,06s. Pedir sólo datos ausentes mejora
  algunas preguntas, pero el inglés sale en español y amount1 sigue inventado.
- astra-direct-missing-language:5 llamadas,6,64s. Heredar el contrato de idioma/
  trato recupera inglés, pero vuelve a preguntar dirección. Tras dos variantes
  sin solución conjunta se cambió de hipótesis: reutilizar aclaración explícita.
  En las dos sondas, los controles con cantidades dadas conservan sus argumentos.

## Validación

Con Python registrado:

```powershell
python -m pytest tests/test_effect_intent.py tests/test_turn_policy.py tests/test_request_reading.py tests/test_compose_contract.py tests/test_c03_calendar_date.py tests/test_c03_request_preservation.py -q
```

**2804 pass,0 skips,44,64s**,17984 terminal0;
scratchpad/c03-constraint-volume-owner.log. El primer borrador tuvo un control
fuera del vocabulario («no toques»); se mantiene ahora como control negativo del
reconocedor, no como evidencia de cobertura general. Se usa «no busques» para
probar la flexión del verbo presente en el vocabulario. La siguiente tanda detectó
dos regresiones de explicación tras negación; ambas corregidas, sin relajar tests.

Ruffpassed. `scripts/test_source_quality.ps1`: **Fast verde**,98777 terminal0,
build Release0errores/0avisos; scratchpad/c03-constraint-volume-fast.log.
El Fast anterior18806 verde precedía a la ampliación de volumen; no es el cierre
de la fuente última. `git diff --check` código0. No Full ni nueva UI física.
No hay cambios.NET en este tramo; Full sobre candidato final sigue pendiente.

Sellos actuales:

- __main__.py:85897f0ace429edb8c9467622e5d72619fd3922b93a5450ac2f5885128fdb763
- llm.py:0abd502508a97c5e4022b7d1260909359389f5d303c95aa0a5a60a62777213d3
- effect_intent.py:223e0c0ae77e51c458118c555979bd66bcc48b3f81af866efbad4209f54fc786
- árbol STT:e713e12f19147a0e403525e0a6c3f0765691053ca398bb1463a2a76648395a9f
- registro:13b971b3165cc84e8d8612289a4e11b3a28b908beaa69576bf566d20a183d1ed

## Siguiente paso

Empezar por la identidad del audio, no por otro prompt: AudioStatusReceipt y
AudioStatusHandler sólo transmiten target/hash/volumen/silencio. WindowsCoreAudioPlatform
ya declara IMMDevice.OpenPropertyStore pero no lee FriendlyName. Heredar una
lectura equivalente de versiones anteriores y contrastar la documentación oficial
antes de ampliarla; conservar el hash y no exponer el identificador físico.
Esto es diagnóstico confirmado del dato ausente, no autorización para inventarlo.

Después precisión del aire, negación social con acción positiva, revisión de
procedencia/frescura y reserva100, recuperación y UI finales, recursos, contratos
posteriores afectados, Full y publicación propia fuera de main. El pool tiene742
entradas:560 con evidencia de longitud íntegra y182 por revisar; autoría humana
y exposición siguen sin certificar. No llamar reales/frescos a todos automáticamente.
