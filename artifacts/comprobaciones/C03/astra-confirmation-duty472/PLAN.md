# 472 — contrato de decisión informada, antes de editar producto

Hallazgo nuevo en fuente466: llm.py9331 exige acción, objetivo y opciones; la fidelidad general sólo prohíbe inventar. No exige explicar el motivo y las consecuencias ya suministradas. Export467/471 las recibe y las omite; 465/468 omiten irreversibilidad aunque cause la conserva. La calidad se juzgó con esa obligación, pero no se la pidió explícitamente al compositor. No añadir frase visible, filtros, riesgos inferidos ni otra capa de generación.

Comparación acotada: sustituir sólo la primera frase de la instrucción de confirmación por una obligación general de explicar acción, objetivo, causa y consecuencias suministradas, conservando su modalidad. Todas las opciones, el contrato literal y los hechos quedan idénticos. Cada primer payload se contrasta automáticamente con468 antes de sustituir. Controles memoria idénticos. Sampler documentado de Qwen2507, no defaults arbitrarios.

Herencia: astra-pending-action367/368 transportan la invocación/cause; astra-confirmation-context369 los preserva durante recuperación. Fuente466 repara pérdida de campos. 469 sólo elimina encabezados vacíos y no se adopta. Esta prueba cambia la obligación semántica de la tarea; no repite sus proyecciones ni abre barrido de modelos o redacción. Si no mejora, detener esta hipótesis.

Fuentes ya aplicables: ficha Qwen/Qwen3-4B-Instruct-2507 (modelo estrictamente no-thinking y receta .7/.8/k20/min0); INVESTIGACION_MODELO_C03 para template/budget real de b10809 y sus reproducciones. La página genérica antigua de Gemma core/prompt-structure está fechada2025 y no se aplica al soporte system de Gemma4; no modificar roles por ella.

No inferencia externa ni edición de fuente/registro. No efectos, UI, voz ni reserva fresca. Adjudicar seis casos por semilla con rúbrica465, controles aparte. La instrucción es código de diagnóstico, no respuesta visible.
