# 06 — VRAM y Estabilidad

Cómo el agente entra y se mantiene estable en hardware modesto (target: 4 GB de
VRAM con el LLM + visión residentes).

**Estado vigente:**
- **Perfil único `vram4`:** Gemma 4 **E2B-FT** Q4_K_M (~3.36 GB) + mmproj
  (visión residente) + KV, ctx **12288**. E4B no entra en 4 GB.
- **Crash CUDA #22527 resuelto:** con **flash-attn OFF** (default) los prompts
  largos ya no crashean (medido estable). Ver `crash_cuda_22527/`.
- **Fallback CPU** (perfil `cpu`, `-ngl 0`, visión OFF) gated, para devolverle
  la GPU a un juego o correr sin gráfica dedicada.

`INFORME_ARQUITECTURA_6GB.md` explora las opciones de arquitectura (incluye
comparaciones E4B/E2B de 6 GB, analíticas). Para el estado ítem-por-ítem ver
[`../_backlog/BACKLOG_MAESTRO.md`](../_backlog/BACKLOG_MAESTRO.md).
