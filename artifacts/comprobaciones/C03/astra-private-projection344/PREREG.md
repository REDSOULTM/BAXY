# 344 — resultados privados como hechos para el compositor

Base:340/343b validadas;341/342 demuestran pérdida de hechos. Herencia y causas
en PROYECCION_PRIVADA344_DISENO.md, con rutas/rangos ya inspeccionados. No cambiar
modelo, cuantización, muestreo, kernel, protección ni default de memoria.

Una reparación de contrato: MemoryOperationResponseProjection conserva sus
validadores y emite resultados tipados con observed; Python ya transmite observed
como seen. Configuración, guardado/corrección, borrado, estado, exportación y
registros dejan de depender de prosa fija o campos que el compositor descarta.
Se conservan redacción de secretos, límites, cuentas, metadatos de replay y
ausencia de IDs/selectores/digests/rutas privadas. No duplicar prosa y hechos.

Confirmación/recuperación privada aporta pendingAction con operación y ámbito,
sin argumentos privados ni tokens. Reutilizar ese contrato ya soportado por el
compositor; quitar la categoría aproximada que sustituye la operación concreta.
Mantener las elecciones y reconciliación exacta existentes.

Actualizar el test antiguo que exige prosa fija, porque contradice C03: comprobar
hechos correctos y que JSON no se acepte como texto final. No quitar controles de
schema, redacción o export-replay. Añadir recorrido de los registros hasta el
payload realmente enviado al modelo y variantes de valores recuperados.

Medir primero baseline, luego dueñas .NET/Python y Fast. Repetir la secuencia342
con confirmación/recall sintéticos declarados, leer mensajes intermedios/finales
y journal. No equiparar persistencia con respuesta útil; no UI/voz física ni
aceptación fresca. No Full durante reparación.
