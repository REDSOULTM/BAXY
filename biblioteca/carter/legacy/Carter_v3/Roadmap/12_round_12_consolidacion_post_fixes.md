# Round 12 - Consolidacion post-fixes

Modelo recomendado:

- Mejor: `GPT-5.4`
- Razonamiento: `High`
- Fallback: `Claude Opus 4.7`

Prompt:

```text
Vivimos en:

c:\Users\usuario\Desktop\ETC\Programacion\Carter OS AI

Tu trabajo ocurre SOLO dentro de:
`Carter_v3/`

OBJETIVO DE ESTA RONDA
Consolidacion honesta despues de los fixes de Round 8 a Round 11.
Esta ronda NO agrega features. Revalida, documenta y deja el
estado del proyecto limpio y auditado.

ANTES DE TOCAR NADA, LEE:
- `ContextoCarter.md`
- `Carter_v3/CHANGELOG.md`
- `Carter_v3/RESIDUAL.md`
- todos los `Carter_v3/V2_IMPORT_ROUND_*_LOG.md` (especialmente 8-11)
- todos los `audit/runs/round_8_*`, `round_9_*`, `round_10_*`, `round_11_*`

TRAZABILIDAD
Crea:
- `Carter_v3/V2_IMPORT_ROUND_12_LOG.md`

MISION
No quiero features nuevas.
Quiero cierre real:
- verificar que C14 quedo cerrado (Round 8)
- verificar que el refactor de dispatch no introdujo regresiones (Round 9)
- verificar que el protocolo de tools mejoró de forma medible (Round 10)
- verificar que la provenance de user_approved es correcta (Round 11)
- dejar CHANGELOG y RESIDUAL con un cierre limpio de esta segunda campana

VALIDACION OBLIGATORIA
- `python -m pytest -q`
- `python audit/hardcode_guard.py`
- `python audit/full_matrix_runner.py --mode live-safe --label round_12_consolidacion_full --out audit/runs/round_12_consolidacion_full.json`

Si hay mas de un modelo local disponible:
- repetir full live-safe con un segundo modelo
- `python audit/full_matrix_runner.py --mode live-safe --model phi3.5:latest --label round_12_consolidacion_cross --out audit/runs/round_12_consolidacion_cross.json`

OBJETIVOS CONCRETOS
1. Revalidar que el baseline del runner es mejor que el de Round 7 (>99.24%)
   o igual con C14 cerrado.
2. Medir impacto acumulado de Round 8-11 por categoria afectada.
3. Detectar si quedo complejidad accidental nueva.
4. Actualizar el inventario de deuda real en RESIDUAL: cerrar lo que si
   se cerro, abrir lo que se descubrio nuevo.
5. Dejar CHANGELOG con cierre claro de esta segunda campana de fixes.

METRICAS A REPORTAR
- Total tests antes/despues (debe ser > 304 con los tests nuevos de R8-R11)
- Total lineas src/carter_v3 antes/despues del refactor R9
- Runner global antes (99.24%) vs despues
- C14 pass rate antes (0% C14.01-04) vs despues
- C11 pass rate (debe mantenerse 100%)

VEREDICTO CANONICO A EMITIR
Al final de tu entrega, emite uno de:

`V3_SECOND_CAMPAIGN_CLOSED`     - todo lo planificado se cerro
`V3_SECOND_CAMPAIGN_PARTIAL`    - cerro con residual documentado honestamente
`V3_SECOND_CAMPAIGN_BLOCKED`    - algun fix no aterrizo y necesita otra ronda

No emitir `CLOSED` si C14 sigue fallando o si el runner bajó de Round 7.

ENTREGA
1. Que rondas (8-11) quedaron realmente cerradas
2. Que ROI real dejo cada ronda (metricas, no narrativa)
3. Que sigue abierto (con honestidad)
4. Resultados reales de todos los runners
5. Veredicto canonico justificado
6. Updates documentales finales en CHANGELOG.md y RESIDUAL.md
```
