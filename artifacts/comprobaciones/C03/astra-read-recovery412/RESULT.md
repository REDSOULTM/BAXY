# 412 —15/15→15/15; no reproduce411, no adoptar recuperación temprana

Quince consultas por brazo: target frío más14casos calientes,30respuestas. Ambas versiones seleccionan identity en el target y conservan todos los controles. La variante añade llamadas y demora sin mejora útil aquí. No fuente nueva, efectos, promoción o aceptación fresca; procesos cerrados, manifiesto intacto.

La hipótesis no quedó probada: el historial reconstruido de activity omitió la bienvenida que sí recibió el modelo en411. payload-diff411.json demuestra que tools/system/sampler/budgets/campos restantes son iguales; sólo falta el primer assistant «¡Hola! Bienvenido. ¿En qué puedo ayudarte hoy?». El observador de activity se conectó después de publicarla. No llamar a412 reproducción exacta ni atribuir su éxito al hook. Mismo riesgo observado404b: para reproducir se toma el historial del payload HTTP nativo, no sólo activity.

413 corrige la procedencia del historial y exige igualdad del primer payload frío con411 antes de seguir. Reutiliza el mismo hook/control; ningún cambio del producto ni otro prompt. Conservar412 y su comparación, no ocultar la reproducción incompleta.

## baseline / cold / actual411-t3

Which Windows account is running BAXY?

action; operación system.identity; 2.422s.

> (propuesta estructurada)

## baseline / warm / actual411-t3

Which Windows account is running BAXY?

action; operación system.identity; 2.218s.

> (propuesta estructurada)

## baseline / warm / account-es

¿Con qué cuenta de Windows se está ejecutando BAXY?

action; operación system.identity; 2.344s.

> (propuesta estructurada)

## baseline / warm / account-en

Which Windows account is running BAXY?

action; operación system.identity; 1.25s.

> (propuesta estructurada)

## baseline / warm / username-en

What is my Windows username?

action; operación system.identity; 3.438s.

> (propuesta estructurada)

## baseline / warm / username-es

Dime la cuenta actual de Windows.

action; operación system.identity; 1.953s.

> (propuesta estructurada)

## baseline / warm / os-version

Which Windows version am I running?

action; operación system.status; 0.203s.

> (propuesta estructurada)

## baseline / warm / os-memory

Qué Windows tengo y cuánta RAM tiene esta máquina

action; operación system.status; 0.125s.

> (propuesta estructurada)

## baseline / warm / cpu

Dime el uso actual de la CPU.

action; operación system.status; 0.172s.

> (propuesta estructurada)

## baseline / warm / concept

¿Qué es una cuenta de Windows?

conversation; operación None; 1.422s.

> Una cuenta de Windows es una identidad digital que te permite acceder a tu PC, guardar archivos, configurar ajustes y usar aplicaciones de forma segura.

## baseline / warm / negative

Do not read my Windows account.

conversation; operación None; 0.562s.

> I won't read your Windows account.

## baseline / warm / actual402b-t6

¿Cómo me llamo?

conversation; operación None; 3.281s.

> Te llamas Álvaro.

## baseline / warm / english-name

What is my name?

conversation; operación None; 1.36s.

> Your name is Álvaro.

## baseline / warm / new-name

¿Cómo me llamo?

conversation; operación None; 1.593s.

> Te llamas Renata.

## baseline / warm / third-party

What is my name?

conversation; operación None; 0.391s.

> Your name is Priya.

## early-read / cold / actual411-t3

Which Windows account is running BAXY?

action; operación system.identity; 2.391s.

> (propuesta estructurada)

## early-read / warm / actual411-t3

Which Windows account is running BAXY?

action; operación system.identity; 2.172s.

> (propuesta estructurada)

## early-read / warm / account-es

¿Con qué cuenta de Windows se está ejecutando BAXY?

action; operación system.identity; 2.313s.

> (propuesta estructurada)

## early-read / warm / account-en

Which Windows account is running BAXY?

action; operación system.identity; 1.328s.

> (propuesta estructurada)

## early-read / warm / username-en

What is my Windows username?

action; operación system.identity; 3.765s.

> (propuesta estructurada)

## early-read / warm / username-es

Dime la cuenta actual de Windows.

action; operación system.identity; 2.25s.

> (propuesta estructurada)

## early-read / warm / os-version

Which Windows version am I running?

action; operación system.status; 0.204s.

> (propuesta estructurada)

## early-read / warm / os-memory

Qué Windows tengo y cuánta RAM tiene esta máquina

action; operación system.status; 0.14s.

> (propuesta estructurada)

## early-read / warm / cpu

Dime el uso actual de la CPU.

action; operación system.status; 0.172s.

> (propuesta estructurada)

## early-read / warm / concept

¿Qué es una cuenta de Windows?

conversation; operación None; 2.672s.

> Una cuenta de Windows es una identidad digital que te permite acceder a tu PC, guardar archivos, configurar ajustes y usar aplicaciones de forma segura.

## early-read / warm / negative

Do not read my Windows account.

conversation; operación None; 1.156s.

> I won't read your Windows account.

## early-read / warm / actual402b-t6

¿Cómo me llamo?

conversation; operación None; 4.328s.

> Te llamas Álvaro.

## early-read / warm / english-name

What is my name?

conversation; operación None; 1.266s.

> Your name is Álvaro.

## early-read / warm / new-name

¿Cómo me llamo?

conversation; operación None; 2.312s.

> Te llamas Renata.

## early-read / warm / third-party

What is my name?

conversation; operación None; 0.516s.

> Your name is Priya.
