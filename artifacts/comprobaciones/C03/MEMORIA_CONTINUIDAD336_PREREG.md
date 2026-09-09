# 336 — intención privada y dato pendiente

334 mantiene2/6 útil:99pide dato y103saluda; ninguna escritura de memoria.
El parser privado admite guardar un nombre en el mismo turno y declaraciones
personales sin consentimiento como AskToSave. No conserva la petición anterior
de guardarlo. El modelo no puede saltarse este canal proponiendo memory.*.

Decisión xhigh: extender los dueños existentes, sin segundo planificador ni
respuestas fijas. MemoryParseResult puede indicar qué dato falta en una petición
explícita; MemoryTurnSession conserva esa intención sólo durante la sesión.
Al recibir una declaración explícita compatible, el parser crea el mismo
MemoryRoutedOperation protegido que usa el guardado completo. PublicAfterMemory
conserva una petición pública separada después del nombre. No anteponer texto de
guardado a cualquier mensaje ni usar la respuesta del asistente como dato humano.

Controles obligatorios antes de producto: declaración aislada nunca persiste;
interrupción no es un valor; cancelar/no guardar/nueva sesión retiran la intención;
credenciales y otra petición privada mantienen su protección; valor no incluye
el saludo ni instrucciones posteriores. Estado de confirmación pendiente no se
consume como un formulario. Ninguna operación se ejecuta hasta tener dato válido.
No rellenar desde cuenta de Windows ni desde frases del asistente.

Esto requiere reconocimiento de petición explícita incompleta y dato tipado en
NaturalMemoryRequestParser, no una nueva entrada literal en su switch histórico.
Mantener separadas aceptación del parser, autorización y guardado verificado.
Se comparará el producto sobre los mismos seis mensajes y se verificará persistencia
en perfil privado tras reinicio; un cambio de historial no acredita durabilidad.

Contraste heredado: LLM_CONTEXT_MEMORY_REPORT.md de Carter_v2:12–40 prohíbe derivar
la identidad declarada de prosa previa del asistente. Mecanismo oficial de
[parámetros requeridos](https://docs.cloud.google.com/dialogflow/cx/docs/concept/parameter)
y [formularios/interrupciones](https://legacy-docs-oss.rasa.com/docs/rasa/forms/)
consultado2026-09-08: separar dato pendiente, interrupción y finalización.
Sin dependencias o servicios externos. Implementación/verificación acotada high;
revisión de autoridad/contexto y diagnóstico de producto xhigh.
