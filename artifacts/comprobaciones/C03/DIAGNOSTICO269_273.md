# C03 — comparaciones269–272 y revisión privada273

C03 EN_CURSO. Ninguna variante de estos tramos se adopta como reparación.
No hubo cambios de fuente del producto ni ejecución de operaciones del dueño.
El dueño terminó de probar y autorizó revisar la sesión264 y operar su bandeja.

## Composición269

Se reutilizó llama.cpp b9980 PID89232, puerto57485, Qwen3.5-4B Q4_K_M del
override264. Antes de cada petición se comprobó /slots sin inferencia activa.
Es el backend existente, no una instancia limpia ni «modelo solo». Las cuatro
peticiones directas no pasan por la UI ni ejecutan herramientas. Se conservan
payloads congelados267, temperatura0, cache_prompt=false y orden antes/después
repetido dos veces. PREREG y respuestas completas en astra-native269.

| Variante | Respuesta, idéntica en ambas repeticiones | Resultado |
|---|---|---|
| Contexto antiguo en situation | Ya he abierto Steam. | Atribuye efecto no ejecutado |
| Contexto separado, fuente267 | Steam ya está abierto. | Aún afirma estado sin lectura actual |

Ambas terminan en stop. Separar procedencia es correcto estructuralmente pero
no demuestra veracidad pública. No ampliar una lista de frases prohibidas para
ocultar este defecto. Sigue pendiente resolver selección y validación de hechos.

## Recuperación270

Mismo E5 CPU y catálogo Core262: retirar únicamente el sufijo de esquema de
los documentos de búsqueda empeora app.open para «Tengo en mente que abras
steam» de rango116 a130 y para «Si, abre steam» de26 a35. Esta última pierde
la shortlist28. No adoptar. astra-retrieval270 contiene entradas y resultados.
Sesión de comando77778 recogida exit0; proceso de medición terminado.

## Selección271–272

Sobre HTTP5 real de UI263, se reemplazó sólo el último candidato por app.open
del catálogo autenticado, manteniendo28 y todos los mensajes/parámetros. Es
una intervención diagnóstica con la operación esperada, no un algoritmo de
recuperación desplegable. Antes y después responden «Steam ya está abierto.»
sin tool_calls. astra-catalog271.

Con ese mismo catálogo, quitar sólo el diálogo previo tampoco selecciona:
«No puedo abrir Steam directamente, pero puedo ayudarte a verificar si ya
está instalado o a iniciar una aplicación específica si lo necesitas.
¿Te gustaría que verifique si Steam está instalado en tu sistema?»
Termina en stop. astra-history272. No adoptar borrado del contexto ni atribuir
todo el fallo al historial: la abstención persiste sin él. No repetir variantes
de etiquetado de historia. Próximo aislamiento: cobertura entendida del contrato
app.open y competencia entre herramientas, con modelo nativo y catálogo real;
resolver también el argumento/identidad antes de afirmar reparación integrada.

## Sesión del dueño273

La copia268 conserva155 registros de decisiones, con54 finales:39conversation,
8action,1plan,6clarify. Son registros del protocolo, no54 éxitos de UI. Hay20
fallos de intento:2ValueError,2TimeoutError,8PlannerContractError y
8ConversationReplyContractError; no se convierten en20 turnos distintos.
Composición:251 filas de borrador,156 combinaciones distintas
trace/etapa/hash/publicación/motivo;100 admitidas por compositor. No equivale a
100 respuestas finales mostradas. Rechazos deduplicados incluyen33extra_claim,
9missing_name y8missing_failure.60 respuestas brutas,43 hashes de pedido.

Informe literal privado:
%LOCALAPPDATA%/BAXY/C03-owner264-snapshot268/REVIEW273.md.
Hash y recuentos en astra-owner-review273/RESULT.json. No se infirieron entradas
ausentes ni se asignaron respuestas brutas a una publicación no observada.
Falta recuperar el texto completo de la conversación de la UI. La instancia
permanece viva y oculta a bandeja; no reiniciarla antes de preservar esa memoria.
La herramienta de escritorio no expuso el icono de bandeja; varios screenshots
mostraron otra ventana activa, por lo que no se hicieron clics con coordenadas
inciertas. El dueño autorizó tomar control: no volver a pedir permiso rutinario.

## Entrega y siguiente trabajo

Cuestionario268 entregado en http://127.0.0.1:63179/, PID101140 sin cierre
automático. Las742 filas son todo el pool recuperado, no todo el PC. Marcas del
dueño en answers.json: no sobrescribir, no rellenar por él ni congelarlas mientras
revisa. Se mantienen autoría y expectativa independientes. No son por sí solas
100 casos frescos de aceptación.

Fuente266/267 aún carece de Fast/modelo/UI integrado; últimoFast262. En estos
tramos sólo se compararon diagnósticos y se entregó herramienta privada, así que
no se repitió Full ni se declara cierre. Continúa todo el alcance de ocho rutas,
100humanos frescos, averías/recuperación, UI/voz/recursos, runtime/instalación,
continuidadC04–C09, Full y publicación fuera main.
