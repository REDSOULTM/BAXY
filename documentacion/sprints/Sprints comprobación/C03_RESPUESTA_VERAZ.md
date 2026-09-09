# C03 — La respuesta final conserva la verdad y tiene voz propia

Actualización de alcance del dueño, 2026-09-08: la reserva, publicación, Full, encuesta y audio se rigen por [el objetivo vigente](../../../artifacts/comprobaciones/C03/astra-baseline-full526/GOAL_OBJECTIVE.md). Las cifras y exigencias anteriores de este prompt se interpretan con esa sustitución explícita.

**Un goal, tramos A–D reanudables. Encargo actual: C03_ASTRA_AUTORIDAD.md, 2026-09-06.**
Predecesor: C02 cumplido. Incorpora [contrato](01_CONTRATO_DE_CAMPANA.md) y
[protocolo vigente](../00_PROTOCOLO_EJECUCION.md). Este prompt sustituye las
instrucciones C03 copiadas en relevos antiguos; éstos conservan valor de evidencia.

## Objetivo

Cada turno debe terminar con una respuesta pública útil, natural y fiel a sus
hechos, incluidas las rutas de error. Repara la frontera entre resultado,
composición y publicación que hizo fallar «¿Qué hora es?» pese al éxito del Core.
El candidato se decide con la autoridad y mediciones de `C03_ASTRA_AUTORIDAD.md`.
Desde el 2026-09-06 se registra Qwen3-4B-Instruct-2507 Q4_K_M con KV q8; el registro
no equivale a aceptación de C03. Conserva las reparaciones demostradas y verifica
el runtime efectivo; no reinicies C01/C02.

## Lecturas y owners

Filas propias G04/G06 y tres ceros transversales de la matriz; R01/R02/R06/R07/R10.
MainWindowViewModel, ModelMessageComposer, PendingModelMessageQueue,
UserMessagePolicy y composición Python. Revisa la herencia de prosa/Q2/Q4 antes
de atribuir el defecto a un modelo o añadir validadores.

## Tramos de trabajo — una causa por ventana

**A. Contrato y diagnóstico del candidato.** Lee el checkpoint actual y las
conclusiones de la [revisión](../REVISION_SPRINTS_2026-09-04.md); abre sólo la
evidencia necesaria para verificar diferencias posteriores. Registra GGUF/hash,
llama-server, template efectivo, thinking, contexto, sampler por rol, límites de
salida y finish_reason. Contrasta ficha, documentación y paper del modelo exacto
con el runtime, siguiendo C03_ASTRA_AUTORIDAD.md. Inspecciona también decisión,
chat y reintentos: adaptar compose no configura automáticamente las otras llamadas.

Toma 8–20 casos discriminantes del desarrollo ya disponible y contrasta:
petición → decisión → hechos → borrador bruto → rechazo concreto → composición
de recuperación → publicación → siguiente turno. Usa entradas literales del corpus
real conforme a la aclaración del dueño en C03_ASTRA_AUTORIDAD.md; conserva su
procedencia y privacidad. No presentes pruebas sintéticas como uso humano real.
Separa defecto de interpretación, pérdida de hechos, modelo, veto falso,
agotamiento y publicación. No lances otro cien hasta tener una hipótesis causal.
Revisa `G03.08/G03C.09/G04.01/G04.02/G06.02/G06.03`: una casilla histórica no
sigue cumplida si hay evidencia posterior que la contradice. No borres la anterior.

**B. Reparar una causa general y comprobar su efecto.** Los puntos 1–5 y 7 de
abajo siguen siendo el alcance. Traza antes de tocar. Si el borrador ya era
correcto, investiga el veto; si recibió intención/hechos incorrectos, corrige ese
owner. Si el prompt introduce causas ajenas («red», welcome, failure), separa
las instrucciones aplicables al turno. Si falla inferencia, mide el perfil nativo.
No diagnostiques sólo mirando la frase final.

Las reglas sobre planetas, `hola` obligatorio al traducir al español, nombre
BAXY obligatorio en cada capacidad
o palabras vetadas no sustituyen comprensión. Una respuesta de capacidades debe
explicar capacidades reales, no pasar por mencionar la marca. Prueba contraste
semántico con temas/entidades nuevos y respuestas válidas que el filtro rechaza.
Retira o sustituye heurísticas incorrectas únicamente con evidencia y garantías
equivalentes: no relajes honestidad/seguridad, ni añadas un segundo compositor.
Tras dos intentos sin mejora cambia la hipótesis, no el examen ni sus umbrales.
Cambiar una respuesta irrelevante por otra irrelevante no cuenta como mejora.
Si varios parches sólo desplazan el síntoma, revisa la representación de intención
y el contrato completo de composición antes de otro veto. Contrasta prohibición
de actuar («no abras X»), consulta de límites («qué no puedes hacer») y petición
real fuera de catálogo: no son la misma intención. Usa nuevos temas y entidades
para demostrar la causa; repetir el mismo panel sólo mide esa regresión.
Dos tandas consecutivas que sólo sustituyen un final incorrecto por otro obligan
a detener esa estrategia de filtros, aunque se les asigne un nuevo número B.
Compara el diseño mínimo de intención/composición con la base bajo la misma
población y perfil; adopta un cambio sólo por mejora semántica y garantías
conservadas, nunca por desaparecer una cadena literal.

La rúbrica evalúa hechos correctos, respuesta al pedido, idioma y utilidad.
Acepta formulaciones equivalentes; no exige comienzos, palabras de marca o una
frase exacta para cada intención. Distingue una causa inventada de una explicación
correcta expresada de otra manera. Conserva los fallos de gramática y naturalidad
sin convertir cada expresión del evaluador en una prohibición del producto.
Brevedad no significa que toda pregunta de conocimiento sea un mensaje de estado.

Aclaración del dueño,2026-09-06: entradas mixtas admiten respuesta natural en
español; no exigir alternancia ni proporciones de idiomas. Las explicaciones
simples no tienen que ser exhaustivas. Se mantienen como fallos contradicciones,
invenciones y efectos sin verificar. Ver C03_ASTRA_AUTORIDAD.md y la adjudicación
expresa del dueño en artifacts/comprobaciones/C03/ACLARACION_DUENO_2026-09-06.md.

**C. Respuesta integrada y estado utilizable.** Con la reparación validada,
recorre todas las rutas, progreso incluido, por C01. Demuestra error inyectado
→ recurso restaurado → petición normal correcta en la misma sesión. Comprueba
UI real en un arranque `py main.py`: el estado SYSTEM del conductor no acredita
por sí solo que el usuario vea/entienda el fallo. Conserva el criterio acústico
de C08 sin presentar un sink como altavoz. Repara las dependencias mínimas de
comprensión/continuidad que bloqueen estas respuestas, dejando trazabilidad para
C05/C06; no intentes toda su campaña en C03.

**D. Aceptación reservada y promoción.** Sólo con el panel de desarrollo verde:
congela 100 turnos normales nuevos, sus expectativas y el candidato. Usa las
rutas del punto 5, ES/EN/spanglish y secuencias con contexto. No son cien variantes
de reloj/identidad/planetas. Adjudica en bloques pequeños preservando orden y
estado; lee cada respuesta y cada progreso. El cambio de modelo no hace fresca
v16. Cualquier muestra usada para corregir pasa a regresión y queda identificada.

Son **100/100 respuestas útiles y fieles**, no cien terminales: un agotamiento
espontáneo falla, un final ausente falla y una aclaración innecesaria falla.
Las inyecciones R07 forman un conjunto separado; pueden aprobar recuperación,
pero no sumar a esos cien. Publica resultados por ruta, idioma y causa, todos
los intentos y falsos rechazos. No elijas sólo la corrida favorable.

Después: Full verde, manifiesto reproducible del candidato que cumpla, arranque sin
override con el modelo registrado y panel público de humo que conserve respuesta
y estado. Una migración del GGUF también exige las regresiones dueñas de sus
otros roles; deja a C06 la certificación extensa. No afirmes promoción si sólo
cambió una variable de entorno. Registra dependencias de evidencia invalidadas.

## Conductas que deben conservarse

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
6. Cumple la aceptación reservada del tramo D y la recuperación del tramo C.
   No inyectes borradores hechos a mano. Revisa narración accesible por la misma
   composición; C08 comprobará el audio físico.
7. Mantén personalidad editable en prompt y separada de la política de seguridad.

## Cierre obligatorio

- [ ] R01/R02 y las rutas de prosa de R06/R07/R10 pasan; una misión aún pendiente
      de C05 no se presenta como completada para aprobar la narración.
- [ ] 100/100 turnos normales reservados con respuesta útil y fiel: cero hechos
      inventados, palabras inventadas, plantillas, agotamientos o finales ausentes.
      Inyecciones evaluadas aparte; no se aprueba silenciando respuestas malas.
- [ ] Ningún mensaje final desaparece al agotarse reintentos; controles y estado
      público permiten continuar con honestidad.
- [ ] Tres ceros y autocorrección probados; la instrumentación identifica qué
      ruta produjo cada texto público y las palabras reales que llegaron.
- [ ] Cada fila asignada de la matriz tiene evidencia actual; acceso a la misma
      prosa accesible preparado sin una segunda implementación.
- [ ] Perfil efectivo y promoción reproducibles sin override; tests propietarios
      y Full verdes; runtime/muestra sellados; trabajo propio publicado.

Evidencia: artifacts/comprobaciones/C03/. Siguiente: C04.
