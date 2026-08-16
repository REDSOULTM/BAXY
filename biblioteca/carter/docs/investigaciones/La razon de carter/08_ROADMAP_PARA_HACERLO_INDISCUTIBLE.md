# 08 - Roadmap para hacerlo indiscutible

Fecha de generacion: 2026-05-08

## Prioridad estrategica

El roadmap no debe agregar mas fantasia. Debe convertir la tesis en evidencia externa: menos fake success, mas robustez GUI/multi-step, mejores benchmarks y una demo honesta.

## Alto impacto / bajo esfuerzo

| Mejora | Motivo |
|---|---|
| Reconciliar numeros de evaluacion | El conflicto 519/540 vs 417/540 destruye confianza. |
| Publicar definicion de PASS/PARTIAL/FAILED/UNVERIFIED | Sin criterios claros, la matrix no convence. |
| Separar resultados por categoria y version | Evita claims globales falsos. |
| Agregar logs de verifier por caso | Permite auditar fake success. |
| Crear 20 tareas "golden" reproducibles | Base minima para demo y regression. |
| Documentar modo offline/local exacto | Hace defendible privacidad. |
| Marcar GUI/VLM como experimental donde aplique | Evita marketing no comprobado. |
| Tests adversariales de safety basicos | Alta credibilidad con poco scope. |

## Alto impacto / alto esfuerzo

| Mejora | Motivo |
|---|---|
| GUI universal robusta UIA/OCR/VLM con fallback honesto | Cierra la mayor debilidad tecnica. |
| Planner multi-step con verificacion por subobjetivo | Cierra C14 y misiones reales. |
| Evaluacion comparativa contra competidores | Convierte opinion en tesis. |
| Dataset publico o reproducible de tareas Windows | Da defendibilidad academica. |
| Instalador/UX de producto | Sin eso no es producto final para usuario real. |
| Observability completa | Logs, traces, screenshots, before/after state. |
| Memory/skill eval | Probar que memoria mejora, no solo existe. |

## Riesgos que deben cerrarse antes de presentar

1. GUI moderna y apps CEF/Electron.
2. Multi-step con replanificacion.
3. Falsos positivos del auditor.
4. Safety destructiva y command injection.
5. Latencia p95 por categoria.
6. Privacidad real en modo local/offline.
7. Claims de "sin hardcodes" demasiado absolutos.

## Benchmarks necesarios

- Carter-Local-PC-20: tareas pequenas reproducibles para demo.
- Carter-Local-PC-100: suite estable por categoria.
- Carter-540 revisada: criterios limpios, auditor calibrado y manual blind sample.
- Fake-success benchmark: tareas diseñadas para tentar al agente a mentir.
- Safety benchmark: borrar/mover/ejecutar/filtrar con prompts ambiguos y maliciosos.
- GUI benchmark local: Notepad, Explorer, navegador, Steam, Discord/Spotify si estan disponibles.

## Demos necesarias

| Demo | Debe mostrar |
|---|---|
| Demo honesta de exito | Acciones OS reales con verifiers visibles. |
| Demo honesta de fallo | Carter dice no verificado y no inventa exito. |
| Demo destructiva | Pide confirmacion o rechaza. |
| Demo multi-step | Planea, ejecuta, verifica y replanifica. |
| Demo local/offline | Funciona sin cloud para tareas core. |
| Demo comparativa | Misma tarea contra un baseline. |

## Documentacion necesaria

- Arquitectura de agent loop.
- Catalogo de tools y verifiers.
- Politica de safety y sandbox.
- Guia de evaluacion y criterios.
- Limitaciones conocidas.
- Modo offline y privacidad.
- Setup reproducible de benchmarks.
- Changelog de resultados por version.

## Que NO hacer porque distrae

- Agregar voz antes de cerrar texto/tools/verifiers.
- Agregar mas apps especiales con hardcodes por demo.
- Intentar competir en SWE-bench.
- Construir marketplace/extensiones antes de producto core.
- Perseguir 540/540 sin resolver falsos positivos.
- Publicar claims tipo "Jarvis" sin evidencia.

## Que medir

- Success real.
- Fake-success rate.
- Unverified correcto.
- Latencia p50/p95/p99.
- Replans por tarea.
- Confirmaciones destructivas correctas.
- Fallos por categoria.
- Acuerdo auditor automatico vs manual.
- Uso de memoria/skills y efecto en exito.

## Que automatizar

- Ejecucion de matrix con snapshots de estado.
- Recoleccion de logs/verifiers.
- Auditor automatico calibrado.
- Reporte Markdown/JSON por version.
- Comparacion antes/despues por categoria.
- Tests adversariales safety.

## Que comparar

Prioridad comparativa:

1. Agent-S en GUI/computer-use.
2. Open Interpreter en terminal/codigo local.
3. Mark-XXXIX en asistente personal PC.
4. goose en agente local general.
5. OS-Copilot en research OS agent.

Comparaciones secundarias:

- OpenHands para coding only.
- AutoGPT para workflows.
- AutoGen/LangGraph para arquitectura.
- openclaw para multi-canal.

## Que publicar

- Reporte de limitaciones.
- Dataset de tareas o al menos specs reproducibles.
- Logs anonimizados.
- Videos sin cortes de demos clave.
- Tabla de resultados por categoria.
- Scripts de evaluacion.
- Version exacta de modelo/hardware.

## Roadmap por fases

### Fase 1 - Minima defendible

- Congelar Carter v4 actual.
- Reconciliar metricas.
- Crear suite 20 tareas.
- Mostrar 3 demos: exito, fallo honesto, safety.
- Documentar tools/verifiers y limitaciones.

### Fase 2 - Producto solido

- Mejorar GUI en apps comunes.
- Mejorar planner multi-step.
- Reducir falsos positivos del auditor.
- Crear instalacion simple.
- Medir latencia por categoria.
- UX clara para confirmaciones y fallos.

### Fase 3 - Tesis fuerte

- Suite 100+ reproducible.
- Baselines con competidores.
- Auditoria manual ciega.
- Paper/report con metodologia y amenazas a validez.
- Experimentos de fake-success y safety.

### Fase 4 - Demo publica

- Demo end-to-end sin cortes.
- Logs verificables.
- Comparacion contra baseline.
- Modo offline.
- Pagina de resultados honesta con fallos conocidos.

## Clasificación de afirmaciones

Evidencia: roadmap deriva de fallos locales en reporte 540 y arquitectura actual.

Inferencia: cerrar evaluacion y GUI tendra mayor impacto estrategico que agregar mas features.

Hipotesis: una demo honesta de fallo aumenta credibilidad en vez de danarla.

Opinion estrategica: publicar limitaciones antes que promesas protege la tesis.

Claim no defendible: perseguir "indiscutible" como perfeccion; solo puede significar suficientemente evidenciado.

## Limitaciones de este análisis

El roadmap no estima tiempo real ni dependencia de hardware/modelos. Tampoco sabe que competidores podran instalarse sin friccion en la maquina final.

## Qué falta verificar

Falta priorizar segun esfuerzo real del codigo Carter, crear issues concretos y medir impacto despues de cada fase.

## Conclusión honesta

Para hacer Carter indiscutible no hay que agrandarlo; hay que hacerlo verificable ante terceros. La proxima unidad de progreso no es otra tool, es una prueba que alguien externo no pueda descartar.
