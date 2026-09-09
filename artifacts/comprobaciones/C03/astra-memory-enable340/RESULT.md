# 340 — activación guiada en validación

Baseline:2 fail,0pass,0skip,29s. Ambos casos terminan sin solicitud de activar
memoria: la cola queda vacía tras memory_disabled. Fallo real de continuidad.

Primer focal tras fuente:1pass,1fail,0skip,32s. Cancelación inglesa pasa.
El otro caso llega a confirmar y guardar un único registro, pero el test intenta
abrir journal/missions.jsonl mientras el motor lo mantiene abierto: IOException.
La lectura del journal se movió después de DisposeAsync, antes de la nueva sesión;
no se cambió la fuente ni se quitó la comprobación de dos invocaciones diferentes.

Cambios: MemoryContinuation reemplaza PublicAfterMemory y conserva temporalmente
el save protegido cuando debe precederle enable. memory.enable tiene su propia
invocación/confirmación; sólo un resultado privado verificado permite un save nuevo.
El token no se traslada. Cancelación y ResetSession descartan la continuación.
Resolve devuelve si consiguió retirar el intento del journal de recuperación;
no se continúa tras un fallo al resolverlo. No se reofrece enable en bucle tras
el segundo save. Sólo guardado normal de la sesión actual; no secretos ni
operaciones heredadas de otra sesión. Defaults/perfiles globales intactos.

Se conserva una sola continuación dentro de MemoryTurnSession, sin otro
planificador, catálogo ni estado duradero paralelo. El dato permanece protegido
en esa continuación. No se presenta como recuperación duradera de la intención
completa después de un cierre del proceso; esa conducta necesita prueba adicional.

Dueñas integradas terminadas:1911pass,0fail,0skip,4m38s. Comando:
`dotnet test tests/Baxy.Integration.Tests -c Release --nologo -v:minimal --filter 'FullyQualifiedName~MemoryAppFlowTests|FullyQualifiedName~MemoryTurnSessionTests|FullyQualifiedName~NaturalMemoryRequestParserTests|FullyQualifiedName~MemoryOperationProtectionTests|FullyQualifiedName~MissionInputPipelineTests|FullyQualifiedName~MindShellEndToEndTests'`.
Incluye postlectura, dos invocaciones distintas y recuerdo del nombre nonce tras
una nueva sesión. El control disabled ahora exige que la
causa exista, que se ofrezca enable, Enabledfalse/TotalRecords0 antes de confirmar
y outbox vacío tras cancelar. Su antigua expectativa de no ofrecer continuación
queda sustituida por la conducta pedida; la protección no se relaja.

341 preparado: mismos seis literales de339, sin confirmación añadida.
342 separado: cinco literales con confirmar y cómo me llamo añadidos como controles
de prueba declarados, nunca atribuidos al dueño ni contados como aceptación fresca.
Fast340 verde: buildRelease18,77s,0errores/advertencias.341 terminó1/6completo,
0silencios;342 terminó2/7completos con una identidad parcial,0silencios. En342
el journal verifica enable y nuevo save; también recall devuelve el nombre,
pero Python descarta records y el modelo niega conocerlo. Confirmación no explica
la acción y las narraciones enable/save reciben payload vacío desde prosa fija.
RESULT/PINS en ambos productos; siguiente contrato privado descrito en
PROYECCION_PRIVADA344_DISENO.md. No declarar resuelta memoria integrada.
No Full en reparación.
