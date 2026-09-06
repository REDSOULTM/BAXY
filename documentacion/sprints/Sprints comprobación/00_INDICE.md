# Sprints comprobación — recuperar el cumplimiento de 01–09

**Campaña en ejecución. C01/C02 cerrados; C03 en curso al revisar el 2026-09-04.**
Estado vivo: [checkpoint](05_ESTADO_Y_CONTINUACION.md).
Replanteamiento inmediato: [mensaje para C03](07_REPLANTEAR_C03.md).
Destino: Grok 4.6 High; tramos pequeños según el [protocolo](../00_PROTOCOLO_EJECUCION.md).
Esta campaña se intercala antes de continuar el Goal 10 original.

## Resultado exigido

BAXY debe cumplir los compromisos de los goals 01–09, incluidos 03B/03C y las
decisiones pertinentes de 09.5, sobre una versión actual reproducible. El cierre
exige pruebas de conducta por la misma entrada de producto del usuario, efectos
observados y respuestas finales correctas. Un informe histórico o Full verde por
sí solo no habilita el 10.

La revisión actual modifica el plan; Grok continúa la implementación C03.
Un solo Cxx activo, reanudable entre sesiones; no hay dos escritores de producto.
No se reinician C01/C02 ni se hereda un pass contradicho por evidencia posterior.

## Orden de ejecución

| Orden | Prompt ejecutable | Qué debe dejar funcionando |
|---|---|---|
| 1 | [C01 — Entrada compartida](C01_ENTRADA_COMPARTIDA.md) | Agente y usuario recorren la misma admisión, estado, ejecución y salida; conductor sin ventana y prueba de equivalencia. |
| 2 | [C02 — Herencia y base](C02_HERENCIA_Y_BASE.md) | Integración heredada coherente, runtime reproducible y Full sin rojos ocultos. |
| 3 | [C03 — Respuesta veraz](C03_RESPUESTA_VERAZ.md) | La persona recibe los hechos verificados, prosa natural y un cierre honesto en cada turno. |
| 4 | [C04 — Operaciones y confirmación](C04_OPERACIONES_Y_CONFIRMACION.md) | Efectos reales, postcondiciones independientes y permisos ligados a la invocación. |
| 5 | [C05 — Misiones y continuidad](C05_MISIONES_Y_CONTINUIDAD.md) | Misiones completas; cancelar, cambiar de tema y Nueva sesión no dejan al usuario atrapado. |
| 6 | [C06 — Comprensión y cobertura](C06_COMPRENSION_Y_COBERTURA.md) | Peticiones frescas bien resueltas, argumentos correctos y cobertura preservada. |
| 7 | [C07 — Señal y recursos](C07_SENAL_Y_RECURSOS.md) | Primera señal y respuesta final dentro del contrato, sin plantillas ni consumo oculto. |
| 8 | [C08 — Voz y accesibilidad](C08_VOZ_Y_ACCESIBILIDAD.md) | Escucha, comprensión, habla e interrupción reales; capacidades accesibles por voz. |
| 9 | [C09 — Admisión al Goal 10](C09_ADMISION_GOAL_10.md) | Revalidación conjunta sobre un mismo commit y certificado LISTO_PARA_GOAL_10. |

Los Cxx son tandas de reparación; no equivalen uno a uno a los goals antiguos.
Un Cxx puede terminar su responsabilidad mientras otras filas del goal original
siguen asignadas a tandas posteriores. **El original sólo queda comprobado cuando
todas sus filas están cumplidas y C09 reproduce el conjunto.** Un fallo de la tanda
actual no se aplaza para poder lanzar la siguiente.

## Cómo lanzar

En una sesión nueva, selecciona Grok 4.6 y High, abre este repositorio en main y
pega entero el Cxx correspondiente como objetivo persistente. El siguiente pendiente de esta máquina es
C03; en otra copia comprueba el checkpoint. Cada Cxx incorpora por referencia el [contrato de campaña](01_CONTRATO_DE_CAMPANA.md)
y el [protocolo Grok](02_PROTOCOLO_GROK_46_500K.md): forman parte de sus instrucciones.

Si cambias de agente o cuenta, conserva la misma carpeta de trabajo y retoma el
mismo Cxx con el [relevo entre agentes](06_RELEVO_ENTRE_AGENTES.md). No hace falta
el chat anterior. El relevo debe comprobar el estado guardado antes de continuar.

Lee sólo esas reglas, las filas asignadas y las fuentes necesarias. No pegues todos
los Cxx ni toda la biblioteca dentro de la misma ventana. Un checkpoint conserva
la tarea; no convierte un fallo en cierre. No continúes 10.7 porque el índice antiguo
lo llame siguiente: la admisión de esta campaña es un prerrequisito nuevo.

## Documentos de control

- [Contrato y prueba de entrada compartida](01_CONTRATO_DE_CAMPANA.md).
- [Grok 4.6 / High / 500K](02_PROTOCOLO_GROK_46_500K.md).
- [Matriz completa de criterios originales](03_MATRIZ_DE_CRITERIOS.md).
- [Casos obligatorios de regresión](04_CASOS_OBLIGATORIOS.md).
- [Estado y continuación](05_ESTADO_Y_CONTINUACION.md).
- [Relevo entre agentes: instrucciones y bloque para pegar](06_RELEVO_ENTRE_AGENTES.md).

Punto de partida: [auditoría del 2026-09-03](../../AUDITORIA_GOALS_01_10_2026-09-03.md),
commit b2505da. Sus seis turnos son regresiones conocidas, no un examen suficiente.
El informe registró Full rojo, respuesta falsa de la hora y secuestro de turnos
por un app.open incierto. C02 vuelve a medir el árbol que encuentre.

## Frontera con el Goal 10 y producto final

Esta campaña restaura prerrequisitos; no declara cumplidos los objetivos propios
de uso diario, familias y 200 turnos de 10.18. Sólo C09 puede habilitar retomarlos.
Una limitación medida, un entorno pendiente o un criterio no ejecutado mantiene
**NO_LISTO**. Los cierres anteriores quedan como historia; no se borran ni se usan
para omitir la reparación.

El cierre de 11 entrega un candidato validado. La [fase 12](../12_PRODUCTO_FINAL.md)
certifica instalación, hardware objetivo y entrega antes de declarar BAXY definitivo.
