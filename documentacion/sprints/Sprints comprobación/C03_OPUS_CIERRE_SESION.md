# Cierre de sesión de Opus y relevo de C03

Cambio de instrucción del dueño: cierra ESTA SESIÓN de trabajo y prepara el
relevo a otro Opus 5 High. **C03 sigue EN_CURSO** salvo que ya exista evidencia
completa y verificable de todos sus criterios. Cerrar la sesión no es cumplir
el goal. Este encargo sustituye ahora la orden de seguir implementando.

1. Deja de iniciar reparaciones, experimentos, evaluaciones, builds y Full.
   Guarda archivos abiertos sin implementar otro cambio. Conserva el WIP
   propio y heredado; no uses reset, clean, restore, stash, commit ni push
   como mecanismo de relevo. No actualices pins para obtener verde al salir.

2. Reconcilia las pruebas que YA lanzaste. Registra PID, fecha de inicio,
   comando, versión/binario/perfil, rutas absolutas de logs y último resultado.
   Si terminaron, recoge su salida y exit code una vez. Si siguen activas,
   déjalas identificadas para recoger después, sin duplicarlas ni esperar
   indefinidamente. Si fuera necesario detener un proceso propio, hazlo de
   forma controlada y registra el intento como INTERRUMPIDO, nunca como pass.
   No mates procesos ajenos ni asumas el resultado de un efecto pendiente.

3. Escribe un único handoff de máximo 80 líneas en
   artifacts/comprobaciones/C03/HANDOFF_OPUS_METODO.md. Debe permitir continuar
   sin el chat e incluir:
   - Raíz, rama, HEAD, fecha y fingerprints de los archivos/configuración
     relevantes de tu candidato; distingue lo heredado y tu última variante.
   - Qué reparación está comprobada, cuál es provisional y qué queda sin probar.
   - Última corrida válida: población, respuestas útiles/fieles, falsos rechazos,
     agotamientos y silencios. Distingue cifras exactas de estimaciones.
   - Fallos pendientes por causa con ejemplos y rutas exactas a sus trazas.
   - Hipótesis descartadas, prueba que las descartó y variantes retiradas.
   - Comandos de validación con resultado, skips y log existente; último Full
     con alcance/candidato. Si no está recogido, escribe NO VERIFICADO.
   - Procesos activos, efectos por observar y siguiente acción concreta.

4. Actualiza artifacts/comprobaciones/C03/CHECKPOINT.md para enlazar ese handoff
   y reflejar el estado actual, sin otra lista contradictoria. Sincroniza
   documentacion/sprints/Sprints comprobación/05_ESTADO_Y_CONTINUACION.md como
   resumen. No cambies criterios ni marques reparado lo aplazado a C05/C06.
   Conserva las adjudicaciones históricas y sus límites.

5. El siguiente agente aplicará
   documentacion/sprints/Sprints comprobación/C03_OPUS5_CONTINUACION_METODO.md
   y su mapa de lecciones. Sólo referencia esos documentos: no ejecutes su
   siguiente reparación ni reabras ahora la investigación para mejorar el informe.

Termina con un mensaje breve: checkpoint/handoff guardados y sus rutas,
C03 EN_CURSO, procesos activos o ninguno, último resultado comprobado y primera
acción del siguiente agente. Después deja de trabajar.

Si el cliente tiene un goal persistente que volverá a lanzarte, usa únicamente
su mecanismo real de pausa/cancelación si está disponible, sin marcar C03
cumplido. Si no puedes detenerlo desde tus herramientas, dilo explícitamente
para que el dueño lo detenga en el cliente antes de lanzar al siguiente agente.
No confundas terminar una respuesta con detener un goal persistente.

