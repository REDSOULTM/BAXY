# Round 3 - UIA determinista

Modelo recomendado:

- Mejor: `Claude Opus 4.7`
- Razonamiento: `High`
- Fallback: `GPT-5.1-Codex-Max`

Prompt:

```text
Vivimos en:

c:\Users\usuario\Desktop\ETC\Programacion\Carter OS AI

Tu trabajo ocurre SOLO dentro de:
`Carter_v3/`

OBJETIVO DE ESTA RONDA
Ejecutar `V2 Import Round 3`: extraer lo util de
`legacy/Carter_v2/src/carter_v2/capabilities/ui.py` para crear una capa UIA
determinista, barata y estrictamente interna.

ANTES DE TOCAR NADA, LEE:
- `ContextoCarter.md`
- `Carter_v3/CLAUDE_V2_IMPORT_HANDOFF.md`
- `Carter_v3/V2_TO_V3_IMPORT_AUDIT.md`
- `Carter_v3/CHANGELOG.md`
- `Carter_v3/RESIDUAL.md`
- `Carter_v3/V2_IMPORT_ROUND_2_LOG.md` si existe
- `Carter_v3/src/carter_v3/perception/probe.py`
- `Carter_v3/src/carter_v3/tools/dispatch.py`
- `Carter_v3/src/carter_v3/tools/verifier.py`
- `Carter_v3/src/carter_v3/agent.py`

Y de legacy:
- `legacy/Carter_v2/src/carter_v2/capabilities/ui.py`
- `legacy/Carter_v2/src/carter_v2/capabilities/window.py`
- `legacy/Carter_v2/src/carter_v2/turn/verification.py`

TRAZABILIDAD
Crea:
- `Carter_v3/V2_IMPORT_ROUND_3_LOG.md`

MISION
No quiero `gui_do`.
Quiero una UIA tier barata y determinista para:
- enumerar controles accesibles
- localizar controles por nombre/rol
- hacer focus/click/type minimo verificable
- resolver cosas que hoy caerian demasiado pronto en screenshot/OCR

REGLAS
- UIA como capa interna, no como explosion de tool surface
- sin hacks por app
- sin scripts magicos
- sin usar vision si UIA o window/probe alcanza
- no exponer `gui_do`
- cero brand logic

OBJETIVOS
1. Introducir primitives internas UIA.
2. Integrarlas a la ladder barata antes de screenshot/OCR.
3. Mejorar categoria 13 solo donde UIA realmente aplique.
4. Mantener honestidad: si UIA no ve el control, no inventar exito.

VALIDACION OBLIGATORIA
- `python -m pytest -q`
- `python audit/hardcode_guard.py`
- `python audit/full_matrix_runner.py --mode live-safe --label v2_import_round_3_full --out audit/runs/v2_import_round_3_full.json`
- `python audit/full_matrix_runner.py --mode live-safe --category 13 --label v2_import_round_3_cat13 --out audit/runs/v2_import_round_3_cat13.json`

ENTREGA FINAL
1. Que parte de `ui.py` si portaste
2. Que parte no y por que
3. Como quedo la ladder barata
4. Que subio realmente en C13
5. Resultados reales
6. Riesgos
7. Updates en `CHANGELOG.md`, `RESIDUAL.md`, `V2_IMPORT_ROUND_3_LOG.md`
```
