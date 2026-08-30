# Goal 9.5.0 — Fuentes del linaje, congeladas

Fecha de corte de esta corrida: **2026-08-30 ~09:52**. Máquina de este goal.

> **Veredicto: PASS.** Las cuatro rutas mínimas están presentes, estables e
> identificadas. Schema Agent se toma del historial Git de `BAXY`. No hay carpeta
> `Probando schemas` y no se exige. Siguiente:
> [`../sprints/09.5.1_MANIFIESTO_Y_COLAS.md`](../sprints/09.5.1_MANIFIESTO_Y_COLAS.md).

La corrida `5db4d64` cerró `FALLO_DE_AMBIENTE` con dos premisas que el dueño
corrigió después (carpeta Schema externa, y tamaño de `models`/`data` como gate).
Ese artefacto **no se reabre**: sigue en
[`artifacts/goal095/environment/09.5.0.md`](../../artifacts/goal095/environment/09.5.0.md)
y en los manifiestos SHA-256 de esa hora. Esta corrida (`run2/`) confirma el
mismo snapshot con las reglas vigentes y publica el cierre verde.

Raíz lógica: `Programacion\`, hermana de `BAXY DEFINITIVO`.

## Método

- Sólo lectura. `git --no-optional-locks`. Ningún checkout, restore ni clean en
  fuentes históricas.
- Recuentos A 09:48 y B 09:52 (~90 s). Cero procesos de copia.
- Si ficheros, bytes y `newest_rel` coinciden con `5db4d64`, **se reutiliza** el
  manifiesto SHA-256; no se vuelve a hashear.
- Ausencia de `.git` no es defecto. FunctionGemma y `Probando Gemma 4` son
  proyectos locales.
- No se busca una quinta carpeta por la palabra `schema`.

## Universo mínimo

| Fuente | Presente | Identidad | Ficheros | Bytes | Suficiente |
|---|---|---|---:|---:|---|
| `Programacion\BAXY` | sí | Git `203c34a9` rama `codex/baxy-cross-encoder-r209-handoff` | 116 641 | 25 488 709 507 | sí |
| `Programacion\Carter OS AI` | sí | Git `9cf62d23` rama `feat/gemma4-integration` | 136 316 | 14 935 292 111 | sí |
| `Programacion\FunctionGemma` | sí | SHA-256 `ff150df2…619eaa` (reutilizado de `5db4d64`) | 1 090 | 34 366 705 385 | sí |
| `Programacion\Probando Gemma 4` | sí | SHA-256 `72f9e5fc…13c7e71` (reutilizado; snapshot **disperso**) | 36 249 | 3 690 624 981 | sí |

A = B en esta corrida y A = recuento de `5db4d64` en las cuatro. HEAD y
`git status` de BAXY y Carter son byte-idénticos a la corrida anterior
(`status` SHA-256 `b0508200…` y `3adb0157…`).

Carter no tiene remotos. BAXY: `origin` `https://github.com/REDSOULTM/Baxy.git`,
`ahead 18`, commit 2026-08-15. Worktrees sucios: evidencia, no se limpia.

## Schema Agent

No es un repositorio hermano. Vive en el Git de `Programacion\BAXY`, como ya
documentó
[`../25_INTEGRACION_GENERACIONAL_CARTER_SCHEMA_BAXY.md`](../25_INTEGRACION_GENERACIONAL_CARTER_SCHEMA_BAXY.md)
(2026-07-22). Refs comprobados en esta corrida (sólo lectura):

| Ref | Commit | Fecha | Rutas con `schema` |
|---|---|---|---:|
| `origin/Tools-Reduce` | `e6f9c1e5` | 2026-06-26 | 12 |
| `origin/vram4_lean` | `c5f65e9a` | 2026-06-17 | 12 |
| `v0.9.2` | `398f120c` | 2026-06-19 | 12 |
| `HEAD` actual | `203c34a9` | 2026-08-15 | 9 |

En `Tools-Reduce` hay, entre otros:
`documentacion/datos_crudos/schemas_16_consolidated.json`,
`schemas_60_individuales.json`, `gemma4_agent/data/fg/tool_schemas_slim.json`,
`gemma4_agent/tools_pkg/tool_schemas.py`. La ausencia de
`Programacion\Probando schemas` no es fallo.

## Material intelectual (existencia, no auditoría)

| Fuente | Código | Docs | Tests | Config | Resultados | Manifiestos |
|---|---|---|---|---|---|---|
| BAXY | `src/` (9), `src\baxy_mind` | `documentacion/` (44), `README.md` | `tests/` (405) | `Baxy.slnx` | `artifacts/` (18) | catálogo en `src` |
| Carter OS AI | `carter_v5` (27), `legacy\Carter_v4` | `La razon de carter` (21), `docs`, `documentacion` | `tests/` + `pytest.ini` | `pytest.ini` | JSON del bench 540 en `La razon de carter` | — |
| FunctionGemma | scripts y `finetune_llm/` (89) | `README_TOOLS.md`, `router\README_ROUTER.md` | **no hay `test_*.py`** | `tool_schemas_*.json` | `finetune_llm\ops\` evals JSON + `kva_gate.json` | `tool_schemas_slim.json` (230 145 B) |
| Probando Gemma 4 | `gemma4_agent/` (42) | `documentacion/` (128), `README.md` | `gemma4_agent\tests\` (282 `test_*.py`) | `pyproject.toml`, `requirements.txt`, `conftest.py` | `overnight_audit_results.json` y JSONL de eval en la raíz | — |

FunctionGemma no trae suite pytest; el material de decisión está en `ops\`
(`NIGHT_RUN_STATE.md`, `eval_*.json`). Eso se nombra, no bloquea.

## Snapshot disperso — `Probando Gemma 4`

Copia deliberada sin ~140 GB de blobs. Gate de tamaño: **ninguno**.

| Categoría omitida | Qué hay hoy | Evidencia histórica (mapa 01, 2026-08-16) | Hash de blobs |
|---|---|---|---|
| `models\` | directorio vacío, 0 ficheros | ~17 GiB de GGUF | no se inventa |
| `data\` | 1 354 ficheros, 247 259 115 bytes | ~39 GiB | no se inventa |
| `checkpoints\model\` | vacío | el mapa 01 ya lo vio vacío | no aplica |

Esos huecos van a `sparse_exclusions` en 09.5.1. No son faltantes físicos de
esta corrida.

## Relacionados, no independientes

| Candidato | Relación |
|---|---|
| `Programacion\BAXY DEFINITIVO` | sitio de trabajo |
| `Programacion\ETC (No relacionado con baxy)` | curso; excluido por nombre y primer nivel |
| `D:\BAXY` | sidecar de julio; `source` es otro HEAD (`c57c7aff`) del mismo remoto que `Programacion\BAXY` |
| `D:\BAXY\FunctionGemma` | 3 ficheros, manifiesto `eddf65f7…`; no duplicado de `Programacion\FunctionGemma` |
| `D:\BAXYRuntime` | runtime del producto actual, no generación |
| acceso directo instalado `BAXY` | `Baxy.Setup.exe --launch`, no fuente |

JRVS no aparece en `Programacion`.

## Estabilidad y no mutación

| Árbol | A = B (run2) | Igual a `5db4d64` | Git vs run1 |
|---|---|---|---|
| BAXY | sí | sí | HEAD y status idénticos |
| Carter OS AI | sí | sí | HEAD y status idénticos |
| FunctionGemma | sí | sí | no aplica (local, sin Git) |
| Probando Gemma 4 | sí | sí | no aplica (local, sin Git) |

## Artefactos

Nueva corrida: [`artifacts/goal095/run2/`](../../artifacts/goal095/run2/).

Manifiestos SHA-256 reutilizados (no regenerados):

- `artifacts/goal095/sources/FunctionGemma.sha256.jsonl`
- `artifacts/goal095/sources/Probando_Gemma_4.sha256.jsonl`

Fallo histórico, intacto: `artifacts/goal095/environment/09.5.0.md`.

Siguiente prompt exacto:
[`../sprints/09.5.1_MANIFIESTO_Y_COLAS.md`](../sprints/09.5.1_MANIFIESTO_Y_COLAS.md).
