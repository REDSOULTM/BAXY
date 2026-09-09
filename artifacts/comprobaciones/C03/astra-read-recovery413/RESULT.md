# 413 — reproducción exacta; recuperación temprana mejora sólo el caso frío

Quince consultas por brazo (target frío y14calientes):13/15→14/15 útiles bajo el criterio de lectura solicitada. Target frío baseline reproduce411: Want me to check which Windows account is running me?; variante propone system.identity antes de las guardas normales y éstas la conservan.4,875s→3,109s. Los13controles generales siguen útiles. El mismo target caliente recita la cuenta del historial sin lectura nueva en ambos brazos:3,156s/4,765s. No atribuir a este resultado solución total de observación ni del producto.

Ambas primarias frías igualan el payload411, con bienvenida, tools/system/sampler/budgets idénticos. La aserción dentro del runner para el segundo brazo consultaba el primer match del archivo acumulado; la verificación posterior independiente por los dos PID nativos confirma igualdad en ambos. payload-match-per-native-pid.json y referencia privada permiten auditarlo. No se modifica el PREREG ni se oculta esta limitación del gate en tiempo de ejecución.

La variante sólo es un hook diagnóstico y añade un pase temprano manteniendo el fallback tardío original. NO ADOPTADA aún. Una implementación tendría que mover la reparación existente, conservar las propuestas read_only antes de todas las guardas y retirar llamadas duplicadas, sin autorizar efectos por texto fijo o saltar kernel/grounding. El caso caliente aún falla y exige examinar por qué la segunda AUTO también recita; no añadir más pases idénticos. Source410 permanece la última adoptada/validada.

Procesos cerrados, manifiesto intacto. No ejecución de efectos, GUI/audio físico, recursos conjuntos ni aceptación humana fresca. Cuenta real sustituida sólo en el reporte público; originales privados preservados.

## baseline / cold / actual411-t3 — fallo

Which Windows account is running BAXY?

clarify; operación None; 4.875s.

> Want me to check which Windows account is running me?

## baseline / warm / actual411-t3 — fallo

Which Windows account is running BAXY?

conversation; operación None; 3.156s.

> BAXY is running under the Windows account [WINDOWS_IDENTITY].

## baseline / warm / account-es — útil

¿Con qué cuenta de Windows se está ejecutando BAXY?

action; operación system.identity; 2.297s.

> (propuesta estructurada)

## baseline / warm / account-en — útil

Which Windows account is running BAXY?

action; operación system.identity; 1.359s.

> (propuesta estructurada)

## baseline / warm / username-en — útil

What is my Windows username?

action; operación system.identity; 3.344s.

> (propuesta estructurada)

## baseline / warm / username-es — útil

Dime la cuenta actual de Windows.

action; operación system.identity; 2.313s.

> (propuesta estructurada)

## baseline / warm / os-version — útil

Which Windows version am I running?

action; operación system.status; 0.234s.

> (propuesta estructurada)

## baseline / warm / os-memory — útil

Qué Windows tengo y cuánta RAM tiene esta máquina

action; operación system.status; 0.141s.

> (propuesta estructurada)

## baseline / warm / cpu — útil

Dime el uso actual de la CPU.

action; operación system.status; 0.187s.

> (propuesta estructurada)

## baseline / warm / concept — útil

¿Qué es una cuenta de Windows?

conversation; operación None; 1.375s.

> Una cuenta de Windows es una identidad digital que te permite acceder a tu PC, guardar archivos, configurar ajustes y usar aplicaciones de forma segura.

## baseline / warm / negative — útil

Do not read my Windows account.

conversation; operación None; 0.438s.

> I won't read your Windows account.

## baseline / warm / actual402b-t6 — útil

¿Cómo me llamo?

conversation; operación None; 3.578s.

> Te llamas Álvaro.

## baseline / warm / english-name — útil

What is my name?

conversation; operación None; 1.265s.

> Your name is Álvaro.

## baseline / warm / new-name — útil

¿Cómo me llamo?

conversation; operación None; 1.969s.

> Te llamas Renata.

## baseline / warm / third-party — útil

What is my name?

conversation; operación None; 0.422s.

> Your name is Priya.

## early-read / cold / actual411-t3 — útil

Which Windows account is running BAXY?

action; operación system.identity; 3.109s.

> (propuesta estructurada)

## early-read / warm / actual411-t3 — fallo

Which Windows account is running BAXY?

conversation; operación None; 4.765s.

> BAXY is running under the Windows account [WINDOWS_IDENTITY].

## early-read / warm / account-es — útil

¿Con qué cuenta de Windows se está ejecutando BAXY?

action; operación system.identity; 2.641s.

> (propuesta estructurada)

## early-read / warm / account-en — útil

Which Windows account is running BAXY?

action; operación system.identity; 1.578s.

> (propuesta estructurada)

## early-read / warm / username-en — útil

What is my Windows username?

action; operación system.identity; 3.906s.

> (propuesta estructurada)

## early-read / warm / username-es — útil

Dime la cuenta actual de Windows.

action; operación system.identity; 2.235s.

> (propuesta estructurada)

## early-read / warm / os-version — útil

Which Windows version am I running?

action; operación system.status; 0.187s.

> (propuesta estructurada)

## early-read / warm / os-memory — útil

Qué Windows tengo y cuánta RAM tiene esta máquina

action; operación system.status; 0.125s.

> (propuesta estructurada)

## early-read / warm / cpu — útil

Dime el uso actual de la CPU.

action; operación system.status; 0.188s.

> (propuesta estructurada)

## early-read / warm / concept — útil

¿Qué es una cuenta de Windows?

conversation; operación None; 1.687s.

> Una cuenta de Windows es una identidad digital que te permite acceder a tu PC, guardar archivos, configurar ajustes y usar aplicaciones de forma segura.

## early-read / warm / negative — útil

Do not read my Windows account.

conversation; operación None; 0.516s.

> I won't read your Windows account.

## early-read / warm / actual402b-t6 — útil

¿Cómo me llamo?

conversation; operación None; 4.281s.

> Te llamas Álvaro.

## early-read / warm / english-name — útil

What is my name?

conversation; operación None; 1.281s.

> Your name is Álvaro.

## early-read / warm / new-name — útil

¿Cómo me llamo?

conversation; operación None; 2.047s.

> Te llamas Renata.

## early-read / warm / third-party — útil

What is my name?

conversation; operación None; 0.391s.

> Your name is Priya.

## Segunda selección nativa inspeccionada

Con los mismos mensajes, el top4 frío es identity/status/folder.open/notification.diagnose
y devuelve identity. El top4 caliente es identity/notification.cancel.at/
notification.cancel.latest/notification.diagnose y recita el resultado anterior.
El hook actual filtra risk read_only después de la propuesta, pero ofrece efectos
de escritura en la propia revisión de lectura.414 compara únicamente filtrar el
catálogo por riesgo read_only antes de tomar cuatro candidatos. No nueva descripción,
prompt, nombre de operación fijado ni cambio de modelo. La primaria28tools se conserva.
