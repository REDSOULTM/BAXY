# 350 — candidato nativo mejora, sin promoción

13 controles idénticos:2507 registrado6/13 útiles; Qwen3.5 disponible10/13. El alternativo repara el nombre del usuario, el guardado y el chat contextual. Siguen mal las dos preguntas por el nombre del asistente con recuerdos ajenos como evidencia y enable añade una vista no observada. Primera respuesta nativa, sin guardas ni ejecución del producto: no aceptación integrada.

GPU pico2507:3497,56MiB; Qwen3.5:3173,56MiB. RAM:2845,06MiB y3723,29MiB, respectivamente. Son procesos nativos aislados, no el mínimo ni voz/GUI. Mismo backend b9980/KV/contexto/sampling, modelos secuenciales, registro intacto.

## memory.recall — registered2507

> Me llamo Emmanuel.

## name-lina — registered2507

> Me llamo Lina.

## name-accent — registered2507

> Tu nombre es Álvaro.

## name-english — registered2507

> Your name is Taylor.

## sister — registered2507

> Tu hermana se llama Olivia.

## assistant-es — registered2507

> Me llamo Emmanuel.

## both-es — registered2507

> Yo soy BAXY, tu compañero. Tú eres Emmanuel.

## assistant-en — registered2507

> My name is Taylor.

## memory.enable — registered2507

> La configuración de la memoria se ha confirmado como completada. El estado actual es "memory configuration" y el resultado es exitoso. El sistema ha sido revisado y está en funcionamiento.

## memory.save — registered2507

> La memoria fue actualizada correctamente. No se realizaron cambios en el sistema.

## disabled-control — registered2507

> La memoria ha sido desactivada según la configuración actual. El estado actual indica que la memoria está deshabilitada.

## actual-chat-who — registered2507

> No tengo acceso a información personal ni identidad. ¿Podrías aclarar más? 😎

## actual-chat-both — registered2507

> Yo soy BAXY, tu compañero en el PC. Y tú, Emmanuel, eres tú mismo — el usuario que está hablando conmigo. ¿Necesitas ayuda con algo en particular? 😎

## memory.recall — available-qwen35

> Tu nombre es Emmanuel.

## name-lina — available-qwen35

> Tu nombre es Lina.

## name-accent — available-qwen35

> Tu nombre es Álvaro.

## name-english — available-qwen35

> Your name is Taylor.

## sister — available-qwen35

> Tu hermana se llama Olivia.

## assistant-es — available-qwen35

> Me llamo Emmanuel.

## both-es — available-qwen35

> Soy BAXY, tu compañero. Eres Emmanuel.

## assistant-en — available-qwen35

> My name is Taylor.

## memory.enable — available-qwen35

> He confirmado que la configuración de memoria está activa y que la vista está habilitada.

## memory.save — available-qwen35

> He confirmado que la memoria se ha actualizado correctamente.

## disabled-control — available-qwen35

> He desactivado la memoria.

## actual-chat-who — available-qwen35

> Eres Emmanuel.

## actual-chat-both — available-qwen35

> Yo soy BAXY, tu compañero en el PC, y tú eres Emmanuel.

## Decisión

Comprobar producto351 con override declarado; no promover por este resultado. Reutilizar el activo y la investigación75–77, no descargar ni cambiar defaults. El nuevo conjunto de fallos justifica esta revisión; no borra regresiones históricas.