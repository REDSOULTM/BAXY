# C03 — checkpoint369 — EN_CURSO — 2026-09-08

Goal completo activo. Goal-c03/HEAD2bf3d4c; preservar WIP/main/evidencia. Sin agentes,
commit/push ni Full durante reparación. BAXY cerrado manualmente; producto364 y
diagnósticos anteriores cerrados. Encuesta1248/742 intacta, servidor101140 disponible.
16mensajes directos consolidados en INSTRUCCIONES_CONSOLIDADAS_2026-09-08.md;
órdenes automáticas excluidas. AGENTS e identidad vigentes. No otro goal.

## Últimas mejoras integradas

340 confirmación exacta para enable y nuevo save;343/343b pregunta por dato faltante;
344 proyección privada observed/pendingAction;354 preserva operación al redactar;
356 corrige eco que vetaba saludo solicitado.357:6/7, saludo visible, cuentaWindows
errónea.359 quitar último recorte del selector solo regresó360:3/7, viejos pedidos
contaminaban acciónactual.361 roles nativos9/11→11/11.362 reemplaza JSON por
systempropio+historialuser/assistant(12mensajes/6000chars)+actualuserliteral.
363:7/7,0silencios; preguntas, activar/guardar/saludar, identidad personal frente
a Windows y recall verificado. RESULT/PINS363. No generalizar a otras rutas.
Python3621091pass0skip5,32s;Fast1,40sverde. App356225pass0skip15s. Dueñas memoria344
1913pass0skip5m19s. Registro2507 intacto;Qwen3.5 diagnóstico, no promoción. Native361
GPU3175,56MiB/RAM4599,84MiB aislado, sin voz/UI/mínimo. Ver PREVIOUS_CHECKPOINT para
historia exacta/rechazos. No repetir wrappers/annotations346/347/349/316/317.

## Generalización364 y reparación365

364:10controles sintéticos ES/EN, Jordan/Álvaro, cancelar.3/10 útiles,1silencio.
Primer turno da nombre y pide guardarlo en la misma frase; privado no lo enlaza
y promete recuerdo. T6similar ofrece nota privada. Nunca hubo save/enable, así
que preguntas sobre confirmar no alcanzaron la ramaMemoryTurnSession. Journal
status+2recallfallidos. T5What is my name? da18borradores I don't know your name
because the memory feature is disabled, vetadosmissing_failure: termina composition_failed.
T10No puedo decirte tu nombre porque la memoria está deshabilitada contradice
Álvaro recién declarado. T4/T9reconocenlosnombres yT8cancelaclarificación. RESULT/PINS364.

365 última fuente validada, integración pendiente: NaturalMemoryRequestParser.Classify enlaza declaración y
solicitud explícita del mismo nombre (antes/después, punto/coma/puntocoma/y/and),
reutilizaMissingNameSavePattern/DeclaredNameInputPattern/Savepersonalpersistent.
Guardas de negación/secretos/autorización van antes. DeclaredName admite espacios;
otra frontera de cláusula no entra como parte del nombre. No nombres fijos.
Tests en NaturalMemoryRequestParserTests y MemoryTurnSessionTests. Baseline5fail6pass
582ms; focalinicial1fail28pass detectó Lina y abre Steam absorbido; focal-fixed29pass
0skip666ms tras impedir esa absorción. Logs/PREREG astra-declared-memory365.

Dueñas .NET365:1926pass0fail0skip4m33s;Fast18,06sverde,0warnings/errors. RESULT/PINS365.
366 completado exit0, handle50133 cerrado: mismos10controles364,3/10 útiles,1silencio.
T1/T6 ahora alcanzan save real fallido por memory_disabled y oferta enable; cancelar no
guarda ni habilita. T2/T7 pierden explicación;T3 idioma;T8 alcancecancelación;T5silencio;
T9 contradice contexto;T10 confunde persistencia con conversación. RESULT/PINS366.
HTTP34 sí contiene la declaración Álvaro como user: se descarta hipótesis de ocultación365.

367/368 nativos cerrados, RESULT/PINS:baseline2/4→3/4 útiles+1parcial. Sólo367pendingAction,
368 también causa inicial. Inglés explica bien; español aún repite pregunta antes de
nombrar activación. No repetir otra variante de prompt/causa. Campos originales de
confirmación sí deben conservarse: implementación369 reutiliza narración existente
para Invalid. Reconciliación no ofrece cancelación que no puede ejecutar; conserva
operación pública en cannot_withdraw_uncertain, nunca argumentos/IDs/tokens.

369 fuente en MemoryTurnSession/PrivateOperationNarration y tests MemoryAppFlowTests.
Baseline real3fail0pass0skip38s. Preparación inicial ubicó variable en test equivocado;
error de compilación conservado baseline-preparation-error.log, corregido antes del
baseline válido. Focal3693pass0skip49s;dueñas1926pass0skip4m44s;Fastverde18,13s0warn/error. RESULT/PINS369. Producto370completadoexit0,handle10711cerrado,4/10útiles+1parcial+1silencio,RESULT/PINS370, mismos10controles366, sólo369cambia. Recogerlo sin editarfuente ni cargarotro modelo.371nativo cerrado, noadoptado2/5→2/5;372nativoen cursohandle55117, sin fuente nueva.
No modelo/producto activo; BAXY manual cerrado, encuesta intacta. ÚltimaPython362.

## Siguiente después del producto y resto íntegro

369 repara hechos de confirmación, pendiente validación; el español parcial367/368
requiere revisar contrato, no otra variante semejante. Separar de T5/T10 con memoria desactivada. El redactor
actual sólo recibe failed/memorydisabled/operationmemory.recall, no la declaración
humana. No relajar missing_failure para publicar una afirmación falsa. StartAsync
de MemoryTurnSession:240 sólo recibe operación/publicObjective, no pedido original;
Host.ContinuePublic llama TryExecuteWithMindAsync, una posible pieza de herencia
para contestar desde sesión, aún sin diseño/adopción. También queda prosa fija
en SendPreparedAsync cuando no llega challenge seguro para secreto: pendienteC03.

Otras ocho rutas/errores y fallos264, encuesta742requisitos(0validaciónindividual
registrada),100humanos frescos(0certificados/0congelados;204por auditar335), averías/
recuperación, escritorio real/voz física/ASR/recursos conjuntos, runtime/instalación,
continuidadC04–C09sin ejecutarlos, Fullfinalverde y publicaciónfuera de main.
No bloqueo externo, porcentaje ni fecha demostrados. C03 sigue íntegro EN_CURSO.
