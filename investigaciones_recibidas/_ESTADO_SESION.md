# Estado de la sesión — resumen para retomar (2026-05-23)

Resumen para el agente (Claude) por si la conversación se comprime (compact).
Léeme + MEMORY.md + CLAUDE.md al retomar.

## Quién y reglas
RED. Branch **PortandoLoMejor**, NO push, NO cambiar de rama, NO borrar tests.
Un cambio = un commit bilingüe + `Co-Authored-By: Claude Opus 4.7`. OSS/local,
voz, **vram4 = Gemma 4 E4B-it Q4_K_M default** (GEMMA4_DEFAULT_PROFILE). Regla de
oro: investigar/medir antes de tocar; los informes fallan en detalles del entorno
→ verificar siempre + opt-in si dudoso. NO instalar torchcodec/torchvision/optimum
(rompen/ensucian el router). Medir vía scripts/smoke_e2e.py (no curl al :8080).

## Lo ARREGLADO esta sesión (en prod, con tests, commiteado)
1. Tilde WhatsApp (gui_type clipboard-paste UTF-8).
2. Router info-vs-acción + health-check ruidoso (intent_router.is_question_lexical,
   router_health). "¿qué es X?" ya no crea documento.
3. win_focus.py (foco+maximize robusto). window(action=focus) lo usa.
4. filesystem.search ignoraba `path` → ahora resuelve Downloads/Descargas/etc al home.
5. chaining-nudge + auto-repair de path + "preguntar cuál abrir" (Codex; el 4B no
   encadena search→open fiable, RED eligió preguntar no auto-ejecutar).
6. Two-track TTS filler (voice_runner: "Voy con eso" mientras piensa).
7. GPU detection fallback a nvidia-smi (arregló "gpu unknown" + budget).
8. torchvision desinstalado (warning cosmético, versión incompatible con torch).
9. WhatsApp: _verify_chat_header OCR antes de escribir (bug "mensaje a mamá fue a
   grupo Música"). Aborta si no confirma el chat.
10. vram4 como default robusto (GEMMA4_DEFAULT_PROFILE).

## MEDIDO y DESCARTADO (opt-in, default OFF — NO reactivar sin re-medir)
- Core-set estable de tools (GEMMA4_STABLE_TOOL_PREFIX): E2E 2x peor.
- FR-CoT thinking (GEMMA4_FRCOT): mejora apps/audio, ROMPE media (Gemma emite el
  formato como texto).

## LO QUE SIGUE (el trabajo grande)
8 prompts de investigación escritos (PROMPT_RESEARCH_[1-8]_*.md, índice en
PROMPT_RESEARCH_INDEX.md). RED los manda a Claude y deja las respuestas en
**investigaciones_recibidas/N_tema.md** (ver README de esa carpeta). Cuando RED
diga "aplicá la N": leer investigación + código real → verificar contra build →
gate → cambio mínimo → medir smoke bajo vram4 → commit/opt-in/revertir.

Temas: 1 tool-calling, 2 memoria/entity-grounding, 3 verificación+recovery,
4 contexto-multiturno, 5 Jarvis-proactivo, 6 estabilidad/no-crash, 7 NLU/multi-
intent, 8 automatización-GUI. Orden de impacto sugerido: 1→5→7→6→2→3→8→4.

## GOTCHAS clave
- agent.py = 3249 líneas (orquestación concentrada). Loop max_agent_turns=8.
- Latencia real = thinking (p90 268tok/4.3s), no prefill (888ms). reasoning ON =
  tool-call 6/6, OFF = 2/6 (acoplamiento a romper).
- Cambios pre-existentes sin commitear de RED en domain_tools.py/planner.py — NO
  tocar. test_chaining_nudge.py / TestSpotifyAutoPlay pueden fallar por eso.
- pytest -k amplio crashea en Windows (torch/onnx) → correr por archivo.
