# C03 — tramo32 — contexto, hora y límites del modelo

2026-09-06. Tramo31 fue progreso;tramo32 también cambia fuente y conducta medida.
EN_CURSO,sin bloqueo externo ni publicación. No modelos nuevos ni subagentes.

## Cambios conservados

- llm._build_turn_policy_payload sitúa el texto actual intacto DESPUÉS del catálogo,
  sin cambiar historial,modelo,schema ni verificadores. Recupera la identidad.
- UserMessagePolicy.ClockTokens admite minutos con1o2 dígitos. En17:04 el modelo
  decía correctamente «Son las17 horas y4 minutos» con los espacios normales;
  Python lo aprobaba y C# exigía dos dígitos. NUnit usa el draft literal capturado
  y rechaza17:05,17:40 y una hora adicional. No relajación de igualdad horaria.
- MainWindowViewModel:la primera clasificación aislada de una aclaración pendiente
  envía pendingClarification:false,coherente con history:[]. Antes falseaba estado.
- _prepare_turn_result:un pedido autónomo knowledge reconocido por el lector
  existente envía preserveObjective:false. Fragmentos siguen con defaulttrue.
  Reutiliza protocolo;no añade parámetro ni clasificador. La restricción ya no se
  concatena a la pregunta de dispositivo,aunque su respuesta final aún falla.

## Producto medido

astra-real-users-order22/:20conocidos+2limpieza,99,09s,GPU3499,56,RAM5006,70MiB,
52435terminal0. Identidad resuelta;fallo nuevo17:04 (capturado,no atribuirlo al orden).
astra-real-users-pending22/:mismos22,90,16s,GPU3499,56,RAM5073,18MiB,46657terminal0.
17/20aceptados;3fallos:t8fecha,t17referentevolumen,t20respuesta negativa.
PRUEBAS_CONTEXTO_REAL_C03.md conserva cada literal y adjudicación. No100frescos ni
porcentaje de goal. T6 explicaSteam útilmente,con imprecisión secundariaWorkshop;
t11 «Okay,no subo el volumen» entendible (texto con espacios en informe).
T18 «Hola,soyBAXY...» responde identidad. T20 «SIEMPRE.¿Qué necesitas...» no aprueba:
que ya no arrastre pending no significa que la petición esté bien respondida.
T21y22 restauraron/verificaron volumen100,muted:false,en misma sesión22.
Registro intacto,sin overrides,sin fixture,conductor sin UI/wakeoff. No apps pendientes.

## Comparaciones por capas

astra-real-context-ablation/:5casos literales conocidos,3etapas:decisión primaria
sin historial,con historial y wrapper con historial;24,84s,GPU3497,56MiB,96612terminal0.
Historial reconstruido desde6mensajes públicos;no wire original ni pending exacto.
Mismos nombres candidatos que raw_attempt original;schemas/descripciones del Core.
Con historial t18pasa de conversación a audio.status; t17pasa de audio.volume a
audio.volume.adjust. El wrapper adicional convierte t17en plan/disagreement.

astra-real-context-order/:baseline vs pedidoalFinal vs historialcomoDatos,5casos×3,
18,34s,GPU3497,56MiB,74583terminal0. Mover pedido al final recupera clasificación
fecha/identidad/negación en la primaria. HistorialcomoDatos no mejora volumen;
no se implementó esa variante adicional. La conducta integrada decide, no estos5.

astra-negative-dialogue-ablation/:6entradas reales ya consumidas,baseline vs añadir
instrucción genérica sobre reconocer restricciones;9,70s,GPU3497,56MiB,31942terminal0.
No mejora t20 («SIEMPRE»). RECHAZADA,NO añadida a fuente. No repetir esa instrucción.

astra-real-dialogue-system-layers/:mismas6,18llamadas,bare/identidad/baseline;
17,86s,GPU3497,56MiB,14900terminal0. Quitar sistema tampoco da un panel verde:
bare t20pide aclarar;identidad t20dice «el audio sigue activo» sin lectura aportada;
baseline t20diceSIEMPRE. NO promover simplificación global por un caso.
Todas conservan chat/guardas/transporte y límites de tokens;bare NO es servidor
totalmente desnudo. Steam falla en las3 por longitud/reintento vacío:rawbare sí
empieza a explicarlo,finish_reason=length. No decir que el modelo no sabe Steam.
El PREREG heredó campo change de la prueba anterior:esa inserción NO se aplicó en
system-layers;method/variants/payloads describen y demuestran las variantes reales.

## Validación

1030Pythonpass,0skip,5,57s:turn_policy,c03_request_preservation,compose_contract.
scratchpad/c03-real-users-pending-owner.log. El test de payload exacto se actualizó
al orden nuevo;schema y contenido íntegros. Prueba nueva de preservación de objetivo
cruza _prepare_turn_result con restricciones reales y verifica cero efectos.
118.NETpass,0skip,1m20s:PlannerAppBoundaryTests,C03FactPreservationTests,
MindShellEndToEndTests.79967terminal0;scratchpad/c03-real-users-pending-dotnet.log.
Previos97.NET de reloj también verdes,8201terminal0.
Fast35716terminal0,0errores/avisos:scratchpad/c03-real-users-pending-fast.log.
Ruff/diffcheckcorrectos;Fullpendiente. Sellos actualizados con script existente.
__main__SHAb40e15da6ff78a91076714f49d35a58e12e14c19ac4171ccda203c95a2cff983.
llmSHAde99d2fba21c54e3cec7ecc4b27ed53dbc66edcddf42874e528c51691374e9b5.

## Siguientes causas demostradas

1. Fecha:pending22 turn-audit request27:raw action/system.time/primary correcto;
   domain_grounding lo convierte en unsupported;domain_confirmation pregunta lo
   que el contexto ya dice. Corregir el veto de dominio, no volver a tocar el prompt
   primario ni añadir simplemente la frase exacta y la fecha a una lista.
2. Volumen:context-ablation/posts,guarded_with_history/t17:primaria propone
   audio.volume.adjust;SEMANTIC_EFFECT_GUARD diceenvironment_change/one,pero
   baxy_effect_count_verification diceMULTIPLE. Se fuerza plan/disagreement.
   Hay dos errores distintos:postcondición absoluta/relativa y contador adicional.
   Herencia posible:_NATIVE_SELECTION_DESCRIPTION_SUFFIXES ya diferencia ambas
   operaciones,pero sólo se usa en selección nativa (desactivada por defecto).
   No retirar guardas sin comprobar corpus de efectos múltiples/exactitud.
3. Negación:pending22 rawchat t20 primero pide dispositivo y luegoSIEMPRE;estado
   pendingya está resuelto,no es fallo del flag. No repetir instrucciones genéricas
   añadidas ni simplificación de sistema:ambas se midieron sin candidato aceptable.
   Revisar cómo se representa una restricción frente a knowledge usando contratos
   existentes;no prosa fija ni lista por cada verbo. Bare también interpreta mal
   este pedido;no atribuir todos los fallos sólo a BAXY.

Sigue faltando desarrolloverde,corpus/procedencia/contexto/reserva100,nooverrides,
UI final,Full,publish fueramain y contratos posteriores afectados. No cerrar.
