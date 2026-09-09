# C03 — EN_CURSO — 431 validado;432 producto5/8;433 validado;4346/8;435 cerrado;436 validado;437 preparado

Goal completo, Goal-c03 / HEAD 2bf3d4c. Preservar WIP/main/evidencia. Sin agentes,
commit/push ni Full durante reparación. BAXY manual cerrado. Encuesta terminada:
742 respuestas, revisión1248; servidor101140/padre29800 intacto.17 mensajes directos
consolidados; automáticos excluidos. No modelos/builds activos.

## Mejora medida
425: cache-ram0 y no-mmap sólo con GPU; CPU conserva mmap. Mismos pesos, contexto,
precisión, slots y sampler.6 focales/293 owners +121subtests,0skips; Fast verde
build4,11s.426 producto: RAM3106,70MiB/GPU3177,56MiB,55,422s, sin corte.
8 terminales,4 útiles, contenidos iguales423/424. Comparación424 mmap+cache0:
RAM5207,20MiB. RSS del árbol; no mínimo global ni certificación de voz física.
Detalle legible en RECURSOS_2026-09-08.md; pruebas y hashes en astra-host-memory425.

## Reparación actual
426 T3/T6 «Abre una aplicación»: native app.open correcto; domain_grounding lo
retira por falta de appId. T3 pide permiso;T6 dice falsamente que no puede.
431 ya reutiliza resolve_explicit_clarification_intent: rama de app.open existente,
gramática de petición completa con objeto genérico, pregunta del modelo por la
aplicación. No ampliar autoridad de appId ni añadir otra capa. PREREG431 escrito.
Baseline15fail/20pass; focal35pass; owners2714pass/0skips48,67s; Fast verde
build3,86s/0warnings/errors. RESULT/PINS431. Siguiente: ejecutar
433: gramática completa de presentación personal en lector social existente;
declinar órdenes/preguntas añadidas con vocabulario compartido, sin nuevos
clasificadores ni efecto. 433:baseline13fail/104pass;focal117pass;owners1397pass/0skips6,83s;
Fast verde build4,23s/0warnings/errors. RESULT/PINS433. Siguiente:
`runtimePython -X utf8 scratchpad/c03-private-product434.py`; mismo432,
sólo fuente433. No fuente mientras corre. Recoger resultado individual.
432:8 publicados,5 útiles; T3 pregunta aplicación. T5 aclaración PC errónea
contamina T6;T7 sujeto erróneo. RAM2377,15MiB/GPU3177,56MiB49,344s, sin corte.

Presentación personal:426/427 AUTO confunde nombre humano con cuentaWindows.
427 guardia genérica9/13: descartar (rompe requests de memoria y app incompleta).
428 status session_context_only2/4;429 evento conversation4/4 composición, todavía
sin clasificación segura.430 alias identity→windows_account descartado:4/11pares,
fallo de harness antes de cuentas y tres presentaciones aún incorrectas. RESULT430.
No atajo C# con DeclaredNameInputPattern: puede tragarse órdenes sin puntuación.

## Fuente anterior y pendientes
418 precedencia privada sobre aclaración pública:6 focales/2007owners/Fast;
runtime explícito omitido, no pass. EN verificado en426; ES T7 dice «Mi nombre»
en vez del nombre humano.416 OS Caption CIM:36provider/193integration/Fast;
4178/9 útiles, cuentaT3 pide permiso innecesario.410/402/404/395/397 conservados.
413/414 early-read intercambian fallos;349 source=user no arregla sujeto.

Quedan ocho rutas y expectativas742/fallos manuales264;0 requisitos certificados
finales y0/100 humanos frescos (204potenciales335 reservados). Averías/recuperación,
UI real,voz física/ASR/wake y ≤4GB conjunto,runtime/instalación/contratosC04–C09,
Full final verde entero y publicación fuera de main. Sin ETA ni cierre parcial.

434:6/8 terminales útiles. T5 social inventa actualización de memoria;T6 aclarada.
T7 mismo error de sujeto. RAM2711,07MiB/GPU3177,56MiB36,047s. RESULT/PINS434.
435 cerrado:7actos sociales4/7→7/7 semánticos; tres controles sin transformación
idénticos. RESULT/PINS435; no idioma EN normal acreditado (sistema ES fijo).
436 validado;437 preparado: acotar sólo historia enviada a chat de decisión explícita social;
historia original intacta, otras rutas/pending conservadas. Focal/owners/Fast y437.

436:3baselinefallos;26focal/1397owners pass,0skips6,94s;Fast verde4,19sbuild.
RESULT/PINS436. Siguiente ejecutar runtimePython -X utf8
scratchpad/c03-private-product437.py. Mismo434, sólo scope436. Sin fuente
durante corrida. VerificarT5sin falso save,T6aclara,T8recuerda;T7pendiente.
