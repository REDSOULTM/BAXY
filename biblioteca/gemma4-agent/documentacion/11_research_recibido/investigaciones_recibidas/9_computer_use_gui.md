# Investigación recibida (claude.ai) — Computer-use GUI con Gemma 4 E4B en vram4

> Respuesta a `PROMPT_RESEARCH_computer_use_gui_control.md`. Pegada tal cual la
> entregó claude.ai (2026-05-24). Contrastar con
> `gemma4_agent/docs/research/agent_arquitectura/computer_use_investigacion_propia_2026_05_24.md`
> (investigación propia) y con el código real antes de aplicar.

---

[Contenido completo de la respuesta de claude.ai — ver el plan técnico de 8
fases: arquitectura macros deterministas observe→act→verify, verify_post_action
con 3 señales (UIA delta + dHash ROI + WinEvent hook), cascada UIA→OCR→visión,
tabla de recovery, seguridad R0-R5 + secret handoff + user-activity monitor,
presupuesto de latencia, checkpoint mínimo, roadmap por fases con gates.

Hallazgos clave citados con fuentes:
- Gemma 4 E4B (no 3n), mmproj oficial ggml-org, audio NO cableado en llama-server.
- UFO² (arXiv 2504.14603): UIA+visión híbrido, speculative multi-action -51.5%.
- Techo real: UI-TARS-1.5 24.6% OSWorld, UFO²+o1 30.5% WAA; 4B local muy por debajo.
- Agent-S2 Mixture of Grounding (arXiv 2504.00906).
- verify_post_action: dHash 8x8 Hamming>=6 sobre ROI, UIA cacheRequest, SetWinEventHook.
- IsPasswordPropertyId (30019) para detectar campos de contraseña.
- --force-renderer-accessibility=complete para CEF.
- Caveats: medir tok/s propios, mmproj 992MB BF16 vs 946 reportado, bug #21402.]

(El texto íntegro está en el historial de la conversación / chat de RED. Este
archivo es el marcador en el flujo investigaciones_recibidas; la síntesis
decisional vive en docs/research/agent_arquitectura/computer_use_sintesis_*.md)
