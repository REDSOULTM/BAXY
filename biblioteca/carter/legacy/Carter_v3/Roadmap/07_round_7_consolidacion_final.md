# Round 7 - consolidacion final

Modelo recomendado:

- Mejor: `GPT-5.4`
- Razonamiento: `High`
- Fallback: `GPT-5.2-Codex`

Prompt:

```text
Vivimos en:

c:\Users\usuario\Desktop\ETC\Programacion\Carter OS AI

Tu trabajo ocurre SOLO dentro de:
`Carter_v3/`

OBJETIVO DE ESTA RONDA
Ejecutar `V2 Import Round 7`: consolidacion final del roadmap v2->v3 ya importado.

ANTES DE TOCAR NADA, LEE:
- `ContextoCarter.md`
- `Carter_v3/CLAUDE_V2_IMPORT_HANDOFF.md`
- `Carter_v3/V2_TO_V3_IMPORT_AUDIT.md`
- `Carter_v3/CHANGELOG.md`
- `Carter_v3/RESIDUAL.md`
- todos los `V2_IMPORT_ROUND_*_LOG.md`
- `audit/runs/v2_import_round_*`

MISION
No quiero features nuevas.
Quiero consolidacion:
- deuda estructural
- docs
- metricas
- cross-model
- cleanup de residual honesto
- veredicto final de esta campana de import

OBJETIVOS
1. Revalidar todo el baseline.
2. Medir impacto acumulado por categoria.
3. Detectar si quedo complejidad accidental.
4. Proponer que cosas de v2 ya NO conviene portar nunca.
5. Dejar `CHANGELOG.md` y `RESIDUAL.md` con cierre claro de la campana.

VALIDACION OBLIGATORIA
- `python -m pytest -q`
- `python audit/hardcode_guard.py`
- `python audit/full_matrix_runner.py --mode live-safe --label v2_import_round_7_full --out audit/runs/v2_import_round_7_full.json`

Si hay mas de un modelo local disponible, ademas:
- repetir full live-safe con un segundo modelo y comparar

ENTREGA
1. Que rondas quedaron realmente cerradas
2. Que ROI real dejo cada ronda
3. Que importaciones futuras NO valen la pena
4. Resultados reales
5. Veredicto canonico de la campana v2->v3
6. Updates documentales finales
```
