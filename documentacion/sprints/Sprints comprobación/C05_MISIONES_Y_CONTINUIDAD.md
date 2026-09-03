# C05 — Misiones completas y una conversación que puede continuar

**Ejecutable: Grok 4.6 High; contexto de 500K; un solo goal persistente.**
Predecesor: C04 cumplido. Incorpora [contrato](01_CONTRATO_DE_CAMPANA.md) y
[protocolo 500K](02_PROTOCOLO_GROK_46_500K.md).

## Objetivo

BAXY debe encadenar operaciones verificadas y recuperarse de errores sin
apropiarse de las siguientes peticiones. Cambiar de tema, cancelar y Nueva sesión
son conductas del producto, con evidencia conservada y una sesión utilizable.

## Lecturas y owners

Filas G07, bancos de 03B/03C y casos R04/R05/R06/R09/R11/R12/R16.
MainWindowViewModel: pendingMindPlan, HandlePendingMindPlanAsync,
StartNewUiSession; stores durables, MissionEngine, planner y capacidad genérica
de interacción con apps. Localiza las piezas heredadas de UIA/OCR/visión.
R6 y Steam históricos sirven de regresión; volver a leer su JSON no los ejecuta.

## Trabajo

1. Reproduce la secuencia exacta que dejó Calculadora: efecto incierto → chiste
   → consulta de red → Nueva sesión → hora y audio. No limpies el store entre
   entradas. Conserva qué turnos llegan al decisor y qué estado los intercepta.
2. Separa un nuevo objetivo de una respuesta que continúa una aclaración o
   confirmación. Mantén memoria útil y evidencia de efectos inciertos sin
   secuestrar entradas ajenas. Usa el mecanismo mínimo común, no otra capa
   de clasificación de frases añadida sobre la existente.
3. Define y cumple los efectos públicos de cancelar, Nueva sesión y reiniciar.
   Cancela trabajo propio cuando procede, conserva identidad y journal del
   efecto incierto, y permite una nueva petición. No purgues evidencia para
   aparentar que la sesión se recuperó.
4. Corrige composición de planes, paso a paso, interrupción, fallos parciales,
   recuperación tras caída y reanudación sin repetición indebida.
   El resumen no puede afirmar que se completó el objetivo con pasos pendientes.
5. Ejecuta misiones reales por C01. Incluye «Abre Steam y ve a la biblioteca»
   sobre Steam, notas/archivos de prueba, ventana/audio y objetivos mixtos.
   UIA/OCR/visión debe resolver la capacidad genérica, sin recetas por nombre de app.
6. Congela al menos 30 misiones frescas variadas y 20 secuencias de continuidad.
   La tasa de misiones completas y verificadas debe ser ≥90 %; los casos
   obligatorios y las secuencias de recuperación deben pasar todos.
   Ningún porcentaje excusa un defecto reproducible de una capacidad comprometida.
7. Reejecuta el banco histórico compuesto: no baja de su baseline y conserva
   como mínimo 6/15 misiones y 15/32 pasos de 03C. Los bancos internos de diagnóstico
   no sustituyen las misiones públicas. Mide silencios y deriva a C07 su evaluación
   temporal final, sin ocultar el estado actual.

## Cierre obligatorio

- [ ] La secuencia R03–R06 ya no captura objetivos nuevos; Nueva sesión y reinicio
      tienen semántica comprobada sin borrar incertidumbre de efectos.
- [ ] Aclaración, confirmación, cancelación y referencia al turno anterior
      funcionan sin confundirlas con un cambio de tema.
- [ ] ≥90 % de las misiones frescas completas; cada paso observado/verificado;
      cero pasos huérfanos o ajenos al plan.
- [ ] Todas las secuencias obligatorias de continuidad pasan sin reset privado
      del harness; no hay duplicados tras timeout/reinicio.
- [ ] Steam real y cascada genérica demostrados; bancos preservados y causas publicadas.
- [ ] Respuestas finales y resúmenes cumplen tres ceros; las métricas temporales
      están registradas para C07 y C09.
- [ ] Filas propias cumplidas, Full verde, estado/artefactos/código publicados.

Evidencia: artifacts/comprobaciones/C05/. Siguiente: C06.
