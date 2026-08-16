# Round 5 - terminal seguro

Modelo recomendado:

- Mejor: `GPT-5.1-Codex-Max`
- Razonamiento: `High`
- Fallback: `Claude Opus 4.7`

Prompt:

```text
Vivimos en:

c:\Users\usuario\Desktop\ETC\Programacion\Carter OS AI

Tu trabajo ocurre SOLO dentro de:
`Carter_v3/`

OBJETIVO DE ESTA RONDA
Ejecutar `V2 Import Round 5`: fortalecer terminal seguro y verificable desde
partes selectivas de:
- `legacy/Carter_v2/src/carter_v2/capabilities/terminal.py`

ANTES DE TOCAR NADA, LEE:
- `ContextoCarter.md`
- `Carter_v3/CLAUDE_V2_IMPORT_HANDOFF.md`
- `Carter_v3/V2_TO_V3_IMPORT_AUDIT.md`
- `Carter_v3/CHANGELOG.md`
- `Carter_v3/RESIDUAL.md`
- `Carter_v3/src/carter_v3/security/policy.py`
- `Carter_v3/src/carter_v3/tools/dispatch.py`
- `Carter_v3/src/carter_v3/tools/verifier.py`

TRAZABILIDAD
Crea:
- `Carter_v3/V2_IMPORT_ROUND_5_LOG.md`

MISION
Quiero que la ejecucion de terminal sea mas util sin abrir agujeros de seguridad.

OBJETIVOS
1. Mejorar ejecucion segura para comandos permitidos.
2. Mantener bloqueo pre-LLM para destructivo.
3. Mejorar verificacion de efectos del terminal cuando sea posible.
4. No convertir terminal en escape hatch de todo el sistema.

REGLAS
- nada de allowlists gigantes por app
- nada de terminal como bypass de policy
- nada de `ok=True` sin readback cuando el caso requiera evidencia
- si no puedes verificar, dilo como `unverified` o `failed`, no como `complete`

VALIDACION
- `python -m pytest -q`
- `python audit/hardcode_guard.py`
- `python audit/full_matrix_runner.py --mode live-safe --label v2_import_round_5_full --out audit/runs/v2_import_round_5_full.json`
- `python audit/full_matrix_runner.py --mode live-safe --category 10 --label v2_import_round_5_cat10 --out audit/runs/v2_import_round_5_cat10.json`
- `python audit/full_matrix_runner.py --mode live-safe --category 11 --label v2_import_round_5_cat11 --out audit/runs/v2_import_round_5_cat11.json`

ENTREGA
1. Que parte de `terminal.py` si sirve para v3
2. Que descartaste
3. Como quedo el contrato de seguridad real
4. Resultados reales
5. Riesgos
6. Updates documentales
```
