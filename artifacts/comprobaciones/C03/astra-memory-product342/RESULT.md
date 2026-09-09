# Producto342 — 2/7 completos; identidad conjunta parcial; cero silencios

Exit0, admisiones200 y ningún timeout. Runtime registrado sin override. 341 conserva seis literales humanos;342 agrega confirmar y cómo me llamo como controles sintéticos explícitamente declarados, no uso humano ni reserva fresca. El conductor no prueba escritorio ni voz física.

## Turno 1

Tienes memoria, puedes guardar mi nombr?, quiero decirte mi nombre y quiero que lo recuerdes cuando te lo pregunte

> ¿Me dices tu nombre, para que lo recuerde?

Útil: pide el nombre faltante.

## Turno 2

me llamo emmanuel, dime hola emmanuel

> Hola Emmanuel, ¿quieres confirmar o cancelar?

Parcial: saludo y elección sin explicar qué se confirma.

## Turno 3

confirmar

> Hola Emmanuel, ¿cómo estás? 😎

Útil para el recorrido: el journal verifica enable y un nuevo save, y se entrega el saludo pendiente. Las narraciones intermedias Confirmado/Guardé son pobres y se revisan abajo.

## Turno 4

Yo soy el

> ¿Y yo? 😏

Fallo: invierte el referente y responde con otra pregunta.

## Turno 5

quien soy

> ¿Eres tú mismo o alguien más? ¿Quieres que te diga algo más? 😏

Fallo: pide desambiguar una identidad ya declarada; dos preguntas innecesarias.

## Turno 6

nono, te pregunte quien soy yo, no tu, dime quien eres tu y quien soy yo

> Yo soy BAXY, tu compañero en el PC. Y tú, Emmanuel, eres tú mismo — el usuario que está hablando contigo. ¿Quieres hablar de algo en particular? 😎

Parcial: identifica BAXY y Emmanuel, pero añade la confusa atribución de que el usuario está hablando consigo mismo. No presentar como respuesta natural plenamente validada.

## Turno 7

cómo me llamo

> No sé cómo te llamas, pero puedo ayudarte si necesitas algo.

Fallo demostrado: niega conocer el nombre después de memory.recall verificado con un registro name=emmanuel.

## Diagnóstico compartido

341: memoria no se habilita sin confirmar.340 añade correctamente el paso privado; la explicación de la confirmación recibe sólo cause=memory_enable, sin pendingAction. El borrador nativo omite qué se autoriza y el guard lo deja pasar.

342: tras confirmar, journal registra memory.enable completado y memory.save completado con nueva invocationId frente al save fallido por memory_disabled. La continuación pública sí saluda. Al recordar, la App emite status/cause memory_records con shown1,total1,records[{label:name,value:emmanuel}], pero Python lo reduce a kindstatus/outcomecompleted/state listed memories: elimina los registros. El modelo ya no recibe el nombre y publica No sé cómo te llamas. Enable/save también llegan como prosa fija al compositor, con payload vacío; éste publica Confirmado y Guardé. Primera transformación incorrecta localizada.

Decisión: reparar el contrato de proyección privada de resultado/confirmación, no introducir otro nombre en prompts o filtro de frases. Preservar los valores permitidos por MemoryOperationResponseProjection y sus reglas de secretos. La referencia conversacional105/107 también sigue pendiente.340 no cierra la memoria integrada sólo por los1911tests. C03 EN_CURSO.
