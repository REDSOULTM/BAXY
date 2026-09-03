# Protocolo de ejecución — Grok 4.6 High, contexto de 500K

Configuración pedida por el dueño: **Grok 4.6, High, 500.000 tokens de contexto
por ventana**. Este protocolo forma parte de todos los Cxx.

## Lanzamiento y persistencia de la meta

Abre el repositorio BAXY Definitivo en main, sesión nueva, modelo grok-4.6,
esfuerzo high. Usa la meta persistente de Grok Build con el texto íntegro de un
único Cxx. El objetivo no se reduce a «continúa» ni cambia al compactar.

Comando interactivo compatible con la ayuda local inspeccionada:

~~~powershell
grok --cwd "C:\Users\usuario\Desktop\ETC\Programacion\BAXY Definitivo" --model grok-4.6 --reasoning-effort high
~~~

Selecciona /goal y pega el Cxx completo una sola vez. Verifica modelo/esfuerzo
efectivos y las herramientas disponibles al arrancar. La selección de modelo
de un prompt no cambia por sí sola la configuración del cliente.
No uses --prompt-file o -p como sustituto automático de una campaña persistente:
la ayuda local los describe como single-turn. El lanzamiento no requiere cambiar
la configuración global del equipo.

High es el esfuerzo durante toda la campaña, por indicación expresa del dueño.
No lo cambies a xhigh ni sustituyas Grok 4.6 por otro modelo por iniciativa propia.
Grok es el agente de desarrollo; esto no sustituye el modelo local de BAXY.

## Presupuesto de cada ventana

500K es capacidad de contexto, no tokens que haya que gastar, ni presupuesto
total de la campaña. Cuenta instrucciones, conversación, herramientas, archivos y
reserva para salida; no planifiques llenar los 500K con lecturas.

Distribución orientativa de trabajo, no cuotas a consumir:
- hasta 50K: contrato, baseline, criterio y owner;
- hasta 250K adicionales: diagnóstico e implementación del tramo;
- reservar al menos 150K: pruebas, correcciones y revisión;
- mantener unos 50K de margen para herramientas/continuación.

Usa /context si está disponible. Al acercarte a 350K ocupados, antes de un log
grande o cuando no quepa la siguiente verificación, escribe el checkpoint y
compacta con el mecanismo del cliente. Hazlo antes del límite, no después.
Si una tanda necesita otra ventana, conserva el mismo objetivo, sus criterios,
cursor y evidencia. Reabre sólo el handoff y las piezas necesarias, no toda la
historia. Agotar contexto no permite cerrar, relajar un listón ni saltar un caso.

## Cuota agotada, corte abrupto y reanudación

La cuota de uso es distinta del contexto de 500K. Compactar no recupera cuota;
una ventana casi vacía puede interrumpirse por el límite de uso. No conviertas
un porcentaje de cuota en tokens/minutos disponibles ni inventes su valor si
el cliente no lo expone al agente.

Si el dueño informa de muy poca cuota (por ejemplo, 3 %), empieza guardando el
checkpoint mínimo y verificando el punto de partida del Cxx. Evita una lectura
masiva; avanza sólo en una unidad pequeña cuyo estado pueda quedar registrado.
Si no hay margen, conserva EN_CURSO, motivo «cuota insuficiente». No es un cierre.

No dependas de recibir un aviso antes del corte. En todas las sesiones:
1. Antes de trabajo costoso, escribe goal, ruta de su objetivo íntegro, commit,
   cambios ajenos, cambios heredados del agente anterior, id de sesión Grok si
   está disponible y primera acción en
   05_ESTADO_Y_CONTINUACION.md. El goal pasa a EN_CURSO.
2. Antes de una prueba larga o con efectos, registra intención, id de intento,
   comando, recursos propios y ruta de log. Tras lanzarla, añade PID, ejecutable
   y hora de inicio cuando estén disponibles. Los logs se guardan mientras corre.
3. Después de cada unidad pequeña de cambios o resultado material, guarda
   archivos afectados, validación pendiente, cursor y siguiente acción.
4. Un corte no cambia el goal a cumplido. Un proceso ya lanzado podría seguir
   ejecutándose: no lo supongas terminado, fallido ni cancelado.

El relevo debe funcionar con un agente nuevo sin el chat anterior, incluso si el
dueño usa otra cuenta con acceso disponible. La cuenta y el id de sesión no son
requisitos de recuperación: el estado necesario vive en el repositorio. Sigue el
[relevo entre agentes](06_RELEVO_ENTRE_AGENTES.md) y retoma el mismo Cxx íntegro.
No transfieras credenciales ni dependas de que el cliente comparta conversaciones
entre cuentas. No debe haber dos agentes escribiendo sobre este árbol a la vez.

Reanudar la conversación anterior es una alternativa si está disponible.
--continue abre la más reciente del directorio; si hubo otras, selecciona el id
correcto con --resume, según la ayuda local y la referencia oficial:

~~~powershell
grok --cwd "C:\Users\usuario\Desktop\ETC\Programacion\BAXY Definitivo" --resume "ID_DE_LA_SESION" --model grok-4.6 --reasoning-effort high
~~~

Sustituye el id por el guardado o seleccionado en el cliente. No uses
--restore-code para recuperar un corte de cuota: conserva el árbol actual.
Verifica que la meta activa mantiene el objetivo íntegro del Cxx; recuperar una
conversación no prueba por sí solo el estado de su meta.

Primero reconcilia checkpoint, criterios activos, git status/diff, logs, procesos
y efectos reales. Contrasta cualquier PID con ejecutable/hora de inicio. Si una
edición quedó parcial, complétala y valida; si una prueba terminó, recoge su
resultado; si un efecto es incierto, observa antes de repetirlo. No lances una
segunda copia ni marques pass sólo porque existe un log. Conserva cambios ajenos.

En cualquier sesión nueva, lee el archivo de estado antes de ejecutar el Cxx:
haber pegado otra vez su objetivo no significa empezar desde cero. Conserva lo
comprobado que siga siendo válido para el árbol y runtime actuales. No empieces
el siguiente Cxx por haber agotado cuota.

Se recupera lo persistido y se reconcilia lo que quedó en vuelo. No se garantiza
conservar razonamiento aún no escrito ni el último cambio incompleto. Un prompt
tampoco recarga cuota ni garantiza reanudación automática al restablecerse el
límite: comprueba la disponibilidad y reanuda en el cliente cuando corresponda.

## Forma de trabajar y de leer los prompts

Cada Cxx tiene objetivo observable, lecturas mínimas, trabajo acotado y lista de
cierre. El contrato estable se lee primero; la evidencia variable después.
No reescribas ni reordenes toda la conversación para actualizar un dato:
anexa un checkpoint breve y mantiene el estado duradero en archivos.

Usa checklist derivado de la aceptación. Toma decisiones de implementación y
ejecútalas; no devuelvas sólo un plan ni un informe cuando el Cxx pide reparar.
Razona con la profundidad High configurada; publica decisiones y evidencias
comprobables, no monólogos ni instrucciones rituales de «piensa paso a paso».

Búsquedas: índice/título/rango/archivo. En Grok usa grep/read_file y los nombres
reales de herramientas que exponga el cliente. Verifica antes de asumir rg en
PowerShell; su disponibilidad en Codex no prueba disponibilidad en Grok.
Git y suites: salida pequeña primero; logs completos a artefactos. No leer corpus
enteros. Lee sólo las filas propias de la matriz, salvo la revisión integral C09.

Tras dos iteraciones sin mejora, revisa la hipótesis y la evidencia heredada.
No añadas cadenas de parches de texto para cada frase fallida. No sustituyas
el scorer ni su población para aprobar. Conserva los fallos y sus causas.

Actualiza estado al terminar una reparación comprobada, al cambiar hipótesis,
ante un bloqueo y antes de compactar. Un proceso de pruebas activo conserva PID,
comando y log; reanudar no debe lanzar una segunda copia sobre el mismo estado.

No uses subagentes por defecto. Una revisión independiente significa observación
independiente del efecto y adjudicación separada del runtime, no pagar otro agente
para que repita una conclusión. Diseño, implementación y cierre permanecen en la
misma tarea. No ejecutes dos campañas que muten el mismo escritorio en paralelo.

## Cierre de una ventana y cierre de un goal

Checkpoint: goal, filas, commit/runtime, hechos, fallos, archivos propios, pruebas,
efectos pendientes, cursor y siguiente acción. Máximo una página de estado.

Cierre Cxx: criterios cumplidos con evidencia actual, resultado exacto de pruebas
y omisiones, cambios publicados propios y nombre del siguiente Cxx. Si no cumple,
continúa o registra el bloqueo concreto con preparación/reanudación; nunca lo
llames cumplido. El protocolo común impide confundir ese bloqueo con admisión.

## Fuentes verificadas y alcance de estas pautas

Consultadas el 2026-09-03. Estas fuentes sustentan capacidades del modelo/cliente;
la división C01–C09 y el reparto de contexto son decisiones para este repositorio.

- [Modelo Grok 4.6](https://docs.x.ai/developers/models/grok-4.6): ventana de 500K.
- [Reasoning](https://docs.x.ai/developers/model-capabilities/text/reasoning):
  high por defecto; xhigh disponible en 4.6.
- [Grok Build](https://docs.x.ai/build/overview): cliente interactivo, headless
  y selección del modelo.
- [Referencia CLI](https://docs.x.ai/build/cli/reference): --resume y --continue;
  la ayuda local explica que --restore-code restaura además un snapshot de código.
- [Compaction](https://docs.x.ai/developers/advanced-api-usage/context-compaction):
  compactar antes de exceder la ventana. La API no es una orden del CLI.
- [Prompt caching](https://docs.x.ai/developers/advanced-api-usage/prompt-caching/best-practices):
  prefijo estable y contenido estático delante; no se garantiza un cache hit.
- Evidencia local: grok --help; [protocolo anterior](../10_PROTOCOLO_GROK46.md)
  y [auditoría de contexto](../../../docs/AUDITORIA_GROK_2026-08-21.md).

No se extrapola una guía de conversación de voz a un agente de programación,
ni se atribuye al proveedor una receta de prompting no documentada.
