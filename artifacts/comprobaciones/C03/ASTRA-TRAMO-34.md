# Tramo 34 — conservar la consulta de fecha de extremo a extremo

2026-09-06. C03 EN_CURSO. Rama Goal-c03; sin publicación en main ni cambios de modelo.

## Causa y reparación

«y la fecha?» perdía su propósito en tres fronteras:

1. El grounding Python consideraba incompatible una consulta nominal con system.time.
   Ahora admite esa compatibilidad sin elegir una operación por la mera presencia de
   una palabra. Las fechas de reuniones/nacimientos y las negaciones siguen excluidas.
2. La App descartaba una acción system.time ya validada si no coincidía con su lista
   de frases de fast path. El veto procede de c1ebb79b; se retiró, conservando el
   reconocimiento positivo, catálogo, grounding de la mente y ejecución del kernel.
3. El selector de antecedente tomaba el eco del pedido actual al final de history.
   Ahora omite sólo ese eco y usa la petición anterior del usuario; no atribuye
   autoridad a palabras del asistente ni salta un nuevo tema del usuario.

La respuesta recibe la fecha local calculada desde el UTC y offset observados.
Python y .NET comprueban las fechas mencionadas, aceptando ISO o meses escritos
ES/EN y año opcional. Una consulta sólo de fecha no exige además decir la hora;
si la dice, debe coincidir. Se conserva también el pedido al proyectar cada paso
de una misión. No se afirma cobertura de días de semana ni de todos los formatos.

## Herencia y contraste

Se reutilizan system.time, el contrato de observación UTC/offset y el conductor.
La skill evidencia-baxy y el índice histórico orientan la búsqueda; la causa exacta
está demostrada por el blame del propietario actual y las trazas, no por testimonios.
La [documentación oficial de Qwen sobre function calling](https://qwen.readthedocs.io/en/stable/framework/function_call.html)
(consultada el 2026-09-06, procedimiento y tool results) distingue selección,
ejecución y devolución del resultado al modelo. Nuestra aplicación de ese principio
es conservar el contrato validado y sus resultados; no demuestra que toda selección
del modelo sea correcta ni justifica quitar autorización. Se hereda la investigación
del modelo y sus comparaciones del tramo33; no se promueve otro sampler/template.

## Evidencia

Las cuatro secuencias son desarrollo consumido, no muestra fresca ni 12 usuarios.
Los textos proceden de logs con referencias en CASES.json; autoría humana versus
automatización aún no resuelta. El orden de tres casos es de diagnóstico, no una
sesión histórica contigua. Se usa el runtime registrado; conductor sin ventana y
wake off: no acredita UI ni audio físico. El informe PRUEBAS_FECHA_C03.md contiene
literales y dictámenes individuales, incluidas las corridas fallidas.

- astra-real-date3: aclaración innecesaria, 56,11 s.
- astra-real-date-context3: fecha inventada 5 abril 2024; Python conserva action,
  pero shell pasa a conversation sin core.call; 58,08 s.
- astra-real-date-shell3: veto retirado, pero primaria pide aclaración; 57,09 s.
  Reutilizó el perfil c03-real-date3; el proceso/conversación sí se reinició.
- astra-real-date-final3: antecedente corregido, 3/3 aceptadas; 54,03 s,
  GPU 3497,56 MiB, RAM 4355,65 MiB, registro intacto. «Hoy es el 6 de septiembre de
  2026.» corresponde a UTC 2026-09-06T21:15:56.1281594+00:00, offset −180 minutos.

La última corrección recursiva de pasos se añadió después de esa medición y tiene
prueba de contrato propia (falló sin ella, pasa con ella). No altera el camino de
operación única medido; se debe incluir en la siguiente corrida integrada.

## Validación y continuación

131 .NET pass, 0 skips, 1m30s: PlannerAppBoundaryTests, C03FactPreservationTests,
MindShellEndToEndTests. Log scratchpad/c03-calendar-shell-owner.log; sesión5835 terminal0.
2549 Python pass, 0 skips, 48,42s: effect_intent, calendar_date, compose_contract,
turn_policy y c03_request_preservation. Log c03-calendar-final-owner.log;
sesión50091 terminal0. La corrección recursiva posterior tiene su propio log
c03-calendar-nested-owner.log: 30 pass, 0 skips, 0,59s. Ruff passed. Fast verde,
sesión43471 terminal0, log c03-calendar-fast.log; build 0 errores/avisos.
Full no ejecutado. Las corridas de producto terminaron con código0.

Faltan volumen absoluto contextual, negación de audio y revisión de conocimiento
simple (aire), antes de reservar/ejecutar los cien casos y validar producto/UI,
recuperación, recursos, contratos posteriores afectados, Full y publicación propia.
La mejora 3/3 es de este diagnóstico; no es un porcentaje de C03 ni actualiza por
sí sola el panel integrado antiguo de 17/20.
