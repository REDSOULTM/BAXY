# 407 — promoción funciona; ventana lexical inicial y dos fallos posteriores

Arranque completo real: snapshot lexical1,250s; E5 ready20,766s; corpus cache25156 listo20,984s; recursos semánticos24,438s. No se demostró bloqueo permanente ni agotamiento185s. No cambiar timeout ni ordenar de nuevo el arranque con esa hipótesis refutada.

Misma abstención de alcance405, esperando la promoción:7/9 útiles (405 frío6/9). Ambas accountES/EN seleccionan system.identity; usernameEN sigue explicit_conversation con falsa negación de acceso, usernameES selecciona system.status. OS/RAM/CPU/concepto/prohibición conservados. Todos los audits ahora semantic.

Sin efectos ni edición de fuente/promoción de runtime. Sin UI/audio físico ni nuevo perfil de recursos. Manifiesto intacto; procesos cerrados. Evidencia completa de drafts privada. La espera sólo es un método diagnóstico; no se añade al producto.

## account-es

¿Con qué cuenta de Windows se está ejecutando BAXY?

action; operación system.identity; 2.594s.

> (propuesta estructurada)

## account-en

Which Windows account is running BAXY?

action; operación system.identity; 2.703s.

> (propuesta estructurada)

## username-en

What is my Windows username?

conversation; operación None; 3.531s.

> I don't have access to your personal computer or your Windows username. To find it, you can press `Win + R`, type `cmd`, and run `whoami`.

## username-es

Dime la cuenta actual de Windows.

action; operación system.status; 2.281s.

> (propuesta estructurada)

## os-version

Which Windows version am I running?

action; operación system.status; 0.157s.

> (propuesta estructurada)

## os-memory

Qué Windows tengo y cuánta RAM tiene esta máquina

action; operación system.status; 0.14s.

> (propuesta estructurada)

## cpu

Dime el uso actual de la CPU.

action; operación system.status; 0.203s.

> (propuesta estructurada)

## concept

¿Qué es una cuenta de Windows?

conversation; operación None; 1.594s.

> Una cuenta de Windows es una identidad digital que te permite acceder al sistema operativo, guardar tus archivos, configuraciones y aplicaciones, y gestionar tus permisos de seguridad dentro de tu PC.

## negative

Do not read my Windows account.

conversation; operación None; 0.484s.

> I won't read your Windows account.
