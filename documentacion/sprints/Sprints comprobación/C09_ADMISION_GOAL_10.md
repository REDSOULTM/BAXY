# C09 — Demostrar que BAXY puede empezar el Goal 10

**Ejecutable: Grok 4.6 High; contexto de 500K; un solo goal persistente.**
Predecesores: C01–C08 cumplidos. Incorpora [contrato](01_CONTRATO_DE_CAMPANA.md) y
[protocolo 500K](02_PROTOCOLO_GROK_46_500K.md).

## Objetivo único

Emite LISTO_PARA_GOAL_10 sólo cuando todos los compromisos de 01–09 estén
demostrados sobre una misma versión final y por la entrada de producto.
Si la revalidación encuentra un defecto, repáralo en su owner y repite lo afectado
dentro de esta meta hasta cumplir. No entregues una auditoría con pendientes
como si fuera admisión, ni empieces el Goal 10 durante C09.

## Lecturas

La matriz completa, los criterios originales enlazados, Identidad, estado y
handoffs C01–C08. Abre evidencia por ruta, no todos los logs.
Distingue qué commit, runtime y corpus acreditaba cada cierre.

## Trabajo

1. Comprueba cobertura de cada criterio original y de los requisitos añadidos
   de entrada/continuidad. Ninguna fila puede desaparecer, fusionarse hasta
   perder su condición, o pasar porque su Markdown lleva una marca antigua.
2. Congela código, assets/runtime, configuración, corpus y oráculos de la
   versión candidata. La revisión final no se hace mezclando éxitos de distintos
   commits o modelos. Los artefactos históricos conservan su identidad.
3. Ejecuta los casos obligatorios R01–R16 y A01–A06 sobre el candidato.
   Mantén varias secuencias largas en la misma sesión: falla, cancelar, cambiar
   de tema, nueva misión, Nueva sesión y reinicio. Sin resets secretos.
4. Revalida las campañas de C03–C08 requeridas por cada fila: 100 respuestas
   consecutivas leídas, matriz de operaciones, misiones frescas, comprensión
   con sus umbrales, relojes, calibración y audio real. Usa aceptación reservada
   fresca para lo que se reparó. Los 200 turnos de 10.18 siguen siendo otro objetivo;
   no copies su nombre ni declares cumplido el Goal 10 con esta campaña.
5. Comprueba equivalencia de la entrada y la proyección final sobre el candidato.
   Observa la integración real de UI/voz/hardware donde el criterio dependa
   de ella. No convierte al dueño en probador. Si el entorno lo impide, queda
   BLOQUEADO_ENTORNO y NO_LISTO, con reanudación exacta.
6. Full dos veces sobre ese árbol y una tercera en clon limpio, con runtime
   aprovisionado de forma reproducible. Ejecuta además los gates físicos
   exigidos; los Explicit fuera de Full no desaparecen del plan.
7. Si falla una fila, conserva el fallo, reabre sus dependencias, repara la
   causa mínima, fija un nuevo candidato y revalida las campañas afectadas.
   Vuelve a ejecutar el conjunto obligatorio y Full sobre el candidato final.
   No repitas ciegamente sólo hasta que pase: una intermitencia sigue siendo
   incidencia mientras no esté explicada y resuelta.
8. Revisa la evidencia directamente: intención → entrada pública → ejecución →
   postcondición → salida exacta → siguiente turno. La afirmación del conductor,
   el booleano verified y los totales no sustituyen la observación independiente.

## Cierre y certificado

Publica artifacts/comprobaciones/C09/ADMISION_GOAL_10.md con:
- commit de código candidato, hash de árbol relevante y commit de publicación
  de evidencia; manifiestos/hashes de modelos, runtime, configuración y entorno;
- criterio original, owner, comando, muestra, resultado, evidencia y fecha;
- cobertura real: operaciones/misiones/idiomas/perfiles físicos comprobados;
- tests y campañas con pass/fail/skips diferenciados; cero pendientes de admisión;
- estado final de sesiones/efectos de prueba y cualquier limpieza propia realizada;
- veredicto único LISTO_PARA_GOAL_10 o NO_LISTO con causa;
- siguiente prompt original y reconciliación de lo ya ejecutado del 10.

Sólo se marca C09 cumplido si:
- [ ] Todas las filas originales y requisitos de campaña están CUMPLIDOS en el candidato.
- [ ] Todos los casos obligatorios pasan y los mínimos originales siguen intactos.
- [ ] Cada capacidad y respuesta se comprobó por la entrada compartida, con sus
      pruebas físicas cuando procedan; cero respuestas/efectos inventados.
- [ ] No quedan fallos reproducibles ni bloqueos de los compromisos, tampoco
      estados pendientes que capturen la siguiente petición.
- [ ] Full 2+clon y gates requeridos verdes, sin omisiones usadas como pass.
- [ ] Código y evidencia propios publicados; checkout certificado limpio y
      hash que permite reproducir lo aceptado sin tocar cambios ajenos.
- [ ] Certificado emitido y estado de campaña actualizado a LISTO_PARA_GOAL_10.

Si cualquiera falta, conserva NO_LISTO y continúa o deja el bloqueo concreto.
No uses «inalcanzable demostrado», «suficiente para seguir» ni un porcentaje global
para habilitar el 10 con una capacidad comprometida incumplida.

Al cumplir, lee el índice del 10 y su estado real. En b2505da el siguiente
pendiente era 10.7; valida ese dato al cerrar, sin borrar 10.0–10.2.5 históricos.
La admisión restaura prerrequisitos, no acredita todavía el uso diario completo.
