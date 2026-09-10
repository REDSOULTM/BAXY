# Modelos e integración: alcance de las comparaciones y resultado 785

Una respuesta obtenida por la API del modelo todavía puede estar condicionada por BAXY. La separación se determina mirando los mensajes y las transformaciones aplicadas. Una regla sin nombre de modelo también puede favorecer las formulaciones con las que se desarrolló. No se ha demostrado que todas las reglas estén adaptadas a Qwen; sí se han demostrado pérdidas de integración.

## Qué se comparó realmente

| Estudio | Intervención y corpus | Qué permite concluir |
|---|---|---|
| 696–698 | 860 respuestas que conservaban instrucciones de BAXY | No constituyen una comparación nativa limpia. |
| [699](../K2_HORIZON_NATIVE699/REPORTE699.md) | Las mismas 50 tareas completas en seis perfiles: 300 respuestas, sin system, herramientas, schema ni filtros de BAXY; plantilla y receta propias | Compara perfiles locales independientes de BAXY. No divide las preguntas en dos mitades. |
| [737](../FACTS_PROMPT737/REPORT.md) | 57 pares con el mismo K2, hechos, backend, plantilla y muestreo; petición directa frente al prompt de redacción de BAXY | Aísla el efecto de ese prompt: 25 aciertos compartidos, 14 sólo con BAXY, 3 sólo directos y 15 pares sin respuesta acreditable. No compara Qwen contra K2. |
| 785, este informe | 50 casos con Qwen y tres configuraciones de muestreo; mismos mensajes BAXY y límite de salida | Diagnostica el muestreo del primer borrador. No mide capacidad nativa, producto completo ni superioridad frente a K2. |

699 encontró 40/50 en Qwen Q4 práctico y 38/50 en K2 3.7 Q4 high práctico: K2 ganó seis pares y perdió ocho. Eso no demuestra un ganador general. Los grandes están cuantizados, los backends difieren y su equivalencia con las referencias originales BF16 no está demostrada. Las referencias con mayor margen de salida están separadas de los perfiles prácticos. Las instrucciones originales del modelo y su plantilla se conservan; no se llaman «originales sin modificar» a los pesos Q4.

737 confirma el riesgo indicado por el dueño: tres respuestas acreditables directas se perdieron al añadir el prompt de BAXY. También hubo mejoras. La decisión se toma por la primera capa que pierde la conducta y por la respuesta completa, sin culpar al modelo de un veto, dato insuficiente, recorte o error de transporte.

## Resultado de 785

Se completaron las 150 peticiones: seis casos históricos de desarrollo, 24 inventarios sintéticos y 20 casos sintéticos de memoria. No son material de reserva. Los tres brazos recibieron los mismos 50 casos, mensajes y hechos. El orden se rotó por caso. Sólo se cambió la receta de muestreo; el presupuesto de 256 tokens quedó fijo para aislar ese factor.

| Brazo | Respuestas completas acreditadas | Fallos | Cortes por límite | Final p50 | Final p95 |
|---|---:|---:|---:|---:|---:|
| A: perfil registrado, temperatura 0 | 30/50 | 20 | 6 | 0,477 s | 3,500 s |
| B: receta Qwen, semilla 0 | 32/50 | 18 | 5 | 0,477 s | 3,500 s |
| C: receta Qwen, semilla 17 | 33/50 | 17 | 6 | 0,469 s | 3,500 s |

B tiene cuatro mejoras y dos regresiones frente a A; C tiene tres mejoras y ninguna regresión en esta pasada. No se elige la semilla con mejor resultado. Dos semillas no demuestran estabilidad ni justifican adoptar un perfil global.

Los parámetros efectivos se comprobaron en los slots de las 150 respuestas, con tolerancia de representación float32: A usó T0, top-k 40, top-p 0,95 y min-p 0,05; B/C usaron T0,7, top-k 20, top-p 0,8 y min-p 0, con semillas 0/17. Todos tuvieron penalizaciones neutras, contexto de 4096 por slot, salida máxima 256 y cero tokens de prompt reutilizados. Los defaults globales de `/props` no sustituyen esa observación por petición. Véase [EFFECTIVE_PARAMS.json](EFFECTIVE_PARAMS.json).

La receta B/C procede de la [tarjeta oficial de Qwen](https://huggingface.co/Qwen/Qwen3-4B-Instruct-2507#best-practices), revisada el 10 de septiembre de 2026. Mantener aquí 256 tokens no reproduce su referencia de 16384: ésta es una prueba controlada del muestreo con el presupuesto del producto. No se usa para descartar el modelo original.

## Causas conservadas

- Diecisiete respuestas se cortaron a 256 tokens en mitad de una identidad del inventario. El límite de la integración impidió observar una respuesta completa. Ese corte no demuestra que el modelo sea incapaz de terminarla con margen suficiente.
- En los 72 inventarios sintéticos hubo 24 fallos de contenido: cortes u omisiones de multiplicidad. Además hubo cinco respuestas con identidades/cantidades correctas pero sujeto incorrecto («Tengo» o «I don't have» para las ventanas del usuario): 43/72 respuestas completas acreditables.
- Persisten intercambios entre RAM instalada, utilizable y disponible. En H0539, B/C cambian la etiqueta equivocada de «disponible» a «instalada»; no reparan el valor semántico. Con capacidad instalada desconocida, B/C la inventan en memory785-5-1.
- Las cifras de memory785-3-1 y 4-1 son correctas; su fallo independiente es atribuir la RAM al narrador. No se cuentan como errores numéricos.
- «Disponible en total» resulta ambiguo en H0655 B/C y memory785-5-1 A. Se conservan sus componentes correctos y la sensibilidad interpretativa; la atribución al narrador ya impide acreditar la respuesta completa. No se afirma que inventen todos los números.
- Los tres brazos conservan «Marka» para la hora correcta. No se añade un reemplazo literal ni se atribuye la errata al modelo sin el contexto de BAXY.

La adjudicación leyó las respuestas completas; no usó el validador de BAXY como juez. Los títulos identifican ventanas y se admite el proceso si el título está vacío. No se exige metadato de proceso no solicitado, pero sí la multiplicidad exacta. La frescura de la observación está respaldada; la edad de apertura de una ventana no. El sujeto se evalúa por separado, con el mismo criterio ya aplicado a CPU/batería. Errores menores de concordancia comprensibles no reciben una penalización nueva.

## Recursos y evidencia

La campaña duró 178,547 s. Pico observado: 3499,56 MiB de VRAM dedicada y 723,36 MiB de RAM residente del árbol del servidor. Se muestreó cada 250 ms; pueden faltar picos más breves. No incluye interfaz, voz ni el resto de BAXY, por lo que no acredita consumo conjunto ni un mínimo realista de memoria. Mediana de generación: aproximadamente 86 tokens/s en los tres brazos. Los tiempos de la tabla incluyen respuestas fallidas y no son latencia de pantalla o voz.

El proceso terminó y la sesión 10660 fue recogida con código 0. Sin violaciones de recursos; driver y diez huellas de fuente intactos. `RESULT.json` conserva el estado anterior a la revisión, `quality_adjudicated=false`; [ADJUDICATION.json](ADJUDICATION.json) añade la revisión posterior sin reescribir la corrida. El registrador `scratchpad/c03-record-prose-sampling785.py` terminó con código 0 y verificó las 150 correspondencias, parámetros, hashes y paridad de mensajes.

Las [132 respuestas sintéticas completas](RESPUESTAS_SINTETICAS.md) son públicas. Las 150 respuestas, sus preguntas, hechos y payloads completos permanecen en `%LOCALAPPDATA%/BAXY/C03-prose-sampling785-private/`: `RESPUESTAS.md`, `cases.json`, `planned.json` y `results.json`. [PRIVATE_PINS.json](PRIVATE_PINS.json) registra sus huellas. Los textos históricos del escritorio no se copian al repositorio público.

## Decisión y continuación

No se cambia modelo, manifiesto, prompt, validador, presupuesto ni sampler. La mejora de dos o tres casos no resuelve la categoría, y cambiar de semilla no corrige los cortes impuestos por BAXY. Antes de otra tanda integrada, aislar el presupuesto de salida en el inventario conservando los mismos hechos, modelo, receta y criterio, y medir respuesta completa, latencia y recursos. No añadir otra frase de prompt: los controles 754–759 y las repeticiones 768/771 ya muestran sus límites. Conservar los casos nativos y las pérdidas de integración como controles separados para ambos modelos.

Sin fuente productiva editada no corresponde repetir suites ni Full. Continúa publicada la fuente 783, commit `63fc4f56f4a90fb434773b58fefffbfbec3c1e07`, con su validación registrada. C03 sigue activo: 28 requisitos cubiertos, 714 abiertos y 0 no aplicables; esta tanda no concede cobertura. Siguen pendientes generalización, reserva, UI real, loopback/AEC, recursos conjuntos, matriz/continuidad y Full final. No hay una decisión pendiente del dueño.
