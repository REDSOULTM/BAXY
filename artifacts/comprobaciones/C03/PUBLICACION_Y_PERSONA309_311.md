# C03 — el sustantivo no es metadiscurso

## Evidencia y primera frontera

Fast308 pasó completo; build Release2,99s, cero advertencias y errores.
UI309 ejecutó el literal humano de desarrollo «quien soy» mediante el formulario
real de React/WebView. La sonda terminó exit0, pero publicó `published:false`:
el DOM sólo tenía el pedido y la bienvenida. No acredita una respuesta correcta.

La mente recibió turn.decide después de catalog.configure y eligió conversación.
system.identity estaba entre los candidatos; no se ejecutó. La hipótesis inicial
de mente aún sin arrancar no explica esta traza. La identificación concreta sigue
pendiente en selección/contexto; no se finge un dato de Windows no leído.

Python aceptó seis composiciones idénticas:
«Tú eres el usuario que está hablando conmigo.». La App rechazó cada una con
`internal_code`: ContainsPersonMetadiscourse vetaba cualquier «el usuario»,
«the user» o «los usuarios». Sólo exceptuaba literalmente «usuario admin».
El baseline de ModelMessageComposer reproduce la pérdida y el reintento idéntico.
La marca response.final de la traza no acredita una fila publicada.

UI310 se abrió normalmente, App102648/backend75204/puerto49955; bienvenida
confirmada en auditoría y ventana BAXY con handle38603984. Se cerró sólo para
recompilar311, tras comprobar cero turnos del dueño y conservar sus seis logs en
%LOCALAPPDATA%/BAXY/C03-ui310-snapshot311. El cuestionario742 permanece abierto.

## Sustitución

La guarda existente ahora exige un sujeto de tercera persona ligado a un verbo
de pedido, deseo o discurso. Se retiran el veto del sustantivo, la excepción de
nombre y los dos chequeos redundantes. No se añade otra capa, prompt o modelo.
El compositor Python tenía el veto equivalente en inglés; se sustituye por el
mismo criterio ES/EN. Una descripción de permisos o una respuesta que se dirige
a la persona no implica narrar su pedido en tercera persona.

El control antiguo que vetaba «Me ocupo de ayudar a los usuarios con sus preguntas»
también codificaba ese falso positivo: es una autodescripción en primera persona.
Se corrige esa expectativa y se añade al lado el contraste «El usuario preguntó
de qué me ocupo en el PC», que sí debe rechazarse. No se omite la prueba ni se
relaja un umbral. Esto no adjudica toda respuesta genérica como suficientemente útil.

## Validación

Baseline .NET sobre referencias308: seis respuestas válidas rechazadas y dos
contrastes rechazados; una novena aserción exigía una causa específica aunque
otra guarda previa también rechazaba, corregida para medir el rechazo.
Log original:7fail/2pass/0skip431ms. Baseline Python:8fail/7pass/46deselected0,77s.
Con fuente311: tres suites Python1040pass/0skip5,52s.

Primer baseline .NET completo chocó con DLL de UI310; conservado. El primer
rerun de voz se lanzó por error antes de terminar el host de la suite anterior y
chocó con su DLL; conservado. No son pases. Esperar al host antes del rerun.
La tanda .NET inicial incluye PlannerAppBoundaryTests, Goal06VisibleVoiceTests
y MindShellEndToEndTests:154pass/1fail/0skip2m19s. El único rojo corresponde a la
expectativa de autodescripción explicada arriba. Rerun de las mismas tres clases:
155pass/0fail/0skip2m16s, `dotnet-owners-corrected.log`. Fast311 pasó completo;
build Release17,84s, cero advertencias y errores, `fast311.log`.

## Producto312 y reapertura313

UI312: mismo literal «quien soy», misma ruta conversación y misma respuesta bruta
que309: «Tú eres el usuario que está hablando conmigo.». Ahora aparece en el DOM
como fila BAXY después del pedido; una composición conversacional frente a seis
en309, sin agotar reintentos. `ui.turn published:true`, terminal done y exit0.
Esto acredita reparación de publicación, no resolución útil de identidad concreta.

El observador HTTP preparado para312 NO se cargó: se configuró PYTHONPATH, mientras
MindSidecarClient consume BAXY_MIND_PYTHONPATH. No existe http-posts.jsonl; por tanto
312 no aporta payload HTTP nativo. Conservar PREREG/script tal como se ejecutaron,
sin cambiarles retrospectivamente la variable. Para la siguiente captura reutilizar
scratchpad/c03-launch288.py, línea env.update, con la variable correcta y sin su
override de modelo. No repetir sólo para conseguir un resultado favorable.

BAXY313 reabierto con `py main.py`, sin hook, override, sonda ni cierre automático.
App70260/createTime1788833381.7059455, launcher105716. Logs privados en
%LOCALAPPDATA%/BAXY/C03-ui313-private. Preservar cualquier nuevo turno del dueño.
Cuestionario742 verificado HTTP200; no se modificaron sus respuestas.

Siguiente: capturar el payload real del selector y resolver por qué responde de
forma genérica a la identidad; no añadir una excepción por frase ni dar por leído
un perfil que no se consultó. La identidad y el resto de C03 siguen EN_CURSO,
sin Full de reparación ni cierre del goal.
