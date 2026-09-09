# C03 — tramo17: conservar título desde petición hasta argumentos

EN_CURSO. Sin Full, promoción ni cien frescos. No nuevos modelos ni subagentes.

Tramo16 probó que el proveedor actualizado aún no recibía el título. La captura
window-title demostró el veto: _window_domain reconoce ventanas activas y algunas
apps, pero no una ventana identificada por un título nuevo. Se hereda el reconocedor
existente y añade la relación ventana→título sin enumerar títulos/apps; la orden de
cierre conserva app.close como efecto. Resolver el título sigue siendo una lectura
previa verificada, nunca un sustituto por ventana activa. Nueve regresiones contrastan
ES/EN/mixed con ventanas físicas/metafóricas y títulos vacíos.

window-title-target: sesión60914 terminó0,58,26s,GPU3497,56MiB,RAM4499,39MiB; registro
intacto.6publicados,2/6útiles/fieles (t2 cancelación de aclaración,t5hora),t2terminología
mejorable. t1/t3 ya conservan app.close→plan, pero preguntan por proceso innecesariamente.
t4 sigue aclarando,t6 niega acceso a tareas. Fixture38428 permanece viva. ADJ escrita.

Nueva frontera trazada: extract_plan_arguments_batch omite descripción canónica,
conservando sólo ID/operación/purpose y schema. Se añade la descripción procedente
del catálogo (ya presente en extracción individual). Sin otra llamada/modelo/capa.
La semántica byTitle está en esa descripción: el esquema por sí solo dice boolean.
Planner trataba cualquier bool como encender/apagar; ahora byTitle se valida contra
la relación título en la petición. Un título no puede perder su selector y convertirse
silenciosamente en proceso. No se cambia la semántica de otros booleanos.

Validación intermedia:2344pass/2fail en effect_intent+turn_policy. Los dos fallos
eran pruebas de good night/see you later con response_language=es pese a exigir EN;
se corrigió el idioma del fixture, sin retirar el rechazo de idioma contrario.
Siguiente integración:2585pass/1fail/104subtests; fallo restante exigía un literal
antiguo del prompt de confirmación. Ahora comprueba el contrato Palabras:continuar,
cancelar, conservando respuesta y único decode. No se restauró wording sólo por test.

Recheck35266 terminó0:2586pass/104subtests en80,10s. Se reprodujo además pérdida de
opcionales válidos: byTitle=true más limit10 sin pedir devolvía None al retirar ambos.
Normalizador ahora retira sólo opcionales inválidos/sin evidencia y conserva válidos;
no puede quitar byTitle de una petición con título y tratarla como proceso. Último
recheck dueño:146pass/104subtests en2,21s;Ruff0. Pines de fuente actuales renovados.

Captura window-title-contract sesión49000 terminó0:71,28s,GPU3499,56MiB,RAM4850,39MiB,
6publicados/2útiles y fieles; no mejora visible. ADJ escrita. Batch recibe descripción
completa pero devuelve process="null",byTitle=true,limit1/10. Se rechaza correctamente.
Journal sólo memory.status/system.time; ninguna ventana resuelta/cerrada. Cambiar de
hipótesis: heredar extracción literal/contrato de identidad antes de más prompts.
Fixture38428 cerrada por Codex tras captura, ver FIXTURE_CLEANUP.json; no éxito deBAXY.
Voz/V8/STT:28pass/1skip ambiental en4s, sesión22136 terminal0. Sin procesos pendientes.

Petición adicional del dueño atendida: PRUEBAS_C03_PARA_EMMAN.md exporta97capturas,
1726turnos/1613terminales publicados, con literales y enlaces a fallos/adjudicación.
No declara1613aciertos ni100frescos. Exportador ymanifest verifican todas las cadenas.
No nueva tarea necesaria para producir el informe; checkpoint preserva reanudación.
