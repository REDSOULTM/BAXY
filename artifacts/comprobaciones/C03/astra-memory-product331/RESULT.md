# Producto331 — 1/6 útil, cero silencios, cierre NO aceptado

Proceso exit0, seis admisiones200 y seis terminales publicados sin timeout. La fuente330 repara99, pero el conjunto retrocede frente a327 (2/6). No promover como solución integrada sin corregir las regresiones. Desarrollo; no reserva, UI gráfica ni voz física.

La única diferencia de fuente prevista es330; al cambiar la primera respuesta cambia también la historia de los turnos siguientes. No atribuir sus diferencias a una modificación directa del modelo ni llamar a esto control de historia idéntica.

## Turno 99

Tienes memoria, puedes guardar mi nombr?, quiero decirte mi nombre y quiero que lo recuerdes cuando te lo pregunte

> ¡Claro que sí! Me encantaría recordar tu nombre. ¿Puedes darme tu nombre ahora? 😎

Útil como petición del dato faltante; no guarda ni propone memory.save.

## Turno 101

mhhhhhh amigo deberias poder

> Mmm, sí, pero no pude entender bien la solicitud. Vamos a intentarlo de nuevo.

Inútil: la reacción se convierte en unsupported; el reintento estructurado se trunca.

## Turno 103

me llamo emmanuel, dime hola emmanuel

> La causa del fallo es que la interpretación de la solicitud no fue válida.

Inútil: HTTP23/27 sí saluda; el guard de explicación rechaza el seguimiento interrogativo sin punto anterior.

## Turno 105

Yo soy el

> ¡Claro! ¿Me dices tu nombre, Emmanuel? Así puedo recordarte mejor. 😎

Inútil: pide un nombre que ya tiene en el historial y en su propia respuesta.

## Turno 107

quien soy

> Tú eres usuario, usuario del dominio REDNOTE.

Inútil para el contexto: consulta la cuenta de Windows en lugar del nombre declarado.

## Turno 109

nono, te pregunte quien soy yo, no tu, dime quien eres tu y quien soy yo

> ¿Quieres que te diga quién soy yo y quién eres tú?

Inútil: vuelve a preguntar si debe contestar ambas identidades.

## Análisis causal y decisión

99: parser privado sin ruta; selector sin memory.*; chat pide nombre. Falta estado de dato pendiente y continuidad privada. 101: verificador sin historia dice incomplete_effect; apply_conversation_effect_presentation lo trata como unsupported. HTTP10/14 niegan memoria por instrucción previa, HTTP11/15 finish_reason=length. No ampliar tokens como solución de la clasificación errónea. 103: saludo válido descartado en __main__.py:6457; guard basado en punto/exclamación confunde pregunta final con respuesta entera interrogativa. 105: error ya en chat, con nombre/historia presentes. 107: selector elige system.identity, dato real de cuenta pero referente equivocado. 109: selector pasa de ninguna operación a system.identity; frontera de observación pide confirmación, no contesta.

Decisión de razonamiento xhigh: separar reparación del guard demostrado de continuidad privada y ambigüedad de identidad. No adoptar más cambios de prompt ni heurísticas por nombre. Memoria exige intención explícita, dato de la persona, protección existente y postlectura persistente; recordar por historial no prueba un guardado. Próximo cambio acotado: validar la forma de respuesta interrogativa; luego repetir los seis casos. El paso de continuidad privada sigue requiriendo xhigh; implementación/tests mecánicos high.

Fuentes contrastadas2026-09-08: [parámetros requeridos](https://docs.cloud.google.com/dialogflow/cx/docs/concept/parameter) distinguen dato pendiente de formulario completo; [Qwen2507 oficial](https://huggingface.co/Qwen/Qwen3-4B-Instruct-2507) y la investigación local vigente conservan el modelo exacto, sin extrapolar Thinking. Herencia: biblioteca/carter/legacy/Carter_v2/LLM_CONTEXT_MEMORY_REPORT.md:12–40 exige procedencia humana y separa cuenta de identidad declarada.
