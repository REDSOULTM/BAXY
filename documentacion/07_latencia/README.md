# 07 — Latencia

Optimización de la latencia por turno de voz (presupuesto tier-Alexa: 4–5 s
tope; 8 s es UX catastrófica).

**Estado vigente:**
- **Palanca principal:** cache-hit del summary/prefill pass (mantener
  `enable_thinking` consistente entre pasadas para no romper el prefix-cache).
  Acción ~2.2 s tras el fix.
- **Cap del forced-retry decode** para no ramblear cuando el primer pase leakea.
- **flash-attn OFF** por estabilidad (ver `06_vram_estabilidad/`); costo prefill
  mitigado. ctx = 12288.
- **Visión (mmproj) RESIDENTE por default (2026-06-09):** `GEMMA4_VISION_ALWAYS=1`.
  Medido que el mmproj cargado YA NO apaga el cache de texto en builds nuevos de
  llama.cpp (#21133): una imagen no paga la carga on-demand (~2-5 s) y el texto
  sigue rápido. Antes era "lazy" (router-mode). Detalle en
  [`SPRINT_prefill_cache_hit.md`](SPRINT_prefill_cache_hit.md).

`research/` contiene la investigación de prefill/cache y de reducción del
thinking. Para el estado ítem-por-ítem ver
[`../_backlog/BACKLOG_MAESTRO.md`](../_backlog/BACKLOG_MAESTRO.md).
