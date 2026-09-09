# C03 — checkpoint364/365 — EN_CURSO — 2026-09-08

Goal completo activo; ramaGoal-c03, HEAD2bf3d4c. Preservar WIP/main/evidencia.
Sin agentes, commit/push ni Full durante reparación. BAXY cerrado para uso manual;
producto364 terminado; baseline365 en curso, handle85875. No fuente365 aún. Encuesta1248/742 intacta,
servidor101140 disponible.16mensajes directos consolidados en
INSTRUCCIONES_CONSOLIDADAS_2026-09-08.md; excluir órdenes automáticas de otra tarea.
AGENTS e identidad vigentes. No reiniciar campaña ni reducir alcance a memoria.

## Estado demostrado

340 activa memoria sólo tras confirmación exacta y nuevo save; cancelar descarta
continuación.343/343b conserva dato requerido hasta publicar la pregunta.344
proyecta resultados privados observados y la acción pendiente inicial/recovery;
schemas/secretos/replay preservados. .NET1913pass0skip5m19s, Fast18,77s de344.
354 conserva operation al componer, acotando error y éxito a la operación real.
356 permite el saludo exacto pedido en App/Python sin aceptar pregunta copiada;
App225pass0skip15s, Python1044pass0skip5,14s, Fast18,00s. Producto3576/7:
saludo publicado, fallo quien soy devuelve cuentaWindows. RESULT/PINS escritos.

358 nativo con historial completo mejora selección6/8→7/8, pero359 solo regresó
en producto3606/7→3/7: viejo pedido de guardar domina Yo soy el y propone archivo.
La compatibilidad lo veta; no efectos ajenos. El sondeo secundario del catálogo
también revierte una abstención válida a identity. No adoptar359 solo.
361 conserva el contenido en roles nativos y mejora9/11→11/11. Variabilidad de
una referencia sintética declarada; seed no garantiza salidaidéntica. GPU3175,56MiB,
RAM4599,84MiB18,34s aislado; no voz/UI/mínimo. No repetir envoltorios/etiquetas
rechazados346/347/349/316/317; diferencias de modelo/input361 están documentadas.

362 última fuente: selector nativo system propio + historial saneado/acotado
user/assistant + petición actual user literal, reemplaza JSON de referencia.
12mensajes/6000chars, sin otro prompt/catálogo/sampler/modelo/límite. Baseline4fail;
Python turn_policy+compose+transport1091pass0skip5,32s, Fastverde1,40s0warnings/errors.
RESULT/PINS362 escritos. No Full. CódigoC# sigue356. Registro2507 intacto;
Qwen3.5 sigue override diagnóstico, no promoción ni prueba de mejora2507.

## Producto363 y siguiente acción

363 completó7/7 turnos,0silencios,adm200,sin timeout; mismos siete pedidos360,
sólo362 diferente. Pregunta nombre, explica memoria desactivada, confirma activar,
guarda en invocación nueva y saluda. Yo soy el reconoce Emmanuel; quien soy
responde Eres Emmanuel; ambas identidades correctas; recall Tu nombre es Emmanuel.
Journal acredita enable/nuevo save/recall, sin cuentaWindows ni archivoajeno.
RESULT/PINS363 escritos.362+359 retenidos como mejora integrada de ese panel.
Preparación363 tuvo sustitución accidental del hash literal por replace360→363;
assert frenó antes dePREREG/inferencia, se restableció el hash original y se
conservó PREPARATION_ERROR.md. Evitar sustituciones globales de IDs en huellas.

364:10controles sintéticos ES/EN, nombresJordan/Álvaro y cancelación.3/10 útiles,
1silencio. No comparación de porcentaje con363 por panel diferente. RESULT/PINS
escritos. Journal:status completado,2recall fallidos; nunca save ni enable.
T1My name is Jordan. Remember my name. promete memoria sin iniciarla. T6Me llamo
Álvaro y quiero que guardes mi nombre. pregunta por nota privada. T2confirmación
inventada, T3cancel fuera de catálogo/en idioma ajeno;T5What is my name? silencio
composition_failed/no_response/retry_exhausted;T7repite aclaración;T10atribuye no
conocer el nombre a memoria deshabilitada pese a conversación. T4/T9reconocen
nombres;T8cancela aclaración. No se alcanzó ninguna confirmación memory.enable.

365baseline en cursohandle85875: nuevos tests DeclarationAndExplicitNameSaveBindTheSamePrivateDatum
(5positivos) y ADeclarationAloneOrAnUnrelatedClauseDoesNotAuthorizeNamePersistence
(6negativos) en NaturalMemoryRequestParserTests.cs. PREREG astra-declared-memory365.
Todavía NO cambios de producción365; última fuente362, Fast/dueñas previas verdes,
tests365 WIP. Recogerbaseline; luego unir declaración y petición explícita sobre
el mismo dato reutilizando piezas existentes, no otra respuesta/prompt del modelo.
Classify:250, MissingNameSavePattern:1651, DeclaredNameInputPattern:1669;
TryBindSaveInput:442 sólo une dato tras pregunta anterior. Sus patrones actuales
no admiten punto+segunda frase ni y+quiero ni nombres compuestos con espacios.
Preservar negaciones/secretos/autoridad/privacidad y resto de objetivos públicos.

Después de esa primera pérdida, resolver conversación reciente con persistencia
desactivada (T5/T10). La inspección pendiente de MemoryTurnSession:138–155 Invalid/
cannot_withdraw_uncertain sin pendingAction sigue sin editar: PrivateOperationNarration
ya lo construye seguro; no confundir rama no alcanzada364 con fallo medido suyo.
Sin Full/promoción, BAXY manual cerrado, encuesta intacta. Mantener C03 completo.

## Resto íntegro pendiente

Memoria integrada aún incompleta. Otras ocho rutas/errores, preguntas durante
confirmación (MemoryTurnSession Invalid aún omite pendingAction),100humanos frescos
(0certificados/0congelados;204 por auditar335), averías/recuperación, UI escritorio/
voz física/ASR/recursos conjuntos, runtime/instalación, contratos C04–C09 sin ejecutar
esos goals, Full final verde y publicación fuera de main. Sin bloqueo externo ni
porcentaje demostrado. Anterior íntegro: astra-model-memory350/PREVIOUS_CHECKPOINT.md.
