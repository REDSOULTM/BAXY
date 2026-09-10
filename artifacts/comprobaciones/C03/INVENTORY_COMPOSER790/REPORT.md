# El rechazo detecta la omisión, pero el reintento no la resuelve

La ejecución790 terminó con **33respuestas correctas de50,17fallos y8finales vacíos**. No hubo timeouts: los67intentos registrados antes de HTTP devolvieron respuesta. Los tres inventarios sintéticos que788 publicaba incompletos ya no se publican, pero **ninguno se recuperó como respuesta completa**. El candidato789 sigue sin adoptar; el bloqueo no se considera resuelto. [Adjudicación](ADJUDICATION.json).

| Evidencia | Resultado |
|---|---|
| Preguntas, hechos y criterios | Los mismos50 casos completos de788 |
| Primeros payloads | 50/50 idénticos, incluido presupuesto512 en inventarios densos |
| Primeros borradores | 49/50 idénticos; cambia2-3, causa no establecida |
| Finales | 42/50 iguales;8resultados nuevos revisados |
| Respuestas HTTP | 67/67 exitosas;0intentos sin terminal;13salidas nuevas leídas |
| Tres listas con multiplicidad omitida | 0recuperadas; tres finales vacíos |
| Seis inventarios antes cortados | Siguen completos en1petición,4,438–4,578s |

Los casos4-2,5-2 y6-2 siguen enumerando cinco títulos sin sus repeticiones exactas después de recibir la corrección factual. H0103 incorpora «8instancias» en una categoría, pero mantiene otras omisiones y etiquetas incorrectas. H0023 vuelve a afirmar cronología no observada pese a recibir su contradicción. La presencia de `rejected_draft` y la repetición cercana de su contenido justifican aislar su efecto en el siguiente diagnóstico; **todavía no demuestran que sea la causa**.

El cambio32→33no se acredita a la nueva comprobación. El caso4-1 conservaba un primer borrador correcto que el verificador de alcance rechazaba. Esta vez el servidor respondió más rápido y un segundo borrador correcto llegó dentro de9s. La reproducción del mismo par de respuestas en787y789 devuelve el mismo final con los mismos dos payloads. El caso2-3 también se entrega igual en ambas fuentes al recibir su nuevo borrador. [Reproducción causal](CAUSAL_REPLAY.json).

Esa reproducción sí demuestra dos cambios directos de aceptación:787entrega las listas incompletas4-2y5-2;789las rechaza. Con los nuevos borradores de6-2, ambas fuentes terminan vacías: sigue interviniendo el verificador anterior de cantidades/alcance. No se confunde impedir una respuesta incompleta con satisfacer lo pedido.

La revisión posterior encontró dos problemas del propio candidato: el último título seguido de un punto y otra frase se informa con cero menciones aunque está presente; y una anotación de proceso en una ventana puede dar crédito indebido a otra ventana sin título. Son contraejemplos sintéticos reproducidos sobre la fuente sellada, con entradas y salidas completas. Deben repararse antes de adoptar789. [Hallazgos de revisión](REVIEW_FINDINGS.json).

El resto conserva la adjudicación de788, incluidos sujetos/etiquetas incorrectos de RAM, la errata del reloj y los falsos vetos de inventarios vacíos o conteos. No se cambian criterios, umbrales ni cuotas. Las respuestas sintéticas nuevas están en [RESPUESTAS_CAMBIADAS.md](RESPUESTAS_CAMBIADAS.md); todas las entradas y salidas, incluidos los históricos, en el directorio privado fijado por PRIVATE_PINS.json.

Los67slots efectivos conservanT0,top-k40,top-p0,95,min-p0,05,penalizaciones neutras,contexto4096,caché0 y los límites de salida originales. Modelo,backend,manifiesto,conductor y13huellas de fuente permanecieron intactos. Un primer borrador distinto pese a payload igual limita la reproducibilidad literal; no se inventa una causa. [Paridad y parámetros](PARITY.json).

Duración93,844s; pico observado **3499,56MiB de VRAM y761,77MiB de RAM residente del árbol del compositor**. No es BAXY completo con UI/providers/voz. Muestreo cada250ms, que puede omitir picos más breves. Los tiempos menores respecto de788no se atribuyen a ahorro de recursos o aceleración del código; no se cambió el perfil. Sesión44316 recogida con exit0 y sin proceso activo.

Siguiente: reparar los dos errores de atribución del verificador con otro sello; después aislar el formato de la corrección sobre los mismos casos. No repetir otra tanda sin intervención ni añadir otra instrucción de concisión: los antecedentes754–759no la justifican. [Antecedente de proyección](../INVENTORY_PROJECTION759/REPORT.md), [canal de corrección768](../INVENTORY_CORRECTION768/REPORT.md). Esta comparación es de integración conQwen; no descartaK2 ni sustituye los controles nativos699y737.

C03 permanece activo:28requisitos cubiertos,714abiertos,0no aplicables. Sin crédito nuevo de encuesta/reserva/UI/voz/recursos conjuntos. RESULT.json conserva el resultado previo a adjudicar; ADJUDICATION.json registra la revisión posterior.789y787quedan preservados sin adopción.
