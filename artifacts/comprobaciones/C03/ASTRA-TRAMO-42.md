# C03 — tramo 42 completado; goal EN_CURSO

El tramo41 fue progreso; C03 sigue activo y sin bloqueo externo.

## Causas contrastadas

Se reutiliza la investigación Qwen/function calling y las mediciones33/40/41;
no se vuelve a buscar whitespace ni a cambiar sampling. El docstring heredado
de operation_is_the_requested_effect ya documenta que sólo rechazaba21/84propuestas
erróneas. Esa compatibilidad débil ahora degradaba una explicación a aclaración.

astra-observation-selection:32 llamadas en ocho controles,14,20s,GPU3497,56MiB.
Para «¿y para qué sirve?» tras SSID, el verificador débil acepta hora/audio/web.
AUTO con historial normal se abstiene ahí, pero pierde dos lecturas y propone
hora ante una prohibición. No se adopta esa variante sin corregir contexto.

astra-native-reference-packet:los mismos ocho controles,6,73s,GPU3497,56MiB.
Una sola diferencia: historial como datos de referencia junto al texto actual
literal, en vez de repetir rolesuser/assistant. Ocho conjuntos de operaciones
correctos, incluidas abstenciones. No es aceptación ni prueba de todo el catálogo.

La fuente adopta ese paquete de referencia en el selector nativo. La recuperación
de catálogo usa AUTO con historial, en vez de los booleanos débiles por operación;
una abstención no vuelve a pasar por el clasificador anterior. Pruebas de catálogo,
literalidad y contexto conservadas. Legacy sin AUTO mantiene su camino explícito.

astra-reference-context11:exit0,97,14s,GPU3499,56MiB,registro intacto. Seguimiento
SSID reparado;8/11útiles. Las tres peticiones de hora tras negación siguen fallando.

La traza t8 revela otra causa anterior a Python: MainWindowViewModel salta
turn.decide si IsNegativeConstraintRequest encuentra «no abras» en cualquier parte.
Envía «no abras Steam, dime la hora» directamente a message.compose sin hechos,
que inventa14horas. El selector no llegó a recibir esa petición.

## Fuente de la candidata actual

- Retirado el atajo negativo de la App y su helper sin otros consumidores.
  Tres pruebas de frontera exigen turn.decide con el texto completo, también para
  una prohibición sola. El primer intento de tests falló por exigir un outbox en
  una ruta sin efecto que no crea archivo; corregido el test para su objetivo real.
- CompoundEffectContract no convierte una cláusula negativa en prohibición global
  cuando hay varias cláusulas. El conteo preserva efectos positivos; las negaciones
  personales EN también son negativas, no efectos desconocidos. Se mantienen
  prohibiciones solas, no-tools, correcciones, otros dispositivos y efectos faltantes.
  No se retira grounding de argumentos ni autorización/verificación del kernel.
- Ocho nuevos controles Python de conservación y restricciones pasan.

## Validación y procesos

Se retiraron las ramas nativas inalcanzables bajo el retorno primario de _decide_turn.
La primaria vuelve a aplicar la normalización heredada de predecesores técnicos
redundantes; conserva grounding_required de los argumentos. Un test específico
comprueba ese contrato sin ejecutar mensajes externos.

astra-scoped-constraints11: 11/11 útiles, 91,16 s, GPU 3499,56 MiB, RAM 6473 MiB,
exit 0, registro intacto. Los mismos once textos de reference-context11 pasan ahora.
Las horas t6/t7/t8/t11 están verificadas: UTC y offset -180 corresponden a 21:32.
No se abre Steam; las prohibiciones no invocan Core. Esta corrida precede la limpieza
de ramas nativas; la siguiente usa la fuente final.

astra-integrated-real22: 19/20 casos de desarrollo útiles y dos controles de limpieza
aprobados aparte. 96,2 s, GPU 3499,56 MiB, RAM 5917,14 MiB, exit 0, registro intacto.
Conserva fecha contextual, volumen absoluto contextual, Steam y dispositivo de audio.
«no silencies el audio» falla: dos fallos de contrato y respuesta final «No pude
interpretar correctamente la solicitud». No es avería inyectada ni aceptación.
Las observaciones acreditan hora 21:45, fecha local 2026-09-06, GPU y audio.
Audio: 100 → 35 → 100, sin silencio, con lectura final. La identidad usuario/REDNOTE
procede de system.identity; no se adjudica como invención.

Validación final de fuente:

- Siete suites Python (turn_policy, request_reading, compose_contract, effect_intent,
  c03_request_preservation, compound_missions, price_v8_veto_damage_by_cause):
  2831 pass, 0 skips, 63,69 s. scratchpad/c03-tranche42-final-owner.log; 99637 exit 0.
- .NET NegativeWordingStillCrossesTheMindDecisionBoundary|Goal06VisibleVoiceTests:
  15 pass, 0 skips, 17 s. scratchpad/c03-negative-boundary-dotnet2.log.
- Fast: verde, build 21,24 s, 0 avisos/errores. scratchpad/c03-tranche42-fast.log;
  17258 exit 0. Ruff pasó. Full y UI actuales aún pendientes para el cierre.
- 42417, 90464 y 74867 terminaron con exit 0; no quedan mediciones propias en curso.

Pines de fuente final en scratchpad/c03-tranche42-final-pins.log:
llm 5420ee567d2ba107d1f3e7900340bbad388226205b169c357dd51120e30a3399;
__main__ e4775597275036cd35a84902d7fee3bea16e9fc520d13b691e0cfba0b50b3ef4;
effect_intent b73c0ab6b3280721eb68ec248f7c53287e1cc0b4a37575f8bac36836d3c69ff9.

PRUEBAS_CONTEXTO_Y_NEGACION_C03.md conserva 40 llamadas del modelo y 44 respuestas
de producto, incluidos los fallos. No son 84 casos nuevos. El próximo paso parte
de turn-audit.jsonl de integrated-real22 (request_id 75) para localizar el contrato
que rechaza la prohibición de silencio. No repetir los veinte casos ni Full antes
de una corrección con evidencia. El orden inverso de cláusulas negativas también
requiere contraste; no se afirma cobertura general de negaciones.

Faltan desarrollo/reserva de 100 con procedencia, autoría y exposición revisadas,
ocho rutas, averías/recuperación, UI/recursos con voz, contratos afectados y Full.
Registro y fuentes de herencia intactos; sin commit/push ni cambios en main.
La reiteración del dueño sobre herencia + estado del arte está en el goal activo;
el documento ejecutable exige ahora el registro breve de cada comparación relevante.
