# Handoff — 09.5.7 tools/skills/misiones — 2026-08-31

## Objetivo
Reconciliar tools, skills, providers y misiones históricas contra el catálogo
vivo, sin recuperar capas descartadas ni un segundo camino.

## Estado
Hecho: síntesis 09.5.7 cerrada. Campañas 09.5.2–09.5.4 siguen pending=0 claimed=0.
En curso: nada de 09.5.7.
Sin empezar: `09.5.8_RUNTIME_UI_RECURSOS.md`.

## Decisiones tomadas
- Conservar ProductCatalog 170/169 (158 alcanzables), MissionEngine, cascada UIA→OCR→visión, planner+veto, skills cerradas al catálogo. Cero trasplantes.
- 67/31/16/158 son linaje; no se encoge el catálogo vivo. Microagentes rechazados (segundo ejecutor).
- Qwen-VL: rechazo medido R-023; no se silencia. Cámara/Field UI → 09.5.8.
- Steam/Spotify adapters siguen; retirarlos es 09.5.9/10, no un segundo provider ahora.
- Catálogo, providers y MissionEngine vivos: no se tocaron.

## Archivos tocados
- `artifacts/goal095/synthesis/09.5.7_tools_skills_misiones.v1.json`
- `artifacts/goal095/ledger/synthesis-09.5.7.json`
- `documentacion/herencia/09_5_7_SINTESIS_TOOLS.md`
- `documentacion/herencia/09_5_COBERTURA.md`
- `scripts/goal095_0957_synthesis.py` + `tests/test_goal095_0957_synthesis.py`
- `artifacts/goal095/campaigns/evidence_assets.json` y `ledger/evidence_assets-132-*.json` `next_prompt` → 09.5.8

## Archivos relevantes aun sin tocar
- `documentacion/sprints/09.5.8_RUNTIME_UI_RECURSOS.md` — siguiente prompt humano

## Hipotesis
Confirmadas: recinto 25/25, 477/477, 132/132 pending=0. 18/18 capacidades. R6 6/6 22/22 y Goal 05 82 observadas siguen vigentes.
Descartadas: «traer microagentes/16 tools/adapters por app cierra cobertura» — segundo camino o invariante roto. «Falta relanzar 09.5.2–09.5.6».

## Comandos ejecutados y resultado
- `py -3.12 -m pytest tests/test_goal095_0957_synthesis.py tests/test_goal095_0956_synthesis.py tests/test_goal095_0955_synthesis.py -q` → 12 passed, 0 skip, 0 failed
- `py -3.12 scripts/_goal095_validate_docs_campaign.py` → 25/25 pending=0 claimed=0
- `py -3.12 scripts/_goal095_validate_code_campaign.py` → 477/477 pending=0 claimed=0
- `py -3.12 scripts/_goal095_validate_evidence_campaign.py` → pending=0 claimed=0 complete=132 relaunch_09_5_4=0 next_human=09.5.8 errors=[]
- No ejecutado: `.\scripts\test_source_quality.ps1 -Mode Full` — no es cierre de esta síntesis

## Problemas pendientes
Ninguno de 09.5.7. Siguiente humano: 09.5.8.

## Siguiente accion recomendada
Pegar `documentacion/sprints/09.5.8_RUNTIME_UI_RECURSOS.md` (sesión nueva, /goal). No relanzar 09.5.2–09.5.7.
