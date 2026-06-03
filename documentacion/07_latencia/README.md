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

`research/` contiene la investigación de prefill/cache y de reducción del
thinking. Para el estado ítem-por-ítem ver
[`../_backlog/BACKLOG_MAESTRO.md`](../_backlog/BACKLOG_MAESTRO.md).
