# `_historico/` — Archivo de proceso

**Esto NO es el estado actual del proyecto.** Es un archivo de proceso:
sprints viejos, auditorías baseline, benchmarks y handoffs ya superados. Se
conserva por trazabilidad (cómo se llegó a las decisiones), pero **no se
mantiene al día** y puede contradecir el estado vigente.

> **Para el estado vigente del proyecto:**
> - Mapa de la doc: [`../README.md`](../README.md)
> - Verdad del estado (ítem por ítem, verificado contra el código): [`../_backlog/BACKLOG_MAESTRO.md`](../_backlog/BACKLOG_MAESTRO.md)

---

## Qué hay acá

| Subcarpeta / archivo | Qué es |
|----------------------|--------|
| `sprints/` | Prompts y logs de los sprints ejecutados (hotfixes, structural, tests-first). |
| `bench_carter/` | Benchmark Carter (540 casos): reportes, comparación de modelos, iteraciones. Incluye el `INDEX.md` viejo del bench. |
| `crash_cuda_v1_v21/` | Investigación del crash CUDA en versiones v1–v21 (resuelto luego con FA off; el resultado final vive en `06_vram_estabilidad/crash_cuda_22527/`). |
| `baseline_audit/` | Auditoría arquitectural ORIGINAL (pre-refactor): inventario, sistema, componentes, clases, datos, dependencias. |
| `auditorias_baseline/` | Logs de optimización, polish, night-audits y checklists de la etapa baseline. |
| `backlogs_superados/` | Backlogs viejos ya consolidados en `_backlog/BACKLOG_MAESTRO.md`. |
| `handoffs/` | Handoffs entre sesiones/agentes (roadmaps, informes nocturnos, prompts de campo). |
| `prompts_research/` | Prompts de research enviados a investigación externa (índices y temas). |
| Archivos sueltos (`router_*.md`, `INFORME_AUDIO_PARA_CARTER.md`, el PDF) | Documentos de router (RouterV2/RRF **borrado**) y audio anteriores, archivados como registro. |
