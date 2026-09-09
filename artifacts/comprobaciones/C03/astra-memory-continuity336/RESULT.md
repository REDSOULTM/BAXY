# 336 — continuidad privada, validación en curso

Primer focal1771 pass/0fail/0skips1s: parser y estado de entrada.
Primera integración16pass1fail19s: la petición y el valor alcanzan memory.save;
el provider devuelve memory_disabled. Causa demostrada en
LocalMemoryStore.cs:493–500: un almacén nuevo nace deshabilitado;
MemoryHandlers.cs:160 comunica esa causa; ProductCatalog.cs:738–746
exige confirmación explícita para memory.enable. No es una pérdida del valor.

La prueba de persistencia ahora activa y confirma usando la App en su perfil
temporal antes de probar el guardado. Mantiene las aserciones de escritura y
recuerdo de un nombre nonce tras cerrar y abrir nueva sesión. No cambió ningún
default, configuración global, permiso ni política de confirmación del producto.
Se añadió una prueba independiente del perfil deshabilitado: exige memory_disabled,
ningún éxito, estado providerEnabled=false yTotalRecords=0. Resultado:1pass0fail0skips12s; guarda deshabilitada, cero registros comprobados por provider.

Dueñas integradas (MemoryAppFlow, MemoryTurnSession, NaturalMemoryRequestParser,
MemoryOperationProtection, MissionInputPipeline, MindShellEndToEnd):
1908 pass/0fail/0skips3m57s. La prueba disabled se añadió después del build de esa
corrida; su resultado se registra aparte. Fast y producto completos aún pendientes.

Fuente: dato pendiente tipado dentro de los dueños existentes; no se guarda una
respuesta del asistente, no se antepone recuerda a texto arbitrario. Interrupciones
no se consumen como nombre. Cancelar/no guardar/reset retiran intención; una nueva
operación privada conserva su propio canal. PublicAfterMemory conserva la petición
pública tras el nombre. No se agregó un literal humano al switch histórico.

Límite pendiente real del producto: con memoria deshabilitada se necesita orientar
la activación y su confirmación, no cambiar el default o presentar incapacidad
permanente. Producto337 debe repetir perfil por defecto, sin ocultar ese estado.
Esfuerzo de diagnóstico concretohigh; decisión de continuidad/activaciónxhigh.

Fast336 verde: buildRelease20,12s,0errores/advertencias. Producto337 terminó:
0/6 completos, un silencio; regresión frente a334. Perfil nuevo deshabilitado,
sin override ni habilitación inyectada. Journal comprueba memory.save fallido
con errorCode memory_disabled. El silencio99 es otro defecto: capacidades
conversacionales introducidas en la aclaración privada. Ver producto337/RESULT.md
y astra-compose-scope338. No adoptar336 como solución integrada de memoria.
