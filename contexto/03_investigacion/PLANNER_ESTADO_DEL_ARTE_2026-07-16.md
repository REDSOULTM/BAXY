# Planner de BAXY — contraste con el estado del arte

Fecha: 2026-07-16. Se priorizaron papers y documentación primaria; los reportes
de usuarios se usan sólo como evidencia cualitativa de operación.

## Hallazgos externos que cambian el diseño

| Evidencia | Hallazgo | Aplicación en BAXY |
|---|---|---|
| [APB](https://arxiv.org/abs/2606.04874) | 4.209 casos orientados específicamente a planning; persisten fallos en horizonte largo, ruido de tools, rechazo calibrado y refinamiento | Batería separada de planning; segunda pasada de auditoría; irrelevantes e irresolubles deben abstenerse |
| [PlanBench-XL](https://arxiv.org/abs/2606.22388) | 1.665 tools y recuperación iterativa; planes aparentemente válidos conservan bloqueos severos | Retrieval por familia y operación; máximo 8 familias/28 operaciones; no proyectar el catálogo completo |
| [ToolMaze](https://arxiv.org/abs/2606.05806) | La recuperación cae especialmente ante fallos semánticos implícitos; fault tolerance progresa más lento que ejecución básica | `EffectMayHaveOccurred` manda; no retry/replan ante ambigüedad; estado inconcluso explícito |
| [ToolSandbox](https://arxiv.org/abs/2408.04682) | Las tareas reales tienen estado implícito, dependencias y milestones intermedios | Grounding después de outputs verificados y observaciones estructuradas |
| [τ-bench](https://arxiv.org/abs/2406.12045) | El estado final y `pass^k` exponen fragilidad que una tasa media oculta | Gates por estado final, cero falso éxito y repetición; no contar sólo JSON válido |
| [ReAct](https://arxiv.org/abs/2210.03629) | Intercalar razonamiento y observación mejora interacción | Se adopta sólo como ciclo acotado plan→acción→observación, no como loop autónomo abierto |
| [LLMCompiler](https://arxiv.org/abs/2312.04511) | DAG y ejecución paralela pueden reducir latencia/coste | El contrato expresa DAG, pero la primera versión ejecuta secuencialmente para preservar confirmación y recovery; paralelismo queda condicionado a independencia probada |
| [AI Agents That Matter](https://arxiv.org/abs/2407.01502) | Accuracy aislada incentiva sistemas caros y sobreajustados; importan coste y reproducibilidad | Se registran arranque, latencia, abstenciones y fallos; no se declara éxito por el prompt de seis casos |
| [CaMeL](https://arxiv.org/abs/2503.18813) | Separar control confiable y datos no confiables permite enforcement de data-flow | Objetivo del usuario controla; outputs libres no cambian el plan; sólo una proyección segura vuelve al modelo |
| [ToolEmu](https://arxiv.org/abs/2309.15817), [AgentDojo](https://arxiv.org/abs/2406.13352) | Los agentes de tools necesitan evaluación adversarial de seguridad y prompt injection | Strings de web/OCR/documentos no se reinyectan; schemas, catálogo y permisos se validan fuera del modelo |

La documentación de [Microsoft Agent Framework Durable
Extension](https://learn.microsoft.com/en-us/agent-framework/integrations/durable-extension)
y [LangGraph persistence](https://docs.langchain.com/oss/python/langgraph/persistence)
coincide en checkpoint por paso, reanudación y human-in-the-loop. BAXY aplica
esos contratos sobre su store cifrado propio para no añadir otro runtime ni
debilitar NativeAOT.

## Reportes de usuarios: señales, no benchmarks

- Un reporte de producción describe loops planner/executor y recomienda gates
  duros de escalamiento: [Why I stopped building autonomous agents](https://www.reddit.com/r/AI_Agents/comments/1ssf0f9/why_i_stopped_building_autonomous_agents_for/).
- Usuarios señalan que muchos «agents» deberían ser workflows por
  trazabilidad: [Most things people ship as agents should be a workflow](https://www.reddit.com/r/AI_Agents/comments/1tfjxrb/most_things_people_ship_as_agents_should_be_a/).
- En incident response, checkpoint/interrupt se describe como contrato de
  auditoría, no detalle interno: [production incident response agent](https://www.reddit.com/r/LangChain/comments/1t2wiog/built_a_production_incident_response_agent_with/).

Estos testimonios refuerzan el híbrido: workflow determinista cuando existe,
planner sólo donde aporta composición, e intervención humana ante ambigüedad.

## Decisión resultante

```text
objetivo confiable
  → retrieval e5-small por cláusula/familia/operación
  → propuesta de skeleton cerrado
  → validación Python sin autoridad
  → auditoría independiente; debe concordar en operaciones
  → extracción literal con opción de abstenerse
  → revalidación .NET contra ProductCatalog
  → checkpoint cifrado
  → core: schema → riesgo → confirmación → efecto → verifier
  → proyección segura de observación
  → siguiente paso o replan seguro (máximo 2)
```

Presupuestos: 16 pasos, 8 familias, 28 operaciones visibles, dos replans y una
sola ejecución activa. Un plan no puede incluir `memory.*`, operaciones
internas, `app.status` privado ni riesgo `forbidden_destructive`.

## Qué no demuestra este corte

- Clasifica las 166 misiones y evalúa las 123 naturales con el LLM local. El
  corte final elimina los 53 errores: 47 planes verificables, 61 aclaraciones
  por autoridad faltante y 15 conversaciones. Una aclaración sigue sin ser una
  capacidad cumplida, pero ya no se presenta como error técnico.
- No certifica cuentas, aplicaciones o servicios externos.
- No prueba paralelismo ni compensación general.
- No convierte una abstención segura en capacidad cumplida.
- No afirma que el modelo E2B sea suficiente para toda la cola larga; la
  arquitectura permite cambiar el planner sin cambiar la autoridad del core.
