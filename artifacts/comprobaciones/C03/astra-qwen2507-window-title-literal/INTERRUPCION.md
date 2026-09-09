# Captura interrumpida por reinicio de Windows

PREREG:2026-09-06 11:30:44 local. Windows LastBootUpTime:11:32:23.
Al reanudar, la sesión6829 ya no existía y tampoco los procesos de PROCESS.json:
monitor39616,launcher19492,conductor34420. No RESULT.json ni terminal de turno
conservado: no adjudicar éxito, GPU ni duración final. Los archivos parciales quedan.
La traza anterior al reinicio mostraba timeout voice.status/unavailable; no se llegó
a medir de forma completa la corrección de extracción literal.

BAXY arrancó de nuevo por Explorer con --from-windows-start (PID27996) y Granite
(llama3372); no pertenecía a la captura. Se detuvo ese árbol concreto, tras verificar
ejecutable y argumento de inicio, para medir una sola instancia. Registro sin editar.
Repetición autorizada en carpeta nueva window-title-literal-resume: reinicio observado,
no búsqueda de una corrida favorable. No borrar ni sobrescribir esta evidencia.
