# Separar respuesta del modelo y rechazo de BAXY

Cuatro llamadas con la misma observación20/25, modelo, backend y sampler comparan dos factores: mantener o quitar el borrador rechazado, y añadir o no una explicación explícita de la ausencia de tiempos de apertura. Las otras entradas permanecen iguales. Se reconstruye el envoltorio verificado con payload proyectado idéntico; audit.situation está truncado y no se presenta como input bruto idéntico.

| Variante | Contenido | Validador actual | Tiempo |
|---|---|---|---:|
| A: corrección768 |20entradas, recencia inventada |Rechazo correcto |4,219s|
| B: quitar borrador |19entradas, falta una instancia |Aceptación incorrecta |3,859s|
| D: quitar borrador y explicar causa |20entradas fieles, página20/25 |Rechazo incorrecto |4,391s|
| C: conservar borrador y explicar causa |20entradas fieles, página20/25 |Rechazo incorrecto |4,375s|

C falla porque «esta lista incluye20ventanas» se interpreta como total25: el vocabulario de página no reconoce lista/list. D falla porque «la lista no incluye todaslasventanas» se interpreta como afirmar exhaustividad. En ambos, decir que el orden de apertura no se conoce es correcto y el guard de cronología no es el disparador. B demuestra además que la presencia de cada nombre no prueba la multiplicidad de las entradas: la adjudicación manual lo rechaza aunque el verificador lo admita.

La explicación explícita produce dos respuestas fieles en esta observación. No prueba estabilidad, generalización ni que los reintentos quepan en el presupuesto total. Prefill/generación y tokens están en ADJUDICATION; todos reportan cache_n0. Pico de servidor3497,56MiB VRAM/718,58MiB RSS;20,469s incluyendo arranque, sin violaciones. Cuatro llamadas terminaron stop, fuentes y driver intactos; no hay crédito de UI/voz/encuesta/reserva ni promoción de modelo.

La siguiente reparación queda localizada en la vinculación de cantidades al sujeto lista/página y la polaridad de la afirmación exhaustiva, conservando los controles negativos. El cambio de instrucciones sólo podrá adoptarse junto con evidencia real de entrega, sin convertir un verificador verde en verdad por definición. C03 activo.
