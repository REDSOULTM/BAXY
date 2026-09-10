# El límite de salida cortaba inventarios correctos

Con los mismos 50 casos y mensajes de 785, cambiar únicamente el máximo de salida de 256 a 512 tokens permite completar correctamente los seis inventarios que se cortaban. Las otras 44 respuestas permanecen idénticas. Es una causa de integración demostrada; no una comparación nativa ni una promoción del modelo.

| Medida | A: máximo 256 | B: máximo 512 |
|---|---:|---:|
| Respuestas completas acreditadas | 30/50 | 36/50 |
| Fallos | 20 | 14 |
| Cortes por límite | 6 | 0 |
| Final p50 | 0,492 s | 0,484 s |
| Final más lento | 3,516 s | 4,547 s |
| Máximo de tokens generados | 256 | 340 |

Se ejecutaron 100 peticiones, alternando los brazos. Las 50 respuestas de A coinciden literalmente con 785A; las seis nuevas de B prolongan el prefijo exacto que antes quedaba cortado. Se conservaron preguntas, hechos, instrucciones, muestreo, backend, modelo, contexto, caché y geometría del servidor. Los parámetros efectivos de los 100 slots confirman que sólo cambió el presupuesto de salida. [Paridad y parámetros](PARITY.json).

El revisor principal leyó los seis finales completos contra las veinte identidades y sus repeticiones. Una revisión independiente confirmó el resultado. Los inventarios de total conocido distinguen 20 entradas de 25 ventanas; los de total desconocido distinguen las 25 observadas del total del inventario, que no se inventa. No añaden edad de apertura, estado de procesos ni otra propiedad no medida. El resto hereda la adjudicación de 785 por igualdad literal y de datos, sin reinterpretarla. [Decisiones](ADJUDICATION.json), [seis pares completos](RESPUESTAS_CAMBIADAS.md).

Los seis finales nuevos tardaron entre 4,437 y 4,547 segundos. Ese intervalo supera el antiguo límite ordinario de cuatro segundos, pero cabe en los nueve ya establecidos para inventarios densos por C#764. La tanda conserva una observación de hasta 15 segundos para distinguir la terminación del modelo del plazo del producto; no cambia ese plazo.

Duración total: 125,797 s. Pico observado del árbol del servidor: 3499,56 MiB de VRAM dedicada y 724,80 MiB de RAM residente, con muestras cada 250 ms. Puede haber picos más breves. Son recursos del servidor; no incluyen BAXY completo, pantalla ni voz. El proceso terminó y la sesión 78684 se recogió con código 0. Guardas, driver y diez huellas de fuente permanecieron intactos durante la corrida.

Los 14 fallos restantes se conservan: esta intervención no corrige el sujeto de algunas respuestas de RAM/ventanas, sus etiquetas, la errata del reloj ni las listas que omiten repeticiones sin llegar al límite. No se concede cobertura de encuesta ni se adopta fuente desde un borrador aislado.

La siguiente comprobación pasa los finales por el compositor real. La reproducción controlada de ese paso encontró que cinco respuestas correctas eran rechazadas por el verificador de cantidades/alcance: no reconocer dos cantidades como declaración de subconjunto; ligar un número a un encabezado de lista lejano; interpretar «20 de las 25 observadas» como afirmación de un total desconocido. El candidato 787 repara esas causas en el verificador existente y reutiliza el presupuesto denso, sin añadir instrucciones. Su aceptación requiere las pruebas dueñas, integridad, Fast y la ejecución real del compositor.

`RESULT.json` conserva el resultado previo a adjudicar; `ADJUDICATION.json` registra la revisión posterior. Los 100 mensajes y respuestas completos permanecen en `%LOCALAPPDATA%/BAXY/C03-inventory-budget786-private/RESPUESTAS.md`; los payloads en `planned.json` y las respuestas de API en `results.json`, con huellas en `PRIVATE_PINS.json`. Los ejemplos públicos son sintéticos. C03 sigue activo, con 28 requisitos cubiertos, 714 abiertos y 0 no aplicables.
