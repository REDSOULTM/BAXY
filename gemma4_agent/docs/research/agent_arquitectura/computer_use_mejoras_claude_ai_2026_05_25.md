# Computer-use GUI — investigación de mejoras (claude.ai, 2026-05-25)

> Respuesta de claude.ai al prompt que mandamos tras completar el roadmap
> computer-use. VERIFICADA parcialmente contra el código real (ver "Verificación
> contra el código" al final). Aplicar con gate + medición, opt-in si dudoso,
> respetando las restricciones de producto (CLAUDE.md).

## TL;DR del informe
Tres palancas de mejor ROI (impacto alto / riesgo bajo / caben en 6GB + Alexa-tier):
1. **R1** `--force-renderer-accessibility=basic` en Chromium/Edge/Electron →
   recupera UIA dentro de WebContents, evita caer a OCR.
2. **R2** Tesseract → RapidOCR/PaddleOCR PP-OCRv5 mobile (ONNX CPU) → mejor en
   texto blanco-sobre-color (Discord/Spotify).
3. **R3** frame-diff dHash → verificación PUSH con `SetWinEventHook` + UIA
   `AutomationPropertyChangedEventHandler` (sin polling, sin VLM).

Valida nuestras decisiones medidas: speculative rechazado (UFO2 logra −51.5% pero
con GPT-4o/o1; con 4B local nuestro 0/12 manda) y vision-no-clica-por-coords
(ScreenSpot-Pro: GPT-4o 0.9%, UI-TARS-7B 35.7%, UI-TARS-1.5 61.6% — clicar por
coords de un VLM 4B local sería peor que random).

## ESTADO DE APLICACIÓN (2026-05-25)
Aplicadas y verificadas esta sesión (commits): **R4** (4d141d8), **R7** (a31a73f),
**R1+R6** (5e81be1), **R8 activity-budget** (135c0db), + fix latente crítico
**SafeInt UIA** (a31a73f, los elementos offscreen con bounds Infinity crasheaban
todo el find por overflow int) + nudge click-intent en la descripción de uia.
Pendientes (Fase 2-3 del informe, requieren más esfuerzo/medición): R2 (OCR A/B),
R3 (WinEvents push), R5 (UIA cache), R8-anchor-binding.

## Recomendaciones (resumen)
| # | Qué | Impacto | Esfuerzo | Estado |
|---|---|---|---|---|
| R1 | `--force-renderer-accessibility` + `ELECTRON_ENABLE_ACCESSIBILITY=1` | Alto | Bajo | **HECHO** (5e81be1): app.open lanza Chromium/Electron con AX; resuelve exe de .lnk/shell via App Paths |
| R2 | OCR → RapidOCR PP-OCRv5 ONNX | Alto | Medio | pendiente (rapidocr+paddleocr ya instalados; falta A/B vs Tesseract) |
| R3 | WinEvents push + UIA event handlers | Alto | Medio | pendiente (Fase 2) |
| R4 | transient-launcher: descartar updater (Squirrel) | Medio | Bajo | **HECHO** (4d141d8): Discord 3 false-pass→0 |
| R5 | UIA CacheRequest + RuntimeId rebind + paralelizar | Medio | Medio | pendiente (Fase 2) |
| R6 | password fields web | Alto seg | Bajo | **HECHO** (5e81be1): con R1 activo, UIA IsPassword se expone en web → el password-guard de Fase 5 bloquea el type. Verificado en form web real. |
| R7 | matcher cross-lingual por embeddings (label↔UI) | Medio | Bajo | **HECHO** (a31a73f): reusa el MiniLM del router, umbral 0.75+margen 0.10, abstiene si dudoso. five↔Cinco=0.992 |
| R8 | activity-budget (+ anchor-binding pendiente) | Alto seg | Medio | **HECHO parcial** (135c0db): cap N acciones/turno. anchor-binding = follow-up |
| R9 | NO migrar a VLM coordinate grounding | — | — | ya es nuestra decisión (no se toca) |

## Fuentes citadas (links del informe)
- Agent-S2 Mixture-of-Grounding: arXiv:2504.00906
- UFO2 (speculative −51.5%, hybrid UIA+OmniParser): arXiv:2504.14603
- ScreenSpot-Pro (grounding VLM <50%): arXiv:2504.07981
- Pop-up injection (ASR 86%): ACL 2025 DOI 10.18653/v1/2025.acl-long.411
- VPI-Bench: arXiv:2506.02456
- LaBSE: "Language-agnostic BERT Sentence Embedding"
- Chromium accessibility docs: chromium.org/developers/accessibility/windows-accessibility
- Microsoft Learn: winevents-overview, CacheRequest (use-caching-in-ui-automation)

## Verificación contra el código (RED + agente, 2026-05-25)
- **R7**: `paraphrase-multilingual-MiniLM-L12-v2` YA está cargado (context_router/
  command_splitter/abstain_head). El matcher cross-lingual NO requiere instalar
  nada — solo reusar el encoder en click_button. Costo ~casi cero. → SUBE prioridad.
- **R2**: `rapidocr_onnxruntime` y `paddleocr` YA instalados (verificado por
  import). Migrar no baja deps pesadas nuevas. → viable ya.
- **R1**: tenemos `--remote-debugging-port=9222` + CDP attach (streaming web,
  domain_tools.py:6506, ops_tools.py:1014), NO la flag `--force-renderer-acc`.
  R1 es complementario (la flag enciende UIA del renderer; el CDP da el AX tree
  por WebSocket — podríamos reusar la infra CDP existente para R6 también).
- **R4**: `verify_app_opened` (tools.py:~5135) matchea por proceso/título laxo;
  NO usa WaitForInputIdle ni filtra Update.exe. El fix de Squirrel es real y
  ataca directamente los 3 false-PASS de Discord. → mejor ROI inmediato medible.
- **R3/R5**: hoy verificación es pull (dHash). WinEvents/CacheRequest son trabajo
  nuevo de medio esfuerzo.

## Caveats que el informe mismo marca (importantes)
- run7 (110 misiones) es chico: 92.7% ± ~5pp (Wilson 95%). KPIs piden eval ≥300/tier.
- Cifras OCR (PaddleOCR vs Tesseract) son de ICDAR2015 (scene text), NO UI de
  Discord/Spotify → la mejora +5-10pp Tier-3 es HIPÓTESIS, validar con corpus propio.
- No hay evidencia pública específica de la flag AX en el binario actual de
  Discord (modifica Electron) → verificar empíricamente.
- LaBSE en GPU (~470MB) NO cabe con LLM+vision en 6GB → mantener en CPU/ONNX/INT8.
