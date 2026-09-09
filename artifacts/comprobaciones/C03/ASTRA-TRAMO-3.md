# C03 — conservar la pregunta y ampliar las rutas, 2026-09-06

INTENT_KNOWLEDGE agrupa cantidades, entidades y definiciones. El compositor
imponía explicar un concepto a todas: «What is fourteen times six?» acabó en
una definición de multiplicación en astra-native-qwen8-q8. Ahora conserva el
pedido y solicita contestarlo directamente. No hay calculadora nueva ni veto
de otra frase. Tres regresiones fallan antes; 366 pruebas dueñas y 101 subtests
pasan después. STT/V8: 17 pass, 1 skip ambiental por entradas STT ausentes.

`astra-knowledge-question` prueba el producto con Granite registrado: 4/4 útiles
y fieles (84, definición DNS, 96, Lima), sin misiones/error pendientes. Su
ADJUDICACION.md conserva las respuestas completas. No es aceptación fresca ni
cobertura de las ocho rutas. Fuente llm.py c3259eec8a93179a7e305f3a05ca542f294d5f0ff49d23c3240a8bae6ece20bc;
árbol de programas STT c7c4888cf97abb6fa3d2cea2cb0a6f215e3ff5cfef9144dc623ed0dc37aa939d.

La prueba qwen8-q8-question tampoco justificó promoción: 10/12, desplazando
fallos. Qwen3.5 sin cierre forzado de razonamiento terminó sólo 6 casos: 2
correctos, 4 timeouts; se interrumpió, sin certificar GPU. Cada diagnóstico tiene
LECTURA.md. No seguir un barrido de modelos ni aumentar plazos sin nueva causa.

Por instrucción expresa del dueño, **Full se reserva para el cierre de C03**.
La segunda ejecución iniciada antes de esa instrucción se interrumpió durante
Python (73 %) para continuar la reparación: exit 1 por cancelación propia.
Estática/build y .NET pasaron; eso no equivale a Full verde. No se lanzó otra.

`astra-routes-development`: 18 pedidos preregistrados, heredados de v18 y ampliados
con spanglish, resumen de lecturas y confirmación/cancelación exacta de un archivo
sintético creado por este diagnóstico en el escritorio. Examina todos los textos
y hechos observados, incluido progreso si se emite. La ausencia de una ruta se
anota como cobertura pendiente. No inyecta averías ni suma a los cien reservados.
Sesión inicial 12021; recoger sin relanzar y limpiar sólo el fixture propio tras
verificar su hash/estado. El checkpoint conserva la ruta y la siguiente acción.

La corrida terminó: 11/18 correctos, 18 publicados. Adjudicación por turno y
causas en su carpeta; fixture intacto y retirado. Entre los fallos, una referencia
documental larga se marcaba como credencial por letras+dígitos/longitud, y el
compositor recibía sólo la proyección pública ocultada. Se hereda el patrón de
documentos del mismo owner para excluir sus extensiones conocidas de la heurística
genérica; marcadores de secretos y prefijos fuertes se comprueban antes, y JWT y
tokens opacos conservan protección. Tres negativos de archivo fallan antes;
los cuatro sensibles ya pasaban. Después, NaturalMemoryRequestParserTests y
MissionInputPipelineTests: **1784 pass, 0 skips**, sin otra compuerta Full.
`astra-filename-projection` terminó: 1/3 correctos; petición preservada, pero una
decisión no disponible se convierte en ambiguous_request. Su adjudicación traza
el siguiente fallo; fixture intacto comprobado y retirado. El diff es del detector
existente; no se creó una segunda composición ni se retiró protección global.
