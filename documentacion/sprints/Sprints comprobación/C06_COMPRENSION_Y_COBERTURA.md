# C06 — Entender peticiones nuevas sin perder cobertura

**Ejecutable: Grok 4.6 High; un goal con tramos reanudables.**
Predecesor: C05 cumplido. Incorpora [contrato](01_CONTRATO_DE_CAMPANA.md) y
[protocolo vigente](../00_PROTOCOLO_EJECUCION.md).

## Objetivo

Cumple comprensión y alcance de 03/03B/03C sobre el producto integrado.
Una operación bien elegida que se pierde en argumentos, política, ejecución,
composición o publicación no es una tarea cumplida.

## Lecturas y owners

Filas propias G03/G03B/G03C, puerta de dominio de G04 y casos R01/R02/R05/R11/R13.
Mapa de comprensión/herencia, libro de cobertura y rechazos medidos. Después,
router, family_classifier, semantic_family_arbiter, catálogo, argumentos y
fronteras que muestre la traza; no empieces añadiendo otro router.

## Tramos de ejecución

A: baseline y contrato/argumentos del modelo promovido en C03. B: una causa de
pérdida por ventana, hasta 20 casos. C: memoria/privacidad. D: las tres corridas
preregistradas, bancos, cobertura y cierre. No cargues los 480 casos al chat.
Si falla una aceptación, conserva el intento y su causa; no relances tres
corridas enteras antes de resolver el panel diagnóstico.

## Trabajo

1. Obtén población y baseline antes de editar. Separa las métricas del decisor,
   argumentos, policy, final publicado y efecto real. Congela el oráculo:
   correcto puede ser ejecutar lo pedido o aclarar cuando la entrada lo exige,
   nunca cambiar una tarea realizable por una charla para contar un acierto.
2. Reproduce el corpus histórico con scorer y bytes originales como regresión
   diagnóstica: ≥90 %, mediana ≥112/124 en tres corridas y ≤5/36 acted en cada
   corrida. Las filas estables nombradas en 03B/03C se resuelven explícitamente.
   No redefinas acted ni conviertas los fallos en exclusiones.
3. Ejecuta además aceptación fresca por C01: al menos 124 entradas in-catalog
   y 36 fuera de catálogo, ES/EN/spanglish, con variantes de argumentos,
   ambigüedad, contexto y objetivos compuestos. Tres corridas preregistradas,
   ≥90 % de resolución correcta por corrida, con todos los casos obligatorios
   correctos. Usa otra población fresca después de reparar con una ya vista.
4. El fuera de catálogo debe llegar sin candidatos operativos; no emitir efectos
   no pedidos. El acted histórico permitido es métrica del decisor, no permiso
   para causar hasta cinco efectos reales no solicitados.
5. Repara la causa que domina la pérdida: evita vetos que convierten «no pude
   identificar» en «BAXY no sabe hacerlo», argumentos sin grounding y errores
   de conversación. Resuelve las 17 filas del contrato de 03B y las estables
   de 03C con evidencia actual; no las empujes a otro goal.
6. Mide cobertura y cuenta antes/después. Conserva 169/158/31 y su libro como
   referencia del 03C; cualquier catálogo actual diferente necesita conciliación
   fila por fila sin pérdida de capacidad. Compara la forma del catálogo sólo
   si bloquea, con efecto sobre tareas completas y tokens.
7. Mide sobrecarga y latencia junto al acierto. C07 posee los umbrales temporales
   y VRAM finales. Declara modelo/runtime/hashes y actualiza costuras afectadas;
   ningún corpus de aceptación ni veredicto entra al runtime para resolverlo.
8. Comprueba memoria visible/editable/borrable con datos ficticios por la misma
   entrada. Verifica la frontera de privacidad con observación de solicitudes
   salientes: puede consultar información externa, pero no enviar el contenido
   privado de la conversación, pantalla, archivos o memoria. El conductor no
   añade servicios externos para resolver una tarea que BAXY debía hacer localmente.

## Cierre obligatorio

- [ ] Scorer histórico preservado, tres corridas con umbrales originales y causas.
- [ ] Aceptación fresca pública ≥90 % por corrida, argumentos puntuados aparte,
      casos obligatorios correctos y cero efectos no pedidos.
- [ ] Las filas nominadas del contrato y la puerta de dominio están resueltas;
      ninguna capacidad desapareció para mejorar el porcentaje.
- [ ] Cobertura/cuenta, bancos compuestos, coste y latencia antes/después publicados.
- [ ] El LLM permanece fuera del proceso principal y declarado en el manifiesto;
      no existe una vía privilegiada para los textos del agente.
- [ ] Memoria y privacidad comprobadas con datos de prueba, cambios observados y
      evidencia de la frontera de salida de información; no sólo una promesa de prompt.
- [ ] Todas las filas propias tienen evidencia; Full verde; código, datos y
      costuras propios publicados sin incorporar holdout a entrenamiento.

Evidencia: artifacts/comprobaciones/C06/. Siguiente: C07.
