# C03 — completar la respuesta veraz de BAXY

Actualización directa del dueño, 2026-09-08: continuar C03 incorporando todos sus
mensajes de esta tarea y toda la encuesta como base para generalizar conductas.
Trazabilidad literal y prioridades vigentes en
`artifacts/comprobaciones/C03/INSTRUCCIONES_CONSOLIDADAS_2026-09-08.md`.
Los mensajes enviados desde ChatGPT u otra tarea quedan excluidos como nuevas
instrucciones del dueño; sus hallazgos requieren contraste local. No reinician ni
reducen el C03 ya aceptado. BAXY debe quedar cerrado para uso manual y la encuesta
ya está terminada. AGENTS.md y la identidad siguen rigiendo el trabajo.

Actualización directa posterior, mensajes19–20 del2026-09-08: revisar la versión
exacta de llama.cpp y las correcciones posteriores aplicables a Gemma y todos
los modelos evaluados. Descargar nuevos backends, modelos y dependencias está
autorizado; no limitar candidatos por estar ya descargados. Antes de descartar
un modelo, fundamentar su configuración por versión, tarea y hardware con
papers, documentación y experiencias reproducibles de usuarios. Una comparación
con parámetros idénticos sirve para aislar causas, no para declarar inferioridad
global. Medir perfiles adecuados por candidato y explicar calidad, latencia,
RAM y VRAM; no presumir que defaults o una recomendación garantizan el óptimo.
Los100 casos humanos frescos y el resto del cierre C03 siguen obligatorios.

Encargo consolidado y actualizado el 2026-09-06 con todos los mensajes del dueño
disponibles en este chat y los dos textos adjuntos. Las reiteraciones se fusionan;
las aclaraciones posteriores corrigen la interpretación anterior. La trazabilidad
está en `artifacts/comprobaciones/C03/INSTRUCCIONES_CONSOLIDADAS_2026-09-06.md`.
Sustituye los relevos y las
restricciones anteriores de autoridad. Conserva el alcance y los criterios de
`C03_RESPUESTA_VERAZ.md`, el contrato de campaña y la identidad del producto.

Para reanudar, manda el estado más reciente de
`artifacts/comprobaciones/C03/CHECKPOINT.md`; cualquier número de tramo anterior
conservado en el resumen del goal es una referencia histórica, no la siguiente tarea.

## Objetivo

Completar C03 en el producto real: BAXY responde a lo que la persona pide con
utilidad, hechos verdaderos, voz propia e idioma adecuado —español, inglés o
spanglish—, también al aclarar, confirmar, informar progreso y explicar errores.
Los siguientes goals deben recibir estas conductas resueltas, sin heredar el
atasco actual. Implementa y verifica; un diagnóstico o un plan no cierran C03.

## Autoridad

Actúa autónomamente. Tienes permiso para modificar, reorganizar, sustituir o
retirar código y documentación del repositorio, preparar el entorno, operar el
PC y evaluar o cambiar el modelo local si mejora BAXY. No pidas confirmaciones
rutinarias: la autorización del dueño ya está dada.

Puedes descargar modelos, runtimes y dependencias que falten. Comprueba primero
los activos existentes y reutiliza los adecuados. Qwen3-4B-Instruct-2507 Q4_K_M
base es el candidato registrado tras la comparación; no una obligación ni una
aceptación de C03: decide por calidad integrada y recursos medidos.
El techo es **4 GB de VRAM para BAXY**, aunque esta GPU tenga más. Registra el
perfil, las huellas, el consumo y la regresión de los roles afectados antes de
promover un modelo; una prueba con override no cambia el runtime del producto.

Trabaja en `Goal-c03` o en otra rama fuera de `main`. Publica el trabajo propio
validado en esa rama. Conserva los cambios ajenos y la evidencia de corridas;
retirar código obsoleto no significa borrar las pruebas de lo que se midió.
No hace falta integrar en `main` para cerrar C03.

La autorización posterior para descargar y cambiar modelos sustituye la consulta
previa del primer adjunto. No confundas el modelo local de BAXY con el agente que
lo desarrolla. Respeta `AGENTS.md` —corrección expresa de «AX.md»— y la identidad;
no cambies sus decisiones para facilitar el examen. Conserva `main` fuera del
alcance de esta entrega y no borres la evidencia necesaria para contrastar mejoras.

## Prioridad y método

La prioridad es que BAXY funcione bien para quien lo usa. Trabaja con rapidez:
hereda primero, investiga sólo lo que falta y construye al final. Consulta la
biblioteca y las mediciones pertinentes antes de repetir un experimento.
Compara las versiones anteriores y recupera sus mejores mecanismos cuando la
evidencia los respalde; no restaures una versión completa por nostalgia.
Reiteración expresa del dueño: hereda al máximo lo que ya esté hecho y funcione
en los proyectos BAXY anteriores de `D:/Perfil/Escritorio/ETC/Programacion`.
Son fuentes de herencia; el sitio de trabajo sigue siendo BAXY DEFINITIVO.

**Herencia contrastada con el estado del arte actual.** Heredar es el punto de
partida, no una razón para conservar una solución inferior. Para cada problema
que bloquee C03, compara el mecanismo heredado con documentación vigente, papers
y soluciones de usuarios o mantenedores que hayan resuelto un problema comparable.
Esta regla abarca comprensión, contexto, arquitectura, prompts, inferencia,
validadores y evaluación, no sólo elegir el LLM. Busca evidencia primaria y
reproducciones con configuración, versiones y resultados; distingue testimonios,
benchmarks ajenos y resultados propios. Comprueba aplicabilidad a Windows, uso
local/privado, identidad y techo de 4 GB. Elige la alternativa más ligera que
demuestre calidad: reutilizar, adaptar, sustituir o construir sólo lo que falte.
Documenta qué se comparó y por qué se adoptó o descartó, con fuentes fechadas y
medición local proporcionada. Evita una investigación general interminable: acota
la búsqueda al bloqueo, reutiliza resultados vigentes y pasa a probar la hipótesis.

Para cada decisión relevante deja una comparación breve y verificable: problema,
solución heredada y su evidencia, alternativa actual y fuentes fechadas, diferencias
de configuración, resultado local y decisión. «Heredar primero» no permite omitir
el contraste actual; «estado del arte» tampoco obliga a sustituir lo que ya cumple.
Una experiencia de usuario orienta la prueba cuando describe cómo la reprodujo;
su popularidad o una afirmación de éxito no sustituyen la medición en BAXY.

**Investiga el modelo exacto antes de ajustar su tratamiento.** Consulta primero
lo ya investigado y después su ficha oficial, documentación, informe técnico y
experiencias de usuarios con configuración y reproducción comprobables. Separa
familia, revisión, cuantización y backend: una receta de Thinking o de otro tamaño
no demuestra cómo debe configurarse el Instruct usado. Registra enlaces, fecha,
versión y diferencias con BAXY: template efectivo, roles de mensajes, contexto por
slot, thinking, parámetros de muestreo, límites de salida, stop, reintentos y
formatos estructurados. Inspecciona lo enviado al servidor, no sólo las constantes.
Los testimonios aportan hipótesis; la adopción exige evidencia local. Reutiliza
esta investigación mientras siga aplicando; no repitas búsquedas en cada edición.
Al cambiar modelo o backend, actualízala. Estado inicial de esta revisión:
`artifacts/comprobaciones/C03/INVESTIGACION_MODELO_C03.md`.

**Aísla el LLM y añade BAXY por piezas.** Con los mismos casos reales de desarrollo,
mide primero el servidor local con su template nativo, sin el wrapper de BAXY y
con presupuesto suficiente para distinguir truncamiento de error. Luego añade
identidad, instrucciones por función, catálogo/contexto, clasificación, validación
y reintentos, composición y aplicación completa. Compara una diferencia cada vez
cuando permita localizar la causa; no vuelvas a ejecutar capas ya demostradas sin
motivo. Registra entrada, respuesta bruta, finish_reason, respuesta publicada,
rechazo, tiempo y recursos. Si una prueba conserva guardas o límites de BAXY, no
la llames «modelo solo». Compara muestreo por rol: conversación, selección de
operaciones y composición tienen responsabilidades distintas. No atribuyas todo
al modelo ni todo al ecosistema; localiza la primera transformación incorrecta.
No envíes el corpus ni las conversaciones a servicios externos para investigarlo.

El recuerdo del dueño de que BAXY funcionaba mejor hace dos semanas es una
pista que debe contrastarse. La auditoría histórica ya demuestra una regresión
en la conservación de la hora. La conversación abierta en Opera puede aportar
contexto si es accesible, pero su lectura no debe detener el trabajo.

Baxy tiene demasiadas versiones anteriores, de las cuales seria ideal sacar la mejor de cada una para hacer este baxy definitivo.

La conversación aportada ya explica la regresión del Goal 06 (`046f034`), la
diferencia entre respuestas publicadas y correctas, y los límites de las pruebas
antiguas de UI, recuperación y hora. Parte de la auditoría existente en
`artifacts/audit/regresiones_20260822_20260905/INFORME.md`, del handoff y de
`SEGUIMIENTOS.md` en la carpeta C03. No reconstruyas toda la campaña ni leas todos
los commits por rutina: sigue las conductas y los cambios que puedan explicar
una regresión. Conserva lo que funcionaba y comprueba que la herencia sigue
respetando la identidad actual.

Revisa el estado actual del repositorio y el historial de commits pertinente
para localizar cuándo se perdieron conductas útiles y por qué las pruebas no
avisaron. Parte de las auditorías y snapshots existentes; amplía la comparación
cuando aporten una causa nueva. Recupera garantías demostradas de las versiones
anteriores y fija las regresiones para que no vuelvan a los siguientes goals.

Puedes corregir, simplificar, sustituir o retirar verificadores defectuosos,
incluidos filtros demasiado restrictivos. Su valor se mide por si distinguen
respuestas útiles y verdaderas de respuestas incorrectas: no por conservar una
implementación histórica. Demuestra con ejemplos válidos e inválidos que la nueva
validación respeta la identidad, mantiene las garantías y mejora el producto.

Resuelve sólo lo que bloquee C03, aunque pertenezca a un componente que otro
goal validará después. No te desvíes hacia defectos internos sin impacto en
la conducta comprometida. No aplaces a otro goal un fallo que impida responder
bien. Si varios parches desplazan el síntoma sin mejorar la respuesta, cambia
el enfoque. No acumules filtros de frases ni capas correctoras.

Trabaja en tramos con una hipótesis, criterio de aceptación y validación
proporcionada. Mide antes/después sobre los mismos casos. Conserva regresiones
y reserva una muestra nueva para aceptación. Actualiza
`artifacts/comprobaciones/C03/CHECKPOINT.md` al terminar cada tramo y antes de
compactar: estado, decisiones, evidencia, procesos activos y siguiente acción.

Tras dos intentos comparables sin mejora útil, abandona esa estrategia y cambia
la hipótesis. No abras una colección de modelos ni repitas cien turnos para
buscar una corrida favorable. Usa contexto acotado y validación por ownership;
Full corresponde al candidato integrado, no a cada edición. Elige la vía más
corta que conserve calidad y cobertura, sin prometer plazos que no hayas medido.
Actualización expresa del dueño: no repetir Full entre cambios o tramos. Usa
pruebas dueñas y mediciones del producto durante la reparación; ejecuta Full
cuando esté resuelto todo lo necesario para cerrar C03 y comprueba verde entero.
La ejecución ya iniciada puede terminar; no autoriza encadenar otra compuerta.

Mantén razonamiento alto como base conforme a AGENTS; dedica más análisis sólo a
una causa que lo necesite. El objetivo de eficiencia es reducir intentos y trabajo
repetido, no saltar verificaciones que acreditan conducta. Si falta una dependencia,
resuélvela dentro de la autorización existente y continúa con trabajo independiente.

## Compromisos que no se rebajan

Catálogo tipado como única fuente de operaciones; mente propone, kernel
autoriza y provider ejecuta. Ningún éxito sin verificación; confirmación ligada
a la invocación exacta; terminales honestos; ninguna respuesta visible fija.
Modelo local, privacidad y techo de 4 GB de VRAM. Arquitectura modular, sin
código muerto ni capas duplicadas.

Un error honesto y recuperable es una conducta válida ante una avería real;
no sustituye una respuesta útil ante una petición normal.

## Encuesta como base de comportamiento — aclaración del dueño, 2026-09-08

Usa todas las respuestas y notas del cuestionario como base para corregir la
conducta de BAXY y generalizar a otros mensajes, junto a AGENTS.md y la identidad.
No es únicamente una acreditación de autoría. Vincula los casos a comprensión,
contexto, capacidad, aclaración, verificación y explicación de límites; contrasta
las soluciones con variantes sin fijar respuestas ni alias por literal histórico.
Conserva las distinciones entre autoría, expectativa positiva o negativa y las
notas de alcance. Registro íntegro: `artifacts/comprobaciones/C03/SURVEY_REQUIREMENTS336.json`;
criterios comunes: `artifacts/comprobaciones/C03/ENCUESTA_COMO_BASE_DE_CONDUCTA.md`.
Todo caso que se use en desarrollo queda excluido de aceptación fresca; esta
base no permite cambiar etiquetas, inventar humanos o rebajar el cierre siguiente.

## Cierre verificable

Actualización expresa del dueño, 2026-09-06: seleccionar casos de uso de los
turnos únicos reales de usuario registrados desde Carter hasta BAXY actual,
heredando el corpus y los extractores del Goal10. No añadir instrucciones
artificiales como «en spanglish» ni traducir o parafrasear para completar cuotas.
Conservar texto literal, procedencia y contexto de las secuencias. El ámbito es
español, inglés y mezcla natural; revisar semánticamente el idioma, porque las
etiquetas históricas `other` también contienen español válido. Los ejemplos de
documentación, prompts de agentes y pruebas sintéticas no se presentan como
uso humano real. Separar desarrollo, regresión y reserva antes de ejecutar;
un texto histórico no es automáticamente una prueba nueva ni independiente del
entrenamiento. Los casos artificiales ya consumidos se conservan como evidencia
y regresión técnica, no como representación del uso cotidiano. Esta selección
no abre ni certifica el Goal10: se heredan sus datos para completar C03.

Aclaración del dueño del 2026-09-06, posterior a los pilotos: «spanglish» exige
comprensión de entradas mixtas, no alternancia obligatoria en la respuesta.
Responder en español a una petición mixta es válido; nombres de productos no
obligan a cambiar de idioma. Se respeta el idioma pedido expresamente, sin cuotas
de frases o palabras de cada lengua. Se aprueban explicaciones sencillas y
bienvenidas naturales aunque mezclen o repitan un saludo. No se exige exhaustividad
técnica cuando la persona no la pide. Conservar contradicciones, hechos inventados
y efectos no verificados como fallos; no confundir simplificación con falsedad.
Los cuatro ejemplos aprobados expresamente por el dueño y su adjudicación anterior
se conservan en artifacts/comprobaciones/C03/ACLARACION_DUENO_2026-09-06.md.

C03 termina cuando se cumplen todos los criterios del goal formal, incluidos:

1. Cien turnos normales frescos, congelados antes de ejecutarlos y leídos y
   adjudicados individualmente: 100/100 útiles y fieles a lo pedido, en los tres
   idiomas y distribuidos entre las ocho rutas de respuesta. Sin hechos o
   palabras inventados, plantillas, fugas internas, agotamientos ni silencios.
2. Los errores conservan su causa y permiten recuperar la sesión. Las averías
   inyectadas se evalúan aparte y no se cuentan entre los cien turnos normales.
3. El recorrido compartido de producto, la UI real y el runtime registrado
   satisfacen las comprobaciones de C03. La salida de un conductor sin ventana
   no acredita por sí sola pantalla ni audio físico.
4. Pruebas dueñas y `scripts/test_source_quality.ps1 -Mode Full` verdes sobre el
   candidato final, sin omitir fallos ni relajar criterios. Runtime y evidencia
   reproducibles; trabajo propio publicado en la rama de trabajo.

Cuenta respuestas correctas, no mensajes publicados ni tests estructurales.
Mantén C03 EN_CURSO hasta demostrar el cierre. Si aparece un bloqueo externo
real que no puedes resolver, documenta la evidencia y la reanudación exacta.
La dificultad, el consumo de contexto o un contratiempo reparable no cierran
el goal. Informa con prosa breve: qué cambió, qué se midió y qué falta.

## Evidencia comprensible y continuidad de la sesión

Mantén un Markdown legible para el dueño con cada entrada literal que se le dio a
BAXY, la respuesta literal recibida y su adjudicación explicada. Para secuencias,
conserva orden y contexto; identifica los hechos observados y enlaza los prompts
internos/payloads y borradores cuando expliquen el fallo. Separa corpus histórico,
desarrollo, regresión y reserva; no reescribas respuestas capturadas ni presentes
una corrección de rúbrica como mejora del modelo. Conserva los cuatro ejemplos
aprobados expresamente en `ACLARACION_DUENO_2026-09-06.md`. Respeta la privacidad
de los logs al decidir qué puede versionarse; el informe local puede enlazar
evidencia privada sin publicar datos sensibles.

Cuando el dueño pregunte por avance, explica qué fallaba al inicio, qué reparación
está demostrada, qué falla ahora, por qué y qué falta para cerrar. Distingue el
inicio de toda la campaña del inicio de esta sesión. Si pide porcentaje, indica
criterios cumplidos/pendientes y el método de estimación; una tasa de un panel no
es el porcentaje del goal. No inventes plazos ni atribuyas garantías de éxito a un
modelo, esfuerzo de razonamiento o suscripción.

No dependas de recordar el chat: registra decisiones y procesos a medida que
avanzas, con siguiente acción y comando de reanudación. El dueño autoriza nuevas
tareas si conservar el contexto lo justifica; no las abras por rutina ni dupliques
escritores del mismo trabajo. Hereda el checkpoint y confirma qué procesos siguen
activos antes de repetirlos. La conversación de Opera es una fuente opcional de
contexto; los adjuntos ya aportados se incorporan sin convertir antiguas órdenes
de cerrar sesiones de Grok/Opus en órdenes de detener el trabajo actual.

## Punto de reanudación de este encargo

No empezar desde cero. El estado vigente es el tramo43 de CHECKPOINT.md y
ASTRA-TRAMO-43.md, en artifacts/comprobaciones/C03/. Qwen3-4B-Instruct-2507 Q4_K_M
sigue registrado. Fecha contextual, volumen absoluto contextual y prohibiciones
simples ya tienen evidencia integrada. No son cien turnos frescos ni un porcentaje
del goal. El tramo44 sólo comenzó con inspección de código antes del relevo pedido
por el dueño; no hay implementación ni procesos pendientes de ese tramo.

La siguiente acción parte de effect_intent._has_contradictory_correction y
unresolved_compound_contract: distinguir una restricción independiente posterior
de una revocación del mismo efecto, y una pregunta negativa de una prohibición.
Los controles fallidos y la selección nativa correcta están capturados. No cambiar
otra vez el prompt para compensar estos vetos ni repetir variantes ya rechazadas.
Heredar investigación y pruebas vigentes; después continuar la reserva de cien,
ocho rutas, recuperación, UI/voz/recursos y Full de cierre. Para nuevos relevos,
manda siempre el checkpoint más reciente sobre este resumen fechado.

## Continuidad del producto

Las decisiones deben favorecer también C04–C09 y los goals posteriores hasta la
instalación. Comprueba las dependencias afectadas por C03 y deja contratos,
regresiones y runtime reproducibles que permitan continuar sin el mismo atasco.
Parte de la revisión de sprints ya realizada y de
`documentacion/sprints/MAPA_COMPLETO_2026-09-05.md`. Ajusta los prompts y criterios
posteriores que resulten incompatibles con el producto reparado: comportamiento
observable, pruebas contra contratos reales y continuidad hasta instalación,
hardware y aceptación del producto instalado en 12.3. Un cierre histórico o
miles de pruebas verdes no certifican esas conductas en el candidato nuevo.
No expandas C03 a ejecutar todos los goals a la vez: cada uno conserva su propia
aceptación. La autoridad amplia no sustituye las decisiones de identidad de
`documentacion/00_IDENTIDAD.md` ni los seis invariantes de `AGENTS.md`.
