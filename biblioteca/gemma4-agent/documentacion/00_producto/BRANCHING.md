# Modelo de ramas — Baxy

> Documento autoritativo del modelo de ramas del repo. Actualizar acá ANTES de
> renombrar/agregar/borrar ramas para que la próxima sesión encuentre el mapa.

## Ramas vivas

### `main` — rama consolidada de producción

**Qué contiene**: estado estable, validado, listo para correr en hardware
target (6 GB VRAM mínimo). Cada commit en `main` debe cumplir simultáneamente:

- `python audit/smoke_mode_a.py` → 143/143 PASS, 6/6 anti-bypass PASS.
- `python -m pytest gemma4_agent/test_gx_features.py gemma4_agent/test_router.py gemma4_agent/test_model_info.py -q` → todo PASS.
- 0 dependencias nuevas que rompan "instalable en 5 minutos".
- Setup del dev (`GEMMA4_MODEL_PATH` apuntando a Q6_K) preservado.

**Cómo llegan los cambios**: vía merge `--no-ff` desde `develop` o desde
ramas `feature/*` específicas tras review. **Nunca commits directos**.

**Tags**: cada release etiquetada con `vX.Y.Z` siguiendo SemVer. Los tags
`backup/*` se mantienen como red de seguridad entre merges grandes.

### `develop` — rama activa de desarrollo continuo

**Qué contiene**: el siguiente release en preparación. Acá llegan los
features intermedios, refactors, fixes que aún no están validados al 100 %
para `main` pero ya pasan el smoke test mínimo.

**Reglas**:
- Cada commit debe compilar (`py_compile`).
- Idealmente cada commit pasa el smoke; si no, marcar el commit como `wip:`
  y arreglar antes del próximo merge a `main`.
- Sin bloqueos sobre `agent.py`/`tool_retrieval.py`/`verifier_orchestrator.py`
  siempre que los cambios sean aditivos y opt-outable.

**Cómo llegan los cambios**: branches `feature/<topic>`, `fix/<topic>`,
`exp/<topic>` que mergean acá vía `--no-ff` cuando el smoke pasa.

**Cómo sube a `main`**: una vez `develop` alcanza un estado validado
estable, se mergea a `main` con `--no-ff` + tag de release.

### Ramas históricas mantenidas

- **`feat/ui-field-react`**: rama de trabajo histórica (~5 sesiones nocturnas).
  Contiene el WIP snapshot `1106273` y todo el merge de Fase 1+2+3 + polish.
  Es la *predecesora* de `main` — no se borra para preservar contexto, pero
  el desarrollo nuevo ya no va ahí.
- **`feature/gemma4-optimization-roadmap`**: branch del roadmap completo.
  Mantenida como safety net.
- **`polish/post-merge-finalize`**: branch de los 4 items de polish post-merge.
  Mantenida como safety net.
- **`master`**: rama original del repo (~5 commits atrás del trabajo reciente).
  No se borra por historicidad, pero no se sigue desarrollando ahí.

## Tags activos

- `v0.9.0` — primer release consolidado en `main` post-merge (Fases 1+2+3 + polish).
- `v0.9.1` — patch: profiles.balanced_8gb ctx 16K (medido) + Task Scheduler upstream.
- `backup/pre-merge-feature-20260515` — snapshot del feature antes del merge a main.
- `backup/pre-merge-main-20260515` — snapshot de `feat/ui-field-react` (main efectivo previo) antes del merge.

## Workflow estándar para el dev

```bash
# Empezar feature nuevo
git checkout develop
git pull
git checkout -b feature/mi-feature

# Trabajar, commitear, validar
python audit/smoke_mode_a.py
python -m pytest gemma4_agent/test_*.py -q

# Cuando esté listo
git checkout develop
git merge --no-ff feature/mi-feature
# branch de feature se mantiene para histórico, no se borra

# Cuando develop alcanza un estado estable
git checkout main
git merge --no-ff develop
git tag -a vX.Y.Z -m "release X.Y.Z: <descripción breve>"
```

## Reglas duras para `main`

1. **Nunca `git push --force` sobre `main`**. Si hay que revertir, usar
   `git revert <commit>` (preserva historia) o tag de backup.
2. **Nunca borrar tags `backup/*`** hasta que el state correspondiente
   haya estado en producción ≥30 días sin incidentes.
3. **Nunca merge directo de `feature/*` a `main`**. Pasa por `develop` primero.
4. **Nunca skip hooks** (`--no-verify`) al commitear o mergear.

## Cuándo crear release

Una release a `main` justifica un tag `vX.Y.Z` cuando:
- **patch** (`v0.0.X`): bug fix sin cambio de comportamiento observable.
- **minor** (`v0.X.0`): feature nueva opt-in, sin romper API ni perfiles.
- **major** (`vX.0.0`): cambio breaking en perfiles, env vars, o defaults.

Estado actual: pre-1.0 (`v0.X.Y`). El primer `v1.0.0` se etiquetará cuando:
- Carter 540 confirme ≥99% pass-rate sobre `balanced` (6 GB target).
- VRAM real medida en RTX 3050 6 GB confirme que `balanced` y `light` entran sin OOM.
