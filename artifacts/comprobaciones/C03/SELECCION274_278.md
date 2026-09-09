# C03 — selección274–278: ordenar por identidad no basta

La tanda anterior273 produjo progreso verificable: cuestionario entregado,
sesión privada preservada y comparaciones que cambiaron el diagnóstico. Esta
tanda sigue EN_CURSO. No se adopta ninguna regla nueva ni se modifica fuente
de producto: las variantes de búsqueda mejoran controles aislados pero fallan
la comprobación de selección o introducen una regresión.

## 274–275: causa localizada en disponibilidad y orden

Se corrigió una limitación del ensayo271: al insertar app.open se había usado
la descripción Core directamente, omitiendo el sufijo que añade el helper real
llm._native_selection_description.274 usa ese helper, sin cambiar su fuente.
Con la descripción real y28herramientas sigue respondiendo «Steam ya está
abierto.»; con sólo app.open selecciona baxy_app__open tanto para el literal
«Tengo en mente que abras steam» como para «abre steam», manteniendo historial.

275 conserva exactamente las28herramientas de274, mismas descripciones,
historial, literal y parámetros; sólo mueve app.open del final al principio.
Selecciona únicamente app.open. Esto prueba sensibilidad al orden en este
caso; no autoriza una regla que siempre abra una aplicación mencionada.

## 276–277: entidad tipada, no adoptada

Se reutiliza el índice autenticado de aplicaciones y su occurrence_pattern.
Sólo para la búsqueda E5 se sustituye el span por «installed application»;
el texto enviado al selector sigue literal. No se altera el catálogo, la
descomposición ni el conjunto de operaciones permitido. Rango semántico de
app.open:116→7,15→4,26→4 en los tres controles del dueño.

Sin embargo, el selector de producción con esas shortlists responde:

| Literal | Selección277 |
|---|---|
| Tengo en mente que abras steam | Ninguna operación |
| abre steam | game.launch, incorrecta |
| Si, abre steam | app.open |

Mejorar rango no demuestra interpretación útil. No adoptar la sustitución de
entidades ni conservar un cambio de fuente basado sólo en top28.

Contraste primario acotado consultado el2026-09-07:
[EntityQuestions](https://aclanthology.org/2021.emnlp-main.496/) documenta problemas
de recuperadores densos ante entidades; [SANTA](https://aclanthology.org/2023.findings-acl.734/)
estudia representación de datos estructurados con entrenamiento y enmascarado
de entidades. Son tareas/modelos distintos; no prueban nuestra transformación
de consulta en inferencia. El ensayo local276–277, no esos papers, decide aquí.
No se descargó ni entrenó otro encoder.

## 278: prioridad de aplicación, descartada por regresión

Todos los14casos del corpus histórico de desarrollo124 que mencionan un nombre
del catálogo actual, más los3controles del dueño. Se compararon34peticiones
nativas con el mismo selector, catálogo, historial correspondiente y sampler.
Se usó el merge ya existente para mover/incluir app.open primero, sin cambiar
el literal ni ejecutar efectos. No son casos frescos humanos de aceptación.

La variante corrige owner-1 y conserva owner-2/3; también corrige la selección
de «necesito el bloc de notas» en esta capa. Pero win-07, «spotify tiene alguna
ventana abierta», pasa de window.application.status correcta a app.installed
incorrecta. Med-04 pasa de media.play.query a media.play.exact para «ponme algo
de bad bunny en spotify»: tampoco conserva la selección más fiel. Los arrays
expected_operations históricos a veces listan alternativas; no se usan para
ocultar esa diferencia semántica. La prioridad incumple el criterio preregistrado
de no perder controles correctos. No adoptar.

Se comprobó además resolve_explicit_effects sobre los mismos17casos: win-07 es
None, por lo que no hay un bypass determinista que permita ignorar su regresión.
El bloqueo de argumento también permanece: resolve_application_catalog_app_id
exige formas de petición conocidas y no groundea la frase larga aun cuando
el selector elige app.open. No ampliar el recognizer con la frase literal ni
relajar la identidad para convertir cualquier mención en autorización.

## Continuación y procesos

No repetir heurísticas de posición, quitar historial o añadir la frase del dueño
al lector. Siguiente cambio de estrategia: contrastar el contrato nativo con
schemas reales de argumentos frente a la selección actual de herramientas
vacías, sobre casos que distingan abrir/instalado/estado/música. Heredar la
investigación de formato y sus rechazos antes de diseñar la comparación. Si se
cambia contrato, mantener separación propuesta/kernel/ejecución y retirar la
capa sustituida sólo tras prueba integrada. La mejora de la capa nativa no
exime de grounding, publicación veraz ni las100aceptaciones completas.

Sesiones15831(E5) y23984(comparación34) recogidas exit0. Backend89232 es el
existente del dueño, puerto57485: se verificó inactivo por /slots antes de cada
petición; no se ejecutaron operaciones ni se publicó texto en su UI. No es un
backend limpio ni una medición de recursos integral. Instancia84328 preservada
para recuperar conversación oculta; cuestionario101140/63179 sigue del dueño,
sin cierre automático ni modificaciones del agente a answers.json.

Últimos cambios reales de producto siguen siendo266/267, con pruebas dueñas
verdes y modelo/UI/Fast integrados pendientes. El defecto público de afirmaciones
sin lectura continúa abierto; ninguno de estos ensayos lo resuelve.
