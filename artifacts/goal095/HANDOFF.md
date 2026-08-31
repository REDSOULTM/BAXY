# Handoff — 09.5.6 voz/audio/presencia — 2026-08-31

## Objetivo
Combinar la mejor evidencia del linaje sobre escuchar, transcribir, despertar,
interrumpir, hablar y permanecer disponible, comparándola con el cierre del Goal 09.

## Estado
Hecho: síntesis 09.5.6 cerrada. Campañas 09.5.2–09.5.4 siguen pending=0 claimed=0.
En curso: nada de 09.5.6.
Sin empezar: `09.5.7_TOOLS_SKILLS_MISIONES.md`.

## Decisiones tomadas
- Conservar Parakeet int8, `baxy.onnx` umbral 0,5, Piper `es_MX-claude-high`, Silero, AEC/ducking, barge-in, always-on por costura. Cero trasplantes.
- FAR 2,50/h (upper 5,26/h) vs 0,1/h se registra; no se retoca el umbral ni `calibration.approved`.
- Qwen-ASR: rechazo medido (recall 0,889, p95 5,61 s, RSS 2,71 GiB). Gemma native audio: API no lista. No se silencian.
- pt/fr/de/it y wake 13 lenguas no crean trabajo. Nombres de apps en inglés = spanglish.
- Pesos/manifiestos vivos: no se tocaron. Goal 09 no se reabre.

## Archivos tocados
- `artifacts/goal095/synthesis/09.5.6_voz_audio_presencia.v1.json`
- `artifacts/goal095/ledger/synthesis-09.5.6.json`
- `documentacion/herencia/09_5_6_SINTESIS_VOZ.md`
- `documentacion/herencia/09_5_COBERTURA.md`
- `scripts/goal095_0956_synthesis.py` + `tests/test_goal095_0956_synthesis.py`
- `artifacts/goal095/campaigns/evidence_assets.json` y `ledger/evidence_assets-132-*.json` `next_prompt` → 09.5.7

## Archivos relevantes aun sin tocar
- `documentacion/sprints/09.5.7_TOOLS_SKILLS_MISIONES.md` — siguiente prompt humano

## Hipotesis
Confirmadas: recinto 25/25, 477/477, 132/132 pending=0. Parakeet/Piper/baxy.onnx vigentes. FAR hueco real.
Descartadas: «HyperSpotter/Qwen-ASR/Gemma-audio cierran Goal 09» — métricas en contra o no comparable. «Falta relanzar 09.5.2–09.5.5».

## Comandos ejecutados y resultado
- `py -3.12 -m pytest tests/test_goal095_0956_synthesis.py tests/test_goal095_0955_synthesis.py tests/test_goal095_evidence_ledger.py tests/test_goal095_docs_ledger.py tests/test_goal095_code_ledger.py -q` → 36 passed, 0 skip, 0 failed
- `py -3.12 scripts/_goal095_validate_evidence_campaign.py` → pending=0 claimed=0 complete=132 relaunch_09_5_4=0 next_human=09.5.7
- `py -3.12 scripts/_goal095_validate_docs_campaign.py` → 25/25 pending=0
- `py -3.12 scripts/_goal095_validate_code_campaign.py` → 477/477 pending=0
- No ejecutado: `.\scripts\test_source_quality.ps1 -Mode Full` — no es cierre de esta síntesis

## Problemas pendientes
Ninguno de 09.5.6. Siguiente humano: 09.5.7.

## Siguiente accion recomendada
Pegar `documentacion/sprints/09.5.7_TOOLS_SKILLS_MISIONES.md` (sesión nueva, /goal). No relanzar 09.5.2–09.5.6.
