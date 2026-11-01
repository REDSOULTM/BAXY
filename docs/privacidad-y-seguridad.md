# Privacidad y seguridad

BAXY actúa sobre tu PC y escucha lo que dices. Por eso la privacidad y la seguridad son parte de la arquitectura, no
un ajuste.

## Qué se queda en tu máquina

- **El modelo** corre en local con `llama-server`, escuchando sólo en la interfaz de bucle local (loopback).
- **La voz**: la palabra de activación, la transcripción (Parakeet) y la voz sintética (Supertonic) corren en la CPU.
  El audio no se guarda ni se envía.
- **La memoria** (lo que le pides recordar), las notas, las tareas y el historial de conversaciones se guardan en
  `%LOCALAPPDATA%\BAXY`, cifrados con DPAPI del usuario de Windows cuando son datos privados
  (`src/Baxy.Security.Windows`).
- **La traza de turnos** (`%LOCALAPPDATA%\BAXY\renew\turns.jsonl`) se queda en el PC y rota al pasar de 50 MB.

## La regla de la red

La línea es de **dirección, no de conexión**. BAXY puede leer la web (buscar, abrir una página, consultar el tiempo)
cuando la petición lo necesita, pero **no envía contenido tuyo** a ningún servicio: ni tu voz, ni tus archivos, ni tu
memoria. La búsqueda lleva las palabras de la consulta, no tu conversación.

## Lo que puedes ver, corregir y borrar

Las operaciones `memory.list`, `memory.correct`, `memory.forget`, `memory.export`, `memory.disable` y
`memory.session.clear` existen para que puedas inspeccionar y borrar lo que BAXY sabe de ti, también por voz.

## Seguridad de las acciones

- **Catálogo cerrado.** El modelo sólo puede pedir operaciones del catálogo tipado
  (`src/Baxy.Kernel/Operations/ProductCatalog.cs`); un texto, una página web o un documento no pueden añadir
  operaciones ni subir su nivel de riesgo.
- **Confirmación ligada a la invocación exacta.** Borrar, enviar un mensaje o cerrar algo con trabajo sin guardar
  pide un sí que vale sólo para esa invocación (misma operación, mismos argumentos). Una respuesta ambigua nunca
  cuenta como sí.
- **Texto pegado no es una orden.** Si pegas un texto con instrucciones, BAXY no las ejecuta: lo trata como contenido.
- **Diario con integridad.** Cada invocación queda en un diario con HMAC (`src/Baxy.Kernel/Journal`), lo que evita
  repetir una acción tras un reinicio y detecta manipulaciones.
- **Estados terminales honestos.** Un efecto que pudo ocurrir pero no se comprobó se informa como tal
  (`effectMayHaveOccurred`), nunca como éxito.
- **Binarios declarados.** La mente sólo arranca un `llama-server` cuyos ficheros coinciden por SHA-256 con los
  declarados en `src/baxy_mind/data/llama_server.v1.json`.

## Datos del repositorio

El repositorio no contiene datos personales. Los bancos de evaluación que parten de peticiones reales y los datos de
entrenamiento viven fuera de él; aquí sólo hay cifras agregadas y huellas SHA-256. Antes de publicar un cambio se
comprueba que ninguna línea añadida coincide con esas peticiones privadas.

`.gitignore` impide subir por accidente los datos locales (memoria, sesiones, capturas, bases de datos) y los
corpus privados. Algunas pruebas y herramientas de medición necesitan esos ficheros locales: en un clon público esas
precondiciones no existen y la prueba lo dice; no se deben subir datos para resolverlo.

## Informar de una vulnerabilidad

Si encuentras un fallo de seguridad (por ejemplo, una forma de que el modelo ejecute algo sin confirmación o de que
salgan datos del PC), **no abras un issue público**: usa
[«Report a vulnerability»](https://github.com/REDSOULTM/BAXY/security/advisories/new) en la pestaña Security del
repositorio.
