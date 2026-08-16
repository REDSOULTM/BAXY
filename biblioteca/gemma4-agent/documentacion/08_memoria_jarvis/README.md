# 08 — Memoria / Jarvis

La capa "viva" del asistente: memoria de largo plazo y personalización por
gustos (al estilo Jarvis), más el análisis de skills/subagents.

**Estado vigente:**
- **Observador de ambiente** (música SMTC, app en foco, ritmo) → **perfil de
  gustos determinista** inyectado al prompt. Privacidad: inspect/forget por
  embeddings.
- **Reflexión de gustos por el LLM local** (`taste_reflection`), gated default-OFF,
  en background (no per-turn), con grounding-guard (la evidencia debe citar una
  observación real).
- **Skills/subagents:** el 4B (E2B-FT) no hace meta-pasos; los skills se
  auto-inyectan en vez de exponer `skill_load`/`subagent` como ruido.

`research/` contiene la investigación de memoria y de la capa Jarvis. Para el
estado ítem-por-ítem ver
[`../_backlog/BACKLOG_MAESTRO.md`](../_backlog/BACKLOG_MAESTRO.md).
