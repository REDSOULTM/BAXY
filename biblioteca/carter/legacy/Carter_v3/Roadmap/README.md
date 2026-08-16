# Carter v3 - Roadmap de prompts

Esta carpeta deja un prompt por archivo para ir ejecutando el roadmap de
Carter v3. Tiene dos campanas:

## Campana 1 — Import selectivo v2 -> v3 (CERRADA)

Orden:

1. `01_round_1_1_doc_sync.md`
2. `02_round_2_process_probe_window.md`
3. `03_round_3_uia_determinista.md`
4. `04_round_4_filesystem_universal.md`
5. `05_round_5_terminal_seguro.md`
6. `06_round_6_browser_minimo_util.md`
7. `07_round_7_consolidacion_final.md`

Veredicto: `V2_TO_V3_IMPORT_CAMPAIGN_CLOSED_SELECTIVE_SUCCESS`

## Campana 2 — Fixes de calidad post-import (PENDIENTE)

Orden recomendado (8b primero — es bloqueante):

8b. `08b_round_8b_app_open_fake_success.md`  ← HACER PRIMERO (bug critico R4)
8.  `08_round_8_c14_typo_targeting.md`
9.  `09_round_9_refactor_dispatch_src.md`
10. `10_round_10_tool_protocol_robusto.md`
11. `11_round_11_user_approved_provenance.md`
12. `12_round_12_consolidacion_post_fixes.md`

Dependencias entre rondas:
- Round 8b es BLOQUEANTE: viola R4 (fake success). Hacer antes que cualquier otra.
- Round 8 es independiente de 8b.
- Round 9 es independiente: no depende de 8 ni 8b.
- Round 10 puede hacerse despues de 9 (el refactor ayuda a diagnosticar).
- Round 11 es independiente de 8, 8b, 9 y 10.
- Round 12 va siempre al final: consolida lo que hicieron 8b, 8-11.

## Resumen de modelos recomendados

Campana 1:
- Round 1.1 -> `GPT-5.4-Mini`
- Round 2   -> `GPT-5.2-Codex`
- Round 3   -> `Claude Opus 4.7`
- Round 4   -> `GPT-5.2-Codex`
- Round 5   -> `GPT-5.1-Codex-Max`
- Round 6   -> `Claude Opus 4.7`
- Round 7   -> `GPT-5.4`

Campana 2:
- Round 8b  -> `Claude Opus 4.7`  (PRIMERO)
- Round 8   -> `Claude Opus 4.7`
- Round 9   -> `GPT-5.2-Codex`
- Round 10  -> `Claude Opus 4.7`
- Round 11  -> `GPT-5.4`
- Round 12  -> `GPT-5.4`

## Problemas que resuelve la Campana 2

| Round | Prioridad | Problema | Residual / Regla violada |
|---|---|---|---|
| 8b | CRITICA | app_open retorna complete aunque Windows muestre error de archivo no encontrado. Dos fallos: cmd /c start silencia el error; verifier confirma procesos preexistentes como evidencia del launch actual. | R4 (fake success) |
| 8  | Alta | C14.01-04 typo/targeting: 4 fails estables del baseline desde Round 4 | R-V3-C1 |
| 9  | Media | dispatch.py en 741 lineas, src/carter_v3 en 6239 lineas | R-V3-C3 |
| 10 | Media | Tool protocol fragil con Ollama; Carter usa fallback estructural en vez de tool-calling real | R-P4-05, R-P3-33 |
| 11 | Media | user_approved auto-generado por LLM destrava gates HIGH-risk sin aprobacion humana real | R-V3-T2 |
| 12 | —     | Consolidacion y veredicto canonico de la campana | — |
