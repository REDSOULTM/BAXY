# C03 — La respuesta final conserva la verdad y tiene voz propia

**Ejecutable: Grok 4.6 High; contexto de 500K; un solo goal persistente.**
Predecesor: C02 cumplido. Incorpora [contrato](01_CONTRATO_DE_CAMPANA.md) y
[protocolo 500K](02_PROTOCOLO_GROK_46_500K.md).

## Objetivo

Cada turno debe terminar con una respuesta pública útil, natural y fiel a sus
hechos, incluidas las rutas de error. Repara la frontera entre resultado,
composición y publicación que hizo fallar «¿Qué hora es?» pese al éxito del Core.

## Lecturas y owners

Filas propias G04/G06 y tres ceros transversales de la matriz; R01/R02/R06/R07/R10.
MainWindowViewModel, ModelMessageComposer, PendingModelMessageQueue,
UserMessagePolicy y composición Python. Revisa la herencia de prosa/Q2/Q4 antes
de atribuir el defecto a un modelo o añadir validadores.

## Trabajo

1. Reproduce por la entrada C01 saludo, pregunta de capacidades, hora y errores.
   Conserva la salida que recibiría el usuario, los hechos y el estado siguiente.
2. Repara pérdida o sustitución de hechos en recuperación de composición.
   Usa el contrato real de system.time (utc y localUtcOffsetMinutes), no el
   localTime artificial del antiguo muestreo. Corrige la causa de rechazos;
   no permitas textos falsos relajando la validación.
3. Repara agotamiento de la cola, silencios y falsa terminación. Una composición
   fallida no puede retirar silenciosamente la respuesta y aparentar normalidad.
   Si un fallo total del modelo impide prosa, debe exponerse un estado de error
   de producto honesto y recuperable; la campaña sigue fallida si deja silencio
   o incumple la prosa comprometida. No lo resuelvas con un literal de disculpa.
4. Comprueba que «no pude confirmar» no se transforma en éxito, y que un éxito
   real no se transforma en imposibilidad. La autocorrección preserva qué se
   observó; una señal temprana nunca afirma efectos todavía no verificados.
5. Audita las rutas que producen respuestas: bienvenida, conversación,
   aclaraciones, confirmaciones, progreso, resultados, errores y resumen de misión.
   Incluye Python, C# y TS. Repara las plantillas como Sigo con {snippet};
   C07 medirá después su latencia. Un censo léxico en cero no sustituye el recorrido.
6. Genera 100 respuestas consecutivas de aceptación fresca por la entrada común,
   en español, inglés y spanglish, repartidas entre esas rutas. Léelas y juzga
   coherencia, hechos, naturalidad y palabras inventadas con la rúbrica congelada.
   No inyectes borradores hechos a mano. Los casos de fallo inyectado se identifican.
   Revisa narración accesible por la misma composición; C08 comprobará el audio físico.
7. Mantén personalidad editable en prompt y separada de la política de seguridad.

## Cierre obligatorio

- [ ] R01/R02 y las rutas de prosa de R06/R07/R10 pasan; una misión aún pendiente
      de C05 no se presenta como completada para aprobar la narración.
- [ ] 100 respuestas consecutivas leídas y adjudicadas: cero hechos inventados,
      palabras inventadas o respuestas por plantilla; los errores conservan causa.
- [ ] Ningún mensaje final desaparece al agotarse reintentos; controles y estado
      público permiten continuar con honestidad.
- [ ] Tres ceros y autocorrección probados; la instrumentación identifica qué
      ruta produjo cada texto público y las palabras reales que llegaron.
- [ ] Cada fila asignada de la matriz tiene evidencia actual; acceso a la misma
      prosa accesible preparado sin una segunda implementación.
- [ ] Tests propietarios y Full verdes; runtime y muestra sellados; trabajo publicado.

Evidencia: artifacts/comprobaciones/C03/. Siguiente: C04.
