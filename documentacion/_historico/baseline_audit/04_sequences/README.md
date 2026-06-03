# Fase 4 — Diagramas de secuencia

> Flujos críticos del agente, derivados del código real (no de
> documentación). Cada diagrama referencia `archivo.py:NNN` para que pueda
> verificarse contra el fuente.

## Índice

| # | Doc | Flujo | Disparador |
|--:|---|---|---|
| 1 | [boot.md](boot.md) | Cold start completo del agente | `AgentRunner.submit` primera vez **o** `python -m gemma4_agent.ui` |
| 2 | [voice_turn.md](voice_turn.md) | Voz → STT → Agent → Tools → TTS | usuario habla con wake activo |
| 3 | [wake_activation.md](wake_activation.md) | Wake-word "gemma" → READY-to-listen | usuario dice "gemma" o "hey gemma" |
| 4 | [slot_filling.md](slot_filling.md) | LLM pregunta param faltante → user responde → continúa | tool requiere arg que falta |
| 5 | [router_fallback.md](router_fallback.md) | Subset vacío → semantic_router fallback → continuation-inherit | regex keyword no matchea |
| 6 | [shutdown.md](shutdown.md) | Cleanup de procesos, threads y handles | Ctrl+C / cerrar ventana / process exit |

## Hallazgos a `_findings_seed.md`

Los diagramas exponen 4 patrones que valen documentar como findings:

1. **Cold boot tiene 7 fases serializadas y 1 paralela.** El "ready" honesto requiere health-check (port) + warmup (1 token chat) + opcional semantic_router pre-load en BG. Si cualquiera falla, el bus emite `state=standby` y la UI gates el input. Bien diseñado pero costoso (30-90s en el peor caso, dominado por `load_tensors` del llama-server).
2. **Voice turn dispara hasta 11 threads en paralelo en producción** (audio capture, audio pump, wake, STT worker, TTS worker, audio ducker COM worker, agent_runner thread, NLI worker, grounding async worker, experience write, telemetry sync listener). Complejidad real.
3. **`run_content` corre 2 LLM extra opcionales** (`_extract_facts` + `_summarize_history_block`) además del loop principal, ambos con cooldowns separados. Si están ON con cooldowns cortos, queman el latency budget.
4. **No hay shutdown explícito coordinado.** Cada subsistema (`VoiceController`, `AgentRunner`, `LlamaServerManager`, `ProfileWatcher`, `LogRecorder`) tiene su `stop()/uninstall()` pero **ningún módulo orquesta el orden**. Si el process exit es abrupto, daemon threads mueren sin flush.
