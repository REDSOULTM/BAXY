# Round 4 - filesystem universal

Modelo recomendado:

- Mejor: `GPT-5.2-Codex`
- Razonamiento: `High`

Prompt:

```text
Vivimos en:

c:\Users\usuario\Desktop\ETC\Programacion\Carter OS AI

Tu trabajo ocurre SOLO dentro de:
`Carter_v3/`

OBJETIVO DE ESTA RONDA
Ejecutar `V2 Import Round 4`: fortalecer helpers universales de filesystem con
extraccion selectiva desde:
- `legacy/Carter_v2/src/carter_v2/capabilities/filesystem.py`

ANTES DE TOCAR NADA, LEE:
- `ContextoCarter.md`
- `Carter_v3/CLAUDE_V2_IMPORT_HANDOFF.md`
- `Carter_v3/V2_TO_V3_IMPORT_AUDIT.md`
- `Carter_v3/CHANGELOG.md`
- `Carter_v3/RESIDUAL.md`
- logs previos de import
- `Carter_v3/src/carter_v3/tools/dispatch.py`
- `Carter_v3/src/carter_v3/tools/verifier.py`
- `Carter_v3/src/carter_v3/security/policy.py`

TRAZABILIDAD
Crea:
- `Carter_v3/V2_IMPORT_ROUND_4_LOG.md`

MISION
Quiero mejorar capacidad real de filesystem sin agrandar mucho la surface publica.

SI puedes trabajar sobre:
- list/search/read/write
- create temp/safe file helpers
- directory inspection
- move/copy/delete con mejor rollback/readback si ya existe la base
- verificadores mas fuertes de cambios en disco

NO quiero:
- zip/unzip por nostalgia
- provider/domain extras
- operaciones peligrosas sin readback serio
- bypass de policy

OBJETIVOS
1. Reemplazar cualquier stub o verificacion debil restante.
2. Mejorar C9 y partes de C12 relacionadas con filesystem.
3. Si introduces move/copy/delete mas fuerte, debe quedar con rollback o
   razon honesta de por que no.

VALIDACION
- `python -m pytest -q`
- `python audit/hardcode_guard.py`
- `python audit/full_matrix_runner.py --mode live-safe --label v2_import_round_4_full --out audit/runs/v2_import_round_4_full.json`
- `python audit/full_matrix_runner.py --mode live-safe --category 9 --label v2_import_round_4_cat9 --out audit/runs/v2_import_round_4_cat9.json`

ENTREGA
1. Import real desde `filesystem.py`
2. Que subio de capacidad verificable
3. Resultados reales
4. Riesgos
5. `CHANGELOG.md`, `RESIDUAL.md`, `V2_IMPORT_ROUND_4_LOG.md`
```
