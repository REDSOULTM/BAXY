# 440 — el refinamiento intercambia el fallo; no se adopta

Ocho casos, once llamadas. Jordan y Marta se atribuyen correctamente tras ver
el borrador; Ana María se pierde y la respuesta niega un dato presente. 5/8→7/8,
pero el criterio exigía conservar los ocho y los hechos. Todos stop. 7,453 s,
GPU3173,5625MiB, RAM1203,80078125MiB, sin violaciones, manifiesto intacto.
Cliente cerrado. No fuente ni guarda de nombres adoptadas. 439/440 cierran la
estrategia de feedback: no añadir más variantes de instrucciones/reintentos.

El compositor de estados excluye deliberadamente la conversación (C#CreateFacts
y Python prompt_facts). Agregar historia puede dar información de atribución,
pero una lectura de datos persistidos también debe funcionar en sesión nueva:
no se fabrica diálogo humano ni se hace depender el dato de una charla anterior.

441 reutiliza el único9B ya disponible y su perfil medido390. Son otros payloads:
composición de memoria actual sin tools, frente al selector AUTO de390. El rechazo
390 se conserva: no certifica ni impide medir esta función. Comparación acotada
antes de cualquier decisión de runtime, sin colección de modelos/descargas.
