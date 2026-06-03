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

`research/` contiene la investigación de GUI/grounding/router-chain. Para el
estado ítem-por-ítem ver
[`../_backlog/BACKLOG_MAESTRO.md`](../_backlog/BACKLOG_MAESTRO.md).
