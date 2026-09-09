# 396 — reparación con historial conservado

Fuente395 real, sin hook que modifique historial: 5/5 útiles en esta corrida de averías. Todos atravesaron una vez bounded_chat_answer; ninguna llamada ejecutada.

Se inyecta explícitamente un primer borrador en idioma opuesto para activar la guardia existente. No son turnos normales ni aceptación fresca. El contexto y las preguntas se heredan del panel sintético385. Modelo, configuración y manifest sin promoción.

La comparación programática de los cinco payloads396 con los de la variante394 dio igualdad en los cinco. Álvaro cambió de “Tu nombre es Álvaro. Lo recordé porque me lo dijiste en tu último mensaje, aunque la memoria privada esté desactivada.” (394: parcial por cronología falsa) a “Te llamas Álvaro.” (396). No atribuir esa variación de inferencia a una diferencia de payload ni borrar el fallo previo; una corrida buena no acredita estabilidad ni cierre.

## t5

**Entrada:** What is my name?

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

**source395**
Borrador inyectado:
> Hola, soy un asistente virtual y estoy aquí para ayudarte con tus preguntas.

Respuesta final:
> Your name is Jordan.

Reintentos: 1; 0.86 s.

## t10

**Entrada:** ¿Cómo me llamo?

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

**source395**
Borrador inyectado:
> Hello, I am a virtual assistant and I am here to help you with your questions.

Respuesta final:
> Te llamas Álvaro.

Reintentos: 1; 0.86 s.

## third-party

**Entrada:** What is my name?

Contexto literal:

**user**
> My coworker is Morgan.

**assistant**
> Morgan is your coworker.

**source395**
Borrador inyectado:
> Hola, soy un asistente virtual y estoy aquí para ayudarte con tus preguntas.

Respuesta final:
> I don't know your name. Could you tell me what it is?

Reintentos: 1; 1.171 s.

## corrected-self-name

**Entrada:** What is my name?

Contexto literal:

**user**
> My name is Taylor.

**assistant**
> Hello Taylor.

**user**
> Actually, my name is Casey.

**assistant**
> Thanks for correcting that.

**source395**
Borrador inyectado:
> Hola, soy un asistente virtual y estoy aquí para ayudarte con tus preguntas.

Respuesta final:
> Your name is Casey.

Reintentos: 1; 0.797 s.

## capital-france

**Entrada:** ¿Cuál es la capital de Francia?

Contexto literal:

**source395**
Borrador inyectado:
> Hello, I am a virtual assistant and I am here to help you with your questions.

Respuesta final:
> La capital de Francia es París.

Reintentos: 1; 0.797 s.
