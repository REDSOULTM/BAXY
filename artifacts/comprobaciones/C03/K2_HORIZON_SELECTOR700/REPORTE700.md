# Efecto de quitar una instrucción de BAXY

En esta categoría, quitar la política del selector empeoró el recuento de ambos perfiles: Qwen pasó de 7/20 a 5/20 y K2 grande high de 10/20 a 8/20. El efecto fue mixto: K2 recuperó una selección de hora y una abstención correcta, pero perdió cuatro casos. Es evidencia de que una instrucción puede perjudicar casos concretos; quitarla no fue una solución general. No demuestra que todas las instrucciones de BAXY ayuden ni que ninguna favorezca a Qwen.

Se reutilizaron los20 controles completos de cada perfil y se hicieron40 nuevas llamadas. El runner verificó pesos, backend y paquetes por hash, comando idéntico salvo puerto/log y cuerpo enviado idéntico salvo eliminar el primer system de1056caracteres. Muestreo propio documentado y K2 high; mismo orden/seed. El catálogo y las historias siguen presentes. Estos son controles históricos de una semilla; no una réplica aleatorizada ni una prueba de todo el producto.

| Modelo | Con política | Sin política | Mejoras | Regresiones |
|---|---:|---:|---:|---:|
| qwen | 7/20 | 5/20 | 0 | 2 |
| k2 | 10/20 | 8/20 | 2 | 4 |

La pérdida compartida más clara es seleccionar una lectura actual cuando la persona sólo habla de lo que hizo ayer. En K2, quitar la política también recuperó una selección de hora, pero perdió lecturas de disco/RAM y añadió una operación no solicitada a la lista de procesos. IDs y razones de cada pareja en SUMMARY700.json.

Uno de los20 casos pide Internet pero el catálogo suministrado carece de esa operación. K2 sin política se abstiene sin inventar datos: eso cuenta como respetar el límite, no como comprobar Internet. Su8/20 incluye esa abstención; entre los19 con capacidad disponible cumple7/19. Qwen sin política inventa conexión y falla ese caso.

Las llamadas usan argumentos vacíos porque se trata de selección; no prueban extracción, autorización, efectos de Windows, GUI o voz. Los finales vacíos de K2 H0532/H0499 no se convierten en respuestas extrayendo razonamiento. Las respuestas completas y las historias quedan en RESPUESTAS700_PRIVADO.md de cada corrida en LOCALAPPDATA; los archivos públicos contienen IDs, adjudicación y hashes.

Esto se une a las300 respuestas originales699. Qwen sigue como candidato de trabajo: K2 no ha demostrado una mejora conjunta de calidad, español, latencia y recursos que justifique sustituirlo en estos perfiles locales. Esa decisión no acepta a Qwen para C03 ni descarta universalmente la familia K2. El trabajo de producto debe continuar reparando los fallos compartidos y midiendo cada transformación antes de adoptar cambios.

Acoplamientos reales aún pendientes de probar si se promueve otro modelo: llm.py5847–5896 fusiona prefijos system por compatibilidad Qwen3.5; el arranque productivo configura reasoning off. Las APIs aisladas no ejercitan esa fusión, shortlist, reanálisis, argumentos, kernel/providers ni salida de escritorio/voz. No se debe cambiar sólo el GGUF y trasladar sin verificar esas decisiones al nuevo modelo.

C03 permanece activo. Encuesta742/rev1248:26cubiertos,716abiertos,0noaplicables. Esta comparación no suma cobertura.
