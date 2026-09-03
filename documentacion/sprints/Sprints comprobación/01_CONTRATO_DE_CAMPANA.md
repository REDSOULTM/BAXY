# Contrato común de los goals C01–C09

Este documento es parte explícita de cada prompt Cxx. Se aplica con Identidad,
AGENTS.md y el goal en ejecución. Los antiguos prompts aportan compromisos y
evidencia; sus salidas «inalcanzable demostrado» no habilitan por sí solas el 10.
La petición del dueño es reparar y demostrar cumplimiento, no volver a cerrar
estudios dejando capacidades básicas pendientes.

## Invariantes y método

Hereda primero; construye sólo después de localizar las piezas y rechazos
pertinentes. Una responsabilidad por pieza; retira lo sustituido. Repara lo que
bloquea los criterios, sin perseguir defectos hipotéticos. El catálogo tipado
sigue siendo único: mente propone, kernel autoriza, provider ejecuta.

Nada se afirma sin verificar; terminales honestos; confirmación exacta; cero
respuestas visibles fijas; modelo local sin sacar contenido del usuario.
El presupuesto de producto sigue siendo 4 GB de VRAM, distinto de los 500K
tokens de contexto del agente de desarrollo. La voz, privacidad y accesibilidad
son compromisos del producto y no se recortan para aprobar pruebas.

## Una entrada de producto para usuario y agente

El conductor de pruebas debe poder enviar la petición que escribiría una persona,
sin elegirle la operación, los argumentos, el plan, el riesgo ni la respuesta.
No requiere abrir Baxy.exe ni WebView2: puede alojar el runtime sin ventana.
Sí debe ejecutar los mismos motores, configuración, stores, controles y salida
de producto que usa la persona. Quitar la ventana no equivale a simular BAXY.

El recorrido compartido abarca:
1. admisión y normalización, incluidos errores, límites, sesión y adjuntos;
2. memoria, aclaración, confirmación, planes pendientes y cancelación;
3. decisión local, catálogo, autorización, ejecución y verificación;
4. composición, cola, progreso, publicación del texto final y salida TTS aplicable;
5. estado posterior que condicionará la próxima petición.

Texto y voz convergen en ese recorrido después de sus adaptadores de entrada.
Una transcripción inyectada sólo prueba la parte textual; no acredita micrófono,
wake, STT ni fin de habla. Un sink de audio sin altavoz no acredita audibilidad.

**No cuentan como aceptación de experiencia de usuario** las llamadas del
conductor a decide, compose, ExecuteOperation, Core, kernel o provider, ni escribir
directamente en la lista de mensajes. Los tests unitarios pueden hacerlo para
diagnosticar. Los scripts antiguos se conservan como diagnóstico/regresión y
se adaptan a la entrada común cuando se usen para aceptar conducta de producto.

C01 debe hacer que UI y conductor compartan implementación, no mantener dos
versiones parecidas. Debe conservar la política de origen confiable y autoridad
del adaptador de UI. La vía local de pruebas no concede autoridad extra.
No es obligatorio un servidor HTTP: el transporte mínimo que use el mismo
controlador y los mismos eventos basta.

**Advertencia comprobada en b2505da:** el POST /turn es una ruta interna del
bridge WebView, no una API HTTP local que ya se pueda invocar con curl.
FieldUiBridge exige Window y WebView2. SubmitAsync también tiene dos sobrecargas.
No declarar que ya hay una entrada equivalente sin demostrar todas esas fronteras.

## Prueba de equivalencia y salida final

C01 documenta los símbolos concretos compartidos y prueba los dos adaptadores con
el mismo estado inicial y peticiones representativas: admisión, errores, adjuntos,
confirmación, cancelación y Nueva sesión. Compara decisiones/política, etapas,
postcondiciones, terminal, contenido factual publicado y estado posterior.
No exigir prosa idéntica byte a byte a un modelo no determinista.

La equivalencia de adaptadores puede verificarse sin ventana por contrato y
código compartido. El conductor recibe la misma proyección de eventos que consume
la UI, incluidos descartes y errores de publicación. No basta observar Messages
antes de que el bridge filtre o cambie lo que la persona recibirá.

Separa accepted, progreso, respuesta final publicada, efecto y recuperación
pendiente. Un HTTP 200, status=accepted, bridge ResponseFinal o fin de SubmitAsync
no prueba que exista una respuesta final útil. Si no llega, el caso falla con su
plazo y diagnóstico. No inventes un mensaje de éxito en el conductor.
Los timeouts no son ausencia de resultados: conservan evidencia y cuentan.

La ruta sin ventana no certifica por sí sola renderizado, WebView2, foco, audio
físico ni periféricos. Las capacidades que dependen de esos elementos requieren
su prueba apropiada; se automatiza cuando hay herramientas disponibles.
El dueño no se convierte en generador de prompts ni juez de las respuestas.

## Oráculo y casos

Separa los datos de entrada de las expectativas. BAXY sólo recibe lo que recibiría
el usuario, nunca la operación esperada, el resultado deseado ni el veredicto.
El evaluador vive fuera del runtime y lee el estado real después de la ejecución.
Para una acción segura, la comprobación independiente debe ser una lectura del
mundo; no basta el journal del mismo ejecutor ni su booleano verified.
El oráculo no reutiliza como verdad la conclusión del verificador bajo prueba:
observa por separado la ventana, archivo, audio o estado del sistema pertinente.

Congela antes de correr: población, precondiciones, postcondiciones, tolerancias,
métricas, reglas de puntuación y mínimos. Hay regresiones conocidas, desarrollo
y aceptación fresca reservada. Un caso usado para reparar pasa a regresión;
la siguiente aceptación usa otra población fresca equivalente. No reintentes
hasta conseguir una respuesta bonita y publiques sólo esa.

Cada invocación conserva: id de caso/sesión/turno, entrada pública, estado inicial,
eventos publicados completos, respuesta final exacta, operaciones efectivamente
emitidas, efectos observados, terminal, estado siguiente, relojes, veredicto,
razón, comando reproducible, commit y huellas de runtime/configuración.
El evaluador puede inspeccionar trazas; esa inspección no puede cambiar la
respuesta, elegir por BAXY ni despejar manualmente una sesión.

Los tres ceros son obligatorios. Los umbrales agregados de comprensión/misiones
no excusan los casos obligatorios fallidos ni defectos reproducibles que impidan
una capacidad comprometida. El informe por causa distingue comprensión,
argumentos, política, ejecución, verificación, prosa, publicación y continuidad.

## Pruebas de fallo y entorno

Para errores difíciles de provocar, la petición sigue entrando por el canal
común y el fallo se introduce en el límite del recurso correspondiente.
Declara la inyección. Prueba la recuperación y vuelve a ejecutar también el
camino real sin sustitutos. Un provider mentiroso simulado comprueba honestidad,
no éxito físico de la operación.

Prepara datos y recursos desechables del test con el mismo mecanismo de producto;
el setup del escenario puede usar tooling externo, pero no resolver la tarea
por BAXY. Observa y restaura sólo los efectos propios que sea seguro restaurar.
No destruyas datos personales, mandes mensajes a terceros ni realices compras
para aprobar una fila. Usa cuentas/recursos de prueba cuando sean necesarios.
Si una capacidad exige un recurso físico ausente, queda BLOQUEADO_ENTORNO con
la preparación y reanudación exactas; no se vuelve un pass de fixture.

Una operación intrínsecamente no verificable debe identificarse y responder
honestamente; no puede venderse como éxito verificado. La falta de equipo o
credenciales para una operación verificable no es «intrínsecamente no verificable».
Esta distinción impide volver a contar 82 categorías estáticas como 82 éxitos.

## Ciclo de trabajo y cierre

Localiza evidencia → reproduce por entrada común → identifica causa → repara
owner mínimo → prueba propietaria → repite conducta → actualiza matriz/estado.
No regreses siempre al inicio de la campaña: conserva lo comprobado y reabre
criterios afectados. C09 hace la revalidación final conjunta.

Usa la escalera de validación del repositorio. Full es obligatorio al cerrar una
tanda de implementación; los gates de proceso real, hardware y voz exigidos por
el criterio se ejecutan además. Los rojos no se omiten ni se normalizan.
Los skips existentes se informan aparte y no satisfacen ninguna fila.
C01 repara los impedimentos mínimos de base que bloqueen su validación y deja
la trazabilidad a C02, que completa la reproducción y el clon limpio. Ninguna
tanda se declara cumplida con Full rojo, aunque el defecto sea preexistente.

Guarda artefactos en artifacts/comprobaciones/Cxx/<corrida>/ y actualiza
05_ESTADO_Y_CONTINUACION.md después de cada hito. No copies datos privados
innecesarios a Git. No modifiques hashes o criterios para que coincidan con una
salida fallida. Distingue sellos históricos de expectativas actuales y justifica
cualquier actualización con qué cambió y qué campaña requiere revalidación.

Publica el trabajo propio de cada tanda conforme al contrato de entrega del
repositorio. Conserva cambios ajenos: el certificado usa un checkout limpio del
commit publicado, no borrar/stashear trabajo del dueño para vaciar git status.
Los conteos antiguos de tests son referencias fechadas; publica los actuales
sin eliminar cobertura para imitarlos.

Estados: PENDIENTE, EN_CURSO, INCUMPLIDO, BLOQUEADO_ENTORNO,
CUMPLIDO. El agotamiento de contexto lleva
a un checkpoint, nunca a CUMPLIDO. Toda fila original conserva fuente, owner,
evidencia actual y estado. C09 produce LISTO_PARA_GOAL_10 sólo con todas cumplidas,
sin excepciones pendientes ni fallos conocidos de los compromisos.
