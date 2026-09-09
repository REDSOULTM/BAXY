# Tramo 35 — selección y dominio del volumen contextual

2026-09-06. C03 EN_CURSO/ACTIVE. Rama Goal-c03. Sin cambio de modelo, sampler,
template, registro, main ni publicación. El turno anterior fue progreso verificable.

## Resultado

En astra-real-volume-context6, «Ponlo a 100 ahora» tras consultar el volumen en35
elige audio.volume, extrae argumentos, ejecuta Core y verifica final100, muted:false.
Respuesta: «El volumen se puso a 100. El sonido no está silenciado.».
El siguiente «Hola, quien sos?» recibe presentación de BAXY, sin reanudar volumen.
Cuatro casos conocidos aprobados más dos de restauración/lectura, no seis casos
frescos. 63,05s; GPU3497,56MiB; RAM4672,29MiB; registro intacto; código0.

PRUEBAS_VOLUMEN_CONTEXTO_C03.md contiene las28 entradas/respuestas de dos corridas,
dictámenes, hechos y las46 respuestas brutas de los diagnósticos. Los payloads
completos se enlazan. Se conservan todos los fallos.

## Herencia, contraste y decisiones

Se reutiliza la investigación específica del tramo33 y la documentación oficial
Qwen function calling consultada en34. Distinguir herramientas con descripciones
del resultado esperado es coherente con esa documentación; decidir si ayuda exige
la comparación local. No se reabre por nombre de modelo la selección forzada,
rechazada históricamente por sus abstenciones fuera de catálogo.

astra-context-contracts:30 llamadas sobre5 textos consumidos e historial reconstruido.
28,56s; GPU3497,56MiB; registro intacto; sesión40586 terminal0.

- JSON actual elige relativo para «Ponlo a 100».
- JSON con límites heredados de _native_selection_description elige absoluto;
  conserva las otras4 decisiones. Se adopta esa presentación del catálogo sin
  mutar las descripciones/contratos autenticados ni duplicar el mecanismo.
- Native AUTO también elige absoluto, pero no lee la fecha contextual y propone
  audio.status ante «no silencies el audio». NO promovido; distinto de required.
- Contador sin historia dice multiple para una acción. Historia como mensajes
  no ofrece una solución general. Contexto en JSON separado del pedido actual
  corrige este conteo. No implica que se hayan pedido efectos en una negación.

astra-context-count-controls:16 llamadas sobre8 controles sintéticos, no uso humano
ni aceptación. 12,47s; GPU3495,56MiB; registro intacto; sesión42223 terminal0.
Conteo actual3/8; contexto separado7/8. Conserva las3 peticiones múltiples y mejora
referencias/restricción. «No cambies el volumen» sigue contado mal como one;
el contador no es quien autoriza acciones y se usa tras clasificar una propuesta.
La descripción method del prerregistro heredó el texto del primer instrumento;
los8 cases y sus marcas synthetic son la población realmente ejecutada. No se
reescribe el prerregistro después de medir.

## Fronteras corregidas

La primera integración astra-real-users-contracts22 mostró que la primaria ya
elegía audio.volume/agreed. El veto domain_grounding lo retiraba por no incluir
el sustantivo en la frase actual. No se ajustó otro prompt para tapar ese veto.

El dominio puede ahora heredar el pedido anterior del usuario ante una referencia
pronominal numérica de nivel absoluto. Usa las operaciones disponibles y exige
un antecedente de audio reconocido y compatible, sin objetivos coordinados.
El patrón abarca setters ES/EN, no una frase exacta. No fuerza una operación,
extrae argumentos ni hereda autoridad del asistente. Otro PC, mañana, otro objeto,
negación o una segunda acción quedan fuera. Data volume se excluye del audio.
Es deliberadamente acotado; no demuestra resolución general de pronombres.

Además, preguntas reconocidas de identidad/capacidad/límites marcan el protocolo
existente preserveObjective:false. El lector común reconoce el voseo «quien sos».
La identidad no se puede usar como valor de una aclaración vieja. La App no cambió.

## Corrida larga y pendientes

astra-real-users-contracts22:20 conocidos +2 de limpieza,92,09s,GPU3499,56MiB,
RAM5325,32MiB,registro intacto,código0,sesión34775 terminal0.
Es anterior a la reparación del dominio y de la identidad. La fecha se mantiene
correcta integrada. Hay6 casos no aprobados en la revisión literal actual:

- t11 afirma «Ya está bajado» sin lectura/acción.
- t15 pide dirección aunque «up» ya la especifica; preguntar cuánto sí es válido.
- t17 pide aclarar el referente de volumen; resuelto en la secuencia posterior.
- t18 reanuda volumen ante identidad; resuelto en la secuencia posterior.
- t19 no identifica de forma demostrada el dispositivo y añade hora no pedida.
- t20 afirma una transición «ya no está silenciado» sin ejecutarla.

La adjudicación antigua era demasiado permisiva con t15 y t19; esta revisión los
explicita. No comparar14/20 contra17/20 como una medida homogénea de regresión.
T11/t20 no están resueltos y no se atribuye su variación a una causa no aislada.
La explicación del aire es correcta en esta secuencia; la afirmación problemática
standalone anterior sigue como regresión pendiente, no se borra con este acierto.

## Validación y reanudación

2611 Python pass,0skip,43,60s: effect_intent,turn_policy,request_reading,
compose_contract,c03_calendar_date; sesión51130 terminal0.
140 c03_request_preservation pass,0skip,0,97s. Ruff passed.
Fast97967 terminal0; build0errores/avisos. Logs scratchpad/c03-context-final-owner.log,
c03-context-fast.log. Full no ejecutado. Todos los procesos propios terminaron.
PC: audio100,muted:false verificado al final de la misma sesión de producto.

Siguiente: representación de restricciones negativas y composición, conservando
la separación entre no ejecutar, estado observado y respuesta natural. No repetir
native AUTO, contador como historia conversacional ni descripciones ya comparadas.
LlmRuntime.chat aún trata las restricciones como knowledge; la rama negativa del
compositor existente sólo contempla no abrir una app. Investigar esa frontera,
no otro filtro de frases visibles. Después, aclaración de dirección y dispositivo,
desarrollo integrado, reserva100/procedencia, producto/UI, recuperación, recursos,
contratos posteriores afectados, Full final y publicación propia.
