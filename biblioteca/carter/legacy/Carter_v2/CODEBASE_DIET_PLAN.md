# Codebase Diet Plan — Carter v2

Fecha: 2026-05-01
Branch: `repo-cleanup-test-rebuild`
Contexto: Ejecutado tras FASE 2 (reorg) y FASE 4 (rebuild tests).

## Resumen ejecutivo

La auditoría (FASE 1) y el codebase scan posterior confirman que **`src/carter_v2/` ya está bien dimensionado** — no hay módulos huérfanos, ni capas de compatibilidad legacy, ni wrappers `_v1`/`_old`. La mayor parte del "diet" sustantivo se ejecutó en FASE 2 al sacar de la raíz 22 markdowns históricos, ~116 archivos probe, runners obsoletos y la suite legacy completa.

Lo que queda está clasificado y justificado.

## 1. Código eliminado / archivado en FASE 2

| Item | Acción | Destino | Justificación |
|---|---|---|---|
| `audit/smoke_runner.py` | ARCHIVE | `audit/temp/` | Superseded por `compound_smoke_runner.py`. Sin importadores. |
| `audit/smoke_runner_fsmoke.py` | ARCHIVE | `audit/temp/` | Variante histórica. |
| `audit/_c3_strip.py` | ARCHIVE | `audit/temp/` | Migración one-shot ya aplicada. |
| `audit/F0_invariants.py.bak` | MOVE | `backups/` | Backup huérfano. |
| ~116 `probe_*` + `.probe*`/`.smoke*`/`.tmp*`/`.diag*` SQLite | ARCHIVE | `backups/probe_archive_20260501-020549/` | Sin uso vivo. |
| `__pycache__/`, `.pytest_cache/`, `test_probe.db`, `test_skills.db` | DELETE | — | Auto-regenerables. |
| Toda `tests/` legacy (1667 tests) | WIPE → BACKUP | `backups/tests_legacy_20260501-020549/` | Reemplazada por suite mínima (FASE 4 → 368 tests). |

## 2. Análisis de `src/carter_v2/` (módulo por módulo)

**Resultado del análisis dead-code (grep + import scan):**
- 0 módulos sin importadores cruzados.
- 0 archivos con sufijo `_legacy` / `_old` / `_v1` / `_compat`.
- 0 wrappers de compatibilidad detectados.

| Subpaquete | Veredicto | Acción |
|---|---|---|
| `adapters/` | CORE — todo en uso | KEEP |
| `capabilities/` | CORE — capacidades determinísticas activas | KEEP |
| `interfaces/{slack,discord,telegram,http,extension_relay}` | OFF_BY_DEFAULT — canales opcionales, importados sólo si se activan | KEEP_LAZY (documentar) |
| `plugins/loader.py` | KEEP_LAZY — plugin discovery local | KEEP |
| `recovery/` | CORE — clasificador + políticas de retry | KEEP |
| `session/` | CORE — estado, memoria, política, observer | KEEP |
| `skills/<vendor>/SKILL.md` (10 vendors) | CORE — cargadas por `session/skills.py` (built-in skill catalog) | KEEP |
| `tasks/background.py` | KEEP_LAZY — tareas async opt-in | KEEP |
| `turn/` | CORE — loop principal, mission state, intent, ledger, perception | KEEP |
| `universal/` | CORE — universal kernel + tool index | KEEP |
| `verification/` | CORE — verificación post-acción | KEEP |
| Archivos top: `main.py`, `config.py`, `event_bus.py`, `types.py` | CORE | KEEP |

## 3. Deprecaciones controladas vivas

`src/carter_v2/adapters/tools.py`:
- Línea 614 — tool marcada `deprecated=True`
- Línea 625 — tool marcada `deprecated=True`
- Línea 2012 — `_TOOL_BY_NAME[_name].deprecated = True` (registro programático)

**Decisión:** KEEP. El sistema de deprecación es la vía oficial; los tools siguen exportándose pero están marcados. No introducir borrados aquí — si algún cliente externo (LLM prompts, plugins) los espera, romperíamos contratos. La eliminación física debe ser una decisión separada con su propio gate.

## 4. Lo que NO se borra (con justificación)

| Item | Razón |
|---|---|
| `interfaces/{slack,discord,telegram,http}` | Canales OFF_BY_DEFAULT pero contratos públicos. Su carga es perezosa; cero costo en runtime de texto. |
| `plugins/loader.py` | API pública para plugins de usuario futuros. |
| `tasks/background.py` | Hook para extensiones; mínimo y autónomo. |
| `universal/` | Kernel LLM-driven activo en planning. |
| `recovery/` | Política de retry; usado por agente. |
| `MEMORY.md`, `DREAMS.md` (raíz) | **Runtime-state** — `session/memory.py:325-326` los lee como `_base_dir / "MEMORY.md"`. **NO mover.** |
| `src/carter_v2/skills/<vendor>/SKILL.md` | Skill catalog built-in cargado por `session/skills.py`. |

## 5. Riesgos restantes

1. **Deprecated tools (2)** — necesitan gate de eliminación si se confirma que ningún prompt los referencia. Recomendación: scan adicional en `src/carter_v2/turn/_system_prompt.py` y `universal/`.
2. **`audit/temp/` (3 archivos archivados)** — pueden borrarse físicamente en una segunda ola si no se necesitan como referencia.
3. **`backups/` crece** — establecer política de retención (sugerencia: comprimir snapshots > 30 días).

## 6. Decisión final

**No se elimina código productivo en esta fase.** El codebase de `src/carter_v2/` es coherente, sin grasa significativa. La limpieza realizada en FASE 2 + FASE 4 es la sustancial.

Cualquier eliminación adicional (e.g. retirar interfaces no usados) debe ser un *follow-up* con su propia evidencia, no parte del cleanup masivo actual.
