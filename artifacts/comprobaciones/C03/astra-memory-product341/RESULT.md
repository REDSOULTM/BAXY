# Producto341 — 1/6 completo, cero silencios

Exit0, admisiones200 y ningún timeout. Runtime registrado sin override. 341 conserva seis literales humanos;342 agrega confirmar y cómo me llamo como controles sintéticos explícitamente declarados, no uso humano ni reserva fresca. El conductor no prueba escritorio ni voz física.

## Turno 1

Tienes memoria, puedes guardar mi nombr?, quiero decirte mi nombre y quiero que lo recuerdes cuando te lo pregunte

> ¿Me dices tu nombre, para que lo recuerde?

Útil: pide el dato que falta.

## Turno 2

mhhhhhh amigo deberias poder

> Mmm, sí, pero no pude entender bien la solicitud. Vamos a intentarlo de nuevo.

Fallo: reacción convertida en incomprensión.

## Turno 3

me llamo emmanuel, dime hola emmanuel

> Hola Emmanuel, ¿quieres confirmar o cancelar?

Parcial: saluda y pide confirmar, pero no dice que se autoriza activar la memoria; no permite una decisión informada.

## Turno 4

Yo soy el

> ¿Quieres confirmar o cancelar?

Fallo: repite confirmar/cancelar ante referencia de identidad, sin explicar acción ni atender el contexto.

## Turno 5

quien soy

> ¿Quieres confirmar o cancelar?

Fallo: repite confirmar/cancelar ante pregunta de identidad.

## Turno 6

nono, te pregunte quien soy yo, no tu, dime quien eres tu y quien soy yo

> ¿Quieres confirmar o cancelar?

Fallo: repite confirmar/cancelar ante pregunta de ambas identidades.

## Diagnóstico compartido

341: memoria no se habilita sin confirmar.340 añade correctamente el paso privado; la explicación de la confirmación recibe sólo cause=memory_enable, sin pendingAction. El borrador nativo omite qué se autoriza y el guard lo deja pasar.

342: tras confirmar, journal registra memory.enable completado y memory.save completado con nueva invocationId frente al save fallido por memory_disabled. La continuación pública sí saluda. Al recordar, la App emite status/cause memory_records con shown1,total1,records[{label:name,value:emmanuel}], pero Python lo reduce a kindstatus/outcomecompleted/state listed memories: elimina los registros. El modelo ya no recibe el nombre y publica No sé cómo te llamas. Enable/save también llegan como prosa fija al compositor, con payload vacío; éste publica Confirmado y Guardé. Primera transformación incorrecta localizada.

Decisión: reparar el contrato de proyección privada de resultado/confirmación, no introducir otro nombre en prompts o filtro de frases. Preservar los valores permitidos por MemoryOperationResponseProjection y sus reglas de secretos. La referencia conversacional105/107 también sigue pendiente.340 no cierra la memoria integrada sólo por los1911tests. C03 EN_CURSO.
