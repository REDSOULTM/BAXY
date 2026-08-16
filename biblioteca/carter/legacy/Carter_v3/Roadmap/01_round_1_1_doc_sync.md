# Round 1.1 - Sync documental

Modelo recomendado:

- Mejor: `GPT-5.4-Mini`
- Razonamiento: `Medium`
- Si quieres mas rigor: `GPT-5.4`

Prompt:

```text
Vivimos en:

c:\Users\usuario\Desktop\ETC\Programacion\Carter OS AI

Tu trabajo ocurre SOLO dentro de:
`Carter_v3/`

No escribas nada fuera de `Carter_v3/`.

OBJETIVO
Cerrar administrativamente la `V2 Import Round 1`, SIN cambiar comportamiento
de codigo salvo que detectes una contradiccion documental evidente.

ANTES DE TOCAR NADA, LEE:
- `ContextoCarter.md`
- `Carter_v3/V2_IMPORT_ROUND_1_LOG.md`
- `Carter_v3/CLAUDE_V2_IMPORT_HANDOFF.md`
- `Carter_v3/V2_TO_V3_IMPORT_AUDIT.md`
- `Carter_v3/CHANGELOG.md`
- `Carter_v3/RESIDUAL.md`
- `Carter_v3/src/carter_v3/agent.py`
- `Carter_v3/src/carter_v3/tools/dispatch.py`
- `Carter_v3/src/carter_v3/perception/app_resolver.py`

VERIFICACION OBLIGATORIA
Ejecuta y usa resultados reales:
- `python -m pytest -q`
- `python audit/hardcode_guard.py`
- `python audit/full_matrix_runner.py --mode live-safe --label round_1_1_doc_sync_full --out audit/runs/round_1_1_doc_sync_full.json`

TRABAJO
1. Verifica si el baseline actual es 525/526 o 526/526.
2. Sincroniza `CHANGELOG.md`, `RESIDUAL.md` y `V2_IMPORT_ROUND_1_LOG.md` con la verdad actual.
3. No abras nuevo scope tecnico.
4. Si detectas artefactos temporales innecesarios de `audit/runs/`, reportalos, pero no borres nada sin justificarlo en el log.

REGLAS
- No cambies contratos publicos.
- No anadas tools.
- No toques `legacy/`.
- No toques codigo si no es estrictamente necesario.
- Cero maquillaje.

ENTREGA FINAL
1. Archivos modificados
2. Que contradicciones documentales corregiste
3. Resultados reales de pytest / hardcode_guard / full runner
4. Confirmacion explicita de que Round 1 quedo cerrada documentalmente
5. Confirmacion de aislamiento: solo `Carter_v3/`
```
