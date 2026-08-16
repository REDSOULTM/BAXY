# Round 6 - browser minimo util

Modelo recomendado:

- Mejor: `Claude Opus 4.7`
- Razonamiento: `High`
- Fallback: `GPT-5.5`

Prompt:

```text
Vivimos en:

c:\Users\usuario\Desktop\ETC\Programacion\Carter OS AI

Tu trabajo ocurre SOLO dentro de:
`Carter_v3/`

OBJETIVO DE ESTA RONDA
Ejecutar `V2 Import Round 6`: redisenar browser/web con extraccion selectiva desde:
- `legacy/Carter_v2/src/carter_v2/capabilities/web.py`

NO quiero portar el surface de v2.
Quiero backend util, poco surface publico y verificacion honesta.

ANTES DE TOCAR NADA, LEE:
- `ContextoCarter.md`
- `Carter_v3/CLAUDE_V2_IMPORT_HANDOFF.md`
- `Carter_v3/V2_TO_V3_IMPORT_AUDIT.md`
- `Carter_v3/CHANGELOG.md`
- `Carter_v3/RESIDUAL.md`
- `Carter_v3/src/carter_v3/tools/dispatch.py`
- `Carter_v3/src/carter_v3/tools/verifier.py`
- `Carter_v3/src/carter_v3/perception/probe.py`
- `Carter_v3/audit/full_matrix_runner.py`

TRAZABILIDAD
Crea:
- `Carter_v3/V2_IMPORT_ROUND_6_LOG.md`

MISION
Mejorar C8 sin reintroducir:
- CDP surface publica
- tabs/profiles/extensiones como tools de core
- hacks por browser

OBJETIVOS
1. Fortalecer `web_open_url`, `web_search`, `web_extract`.
2. Mejorar readback de URL/tab/domain cuando sea posible.
3. Si introduces backend mas fuerte, que quede escondido detras del surface
   chico actual.
4. No tocar vision salvo que el caso realmente lo requiera.
5. Mantener honestidad de status/verifier.

VALIDACION
- `python -m pytest -q`
- `python audit/hardcode_guard.py`
- `python audit/full_matrix_runner.py --mode live-safe --label v2_import_round_6_full --out audit/runs/v2_import_round_6_full.json`
- `python audit/full_matrix_runner.py --mode live-safe --category 8 --label v2_import_round_6_cat8 --out audit/runs/v2_import_round_6_cat8.json`

ENTREGA
1. Que parte de `web.py` portaste realmente
2. Que no portaste y por que
3. Que mejoro de C8 con evidencia real
4. Que sigue pendiente
5. Resultados reales
6. Updates documentales
```
