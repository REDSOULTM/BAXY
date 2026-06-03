# `docs/architecture/` — guía rápida

## Estructura

```
docs/architecture/
├── README.md                          ← este archivo
├── PLAN_CERRADO.md                    ← cierre formal del plan (8 sprints, métricas finales)
├── _baseline_audit/                   ← auditoría ORIGINAL (pre-Sprint 0, baseline aa99458)
│   ├── 00_inventory.md
│   ├── 01_system.md
│   ├── 02_components/
│   ├── 03_classes/
│   ├── 04_sequences/
│   ├── 05_data.md
│   ├── 06_dependencies.md
│   ├── 07_tools.md
│   ├── 08_findings.md
│   └── _findings_seed.md
├── 00_delta_inventory.md              ← (nuevo) qué archivos cambiaron, +/− por módulo
├── 01_delta_system.md                 ← (nuevo) containers actualizados, diagrama nuevo
├── 02_delta_components.md             ← (nuevo) los 9 módulos nuevos en detalle
├── 03_delta_classes.md                ← (nuevo) UML solo de clases que cambiaron
├── 05_delta_data.md                   ← (nuevo) sinks 4→3, state.json en uso
├── 06_delta_dependencies.md           ← (nuevo) grafo actualizado, comparativa
├── 08_findings_post_plan.md           ← (nuevo) deuda restante + Sprint 3b
└── sprint_prompts/                    ← prompts ejecutados + logs de cada sprint
    ├── sprint_0_and_1_tonight.md
    ├── sprint_2_instrumentation.md
    ├── sprint_3a_minimal.md
    ├── sprint_3a_recortes_confiables.md  ← (descartado, sustituido por minimal)
    ├── sprint_4_structural.md
    ├── sprint_5a_tests_first.md
    ├── sprint_5b_splits_with_safety_net.md
    ├── sprint_6_unblock_and_finish.md
    ├── _overnight_log.md              ← Sprint 0+1
    ├── _sprint2_log.md
    ├── _sprint2_usage_report.md
    ├── _sprint3a_log.md
    ├── _sprint4_log.md
    ├── _sprint5a_log.md
    ├── _sprint5b_log.md
    └── _sprint6_log.md
```

## Cómo leer

- **¿Querés entender el estado ACTUAL del repo?** Empezá por
  [00_delta_inventory.md](00_delta_inventory.md) y seguí con los
  delta docs en orden.
- **¿Querés entender qué se cambió y por qué?** Cada delta doc cita
  los sprints que lo afectaron + cita el documento baseline para
  comparar.
- **¿Querés entender qué quedó como deuda y qué se conservó a
  propósito?** [08_findings_post_plan.md](08_findings_post_plan.md).
- **¿Querés entender el plan ejecutado?** [PLAN_CERRADO.md](PLAN_CERRADO.md)
  y los logs en [../_historico/sprints/](../_historico/sprints/).
- **¿Querés el estado PRE-refactor para comparar?**
  [../_historico/baseline_audit/](../_historico/baseline_audit/) tiene la auditoría original.

## Estado del plan

- **Plan original (5 sprints):** Sprint 0+1+2+3+4.
- **Plan ejecutado (8 sprints):** Sprint 0+1+2+3a+4+5a+5b+6.
- **Pendiente (1 sprint diferido):** Sprint 3b (medir uso real de
  personas/microagents/skills tras 7-10 días con instrumentación de
  Sprint 2 activa).

## Métricas de cierre

| Métrica | Baseline | Cierre |
|---|--:|--:|
| LOC totales del paquete | 55 633 | **53 800** (−1 833 neto) |
| `agent.py` LOC | 2 968 | **1 930** (−35 %) |
| `tools.py` LOC | 4 825 | **4 282** (−11 %) |
| Tests verde | 80 | **742** |
| Compound tools | 65 | **65** (intactas) |
| Ciclos de import | 0 | 0 |
| Duplicaciones auto-confesadas | 3 | 0 |
| God classes >1 000 LOC | 4 | 2 (UI, conservadas) |
