# 392 — resolvedor contextual existente

Rechazado como dueño general de preguntas con historial: 5/10 útiles. Esquema válido y guardias aprobadas no bastan.

Útiles: t5 (Jordan), t10 (Álvaro), assistant-conflict (Jordan), human-identity-es (Eva), corrected-self-name (Casey). Fallos: third-party atribuye Morgan al usuario; family-identity atribuye Noah al usuario aunque es su hermano; explicit-persistence inventa que Jordan fue guardado; product380-t9 niega el dato de Álvaro por memoria deshabilitada; assistant-identity responde como asistente genérico en español a una pregunta inglesa. Las guardias sólo detectan el último idioma, no los errores de atribución ni el guardado inventado. No enrutar todas las preguntas aquí ni interpretar direct_answer no vacío como evidencia.

Sin edición de fuente ni promoción de runtime. Diagnóstico de desarrollo; no acredita aceptación humana fresca, producto completo, UI ni voz física.

## t5

Contexto literal:

**user**
> My name is Jordan. Remember my name.

**assistant**
> Jordan, I remember your name. The save operation failed because memory was disabled.

**assistant**
> Jordan, I'm ready to enable your private local memory. Do you want to confirm this action or cancel it?

**user**
> What would I be confirming?

**assistant**
> What would you like to confirm or cancel? Please choose either confirm or cancel.

**user**
> cancel

**assistant**
> Cancelado.

**user**
> Who am I?

**assistant**
> You are Jordan, a user who just tried to enable private local memory but canceled the action.

Entrada:
> What is my name?

Respuesta literal:

> Your name is Jordan.

1.534 s. Guardia de estado no leído: False; idioma opuesto: False. Estas guardias no certifican verdad semántica.

## t10

Contexto literal:

**assistant**
> You are Jordan, a user who just tried to enable private local memory but canceled the action.

**user**
> What is my name?

**user**
> Me llamo Álvaro y quiero que guardes mi nombre.

**assistant**
> Hola Álvaro, no puedo guardar tu nombre porque la memoria está deshabilitada.

**assistant**
> Hola Álvaro, ¿te gustaría que active mi memoria privada para guardarte tu nombre? Por favor, dime si quieres confirmar o cancelar.

**user**
> ¿Qué vas a activar?

**assistant**
> ¿Qué vas a activar? ¿Confirmar o cancelar?

**user**
> cancelar

**assistant**
> Se ha cancelado la memoria.

**user**
> quién soy ahora

**assistant**
> Eres Álvaro, pero como cancelaste la activación de la memoria privada, no tengo guardado tu nombre en mi contexto actual.

Entrada:
> ¿Cómo me llamo?

Respuesta literal:

> Tu nombre es Álvaro.

2.177 s. Guardia de estado no leído: False; idioma opuesto: False. Estas guardias no certifican verdad semántica.

## third-party

Contexto literal:

**user**
> My coworker is Morgan.

**assistant**
> Morgan is your coworker.

Entrada:
> What is my name?

Respuesta literal:

> Tu nombre es Morgan.

1.377 s. Guardia de estado no leído: False; idioma opuesto: False. Estas guardias no certifican verdad semántica.

## assistant-conflict

Contexto literal:

**user**
> My name is Jordan.

**assistant**
> Your name is Morgan.

Entrada:
> What is my name?

Respuesta literal:

> Your name is Jordan.

1.671 s. Guardia de estado no leído: False; idioma opuesto: False. Estas guardias no certifican verdad semántica.

## explicit-persistence

Contexto literal:

**user**
> My name is Jordan.

**assistant**
> Hello Jordan.

Entrada:
> What name have you saved in private memory?

Respuesta literal:

> I have saved the name 'Jordan' in private memory.

1.356 s. Guardia de estado no leído: False; idioma opuesto: False. Estas guardias no certifican verdad semántica.

## product380-t9

Contexto literal:

**assistant**
> The memory enable action has been cancelled.

**user**
> Who am I?

**assistant**
> You are Jordan, a user who just asked me to remember your name.

**user**
> What is my name?

**user**
> Me llamo Álvaro y quiero que guardes mi nombre.

**assistant**
> Hola Álvaro, no puedo guardar tu nombre porque la memoria está deshabilitada.

**assistant**
> Hola Álvaro, ¿te gustaría que active mi memoria privada para guardarte tu nombre? Por favor, dime si quieres confirmar o cancelar.

**user**
> ¿Qué vas a activar?

**assistant**
> ¿Qué vas a activar? ¿Confirmar o cancelar la activación de la memoria local privada?

**user**
> cancelar

**assistant**
> Se ha cancelado la activación de la memoria privada local.

Entrada:
> quién soy ahora

Respuesta literal:

> No tengo información sobre quién eres ahora, ya que no puedo recordar tu identidad porque la memoria está deshabilitada.

2.564 s. Guardia de estado no leído: False; idioma opuesto: False. Estas guardias no certifican verdad semántica.

## assistant-identity

Contexto literal:

**user**
> My name is Taylor.

**assistant**
> Hello Taylor.

Entrada:
> Who are you?

Respuesta literal:

> Soy un asistente virtual diseñado para ayudarte con tareas y responder preguntas.

1.468 s. Guardia de estado no leído: False; idioma opuesto: True. Estas guardias no certifican verdad semántica.

## human-identity-es

Contexto literal:

**user**
> Me llamo Eva.

**assistant**
> Tu cuenta de Windows es otra identidad.

Entrada:
> ¿Quién soy?

Respuesta literal:

> Eres Eva.

1.44 s. Guardia de estado no leído: False; idioma opuesto: False. Estas guardias no certifican verdad semántica.

## family-identity

Contexto literal:

**user**
> My brother is Noah.

**assistant**
> Noah is your brother.

Entrada:
> What is my name?

Respuesta literal:

> Tu nombre es Noah.

1.22 s. Guardia de estado no leído: False; idioma opuesto: False. Estas guardias no certifican verdad semántica.

## corrected-self-name

Contexto literal:

**user**
> My name is Taylor.

**assistant**
> Hello Taylor.

**user**
> Actually, my name is Casey.

**assistant**
> Thanks for correcting that.

Entrada:
> What is my name?

Respuesta literal:

> Your name is Casey.

1.146 s. Guardia de estado no leído: False; idioma opuesto: False. Estas guardias no certifican verdad semántica.

