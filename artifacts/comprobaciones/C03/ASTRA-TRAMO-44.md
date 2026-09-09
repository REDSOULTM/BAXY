# C03 — tramo44 reparación integrada demostrada; goal EN_CURSO

Relevo activo: tarea 01a07974-2a33-7ed3-ba87-2436944e8115. La inspección del
tramo44 de la tarea anterior no dejó implementación. Esta tarea continúa43.

Hipótesis: el veto de conservación interpreta toda negación posterior como
revocación global y una pregunta negativa de estado como orden negativa.
Control antes: closed-prohibition11 t8/t9/t10 fallidos; selección nativa correcta.
Aceptación del tramo: recuperar esos controles integrados sin perder prohibiciones,
revocaciones reales ni conservación de efectos positivos pendientes.

Herencia: explicit_negative_constraint (tramo37/43), segmentación de cláusulas y
reconocimiento de efectos existente. Contraste vigente reutilizado:
INVESTIGACION_FORMATO_Y_CLASIFICACION_C03.md, consulta2026-09-06 (Qwen function
calling, ficha exacta y réplica dotTXT), e INVESTIGACION_MODELO_C03.md.
La forma nativa no acredita semántica; el selector ya acertó estos controles.
No se modifica prompt, muestreo ni modelo. La alternativa de otro prompt quedó
rechazada localmente43; se repara la primera transformación incorrecta.

Cambio en evaluación: separar cláusulas negativas tras coma/punto y coma;
reutilizar las formas imperativas existentes sólo para comparar alcance con el
catálogo real. Una prohibición completa de otra operación no veta la lectura
positiva. El lector literal sigue absteniéndose: esta comparación no ejecuta
formas afirmativas proyectadas. Las operaciones coincidentes, referentes sin
objeto y negaciones no resueltas conservan el veto. Una negación de cópula de
estado no equivale a prohibición; no concede autoridad por sí misma.

Primera suite detectó un argumento de índice de aplicaciones mal construido en
la nueva comparación (8 fallos,1561pass); corregido usando el constructor dueño.
Logs locales fuera del árbol: %TEMP%/c03-tranche44-effect.log y effect2.log.
Segunda ejecución en curso al escribir este registro. No Full.

## Resultado integrado

La variante parcial scoped-prohibition11 obtuvo8/11,106,84s, sin mejora: el lector
literal aún abstiene, domain_grounding pierde la hora tras coma y la pregunta
negativa se reclasifica como conversación. Se completa la misma reparación en
el owner: resolver y veto comparten comparación de operaciones, la interrogación
de estado conserva cabeza y offsets de evidencia. Ya no se mantiene la abstención
literal en los casos cuya independencia está demostrada. La pregunta no concede
mutaciones y una prohibición posterior sigue revocando.

scoped-reader11:11/11 útiles,65,08s,GPU3497,56MiB,RAM5142,96MiB,registro intacto.
t8 observa muted=false/level100; t9/t10/t11 devuelven22:36 concordante con UTC y
offset−180. No app.open/game.launch. Literales y adjudicación individual:
PRUEBAS_ALCANCE_LECTOR_C03.md. Panel consumido, no cien frescos ni UI/audio físico.

23controles dirigidos pasan por lector y política completa. Siete suites sobre
la fuente final:2902pass,115subtests,0skips,48,84s. Se conserva un fallo intermedio
que descubrió una revocación tras signo de pregunta; se reparó el separador y
el marcador de corrección. Logs %TEMP%/c03-tranche44-reader-owners.log.
Fast de la fuente parcial verde (build3,58s); Fast de fuente final verde,
build1,54s,0avisos/errores,sesión37087 exit0,
log %TEMP%/c03-tranche44-reader-fast.log. Diffcheck verde.
Las mediciones28105/97412 y suites54838/80252/18862/11046 están terminadas.

Sigue todo el cierre C03: procedencia/exposición y reserva100, ocho rutas,
averías/recuperación, UI/voz/recursos, contratos, Full final y publicación.
Corpus:16sesiones.gemma4 suman82ocurrencias únicas por archivo (hay duplicados y
audio de fondo); no bastan solas para100. Continuar fuentes y contexto de Goal10.
