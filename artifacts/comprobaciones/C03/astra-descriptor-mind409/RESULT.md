# 409 — decisiones con E5 cargado:11/13→13/13

Dos sidecars secuenciales, trece sintéticos por brazo. Mismo scope405, historia, modelo y sampler; sólo descripción system.identity exacta387 cambia. La selección mejora usernameEN/ES; cuatro consultas de cuenta eligen identity, tres recursos status, concepto/prohibición y cuatro nombres personales permanecen útiles sin operación. No regresiones útiles en estos controles.

Ambos alcanzaron recursos semánticos:24,609s y26,234s desde el observador. El español de Álvaro contiene el carácterÁ real(U+00C1), no una secuencia de escape visible. No son efectos ejecutados ni productoUI/voz/frescos. Manifiesto intacto, procesos cerrados. La consulta usernameEN fría sigue pendiente: en408 el descriptor la deja en rango20, fuera del top4 para retirar conocimiento cerrado.

Se adopta la descripción y la abstención del scope de recursos ante cuenta/usuario. Se excluyen de la versión de producto las palabras genéricas identidad/identity usadas en el hook405: la identidad de GPU pertenece a system.status. Los nuevos controles410 preservan ese alcance; no hay mapeo fijo hacia system.identity.

## baseline / account-es — útil

¿Con qué cuenta de Windows se está ejecutando BAXY?

action; operación system.identity; 2.641s.

> (propuesta estructurada)

## baseline / account-en — útil

Which Windows account is running BAXY?

action; operación system.identity; 2.406s.

> (propuesta estructurada)

## baseline / username-en — fallo

What is my Windows username?

conversation; operación None; 3.625s.

> I don't have access to your personal computer or your Windows username. To find it, you can press `Win + R`, type `cmd`, and run `whoami`.

## baseline / username-es — fallo

Dime la cuenta actual de Windows.

action; operación system.status; 2.188s.

> (propuesta estructurada)

## baseline / os-version — útil

Which Windows version am I running?

action; operación system.status; 0.14s.

> (propuesta estructurada)

## baseline / os-memory — útil

Qué Windows tengo y cuánta RAM tiene esta máquina

action; operación system.status; 0.141s.

> (propuesta estructurada)

## baseline / cpu — útil

Dime el uso actual de la CPU.

action; operación system.status; 0.203s.

> (propuesta estructurada)

## baseline / concept — útil

¿Qué es una cuenta de Windows?

conversation; operación None; 1.594s.

> Una cuenta de Windows es una identidad digital que te permite acceder al sistema operativo, guardar tus archivos, configuraciones y aplicaciones, y gestionar tus permisos de seguridad dentro de tu PC.

## baseline / negative — útil

Do not read my Windows account.

conversation; operación None; 0.484s.

> I won't read your Windows account.

## baseline / actual402b-t6 — útil

¿Cómo me llamo?

conversation; operación None; 3.438s.

> Te llamas Álvaro.

## baseline / english-name — útil

What is my name?

conversation; operación None; 1.203s.

> Your name is Álvaro.

## baseline / new-name — útil

¿Cómo me llamo?

conversation; operación None; 1.562s.

> Te llamas Renata.

## baseline / third-party — útil

What is my name?

conversation; operación None; 0.422s.

> Your name is Priya.

## descriptor / account-es — útil

¿Con qué cuenta de Windows se está ejecutando BAXY?

action; operación system.identity; 2.438s.

> (propuesta estructurada)

## descriptor / account-en — útil

Which Windows account is running BAXY?

action; operación system.identity; 2.375s.

> (propuesta estructurada)

## descriptor / username-en — útil

What is my Windows username?

action; operación system.identity; 3.641s.

> (propuesta estructurada)

## descriptor / username-es — útil

Dime la cuenta actual de Windows.

action; operación system.identity; 2.125s.

> (propuesta estructurada)

## descriptor / os-version — útil

Which Windows version am I running?

action; operación system.status; 0.187s.

> (propuesta estructurada)

## descriptor / os-memory — útil

Qué Windows tengo y cuánta RAM tiene esta máquina

action; operación system.status; 0.141s.

> (propuesta estructurada)

## descriptor / cpu — útil

Dime el uso actual de la CPU.

action; operación system.status; 0.203s.

> (propuesta estructurada)

## descriptor / concept — útil

¿Qué es una cuenta de Windows?

conversation; operación None; 1.39s.

> Una cuenta de Windows es una identidad digital que te permite acceder a tu PC, guardar archivos, configurar ajustes y usar aplicaciones de forma segura.

## descriptor / negative — útil

Do not read my Windows account.

conversation; operación None; 0.485s.

> I won't read your Windows account.

## descriptor / actual402b-t6 — útil

¿Cómo me llamo?

conversation; operación None; 3.703s.

> Te llamas Álvaro.

## descriptor / english-name — útil

What is my name?

conversation; operación None; 1.312s.

> Your name is Álvaro.

## descriptor / new-name — útil

¿Cómo me llamo?

conversation; operación None; 1.641s.

> Te llamas Renata.

## descriptor / third-party — útil

What is my name?

conversation; operación None; 0.406s.

> Your name is Priya.
