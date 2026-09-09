# C03 — tramo46: ajuste incompleto reparado; goal EN_CURSO

Fuente inicial45 y runtime registrado sin cambios. Se repitieron los33 controles
técnicos consumidos de rutas porque la evidencia de confirmación/aclaración/resumen
era anterior a las últimas reparaciones de interpretación. No reserva humana.
Tres averías de composición y sus recuperaciones se midieron aparte en la misma
sesión. Todos los procesos propios de estos paneles terminaron.

## Causa y comparación

astra-routes-regression46:31/33 útiles. t23 «Ajusta el volumen.» recibe audio.status
desde el selector nativo; el lector literal no reconoce aclaración. El provider
consulta correctamente100 pero esa no era la petición. t24 «Déjalo al 80%.» pierde
el antecedente: domain_grounding retira audio.volume y la composición pregunta
por tarea/tiempo sin apoyo. t18 menciona ventana maximizada: sí está en window.resolve,
por lo que no se inventa un fallo por mera redacción.

Herencia: aclaración contractual de volumen relativo en effect_intent y vocabulario
de fijación absoluta del mismo owner. Contraste actual reutilizado:
INVESTIGACION_FORMATO_Y_CLASIFICACION_C03.md e INVESTIGACION_MODELO_C03.md,
consultas2026-09-06 para este Qwen/llama.cpp, y rechazo43 de retirar historial.
No hay nueva configuración ni receta aplicada de otro modelo.

astra-incomplete-volume46: ocho controles, con y sin los tres pares previos
reconstruidos de las respuestas públicas. Misma lista28 de candidatos de request79,
contratos reales del catálogo, payload/response HTTP guardados. No llamadas de
efecto. Con historial reproduce audio.status; sin historial elige familia de
ajuste pero también atribuye audio a volumen de ventas. No promover retirada de
historial. 16llamadas,17,86s,GPU3495,56MiB,RAM2825,86MiB,registro intacto,exit0.
La reconstrucción pública no se presenta como captura del cable del panel original.

## Cambio adoptado

effect_intent reconoce la construcción completa de fijación de volumen sin nivel
como aclaración audio.volume/level. Reutiliza la gramática de verbos de la lectura
absoluta, extrayéndola de sus tres repeticiones. La forma acotada excluye niveles
ya escritos, otros dominios, ámbitos de aplicación, coordinación y revocación.
No se ejecuta ninguna consulta para decidir el nivel. La pregunta sigue siendo
redactada por el modelo, con la identidad y el campo faltante ya conservados.
No cambios de prompt, modelo, C#, provider ni resolución contextual: el mecanismo
pendiente existente completa las tres secuencias una vez preservada su intención.

Pruebas añaden límites de ámbito/dato completo y catálogo sin autoridad; amplían
el test de política existente para exigir pregunta del modelo, sin retrieval ni
selección, aun con una consulta anterior de audio. No duplicación de fixture.

## Producto corregido y defecto pendiente

astra-routes-volume46 repite los33 normales con idéntico orden/contexto.112,33s,
GPU3499,56MiB,RAM5872,35MiB,registro intacto,exit0. Fixture cerrado por producto,
sin limpieza forzada. t23 pide nivel; t24 aplica80 y t25 verifica80. Inglés aplica60,
mezcla aplica40, restauración final100 verificada. Sin voz/UI por diseño del conductor.

32/33 útiles. El ajuste queda reparado, pero t10 ahora dice «la Luna mantiene a la
Tierra en su órbita» en una explicación de gravedad: ejemplo causal incorrecto,
no una preferencia de estilo. Se conserva como nuevo bloqueo de conversación.
No repetir panel para buscar una respuesta favorable. Aislar entrada, historial,
payload real y respuesta bruta con controles de conocimiento antes de tratarlo.
La temperatura recomendada ya fue comparada/rechazada33: no reabrir sin causa nueva.

Seis rutas visibles en estos paneles; progreso y error con prosa siguen pendientes.
Los tres fallos del compositor recuperaron tras restauración, pero no acreditan
una respuesta normal de error. PRUEBAS_RUTAS_C03_TRAMO46.md conserva los literales.

## Validación

Runtime Python -m pytest tests/test_effect_intent.py tests/test_turn_policy.py -q:
2525pass,0skips,58,94s,exit0. Otras cinco suites dueñas del lector/plan/composición:
402pass,115subtests,0skips,3,04s,exit0. Total2927pass,115subtests,0skips.
Logs %TEMP%/c03-incomplete-volume46-owners.log y c03-volume46-related.log.
Fast verde, build4,73s,0avisos/errores,exit0 (sesión43629); no Full.
TRAMO46_PINS.json fija fuentes finales. Un movimiento de comentario junto a _SET_VOLUME_VERB posterior al panel
no cambia código ejecutable; queda reflejado en el hash final.

Reserva239 candidatos aún no descartados: no100congelados/ejecutados.
Validación del dueño de los tres ingleses ya registrada; no pedirla de nuevo.
