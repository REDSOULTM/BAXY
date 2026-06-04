# 09 — Fine-tuning (modelo Gemma 4 E2B)

Documentación del pipeline de fine-tuning del modelo del agente **Baxy** (el producto;
antes "Gemma 4 Agent" → "Carter" → **Baxy**). El **modelo** es **Gemma 4 E2B** de Google
— ese nombre NO se renombra; "Baxy" es el producto que corre sobre él.

**Estado vigente (HECHO, verificado on-disk):** el modelo en producción es el **Gemma 4 E2B
fine-tuneado**, **desplegado IN-PLACE** en `models/E2B/gemma-4-E2B-it-Q4_K_M.gguf` (GGUF
`Q4_K_M`, 3.4 GB on-disk). El base original quedó respaldado en el mismo dir como
`gemma-4-E2B-it-Q4_K_M.BASE-BACKUP.gguf` (3.1 GB); la visión va en `mmproj-F16.gguf`
(985 MB). Entra completo en 4 GB de VRAM (**2.07 GB texto medido**, ~3.0–3.36 GB con visión
lazy). El FT se entrenó con QLoRA-4bit (Unsloth) sobre un dataset curado de mensajes
históricos + cobertura de las **61 tools** (smart_home eliminada). **Gate pasado:** 0% tools
inventadas en prod (con array de tools). Revertir = copiar el `.BASE-BACKUP.gguf` sobre el
`.gguf`. Detalle del deploy en `MISION_COMPLETA_HANDOFF.md`.

> **Nota:** el dataset, los scripts de entrenamiento y los artefactos GGUF viven en
> `dataset_finetune/` en la raíz del repo, **fuera de git** (son decenas de GB,
> regenerables desde los scripts versionados). Aquí queda solo la documentación
> narrativa (decisiones, método, estado, personalidad, recolección de datos).

## Contenido

| Doc | Qué cubre |
|---|---|
| `DECISION_MAESTRA_4GB.md` | Por qué E2B y no E4B (E4B no entra en 4 GB). Decisión EJECUTADA. |
| `METODO_FINETUNE.md` | Método de entrenamiento (QLoRA / Unsloth) y su evidencia. El veredicto cita E4B; el target real es E2B (ver banner del doc). |
| `ESTADO_COMPLETO_2026-06-02.md` | Estado del FT al cierre: gate pasado, VRAM, dataset. Deploy ya completado. |
| `PERSONALIDAD.md` | Character card / personalidad de Baxy. |
| `RECOLECCION_HISTORICA.md` | Cómo se recolectó el corpus de mensajes históricos (lineage Carter OS → Baxy). |
| `DATASETS_EXTERNOS.md` | Datasets externos evaluados y su decisión de licencia. |
| `HANDOFF_finetune.md`, `MISION_COMPLETA_HANDOFF.md` | Handoffs del trabajo de FT (registro HISTÓRICO de cómo se llegó al estado actual; `MISION_COMPLETA_HANDOFF.md` documenta el deploy in-place y los 2 bugs cazados en vivo). |

> Los dos `*HANDOFF*` y `RECOLECCION_HISTORICA` se conservan como **historia** (no son el
> estado actual): registran las fases, decisiones y bugs del proceso de FT. El estado
> vigente es el de arriba + `ESTADO_COMPLETO_2026-06-02.md`.

Para el estado general del proyecto, ver [`../_backlog/BACKLOG_MAESTRO.md`](../_backlog/BACKLOG_MAESTRO.md).
