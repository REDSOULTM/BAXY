# 04 — Computer Use

Control del SO por voz: el agente actúa en cualquier app (abrir, escribir,
clickear, instalar, navegar), pensado como capa de accesibilidad.

**Estado vigente:**
- **Cascada de grounding:** UIA → OCR → visión (sana; el gap medido fue de
  ROUTING, no de grounding). Grounding por visión local NO es viable en el
  target 4 GB (medido).
- **Perfil único `vram4`** (E2B-FT, ctx 12288) + **modos de accesibilidad**
  (`normal`/`no_vidente`/`movilidad`), activables por voz vía embeddings.
- **Verify tri-estado** (`None` ≠ `False`) para no mentir ni doble-clickear.

**Actualizaciones recientes (2026-06-07 → 2026-06-09):**
- **Click visual robusto:** "apretá el icono de X" que se ve en pantalla ya no
  cae en un callejón (`steam(click)` enum inválido → reintento → nada). Se
  redirige el verbo de click-visual no-válido a `gui(click_text)` (OCR localiza y
  clickea) — `tools_pkg/visual_click_redirect.py`. `uia/browser(click)` válidos
  NO se secuestran.
- **describe_screen sin alucinar:** monitor `"active"` (ventana en foco, no la
  panorámica multi-monitor que el 2B alucina) + ancla OCR (Tesseract lee el texto
  real). El OCR crudo ya NO se filtra al reply (`_strip_ocr_echo` en
  `tools_pkg/vision_describe.py`).
- **Resolución de sitios ("ve a X"):** lookup real por búsqueda (no adivina TLD),
  desempate de homónimos por país del SO, **señal estructural** anti-agregador
  (sin lista hardcoded de dominios), **popularidad** (posición del buscador) y
  **validación DNS** (no abrir dominios muertos). `tools_pkg/site_resolver.py`.
- **cancel_turn espurio arreglado:** "ve a X"/"desmutea" ya no caen a session-only.

`research/` contiene la investigación de GUI/grounding/router-chain. Para el
estado ítem-por-ítem ver
[`../_backlog/BACKLOG_MAESTRO.md`](../_backlog/BACKLOG_MAESTRO.md).
