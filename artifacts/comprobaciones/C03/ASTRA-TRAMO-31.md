# C03 — tramo31 — dos causas reparadas con herencia

2026-09-06. Tramo30 fue progreso: corpus, medición y adjudicación cambiaron la
prioridad. Tramo31 también es progreso; no bloqueo externo ni cierre de C03.

## Causas y cambios

1. GPU: _explicit_system_status_scope("Que gpu tengo?") ya devolvía gpu_identity,
   pero _ground_explicit_arguments lo convertía en {}. La normalización literal
   eliminaba el enum opcional porque su nombre técnico no estaba en el texto.
   El Core ejecutaba el default summary y el compositor infería GPU del CPU.
   Se hereda el lector existente y se conserva su resultado validado por schema,
   como ya se hacía con otras identidades canónicas. No nuevo provider/operación.
   El mismo arreglo conserva RAM→memory, CPU+RAM→cpu_memory y otros alcances.
2. Negación: _explicit_stable_no_effect_turn_decision ya reconocía leading_negation,
   pero la asignaba a unsupported. «no subas el volumen» generaba inicialmente
   «No subo el volumen.» y el guard de incapacidad lo rechazaba. Se clasifica como
   conversación knowledge; se conserva el tratamiento followup de preferencias de
   silencio. Sin efectos ni respuesta fija, sin relajar el guard de veracidad.

Fuente cambiada: src/baxy_mind/__main__.py, dos decisiones más comentario. No .NET
ni modelo nuevo. No se cambió fuente durante la medición.

## Validación

Se extendió tests/test_system_status_scope_grounding.py: sus25 casos ahora cruzan
también grounding (antes sólo el lector); schema incompatible no puede descartar
scope para simular ajuste. Dos casos reales de negación fijan cero efectos.
Dos expectativas antiguas pedían unsupported al solicitar explicar Spotify sin
abrirlo: se corrigen a knowledge, conservando cero autoridad. Primera corrida
detectó una colisión con pytest.request en el test nuevo; corregida. La siguiente
detectó el cambio no deseado de preferencias de silencio; se conservó followup.

1202 passed +115 subtests,0 skips,6,36s: test_system_status_scope_grounding,
test_c03_request_preservation,test_turn_policy,test_planner. Log
scratchpad/c03-real-users-cause-owner.log. Ruff y git diff --check correctos.
Fast40349 terminal0: scratchpad/c03-real-users-cause-fast.log; build0errores/avisos.
Full pendiente hasta resolver el candidato entero. Sellos actualizados por guion
existente; __main__SHAad82bf6490eccc076e19bce9911c9192376b97f6a8e872125dfa43963dd6cd97,
llmSHA9dc120c15feef8e83a88625aae4e5c7f8ce5ec3919a16bad052505e39c5872c9.

## Producto real

astra-real-users-cause22/:mismos20 conocidos+2limpieza,prerregistro,huellas,adjudicación.
PRUEBAS_CORPUS_REAL_AJUSTE_C03.md compara entradas y respuestas literalmente.
14→16 aceptados sobre20. t10 identifica RTX3060 desde adapters verificados.
t11 responde «Got it, volume no sube.»: útil/sin efecto, mezcla torpe conservada
como observación de desarrollo; no aceptación final de naturalidad. No silencio.
Persisten t8fecha,t17referente volumen,t18identidad,t20negación durante aclaración.
No omitirlos ni contar22/22. T21 «pon el volumen al 100» y t22 «mostrame el volumen»
restauraron/verificaron100,muted:false al terminar la MISMA sesión22.

98540 terminal0,100,06s,GPU3499,56MiB,RAM5165,28MiB,registro intacto. Sin overrides,
sin fixture;conductor sin ventana/wakeoff por diseño. No prueba UI/audio físico.
Sin procesos propios pendientes. Volumen100/no silenciado.

## Siguiente causa

La mente t17 propone audio.volume.adjust para «Ponlo a 100 ahora» y los verificadores
discrepan; deriva a unsupported. En t18 el modelo recibe «quien sos?» y contexto
previo de audio; primero pregunta sobre volumen y la recuperación produce «¿En qué
puedo ayudarte?». El saludo no fue tragado por el shortcut: ya hay un test que lo
impide en Python. No añadir simplemente quien sos a una lista de saludos.
En t20 la aclaración pendiente sigue dominando el texto nuevo. Revisar presentación
del contexto/validación de referencia con capturas de payload y ablar capas sobre
casos reales; no fabricar ejemplos en spanglish ni añadir filtros por frase.
La clasificación negativa reparada NO basta para el contexto pending.

Falta desarrollo verde,corpus revisado y reserva100,UI final,Full,publicación fuera
main,contratos posteriores afectados. Mantener goal activo y objetivo completo.
