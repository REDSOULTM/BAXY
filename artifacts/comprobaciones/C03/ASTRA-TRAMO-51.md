# C03 — tramo 51: narración explícita del progreso

Estado: reparación de progreso adoptada. Continúa el alcance completo.

## Herencia y diferencia comprobada

El commit44b7c45 (2026-08-23) describía explícitamente la tarea de progreso,
pero imponía «Sigo»/«Still working» y otros prefijos visibles. El compositor
actual conserva la identidad y el principio de hechos verificados, pero la
instrucción general no distingue suficientemente narrar el trabajo de contestar
la consulta. El tramo50 reprodujo la pérdida antes de los validadores y descartó
dos representaciones de datos. No se repiten ni se promueven.

Se hereda la responsabilidad de narración, sin restaurar las frases prescritas.
La comparación native progress-role51 añade una única instrucción system al
primer payload real capturado en50. El resto queda idéntico: texto original,
situation=status/in progress, idioma, Qwen3-4B-Instruct-2507 Q4_K_M, plantilla,
temperatura0, max_tokens256, cache_prompt=false. No hay guardas ni reintentos
en la comparación nativa. Reutiliza la investigación oficial del modelo/backend
de INVESTIGACION_MODELO_C03.md, vigente para esta misma configuración.

La instrucción describe la tarea de escribir un aviso breve en primera persona,
con resultados aún no disponibles. No prescribe la respuesta visible. Los cinco
borradores nativos son útiles y no inventan observaciones; posts.jsonl conserva
payloads y finish_reason=stop. 6,28 s, GPU3497,56 MiB, RAM2822,94 MiB, registro
intacto, exit0. No efectos sobre PC, reserva humana ni UI/audio.

## Candidata de producto

- llm.py conserva esa instrucción tanto en primero como en reintento de acting.
  Sustituye la corrección que dictaba «Sigo»/«Still working» por la descripción
  de la tarea. El mensaje final sigue siendo generado por el modelo.
- El control de progreso reutiliza las clases existentes de lectura instrumental
  y predicación de estado presente. Una hora o porcentaje inventados no quedan
  autorizados por coexistir con «en curso». Puede mencionar un objetivo numérico
  literal (hora de recordatorio, ajuste de volumen) sin afirmarlo como resultado.
- No cambios en C#, operaciones, proveedores, historial, modelo o sampler.

Controles nuevos: progreso con horas/CPU inventados; volumen solicitado que se
presenta falsamente como medido; objetivos numéricos válidos; preservación de la
instrucción en el reintento y ausencia de una frase visible prescrita.

## Validación

Diez suites pytest: c03_request_preservation, goal06_voice, compose_contract,
first_signal, effect_intent, turn_policy, compound_missions, planner,
request_reading y system_status_scope_grounding.
**3123 pass, 115 subtests, 0 skips, 46,52 s**, sesión88160 exit0.
Log c03-progress51-regression.log. Antes hubo un error de colección por usar el
nombre reservado request en parametrización y una inserción mal ubicada de la
instrucción en chat en vez de compose; ambos corregidos antes de la regresión.
Se conservaron las pruebas y los logs c03-progress51-owners*.log/repair.log.

Producto astra-progress51 en ejecución, sesión89117: mismos siete inputs de49,
huellas y método en PREREG. Falsa inversión C# de «no hay fallos» aún presente
para aislar el cambio de progreso. Contar boot_stage.label, no sólo finales.
No Fast51/Full ni nueva UI/voz hasta esta anotación. No cierre ni publicación.

Producto completado, sesión89117 exit0: **6/7 turnos completos útiles** frente
a4/7 de49. Los cinco avisos son fieles, sin hora/CPU/volumen inventados. t6 sigue
fallando sólo por el rechazo C# de «No hay fallos», intacto en este tramo.
69,08 s, GPU3497,56 MiB, RAM4611,50 MiB, registro intacto. PRUEBAS_PROGRESO51.md
conserva las siete entradas/respuestas/etiquetas literales. t4 necesitó tres
intentos: dos avisos honestos rechazados por posición de la señal de progreso,
y el tercero útil publicado; no afirmar que todos pasan a la primera.

Fast verde, Release2,85 s,0 avisos/errores, sesión11560 exit0; log
c03-progress51-fast.log. TRAMO51_PINS.json fija la fuente. Sin procesos propios,
sin Full ni UI/voz nuevos. Siguiente52: falsa inversión por negación de fallos.
