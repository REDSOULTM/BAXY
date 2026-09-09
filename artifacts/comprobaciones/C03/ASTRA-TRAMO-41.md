# C03 — tramo41 — selección nativa y contexto

C03 EN_CURSO, sin bloqueo externo. La respuesta anterior al dueño sólo confirmó
una instrucción existente (no progreso); este tramo sí cambia fuente y mide producto.

## Cambios y evidencia

La candidata de llm.py usa AUTO como selección primaria sin el clasificador de
tipo secundario, conservando el catálogo, el grounding de argumentos y los gates
de main/Core. No está aceptada como solución completa: el producto sigue perdiendo
peticiones tras negaciones y un seguimiento. Se rechazan llamadas truncadas,
fuera del catálogo o con argumentos prematuros; cuatro controles de frontera.
La fuente conserva ramas nativas antiguas ahora inalcanzables: retirarlas si se
adopta definitivamente la candidata; no presentar este WIP como cierre limpio.

astra-native-primary13: exit0,117,22s,GPU3499,56MiB. Presupuesto nativo96.
astra-native-budget13: exit0,103,17s,GPU3497,56MiB. Presupuesto256 y una frase
si se abstiene. Steam pasa de composition_failed a prosa falsa (Microsoft),
SSID conserva analogía falsa; más presupuesto no acredita calidad. No repetir
esa estrategia. Los fallos se mantienen en el informe literal.

astra-knowledge-history-factorial:12 llamadas,35,61s,GPU3497,56MiB,registro intacto.
Mismo modelo/template/sampler/budget; factores políticas presentes/ausentes e
historial publicado presente/ausente. Con políticas y sin historial ajeno al tema,
Steam es Valve y SSID es nombre de red. Con historial hay errores. Sin políticas,
varias salidas se cortan. No atribuir desconocimiento universal al modelo ni borrar
la conversación general. Se heredan instrumentos/documentación33/40 y el detector
de tema de request_reading, cuya evidencia histórica ya describía arrastre de temas.

La generación de una definición nueva con un tema de una palabra omite contexto
ajeno. Se conserva el historial almacenado; temas ya mencionados, referencias y
descripciones complejas conservan contexto. No hay nombres de productos en la regla.
astra-definition-context7: exit0,82,11s,GPU3499,56MiB,registro intacto. Steam y SSID
correctos, agua/aire/DNS útiles. Dos fallos nuevos expuestos por los controles:

- «¿y para qué sirve?» pierde SSID: turn-audit request18 cambia knowledge a clarify
  en observation_not_recital. _catalog_answers_the_request vuelve a consultar una
  compatibilidad sin historial, decide web.search y pide un propósito. No fue la
  eliminación del historial de chat: chat no se alcanzó en ese turno.
- «explain what DNS does»: primer chat correcto; App rechaza www.google.com como
  internal_code; compose rechaza www.example.com dos veces y la tercera prosa empeora.

Se corrige esta segunda causa en los verificadores Python y App: los hosts con
prefijo explícito http(s) o www no son operaciones internas por contener puntos.
Los códigos fuera del host, snake_case y las demás fugas siguen rechazándose.
Pruebas positivas y negativas en ambos extremos; no se maquilla la captura anterior.

## Validación

- Python siete suites dueñas:2819pass,0skip,53,66s; c03-tranche41-owner.log,
  sesión64620 terminal0. Incluye effect_intent y los pines de veto.
- .NET C03FactPreservationTests y Goal06VisibleVoiceTests:45pass,0skip,3s;
  c03-public-host-dotnet.log,22559 terminal0.
- Ruff y git diff --check pasan. Fast72324 terminal0, build21,32s,0errores/avisos.
- No Full ni UI41; no son los cien reservados. Public-host3 completado: exit0,57.12s,GPU3497.56MiB,registro intacto; ver dictamen literal.

Pines: llm a9a4d61a022ba227a623d5bdf6bbb5013ad8fd6659c6158d60d276d98b80c763;
main943b077761c897ef6f6904b5d6339bc400c6ffd67b01d6b0f545981e73f08a23;
STT afed307eeea1956f3e75b2a97ebb756292ddc0696e1380a1d5c6854b3a54525b.
Registro de modelo intacto. No cambios en main ni commit/push.

## Continuación

Terminar public-host3 y registrar literales. Resolver conjuntamente la recuperación
de observaciones sin contexto y el contrato global de negación; no volver a añadir
clasificadores de tipo que contradicen la selección sin evidencia. Se mantienen
pendientes profundidad/truncación, reserva100 con procedencia/autoría/contexto,
ocho rutas, averías/recuperación/UI/recursos, contratos posteriores, Full y publicación.
Informe: PRUEBAS_SELECTOR_Y_CONTEXTO_C03.md. Copia pre-candidata:
scratchpad/c03-native-primary-before/{llm.py,test_turn_policy.py}; no revertir otros
cambios acumulados. CHECKPOINT es la entrada para reanudar, no el tramo32 del goal.
