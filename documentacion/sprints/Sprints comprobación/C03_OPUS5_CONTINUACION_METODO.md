# Continuación de C03 con Opus 5 High — método revisado

Mensaje del dueño para continuar C03, en el agente actual o en uno nuevo tras
el cierre de sesión del anterior. Conserva el mismo objetivo de producto.
Sustituye las órdenes de arranque y el método de trabajo del relevo anterior;
conserva el objetivo y todos los criterios de cierre de
[C03](C03_RESPUESTA_VERAZ.md). Continúa con Opus 5 High y thinking activado.
Granite 4.2 3B sigue siendo el modelo local de BAXY.

## Producto y alcance

Quiero BAXY: un compañero local que comprende la petición, conversa con
naturalidad, actúa cuando se lo piden y cuenta lo realmente verificado.
Cumple [Identidad](../../00_IDENTIDAD.md), las cinco leyes y los seis invariantes
de AGENTS. Una respuesta publicada, un terminal honesto o tests verdes no
sustituyen una respuesta útil y fiel. Tampoco basta con nombrar el tema.

Tu encargo sigue siendo COMPLETAR C03. Repara las dependencias mínimas de
comprensión y continuidad que lo bloquean, aunque su owner participe en C05/C06.
Dejar allí una nota no resuelve un fallo de C03. No abras esos goals ni sus
campañas completas. Refactoriza donde la evidencia lo justifique y retira lo
sustituido. Conserva catálogo, autorización, confirmación exacta, verificación,
privacidad y accesibilidad. No añadas otro cerebro ni otro compositor.
No cambies de modelo, entrenes ni reduzcas cobertura para escapar del problema.

## Retoma una vez

Confirma la raíz BAXY Definitivo, rama main, cambios y procesos. Si eres el agente
nuevo, lee primero el handoff de sesión enlazado desde CHECKPOINT y confirma
que el anterior dejó de escribir. No dependas de su chat. Recoge la corrida
activa antes de lanzar otra; no la canceles ni dupliques sólo por este mensaje.
Conserva tu WIP y el ajeno. No reinicies Good afternoon ni reparaciones ya probadas.

Reconcília el [checkpoint de trabajo](../../../artifacts/comprobaciones/C03/CHECKPOINT.md)
con el [estado de campaña](05_ESTADO_Y_CONTINUACION.md), archivos y resultados
posteriores. El primero citaba panel-opus-13 y el segundo aún panel-opus-12:
ninguno demuestra por sí solo el estado actual. Usa CHECKPOINT como punto único
de reanudación y el estado de campaña como resumen enlazado, sin dos listas
contradictorias de próximas acciones. Guarda logs con rutas absolutas existentes.

Lee una vez las [lecciones acumuladas](C03_LECCIONES_METODO_2026-09-05.md).
Después abre sólo el informe, traza y código necesarios para el fallo elegido.
No releas todas las corridas ni el antiguo diagnóstico como si siguiera vigente.

## Ciclo de reparación

1. **Selecciona el bloqueo por impacto.** Agrupa fallos por causa observada:
   intención/hechos/contexto, generación, veto incorrecto, publicación/estado.
   Prioriza falsedad, respuestas ajenas, fugas internas y ausencia de respuesta
   antes que pulir una formulación que ya cumple. No atribuyas todo a Granite.
   Reutiliza la adjudicación disponible; no crees otra campaña de auditoría.

2. **Encuentra la primera etapa incorrecta.** Para un caso fallido y su contraste
   cercano correcto, sigue petición → lectura/intención → contexto/hechos →
   prompt efectivo → borrador bruto → validación/reintentos → texto y estado
   públicos. Usa las trazas existentes. Distingue dato ausente, generación mala,
   borrador correcto rechazado y respuesta perdida en publicación.
   Formula causa, evidencia, cambio propuesto y resultado esperado en pocas líneas.

3. **Haz una prueba que decida entre causas.** Primero usa pruebas dueñas baratas
   para errores deterministas. Si necesitas Granite, elige un panel de 8–20
   casos de desarrollo con contrastes y secuencias completas. Una variable causal
   por comparación; puede requerir cambiar varios archivos del mismo contrato.
   Identifica fuente, binario Release, GGUF, prompt, parámetros y sesión efectivos.
   El conductor usa Release: compilar Debug no comprueba el cambio.

4. **Compara antes/después con los mismos criterios.** Usa el resultado anterior
   si su configuración y población son comparables; no lo repitas por rutina.
   Cuenta respuestas pertinentes y fieles, falsos rechazos, agotamientos/silencios
   y llamadas/tiempo disponibles en trazas, por clase. Incluye pérdidas en casos
   antes correctos. No llames mejora a publicar más respuestas equivocadas.
   No infieras ahorro de cuota desde el número de llamadas locales a Granite.

5. **Decide y continúa.** Conserva una reparación causal demostrada; documenta
   qué queda pendiente. Si aparecen regresiones, corrígelas o retira sólo tu
   variante identificada, preservando WIP heredado. Dos variantes de la MISMA
   estrategia sin mejora exigen una prueba discriminante nueva antes de otra:
   cambiar las palabras del prompt no crea una hipótesis nueva. Continúa
   investigando el mecanismo; esta regla no autoriza abandonar C03.

Después de reparar la clase, incorpora contrastes nuevos de desarrollo y la
regresión transversal afectada. Para resultados estocásticos dudosos, decide
antes una repetición acotada y cuenta todos los resultados. No repitas hasta
conseguir la corrida favorable ni uses esos casos como aceptación fresca.

## Decisiones que requieren especial cuidado

- **Validadores:** una regla nueva debe proteger un contrato y demostrar tanto
  un rechazo necesario como una respuesta válida cercana que conserva. No añadas
  listas de frases del examen, nombres propios ni recortes que fabriquen prosa.
  Una regla incorrecta puede retirarse con evidencia; no rebajes las garantías.
  Evalúa naturalidad por significado y por la rúbrica vigente, no por coincidir
  con tu frase favorita.
- **Continuidad:** transportar el tema no garantiza contestar «por qué».
  Traza dónde se conserva o pierde la pregunta y la información pertinente.
  Llevar sólo peticiones anteriores es una solución parcial, no un dogma;
  usa el contexto mínimo suficiente sin tratar texto conversacional como
  hechos del PC ni instrucciones ejecutables.
- **Capacidades y límites:** fundamenta la respuesta en el catálogo activo y
  el estado real. «No abras X» es una restricción de este turno, no prueba de
  incapacidad permanente. No reemplaces una explicación por una aclaración
  innecesaria ni inventes limitaciones.
- **Generación:** si llega información correcta y falla el borrador, mide ese
  punto con el perfil efectivo. No aumentes reintentos ni vetos automáticamente.
  Un resultado directo de laboratorio ayuda a diagnosticar, no acredita producto.
  Si sospechas un límite del modelo, demuéstralo con comparación controlada y
  ejemplos; «es un 3B» y «otro owner» no son diagnósticos.

## Validación y cierre

Tests dueños tras la reparación. Full al cierre integrado según AGENTS, no tras
cada variante de redacción ni repetido sobre dependencias iguales sin motivo.
Conserva los checks exigidos y separa skips ambientales de passes. Un pin nuevo
no acredita una medición física nueva.

Sólo con desarrollo y regresiones pertinentes verdes, congela el candidato y
100 turnos NUEVOS representativos de todas las rutas, idiomas y secuencias
exigidas. Expectativas externas al runtime, sin respuestas modelo para copiar.
Adjudica todos los turnos y progresos en bloques de hasta 20 sin partir secuencias.
Exige 100/100 útiles, naturales y fieles: un silencio, agotamiento espontáneo,
aclaración innecesaria o respuesta ajena falla. Los casos usados para reparar
pasan a regresión; mantén cobertura y todos los intentos.

Completa además matriz, R07 en una misma sesión, UI real, runtime reproducible
sin override, regresiones de roles afectados y Full del candidato final.
Conserva evidencia previa sólo si sus dependencias siguen vigentes. Las pruebas
físicas asignadas a C08 no se sustituyen por un sink. Publica exclusivamente el
trabajo autorizado de C03, sin cambios ajenos ni datos privados. Sólo entonces
C03 CUMPLIDO y queda habilitado C04; no declares todavía BAXY definitivo.

## Contexto, comunicación y continuidad

Sin subagentes ni harness nuevo. Toma decisiones rutinarias y ejecuta; no devuelvas
sólo un plan. Informa brevemente de causa encontrada, mejora medida, regresión
o cambio de enfoque. No narres cada comando ni redactes un informe por variante.

Checkpoint de máximo 80 líneas antes de pruebas largas, tras hitos y antes de
compactar: candidato, causa, resultado exacto, hipótesis descartadas, evidencia
invalidada, PID/inicio/log y siguiente acción. Historial fuera del contexto activo.
Usa la compactación real de tu cliente al cerrar una unidad; no inventes tokens
disponibles ni comandos de Grok. El objetivo de 60–100K es política conservadora
del proyecto, no un límite oficial de Opus.

Si cuota o contexto se agotan, guarda una continuación ejecutable. Si aparece
un límite demostrado que exige cambiar una decisión del dueño, entrega la
evidencia y la decisión concreta necesaria. C03 permanece abierto; no reduzcas
el producto para poder declarar éxito.

Empieza recogiendo tu resultado más reciente. Elige la clase todavía fallida con
mayor impacto, muestra en pocas líneas dónde nace y ejecuta la reparación con
comparación antes/después. Continúa hasta el cierre verificable.
