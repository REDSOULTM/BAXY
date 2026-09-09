# 356 — saludo solicitado frente a eco inútil

351/355: la mente genera Hola Emmanuel para el objetivo público dime hola
emmanuel. La App registra restates_request; RestatesTheRequest quita dime y
confunde el texto solicitado con repetir una petición informativa. La recuperación
recibe confirmar y repite el resultado anterior. No modificar el prompt/modelo.

Reutilizar StartsWithGreeting ya existente: dentro de la comparación con el
resto de una petición tras quitar dime/decime/tell me/etc., un saludo que coincide
exactamente con lo pedido no constituye eco inútil. Conservar el veto de repetir
la petición entera, el resto de los ecos y todas las guardas posteriores.
No cambiar IsGreetingRequest global ni clasificar una petición compuesta entera
como un saludo. No nombres fijos ni respuestas preescritas.

Herencia: Carter_v2 LLM_CONTEXT_MEMORY_REPORT.md R4 muestra el riesgo de eco de
historial; aquí el HTTP actual demuestra que el modelo devuelve el texto que
se solicitó explícitamente. C03 exige distinguir salida pedida y copia inútil,
conservando las garantías del publicador; no ensayar otra plantilla después de
un borrador correcto. Reusar investigación exacta de modelo/formato vigente.

Primero baseline de la política y del compositor real de la App: variantes
españolas, inglesas, nombres compuestos, pregunta copiada y afirmación de efecto
no verificado. Después dueñas App y Fast; repetir355 con modelo/perfil equivalentes.
No Full durante reparación ni promoción de Qwen3.5 por este cambio.

Al preparar baseline, el stub .NET eludía el control Python para Hola Lina,
abrí Spotify: el helper C# no es el dueño de ese rechazo. Se conserva esa prueba
en el compositor Python real con su retry (rechazo observado unmentioned_name).
En la App se comprueba su piso existente de éxito no verificado Listo, ya está.
No se cambia ninguna guarda de efectos ni se afirma que el helper C# las cubra
todas. Baseline inicial5fail3pass queda preservado como baseline-wrong-owner.log.

El baseline correcto de App dio4fail4pass0skip: los cuatro saludos válidos se
rechazaban. El control Python mostró además el mismo veto en el compositor:
Hola Lina devuelve extra_claim y el retry descarta el saludo correcto. Se repara
la misma comparación en ambos dueños, sin cambiar los prompts ni la lectura
global de saludos. La excepción exige que el resto coincida con el saludo pedido
y que no contenga una petición informativa: copiar hola Lina y explícame qué es
la gravedad sigue rechazado. Toda la petición copiada también conserva el veto.
Se añaden ocho controles directos de composición y el retry de la afirmación
ajena. El rechazo del nombre ajeno no demuestra detección general de efectos.
