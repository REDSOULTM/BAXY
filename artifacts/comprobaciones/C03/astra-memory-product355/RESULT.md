# Producto355 — 6/7 completos, cero silencios

Mismos siete pedidos y overrideQwen3.5 de351; única diferencia de fuente354 conserva operation al componer. Exit0, admisiones200, sin timeout; registro intacto. Cinco literales humanos más confirmar/recall sintéticos declarados. No reserva fresca, escritorio gráfico ni voz física.

## Turno 1

Tienes memoria, puedes guardar mi nombr?, quiero decirte mi nombre y quiero que lo recuerdes cuando te lo pregunte

> ¿Cómo te llamas?

Útil: pide el nombre faltante.

## Turno 2

me llamo emmanuel, dime hola emmanuel

> Hola Emmanuel, no pude guardar la información porque la memoria está deshabilitada.

> Hola Emmanuel. ¿Quieres que active la memoria privada local? Elige confirmar o cancelar.

Útil: el fallo se limita a guardar con memoria desactivada; saluda y explica la activación que se confirma. Ya no dice no poder saludar.

## Turno 3

confirmar

> He confirmado que la configuración de memoria está activa.

> He confirmado que la memoria se ha guardado correctamente.

Útil: confirmación de activación y nuevo guardado verificados, sin inventar una vista ni cambios globales. El saludo pedido ya se vio en T2. Subsiste un defecto separado: la continuación genera Hola Emmanuel, que la App veta como restates_request y recompone el resultado anterior.

## Turno 4

Yo soy el

> ¡Hola Emmanuel! ¿En qué puedo ayudarte hoy?

Útil: reconoce a Emmanuel en el saludo frente a la referencia Yo soy el; la oferta adicional es innecesaria pero no contradice.

## Turno 5

quien soy

> Eres usuario.

Fallo: system.identity devuelve la cuenta Windows usuario, que no responde al referente personal Emmanuel ya aportado y guardado. Provider veraz, selección/contexto incorrectos.

## Turno 6

nono, te pregunte quien soy yo, no tu, dime quien eres tu y quien soy yo

> Yo soy BAXY, tu compañero en el PC, y tú eres Emmanuel.

Útil: distingue BAXY y Emmanuel.

## Turno 7

cómo me llamo

> Tu nombre es Emmanuel.

Útil: devuelve Emmanuel desde memory.recall verificado.

## Decisión y límites

Mantener354: mejora de3514/7 a3556/7, con los mismos controles y sin relajar guardas. Mantener Qwen3.5 como candidato no promovido; otras rutas, selector, recursos conjuntos y runtime siguen necesitando comprobación. El journal acredita enable, nuevo save distinto del fallido y recall. No equiparar esto con C03 completo ni con100casos humanos frescos.

Siguiente causa: RestatesTheRequest trata dime hola emmanuel como una petición de información y rechaza Hola Emmanuel por coincidir con el resto tras quitar dime. El objetivo público tras memoria es esa petición de saludo; el modelo ya la cumple. Corregir sólo ese veto con variantes generales de saludo/cita solicitados y controles de eco realmente inútil, sin nombre fijo. Después, contrastar contexto del selector que aún interpreta quien soy como system.identity. No editar otro prompt para suplir un borrador ya correcto.