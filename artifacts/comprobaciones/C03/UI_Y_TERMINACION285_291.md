# C03 — UI, truncamiento y abstención285–291

Estado EN_CURSO. Única fuente adoptada continúa284. No adoptar285–291.

## Verificación del cambio284

Fast287 completo: source_quality_gate_passed: mode=Fast. Compilación Release
4,45s,0 advertencias,0 errores. Log astra-runtime287/fast.log. No Full.
Integra también266/267. Pruebas dueñas284:1012pass0skip5,20s,ruff verde.
UI288 real (py main.py, Qwen3.5 mismo override264, fuente284):
«quien soy» → «Tu nombre de usuario en el sistema es usuario.» Visible en pantalla,
21:24:43→21:24:45 hora local, tras system.identity leído y verificado.
Se observó estado Speaking, sin grabación física nueva: no acreditar audio físico.

## Comparaciones de conversación285–287

285 reconstruyó diálogo desde UI282 para índice5 y capturó payload de chat,
pero usó el default0,7 en vez del0 del caller real __main__:6432. No llamarlo
replay fiel del turno original. Su último print falló por encoding de consola,
después de obtener respuesta; no es fallo del LLM. Los logs se preservan.
286 corrige temperatura0 y salida ASCII de consola (JSON guardado UTF8).
Comparó presencia de instrucción de etapa y diálogo, más identidad mínima.
No reprodujo la negativa original; aparecieron nombres de museos no acreditados.
No adoptar supresión de instrucciones ni historial basándose en ese diagnóstico.
287 repitió los mismos payloads con modelo2507 registrado y servidor/perfil
constantes. Tampoco certifica calidad; identidad mínima trunca en ambos modelos.
No promovido ni cambiado registro. SHA del modelo2507 y registro verificadas.
Servidor287 terminado en finally, MODEL_STOP.json. La comparación de prosa no
diagnosticaba la primera frontera errónea del turno inicial de París.

## Primera frontera errónea recuperada en UI288

«Hola hablame de paris, donde podria ir?» →
«No puedo darte recomendaciones porque la interpretación de tu solicitud falló.»
En esta sesión el contexto previo es el control de identidad; no idéntico264,
pero reproduce el mismo resultado visible y ahora conserva los payloads internos.

HTTP7: selector nativo con28tools, auto,256tokens,temperatura0; comienza a
redactar recomendaciones en lugar de terminar la selección. finish_reason=length,
256tokens de salida,2246 de entrada,11,438s. llm.py rechaza selección truncada.
HTTP9: repite el selector y agota presupuesto local (TimeoutError a3,672s).
HTTP10: recuperación pide preferencia de experiencia. HTTP11: compositor de error
genera una recomendación útil, pero omite la causa de fallo suministrada; el
validador la rechaza correctamente para ese contrato. HTTP12 formula el fallo.
El problema inicial no es que ese compositor desconozca París: es el selector.
No aceptar decisiones truncadas ni atribuir éxito a la recuperación.
Logs completos privados C03-ui288-private/http-posts.jsonl, turn-audit.jsonl,
compose-audit.jsonl. Observador delega sin modificar payload/respuesta/algoritmos.

## Decisión sobre289–291

Herencia: biblioteca/gemma4-agent/documentacion/02_router/research/1_toolcalling.md
333–335 propone required permanente con resultado conversacional; 4–5 separa
sintaxis de semántica. INVESTIGACION_FORMATO_Y_CLASIFICACION_C03.md recuerda el
required de efectos antes rechazado. Aquí se probó un resultado interno sin
autoridad ejecutable, no forzar una operación después de una abstención.
Contraste oficial consultado2026-09-07:
https://raw.githubusercontent.com/ggml-org/llama.cpp/b9980/docs/function-calling.md
El documento acredita soporte nativo/plantillas; el comportamiento required con
Qwen3.5 concreto se midió localmente, no se dedujo de la tabla de familias.

289:14 llamadas,7 controles antes/después. Required + baxy_no_effect_decision
(sin argumentos ni autoridad), cambiando sólo frases incompatibles del selector.
París: antes length8,547s, después decisión sin efecto tool_calls3,031s.
Identidad, apertura simple, estado de ventana y música conservan selección.
app05 sigue confundido con game.install.status y cmp01 sigue omitiendo app.open.
No declarar7/7. Los expected de med04 son alternativas, no compuesto.

290:22 llamadas,11 controles históricos de alcance reconstruidos por builder
actual con descripciones autenticadas y subconjunto original. La propuesta
pierde scope3 «no abras Steam, dime la hora» (retira reloj permitido) y scope7
traducción (propone reloj). Baseline actual ya falla scope8 y scope10; no
atribuir a la propuesta esos errores anteriores. Propuesta descartada.

291:18 llamadas, sólo cambia descripción de la decisión vacía por predicado
de cero efectos en el pedido entero. Recupera scope3, pero pierde apertura simple,
scope6 prohibición de herramientas, mantiene error de traducción y falla scope8.
Segunda propuesta descartada. NO seguir otro barrido de nombre/prompt/descriptor
de abstención ni esconder regresiones con bypass posterior.

Siguiente estrategia: mantener AUTO y estudiar terminación del canal libre del
selector con el contrato/parser del backend, o sustituir esa representación
completa conservando los18 controles. No aumentar límites a ciegas, relajar
validación de length, forzar efectos ni añadir patrón París. Investigar mecanismo
antes de implementar. Corpus final100 permanece separado de estos controles.

Instancia264 cerrada sólo después de comprobar SHA de transcripción282. Árbol
propio completo terminado, cuestionario excluido. Nueva UI288 queda abierta sin
temporizador; cuestionario742 sigue en63179, sin editar marcas. Ocho rutas,
100/100frescos, averías/recuperación, voz/ASR/recursos finales, runtime/instalación,
continuidadC04–C09, Full y publicación fuera main pendientes. No bloqueo externo.
