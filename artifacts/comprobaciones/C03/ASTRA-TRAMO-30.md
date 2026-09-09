# C03 — tramo 30 — corpus literal

2026-09-06. EN_CURSO, sin bloqueo externo; rama Goal-c03, sin publicación.

El dueño rechazó entradas artificiales como «Dime la hora, please, en spanglish».
C03_ASTRA_AUTORIDAD.md exige ahora heredar turnos únicos literales de logs,
español/inglés/mezcla natural, sin traducciones ni añadidos para cuotas. Conservar
procedencia/contexto y reservar antes de ejecutar. Evidencia técnica previa intacta.

select_n10 del Goal10 aporta1947 registros/626 textos únicos. Con el log vivo
Probando Gemma4 y Carter_v1/carter_session.log:742 candidatos únicos provisionales.
5476 registros incluyen solapamiento entre copias; no son interacciones independientes.
Falta atribución humana frente a benchmarks, cobertura Carterv2–v5/actual y revisión
semántica del idioma (other etiqueta incluso hola). Corpus completo privado fuera Git:
REAL_USER_POOL_MANIFEST.json. Script: scratchpad/c03-real-user-pool.py.

REAL_USER_LITERAL_INTEGRITY.json contrasta longitudes del log vivo Probando:
560 respaldados por texto completo/contador de longitud;182 pendientes de esa
corroboración. No significa que182 estén truncados: incluye otras fuentes. Seis
casos de desarrollo proceden de Gemma histórico(2)/Carter(4), no del log con contador.
La autoría humana y la independencia del entrenamiento siguen siendo cuestiones aparte.

## Medición

PRUEBAS_CORPUS_REAL_C03.md muestra20 entradas/respuestas/motivos;14 aceptadas,6 fallos.
astra-real-users-development20/ conserva CASES,PREREG,RESULT,paired,events,
compose-audit y adjudication. Secuencia organizada para diagnóstico: no se afirma
reproducir veinte turnos consecutivos de una sesión histórica. No aceptación fresca.

Fallos:fecha tras hora pide aclaración innecesaria;GPU inferida del nombreCPU sin
inventario;restricción negativa termina composition_failed;referente volumen perdido;
pregunta identidad omitida;nueva restricción ignorada por aclaración pendiente.
Preguntar cuánto subir se acepta con redundancia menor;aclarar salida/micrófono se
acepta. No exigir pulir estilo ni explicaciones exhaustivas.

Runtime registrado sin overrides;conductor sin ventana,wakeoff por diseño.
117,09s,GPU3499,56MiB,RAM5376,75MiB,86246 terminal0. No UI/hardware ni verde de producto.
T12 verificó100→35;t17 no restauró. Limpieza independiente registrada en
astra-real-users-volume-restore/:«pon el volumen al 100» verificó35→100;
«mostrame el volumen» confirmó100,muted:false.54,05s,GPU3497,56MiB,94499 terminal0.
Perfil nuevo para limpieza,no recuperación en sesión t17. Registro intacto.
Errata PREREG restauración:hereda mención Ponlo a100 del guion20;entradas efectivas
son las dos de turns/paired. No cambia la evidencia de la ejecución.

## Fuente y validación

Antes de la aclaración se cambió llm._compose_shape_instruction:
«Name mute state.»→«Describe whether sound is silenced.». Sin veto por palabra.
astra-audio-wording-ablation/:30 hechos conocidos×2 variantes,37,56s,GPU3499,56,
RAM3244,05MiB,84340 terminal0. Corrige dos desmudo y conserva muted:true.
No30/30:hay fallo de explicación de sinónimos en ejemplo artificial;priorizar real.
Pruebas dueñas:c03_request_preservation,compose_contract,planner:
300passed+115subtests,0skips,2,02s; scratchpad/c03-real-users-owner.log.
Fast tramo29 precede a esta edición;Full pendiente hasta candidato completo.

Sin procesos propios pendientes. Volumen100/no silenciado verificado. Seguir causas
compartidas de contexto,negación,pending e identidad;obtener datos GPU del owner,
no inferirlos. Revisar idiomas,autoría,integridad/contexto de candidatos y reservar100
no consumidos. No nuevos barridos de modelos ni retocar filtros para aparentar éxito.
C03 sigue pendiente de aceptación,UI final,Full,publicación y contratos afectados.
