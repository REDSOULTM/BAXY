# BAXY puede perder respuestas correctas del modelo

La ejecución del compositor completo terminó con **32 respuestas correctas de 50**, 18 fallos, cuatro timeouts y dos finales vacíos. Los seis inventarios que el límite de 256 tokens cortaba se entregaron completos con el candidato 787, en una sola petición cada uno y entre 7,421 y 7,672 segundos, dentro del plazo de nueve segundos. Los criterios siguen siendo los de 785 y 786. [Adjudicación por caso](ADJUDICATION.json).

El candidato **queda sin adoptar**. El caso sintético `inventory785-5-2` pasa ahora un veto falso de alcance, pero su respuesta sigue incompleta: enumera cinco títulos para veinte entradas sin precisar cuántas ventanas tienen cada título. Las pruebas unitarias verdes no acreditan esa conducta. Antes de editar de nuevo se conserva la fuente exacta de 787 y su validación; la siguiente reparación tendrá otro sello.

| Etapa | Qué se mantiene | Qué demuestra |
|---|---|---|
| 786: 50 casos × salida 256/512 | Modelo, mensajes, hechos, muestreo y backend iguales | Seis cortes causados por el presupuesto de integración; 30/50 → 36/50 en bruto |
| 787: candidato y pruebas | Instrucciones y perfil del modelo sin cambios | Presupuesto denso existente y corrección del alcance numérico; 2901 pass, 1 skip ambiental, 121 subtests; Fast exit 0 |
| 788: mismos 50 en el compositor real | Primeros mensajes idénticos a 785; sólo cambia el límite denso | Las seis respuestas completas llegan; otras respuestas correctas se pierden en validación/reintentos |
| Reproducción de validadores anterior/787 | Los mismos 50 primeros borradores capturados | Atribuye vetos a BAXY sin invocar otra vez el modelo; no mide latencia ni calidad nativa |

En la reproducción, seis borradores ganan entrega y ninguno pierde entrega. **Eso no equivale a seis mejoras de calidad:** cinco son completos y correctos; el sexto es la lista incompleta `5-2`. El fallo de cobertura de identidades ya existía y el veto falso anterior lo ocultaba. El verificador comprueba cantidades y alcance, pero no contrasta las repeticiones enumeradas con las veinte entradas observadas. [Atribución](VALIDATOR_ATTRIBUTION.json).

Los cuatro casos con primer borrador correcto y final fallido también eran rechazados por el validador anterior: `1-3` y `1-4` por `copied_instruction`, `2-2` por `reversed_result`, `4-1` por `extra_claim`. En 788 los dos primeros agotan tres respuestas correctas y devuelven vacío; los otros terminan por presupuesto. Esta comparación identifica defectos de integración previos; no permite afirmar que el modelo produjo respuestas incorrectas en esos primeros borradores.

Los demás fallos se conservan íntegros: inventarios con repeticiones omitidas, cronología no observada, sujeto o etiquetas incorrectas en RAM y la errata del reloj. No se convierten omisiones en aciertos porque las cantidades coincidan. Cuarenta y un finales coinciden literalmente con los ya adjudicados de 786; el revisor principal leyó los nueve resultados finales nuevos, los nueve reintentos HTTP exitosos y los seis inventarios completos. [Respuestas sintéticas](RESPUESTAS_SINTETICAS.md).

Se capturaron **59 respuestas HTTP exitosas** y sus parámetros efectivos; no se afirma que hubiera sólo 59 intentos. El conductor escribe el payload después del retorno exitoso y no conserva el de las peticiones fallidas o abortadas. `replies.jsonl` sí registra los cuatro `TimeoutError` finales. La declaración inicial del preregistro sobre conservar todos los reintentos queda limitada por esta implementación. [Paridad y límites](PARITY.json).

El muestreo efectivo de esas 59 respuestas conserva T0, top-k40, top-p0,95, min-p0,05, penalizaciones neutras, contexto4096 y cero tokens de caché. Los primeros 50 payloads se comprobaron contra los congelados antes de enviarlos. Fuente, manifiesto, modelo y conductor mantuvieron sus huellas durante la ejecución. Duración: 134,562 segundos; sesión26847 recogida con código0.

Pico observado: **3499,56 MiB de VRAM dedicada y 763,57 MiB de RAM residente del árbol del compositor**. El muestreo cada250ms puede omitir picos breves. Estas cifras no representan BAXY completo con UI, providers y voz. No acreditan el requisito conjunto de4GiB ni el mínimo de memoria alcanzable.

## Qué significa para la comparación Qwen–K2

El dueño señaló correctamente que una integración ajustada durante el trabajo con Qwen puede sesgar la evaluación de K2. No se presupone que todo el código favorezca a Qwen: se mide la primera transformación que pierde una conducta.

Las primeras860 respuestas de696–698 conservaban instrucciones de BAXY y no sirven como prueba limpia del modelo. La comparación699 añadió **los mismos50 casos completos para cada uno de seis perfiles**, 300 respuestas sin system de BAXY, herramientas, schema ni filtros del producto, con plantilla y receta propias. No se dividió el panel entre modelos. Es evidencia de perfiles locales: BF16 para K2 pequeño y Q4 para los grandes, con límites documentados de backend, contexto, KV y salida; no equivalencia con los originales BF16 ni ranking universal. [Informe nativo699](../K2_HORIZON_NATIVE699/REPORTE699.md).

La prueba737 aisló el prompt dentro de K2 en57 pares con los mismos hechos, plantilla, backend y muestreo. Hubo25 aciertos compartidos,14 sólo con BAXY,3 sólo con la petición directa y15 sin respuesta acreditable en ninguno. El prompt mejora el agregado y perjudica casos concretos. Esa prueba no evalúa todos los filtros del producto ni vuelve a comparar ambos modelos. [Informe de prompt737](../FACTS_PROMPT737/REPORT.md).

786–788 investigan presupuesto y validadores de BAXY con Qwen. **No se utilizan para descartar K2 o proclamar un modelo ganador.** La comparación sigue separando capacidad nativa, cambio debido al prompt y cambio debido a transporte, proyección, verificadores y plazos. Las recetas nativas se mantienen como controles, sin exigir a K2 imitar la redacción de Qwen.

El siguiente bloqueo es la cobertura de identidades y multiplicidad en `window_prose_facts.py`, antes de adoptar787. Después quedan los vetos de los cuatro casos correctos. No hay inferencia ni validación activa al registrar este resultado. C03 sigue activo:28 requisitos cubiertos,714 abiertos,0 no aplicables; esta tanda no concede cobertura, UI, voz ni aceptación de reserva. `RESULT.json` conserva el estado previo a adjudicar y `ADJUDICATION.json` la revisión posterior.
