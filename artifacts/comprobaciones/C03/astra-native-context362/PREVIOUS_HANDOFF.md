# C03 — checkpoint360/361 — EN_CURSO — 2026-09-08

Goal completo activo; rama Goal-c03, HEAD2bf3d4c. WIP/main/evidencia conservados;
sin agentes, commit/push ni Full durante reparación. BAXY cerrado manual;
producto360 terminó con regresión. Diagnóstico361 en curso, handle34499. Encuesta1248/742 intacta, servidor101140 disponible.
16 mensajes directos consolidados en INSTRUCCIONES_CONSOLIDADAS_2026-09-08.md;
excluir órdenes automáticas de otra tarea. AGENTS e identidad vigentes.

## Estado demostrado

340 habilita sólo con confirmación exacta y luego nuevo save; cancelar descarta
continuación.343/343b conserva el dato requerido hasta publicar preguntas válidas.
344: MemoryOperationResponseProjection emite observed
para resultados privados; PrivateOperationNarration añade pendingAction inicial/
recuperación. Schemas, secretos y replay preservados; prosa fija reemplazada.
Focal9pass/0skip122ms; dueñas .NET1913pass/0skip5m19s; Python compositor85pass/
0skip0,65s; Fast verde build18,77s,0warnings/errors. Logs en astra-private-projection344.

345 con2507:3/7 turnos completos,0silencios. Confirmación ahora explica activar;
recall recibe el nombre, pero se lo atribuye al asistente. Enable/save inventan
afirmaciones.346/347/349 no reparan el sujeto: ninguna variante adoptada.348
diálogo nativo conserva8/8 atribuciones,7/8 útiles por un idioma. Ver REVIEW.md
de cada panel; no repetir etiquetas/retornos/annotations de esas tandas.

350:13 mismos payloads,2507 nativo6/13 útiles frente a Qwen3.5 disponible10/13.
GPU3497,56/3173,56MiB; RAM2845,06/3723,29MiB. Aislado, no voz/mínimo.
351 producto con override3.5:4/7 completos,0silencios. Recuerda Tu nombre es
Emmanuel y distingue ambas identidades. Fallos: error atribuye memoria desactivada
a saludar; enable inventa una vista habilitada; saludo corto nativo Hola Emmanuel
no se publica; quien soy elige system.identity y responde cuenta usuario. RESULT/
PINS350/351 escritos. Registro2507 intacto; no promover3.5. Todos handles cerrados.

354 última fuente: Python conserva operation tipada en la proyección, también
en el retry. Baseline2fail; dueñas1035pass/0skip5,13s; Fast3,39s verde. No nueva
guarda/prompt/modelo.353 composición nativa real:3.5 pasa7/9→9/9 al acotar el fallo
a guardar y enabled a memoria;2507 mejora enable pero mantiene otros defectos.
REVIEW352/353 y RESULT354 escritos. Resto de fuente y registro intactos.

## Fuente356 y siguiente acción concreta

App y compositor Python corrigen el veto al saludo exacto solicitado después de
dime/decime/tell me. El eco de una petición informativa sigue rechazado. No otro
prompt, modelo ni nombres fijos. Baseline App4fail4pass; focal App8pass y Python9pass;
dueñas App225pass0skip15s, Python1044pass0skip5,14s, Fast verde. RESULT/PINS356 escritos.
No Full. Producto355 sigue siendo la última evidencia integrada:6/7,0silencios.

Producto357 completó6/7,0silencios; Hola Emmanuel se publica enT3. RESULT/PINS
escritos, journal acredita enable/nuevo save/recall, registro intacto. Única falla
del panel: quien soy devuelve cuentaWindows usuario. BAXY cerrado tras el conductor.
358 terminó: selección6/8→7/8 conservando historial acotado completo; variante
sintética ambas identidades aún escogeWindows, fallo pendiente. REVIEW358 escrito.
GPU3175,56MiB/RAM3315,59MiB aislado, registro intacto. No efectos ni voz/UI.
359 fuente última: retira sólo [-6:] del selector nativo. El sanitizador conserva
12mensajes/6000chars y roles user/assistant; no tocar modelo/prompts/catálogo.
Baseline2fail1pass; dueñas turn_policy+compose+transport1091pass0skip5,32s;
Fast verde build1,72s0warnings/errors. RESULT/PINS escritos. Handles cerrados.

360 terminó3/7 completos0silencios frente a3576/7. RESULT/PINS360 escritos;
journal sólo enable/save, no escritura de archivo. Fuente359 pasa tests/Fast
pero NO es solución integrada;356 sigue siendo la última mejora integrada.
Primera divergencia360 HTTP13: Yo soy el propone filesystem.write.text al leer
viejos pedidos de guardar el nombre; HTTP14 lo veta incompatible. DespuésHTTP24
propone note.read sin argumentos para quien soy. HTTP29 abstiene correctamente
para ambas identidades; sondeo secundarioHTTP31 de4candidatos revierte a identity.
__main__.py:6282 _catalog_answers_the_request repite sondeo después de abstención;
su rama nativa2054 vuelve a llamar al mismo selector. No editar descriptores para
el fallo de archivo ni otra respuesta prefabricada.

361 en curso handle34499: scratchpad/c03-native-context361.py, out
astra-native-context361, privadoLOCALAPPDATA/BAXY/C03-native-context361-private.
11payloads fijos (8de358 y reales36013/29/31), sólo JSON referencia frente a roles
nativos con el mismo texto y modeloQwen3.5.316 ensayó2507 y otro contexto; diferencia
declarada en PREREG. Sin efectos, fuente, prompt ni promoción. Recoger resultado;
si falla, cambiar estrategia y no otra variante de prosa. BAXY manual cerrado.

## Resto íntegro pendiente

Memoria integrada aún incompleta. Otras ocho rutas/errores, preguntas durante
confirmación (MemoryTurnSession Invalid aún omite pendingAction),100humanos frescos
(0certificados/0congelados;204 por auditar335), averías/recuperación, UI escritorio/
voz física/ASR/recursos conjuntos, runtime/instalación, contratos C04–C09 sin ejecutar
esos goals, Full final verde y publicación fuera de main. Sin bloqueo externo ni
porcentaje demostrado. Anterior íntegro: astra-model-memory350/PREVIOUS_CHECKPOINT.md.
