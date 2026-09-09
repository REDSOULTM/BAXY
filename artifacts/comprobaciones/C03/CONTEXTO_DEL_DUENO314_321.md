# C03 — identidad con el contexto humano

##314–318: selector, sin cambio adoptado

314 cargó el observador con BAXY_MIND_PYTHONPATH y capturó los argumentos reales
de LlmRuntime._post. Root314 tiene un solo system; la normalización del prefijo
no lo modifica. Chat319 sí tiene varios system: el transporte de producción los
concatena. No confundir captura antes de _post con bytes del socket.

Root314 recibió28 herramientas, incluida system.identity, y contestó que podía
revisar usuario/dominio si se le volvía a pedir. El producto publicó la referencia
genérica al usuario. Se conservan captura HTTP privada, decisiones y DOM.

316 aisló representación e historia con el mismo root y parámetros. JSON+saludo
reprodujo exactamente314; roles nativos+saludo contestaron «Soy BAXY»; JSON sin
saludo tampoco seleccionó identidad; roles nativos sin saludo sí la seleccionaron.
317 conservó historia como datos y dejó el pedido literal: tampoco mejoró.
318 contrastó roles nativos preservando toda la historia en18 controles292:
14/18 frente17/18. Mejoró window.application.status, pero regresó París, repetir
abre Steam y dos negaciones. No adoptar representación ni eliminar la historia
para hacer pasar una pregunta aislada. Sin nuevos prompts, modelos o descriptores.

##319: la pregunta humana tenía nombre y contexto

La petición real del dueño no era identificar su cuenta Windows en una sesión
vacía. Antes había dicho «me llamo emmanuel, dime hola emmanuel» y «Yo soy el».
Los controles de cuenta siguen siendo útiles para verificar resultados de esa
operación, pero no resuelven la pregunta humana en su contexto. Este hallazgo
cambia la siguiente acción: conservar y usar el nombre aportado por la persona.

319 ejecutó por el conductor los seis literales de TRANSCRIPT282 índices
99,101,103,105,107,109, en orden, con respuestas del candidato actual. Perfil
privado separado C03-memory-profile319. Es desarrollo humano recuperado, no
aceptación fresca ni evidencia gráfica/acústica. Runtime registrado intacto.

| Índice | Pedido | Resultado319 | Dictamen |
|---|---|---|---|
|99|Tienes memoria, puedes guardar mi nombr?, quiero decirte mi nombre y quiero que lo recuerdes cuando te lo pregunte|Agotó composición; no respuesta|Falla: no ofreció recibir y recordar el nombre|
|101|mhhhhhh amigo deberias poder|Mmm, sí, pero no pude entender bien la solicitud. Vamos a intentarlo de nuevo.|No resuelve la capacidad reclamada|
|103|me llamo emmanuel, dime hola emmanuel|Hola Emmanuel! 😎|Saludo útil|
|105|Yo soy el|¡Hola! ¿Y tú cómo te llamas? 😎|Pregunta un dato ya aportado|
|107|quien soy|Agotó composición; no respuesta|Falla|
|109|nono, te pregunte quien soy yo, no tu, dime quien eres tu y quien soy yo|Yo soy BAXY, un compañero que solo hace lo que este PC le pide y nada más.|Omite quién es la persona y responde sobre límites|

1/6 útil, dos silencios; exit0 no es aprobación. Los eventos, posteos y terminales
completos permanecen en %LOCALAPPDATA%/BAXY/C03-memory-product319-private. El journal
está en C03-memory-profile319/journal/missions.jsonl; sólo registra memory.status
started/completed. No se guardó el nombre; el perfil de prueba no es el del dueño.
En105 el modelo recibió el nombre dentro de la historia y volvió a preguntarlo:
no se puede atribuir ese fallo a una historia truncada. En109 la primera lectura
de App recibió historia vacía al existir una aclaración pendiente de107; frontera
de continuidad también pendiente. No inventar una única causa para toda la secuencia.

320 probó el resolvedor contextual ya existente sobre esta misma historia, con
un control siguiente de HDMI/VGA tomado del dueño. No arregló las identidades:
repetición vacía105, falsa falta de contexto107 y explicación genérica109. Hubo
truncamientos del esquema en109 y HDMI/VGA; se conservaron reintentos/respuestas.
No promover el resolvedor por mencionar Emmanuel como ejemplo hipotético.

##321: error determinista corregido

read_request109 devolvía identity+knowledge+refuse porque _LIMIT incluía un «no»
suelto y lo combinaba con cualquier segunda persona e interrogativo. Entonces
_compose_situation_payload añadía beyond:none y cambiaba la tarea a explicar límites.
Se separan los términos explícitos de límites de la negación ligada a una actividad,
reutilizando _DOING. No se añade una excepción por nombre o pregunta de identidad.

Baseline6fail/5pass1,33s. Cuatro suites dueñas:1254pass/0skip5,98s. Fuente modificada:
request_reading.py; pruebas en test_request_reading.py. Fast321 verde, build3,78s,
cero errores/advertencias. Producto322 repitió los seis literales: sigue1/6 útil,
dos silencios.109 ahora dice «Soy BAXY. Tú eres el que pregunta quién es quién.»;
se eliminó el encargo espurio de límites, pero todavía falta la identidad humana.

##323–324: la aclaración no debe borrar el historial

323 aisló el chat real322 de109. Antes, sin historial: «Yo soy BAXY, tu compañero
en el PC. Y tú, no lo sabes aún, pero eres el usuario que está hablando conmigo.
¿Quieres que te diga más sobre nosotros? 😎». Con sólo el historial real repuesto:
«Yo soy BAXY, tu compañero en el PC. Y tú te llamas Emmanuel. 😎».
Mismo modelo y payload salvo historia; sin resolvedor320 ni instrucciones nuevas.

324 transporta BuildMindHistory también si existe aclaración pendiente, manteniendo
pendingClarification:false para la primera lectura. La reanudación y autorización
siguen en MindClarificationPolicy. Baseline de un nonce introducido antes de una
aclaración:1fail/0pass/0skip5s, historia perdida en el mensaje del proceso. Pruebas
dueñas324 en curso; pendiente Fast y misma secuencia completa325. No se declara
el arreglo global por un replay nativo.

## Preferencia vigente del dueño

Pidió cerrar BAXY y mantener el trabajo; no lo usará ahora. UI315 y su backend se
cerraron después de verificar cero turnos nuevos y guardar snapshot319. No volver
a abrir una instancia para uso manual sin que lo pida. La encuesta742 continúa
abierta, en edición por él; avisará cuando esté lista. No modificar sus marcas.
