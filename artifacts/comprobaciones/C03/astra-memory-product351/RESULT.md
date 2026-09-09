# Producto351 — 4/7 completos, cero silencios

Mismos siete pedidos345, Qwen3.5-4B-Q4_K_M como único override de modelo. Exit0, admisiones200, ningún timeout; registro intacto. Cinco literales humanos y dos controles sintéticos ya declarados. Conductor no prueba UI/voz.

## Turno 1

Tienes memoria, puedes guardar mi nombr?, quiero decirte mi nombre y quiero que lo recuerdes cuando te lo pregunte

> ¿Cómo te llamas?

Útil: pide el nombre faltante.

## Turno 2

me llamo emmanuel, dime hola emmanuel

> Hola Emmanuel, no puedo saludarte porque la memoria está deshabilitada.

> Hola Emmanuel. ¿Quieres que active la memoria privada local? Elige confirmar o cancelar.

Fallo del turno completo: la confirmación explica la activación, pero antes dice no poder saludar por memoria deshabilitada. El fallo sólo afecta memory.save, no saludar; además ya saluda en esa misma frase.

## Turno 3

confirmar

> He confirmado que la configuración de memoria está activa y que la vista está habilitada.

> He confirmado que la memoria se ha actualizado correctamente.

Fallo: nuevo save verificado y narrado, pero enable inventa una vista habilitada. Hola Emmanuel sí existe como borrador nativo de la continuación, pero no se publica; hay que localizar ese descarte, no pedir al modelo otro saludo.

## Turno 4

Yo soy el

> ¡Hola Emmanuel! ¿En qué puedo ayudarte hoy?

Útil como reconocimiento contextual: saluda a Emmanuel al afirmar Yo soy el. Añade una oferta innecesaria, sin cambiar la identidad.

## Turno 5

quien soy

> Eres usuario.

Fallo: ejecuta system.identity y publica la cuenta Windows usuario en vez del nombre Emmanuel aportado para esta conversación.350 sólo probaba el chat fijo y no cubría esta selección.

## Turno 6

nono, te pregunte quien soy yo, no tu, dime quien eres tu y quien soy yo

> Yo soy BAXY, tu compañero en el PC, y tú eres Emmanuel.

Útil: BAXY y Emmanuel correctamente diferenciados.

## Turno 7

cómo me llamo

> Tu nombre es Emmanuel.

Útil: Tu nombre es Emmanuel, fiel al recuerdo verificado.

## Decisión

No promoción. Mejora real del recuerdo y del reconocimiento frente a345, pero no cierre del recorrido. La App conserva operation en resultados/errores privados; Python lo descarta del payload de composición. En error, eso permite atribuir memory_disabled a saludar; en enable, enabled carece de ámbito. Siguiente352: medir preservación de esa identidad de operación con los HTTP exactos antes de editar. También quedan el descarte del saludo corto válido y la selección de identidad Windows con contexto personal explícito.