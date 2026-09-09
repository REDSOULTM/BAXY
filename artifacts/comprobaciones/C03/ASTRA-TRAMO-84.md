# C03 — conservar búsqueda vacía — tramo84

83 verificó entries=[]/count=0 y luego convirtió el null de grounding en
step_data_missing.2/4 útil: los siguientes archivo real y reloj recuperan,
pero las dos explicaciones de ausencia no. PRUEBAS_BUSQUEDA_VACIA83.md.

Herencia: PlanObservationProjector ya filtra productores permitidos, status
completado, verificación y dependencia exacta. Se extrae esa selección común
para reutilizarla también al distinguir vacío: sólo para filesystem.read.text,
con entries vacío y count entero0 explícitos en todos los resultados admitidos.
Falta de datos, inconsistencia, otra familia o productor no verificado no prueban
ausencia. El ejecutor conserva file_search_no_matches antes de pedir grounding
imposible. No se cambia provider ni catálogo, ni se afirma inexistencia global.
Es el contraste concreto de result-set vacío frente a datos ausentes; la evidencia
local determina la causa, no otra instrucción al modelo.

Pruebas dueñas47168exit0:162pass/0skips/8s en PlannerAppBoundaryTests y C03FactPreservationTests.
Ocho contrastes nuevos cubren búsqueda/lista, datos ausentes/inconsistentes,
verificación y dependencia exacta. No cambios Python después de81.
Fast84 inicial93075 terminó con dos errores de formato en el test nuevo.
Corregido el formato, la repetición18548 terminó verde: mode=Fast,
Release16,67s,0 avisos/errores; log TEMP/c03-empty84-fast-retry.log.
files84-emptycause preparado para comparar los cuatro turnos de83.
Modelo Qwen3.5 override sin promoción, C03 completo EN_CURSO.
