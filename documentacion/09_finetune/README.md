# 09 — Fine-tuning (Gemma 4 E2B)

Documentación del pipeline de fine-tuning del modelo del agente.

**Estado vigente:** el modelo en producción es **Gemma 4 E2B fine-tuneado** (GGUF
`Q4_K_M`), desplegado in-place en `models/E2B/`. Entra completo en 4 GB de VRAM
(~2 GB texto, ~3.36 GB con visión). El FT se entrenó con QLoRA (Unsloth) sobre un
dataset curado de mensajes históricos + cobertura de todas las tools.

> **Nota:** el dataset, los scripts de entrenamiento y los artefactos GGUF viven en
> `dataset_finetune/` en la raíz del repo, **fuera de git** (son decenas de GB,
> regenerables desde los scripts versionados). Aquí queda solo la documentación
> narrativa (decisiones, método, estado, personalidad, recolección de datos).

## Contenido

| Doc | Qué cubre |
|---|---|
| `DECISION_MAESTRA_4GB.md` | Por qué E2B y no E4B (E4B no entra en 4 GB). |
| `METODO_FINETUNE.md` | Método de entrenamiento (QLoRA / Unsloth) y su evidencia. |
| `ESTADO_COMPLETO_2026-06-02.md` | Estado del FT al cierre: gate pasado, VRAM, deploy. |
| `PERSONALIDAD.md` | Character card / personalidad del agente. |
| `RECOLECCION_HISTORICA.md` | Cómo se recolectó el corpus de mensajes históricos. |
| `DATASETS_EXTERNOS.md` | Datasets externos usados y su decisión de licencia. |
| `HANDOFF_finetune.md`, `MISION_COMPLETA_HANDOFF.md` | Handoffs del trabajo de FT. |

Para el estado general del proyecto, ver [`../_backlog/BACKLOG_MAESTRO.md`](../_backlog/BACKLOG_MAESTRO.md).
