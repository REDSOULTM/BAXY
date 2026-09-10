# K2, Qwen y el efecto de BAXY

Tu objeción era correcta: un modelo puede funcionar bien por separado y empeorar al recibir instrucciones, transformaciones o ajustes pensados para otro. La comparación inicial usaba servidores nativos, pero enviaba instrucciones de BAXY. No debía presentarla como una referencia independiente del modelo.

Corregí esa parte y conservé los resultados anteriores con la rectificación visible. Ahora hay **300 respuestas independientes** y **40 nuevas respuestas emparejadas** para medir una instrucción. No he cambiado el modelo instalado ni he cerrado C03.

## Qué probé realmente

Cada perfil recibió las mismas 50 tareas nuevas, sin instrucciones de BAXY, catálogo de herramientas ni formato de respuesta impuesto. Había español, inglés y mezcla, con criterios definidos antes de ejecutar. Usé la plantilla del modelo, sus ajustes de muestreo documentados y declaré la cuantización y el backend. Revisé todas las respuestas completas, incluidos fallos, texto incoherente y finales vacíos.

También separé las referencias con margen largo de razonamiento de los perfiles prácticos para este PC. IFM recomienda razonamiento alto y al menos 32.768 tokens de salida; por eso no descarté K2 por fallar con razonamiento reducido. Medí ambos y comprobé sus ajustes efectivos. [K2 pequeño](https://huggingface.co/IFM/K2-Horizon-0.9B), [K2 grande](https://huggingface.co/IFM/K2-Horizon-3.7B).

| Perfil | Casos que cumplen | Mediana hasta terminar | Pico VRAM | Pico RAM |
|---|---:|---:|---:|---:|
| Qwen Q4, referencia larga | 40/50 | 3,33 s | 2,58 GiB | 2,19 GiB |
| K2 pequeño BF16, razonamiento alto | 33/50 | 4,59 s | 3,10 GiB | 0,67 GiB |
| K2 grande Q4, referencia larga | 39/50 | 21,91 s | 2,99 GiB | 3,46 GiB |
| Qwen Q4, perfil práctico | 40/50 | 1,35 s | 3,09 GiB | 0,70 GiB |
| K2 grande Q4, práctico con razonamiento reducido | 28/50 | 1,90 s | 3,36 GiB | 0,77 GiB |
| K2 grande Q4, práctico con razonamiento alto | 38/50 | 8,83 s | 3,36 GiB | 0,77 GiB |

**Estos consumos corresponden al servidor del modelo, no a todo BAXY.** En las referencias largas de los modelos grandes, parte de la memoria de atención se trasladó a RAM. Los prácticos la mantuvieron en GPU. Los picos son muestras cada 250 ms; no una garantía sobre intervalos más breves.

La espera también importa: el primer texto de Qwen práctico llegó en una mediana de 0,047 s; K2 grande práctico con razonamiento alto, en 6,08 s. Son tiempos del stream del servidor, todavía no de pantalla ni voz. El pequeño BF16 tuvo dos finales vacíos; uno agotó 32.768 tokens tras 511 s. Se cuentan como fallos.

K2 grande práctico resolvió **seis preguntas que Qwen falló**, pero falló **ocho que Qwen resolvió**. Una diferencia de dos casos no prueba una superioridad universal. En los 30 casos españoles, esos perfiles cumplieron 22 y 25 respectivamente. Las discrepancias interpretativas de uno de los revisores están documentadas; no se ocultaron para favorecer un resultado.

## Qué pasó al quitar una instrucción de BAXY

Comparé 20 selectores completos por modelo, con el mismo catálogo, historia, pesos y parámetros. La única diferencia en cada petición fue quitar un mensaje de sistema. Los controles con la instrucción ya existían y se conservaron por hash.

| Modelo | Con la instrucción | Sin ella |
|---|---:|---:|
| Qwen | 7/20 | 5/20 |
| K2 grande, razonamiento alto | 10/20 | 8/20 |

El efecto fue mixto. **Al quitarla, K2 recuperó un caso de hora**: ahí sí apareció un perjuicio asociado a esa instrucción. También corrigió una abstención, pero perdió cuatro casos. Ambos modelos empezaron a pedir una lectura actual ante una frase que sólo hablaba de ayer. Quitar toda esa política no mejoró el conjunto.

Uno de los casos carecía de herramienta para comprobar Internet. La abstención de K2 cuenta como respetar ese límite, **no como haber comprobado Internet**. El catálogo y el historial seguían presentes: esta prueba no mide todas las capas de BAXY. Usa controles históricos de una semilla; no es una réplica aleatorizada.

## Qué decisión tomo y qué sigue

**Mantengo Qwen como candidato de trabajo para continuar C03.** K2 no mostró una mejora conjunta de calidad, español, latencia y memoria que justifique sustituirlo en estos perfiles locales. Eso no significa que Qwen ya cumpla C03, ni que K2 sea un mal modelo en general. Los errores compartidos siguen siendo bloqueantes del producto.

En el código encontré adaptaciones reales motivadas por Qwen: la unión de varios mensajes de sistema antes del envío y un arranque del servidor con razonamiento desactivado. Si se integra otro modelo, hay que verificar esas decisiones. Las pruebas independientes omitieron esas transformaciones; no bastaría con cambiar el GGUF.

La comparación termina aquí y retomo la revisión de los resultados de producto 694 y la posible adopción de la corrección compartida 693. Después siguen cobertura generalizada de la encuesta, ocho rutas, reserva de cien turnos, recuperación de fallos, pantalla/voz, loopback/AEC, recursos del producto completo y validación final. **El registro sigue en 26 requisitos cubiertos y 716 abiertos de 742.** Las pruebas de modelos no aumentan esa cobertura.

Los resultados describen nuestras ejecuciones locales de llama.cpp, incluidas las correcciones de compatibilidad de K2. Verificar tokenizador y plantilla no demuestra equivalencia completa con la ejecución BF16 oficial en otro backend. Por eso no atribuyo automáticamente cada fallo observado a los pesos originales.

[Detalle de las 300 respuestas originales y sus perfiles](../K2_HORIZON_NATIVE699/REPORTE699.md) · [Comparación de la instrucción y adjudicaciones](REPORTE700.md). Las respuestas sintéticas completas están enlazadas en el primero. Las historias privadas del selector permanecen en LOCALAPPDATA y no se publican en Git.
