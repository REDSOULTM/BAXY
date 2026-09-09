# C03 — presupuesto previo a la clasificación

## Regresión identificada

44b7c45b (2026-08-23), «goal06: acting es sigo/still-working», añadió una
restricción de palabras al progreso. 21547eba generaba su señal sin inferencia.
c1ebb79b (2026-09-04), «C03: public compose keeps verified facts and own voice»,
sustituyó formulate_progress por compose_user_message antes de clasificar,
sin ampliar ni separar el presupuesto normal de 17 s. No se restaura la
plantilla: contradice la identidad. El código de temporización quedó acoplado
a una composición con hasta tres intentos y al mismo deadline de la respuesta.

Request-preserved mantiene 4/6 útiles. Su audit demuestra que esa composición
precede a la política/guard/idioma y deja sólo 5.781 s a una triple llamada que
agota ese remanente. Esto es evidencia del presupuesto consumido, no prueba
de que sea la única causa de todas las respuestas ausentes.

## Cambio acotado y prueba

Se retiran las dos llamadas de progreso previas a un catálogo/clasificación
no resueltos. La señal de una misión explícita ya reconocida y los hitos de
la ejecución conservan su recorrido. No cambian catálogo, validadores,
modelo, muestreo ni plazos. No se inserta texto fijo ni se amplían timeouts.
Dos regresiones prueban que un compositor de progreso agotado no puede impedir
una conversación que sí tiene respuesta; antes ambas fallan con TimeoutError.
Después: 1242 pass/101 subtests en turn_policy, C03, reader, voz, planner y
first_signal; 19 pass/1 skip ambiental/838 deselected en pins y esos dos casos.
Ruff verde. Los tests no certifican calidad del modelo ni tiempo de UI.

astra-qwen8-preclassification compara los mismos seis controles; source/model/
muestreo quedan prerregistrados. El monitor conserva el techo de 4096 MiB.
No hay Full ni aceptación fresca; estado/proceso en CHECKPOINT.md.

## Continuidad

C07 deberá medir el intervalo sin salida y la primera señal en esta ruta,
con modelo real. El p95 histórico de 0.16 s de la señal sin modelo no es una
certificación del producto actual. Si necesita una señal durante interpretación,
su formulación no puede volver a agotar la respuesta final ni afirmar ejecución.
El requisito temporal de C07 sigue vigente; no se declara cumplido por C03.
