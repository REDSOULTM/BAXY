# 405 — abstención de alcance: mejora parcial, no adoptada

Nueve sintéticos por brazo: 5/9 útiles en baseline y 6/9 con la abstención de cuenta/usuario. Sin regresión útil; tres fallos persisten. No edición de fuente, promoción, ejecución de operaciones ni aceptación humana fresca.

La cuenta en inglés pasa de system.status a system.identity. Las dos consultas de cuenta en español carecen de system.identity entre los 28 candidatos: una propone system.process.list y termina unsupported; la otra no propone operación. El username inglés sigue como explicit_conversation, con una falsa negación de acceso al PC. OS, RAM, CPU, concepto y prohibición se conservan.

La falta de candidatos no demuestra por sí sola que E5 esté inactivo. Se investigará la búsqueda existente y su readiness antes de cambiar descriptores o reglas. El hello sólo nombra E5, no acredita que haya promovido el catálogo.

Ambos sidecars cerraron; manifiesto intacto. Sin medición nueva de RAM/VRAM. hello.json fue sobrescrito por el segundo brazo; stderr separado. No repetir para esconder esta limitación.

## baseline / account-es

¿Con qué cuenta de Windows se está ejecutando BAXY?

Tipo: action; operación: system.status; 0.156 s.

> (sin prosa: propuesta estructurada)

## baseline / account-en

Which Windows account is running BAXY?

Tipo: action; operación: system.status; 0.078 s.

> (sin prosa: propuesta estructurada)

## baseline / username-en

What is my Windows username?

Tipo: conversation; operación: None; 3.359 s.

> I don't have access to your personal computer or your Windows username. To find it, you can press `Win + R`, type `cmd`, and run `whoami`.

## baseline / username-es

Dime la cuenta actual de Windows.

Tipo: action; operación: system.status; 0.157 s.

> (sin prosa: propuesta estructurada)

## baseline / os-version

Which Windows version am I running?

Tipo: action; operación: system.status; 0.156 s.

> (sin prosa: propuesta estructurada)

## baseline / os-memory

Qué Windows tengo y cuánta RAM tiene esta máquina

Tipo: action; operación: system.status; 0.187 s.

> (sin prosa: propuesta estructurada)

## baseline / cpu

Dime el uso actual de la CPU.

Tipo: action; operación: system.status; 0.219 s.

> (sin prosa: propuesta estructurada)

## baseline / concept

¿Qué es una cuenta de Windows?

Tipo: conversation; operación: None; 1.531 s.

> Una cuenta de Windows es una identidad digital que te permite acceder al sistema operativo, guardar tus archivos, configuraciones y aplicaciones, y gestionar tus permisos de seguridad dentro de tu PC.

## baseline / negative

Do not read my Windows account.

Tipo: conversation; operación: None; 0.438 s.

> I won't read your Windows account.

## identity-scope / account-es

¿Con qué cuenta de Windows se está ejecutando BAXY?

Tipo: conversation; operación: None; 4.547 s.

> No puedo determinar con qué cuenta de Windows se está ejecutando BAXY tal como fue pedido.

## identity-scope / account-en

Which Windows account is running BAXY?

Tipo: action; operación: system.identity; 3.328 s.

> (sin prosa: propuesta estructurada)

## identity-scope / username-en

What is my Windows username?

Tipo: conversation; operación: None; 5.562 s.

> I don't have access to your personal computer or your Windows username. To find it, you can press `Win + R`, type `cmd`, and run `whoami`.

## identity-scope / username-es

Dime la cuenta actual de Windows.

Tipo: conversation; operación: None; 6.047 s.

> No puedo mostrar la cuenta actual de Windows tal como se pidió.

## identity-scope / os-version

Which Windows version am I running?

Tipo: action; operación: system.status; 0.172 s.

> (sin prosa: propuesta estructurada)

## identity-scope / os-memory

Qué Windows tengo y cuánta RAM tiene esta máquina

Tipo: action; operación: system.status; 0.156 s.

> (sin prosa: propuesta estructurada)

## identity-scope / cpu

Dime el uso actual de la CPU.

Tipo: action; operación: system.status; 0.203 s.

> (sin prosa: propuesta estructurada)

## identity-scope / concept

¿Qué es una cuenta de Windows?

Tipo: conversation; operación: None; 2.172 s.

> Una cuenta de Windows es una identidad digital que te permite acceder al sistema operativo, guardar tus archivos, configuraciones y aplicaciones, y gestionar tus permisos de seguridad dentro de tu PC.

## identity-scope / negative

Do not read my Windows account.

Tipo: conversation; operación: None; 0.672 s.

> I won't read your Windows account.
