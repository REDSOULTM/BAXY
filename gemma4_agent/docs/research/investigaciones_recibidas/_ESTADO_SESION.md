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

## LAS 8 INVESTIGACIONES — TODAS APLICADAS (2026-05-23)
Cada una verificada contra código real + medida bajo vram4 + commit bilingüe.

1. **tool-calling** (commit previo): sampling greedy en turno de acción
   (-15% latencia). Prefill/few-shot DESCARTADO (no había problema medible).
2. **memoria/grounding** (ca9dd9f): resolver contactos con fuzzy (Jaro-Winkler,
   universal) + fonético (metaphone) + flag ambiguous → pregunta en vez de
   adivinar. Ataca el bug "mamá→Música" en su raíz (pre-tool-call).
3. **verificación** (345b24f): email.send → requires_confirmation (sin backstop,
   irreversible); tabla declarativa de riesgo verify_policy.py. whatsapp queda
   fluido (ya verifica por OCR/UIA). El resto de inv 3 ya estaba cubierto
   (loop_detector result-aware, replan acotado).
4. **contexto multi-turno** (efa9825): context_router.py — droppea historial en
   turnos atómicos. MULTILINGÜE (embeddings, no regex es) + fallback seguro.
   Win ~272tok/62ms por turno. HALLAZGO: cache-reuse SÍ funciona en b9090
   (#21468 no afecta).
5. **Jarvis proactivo** (commit previo): behavior_log + pattern_miner +
   suggestion_queue + handler sí/no que crea rutina. Verificado en vivo.
6. **estabilidad** (5f29fcf): vram_watchdog.py — muestrea VRAM libre, avisa antes
   del OOM zombie (#13085). No-op sin GPU NVIDIA.
7. **NLU/multi-intent** (8d8f5bc + ec48d15): command_splitter — parte "abrí X y
   bajá Y". Ahora MULTILINGÜE (conjunción multi-idioma + check acción-vs-
   sustantivo por embeddings). Medido 5 idiomas 10/10.
8. **automatización-GUI** (cba61ae): _verify_chat_header usa UIA (árbol de
   accesibilidad) PRIMERO, OCR fallback. Más rápido, sin mmproj.

### Principio del usuario aplicado retroactivamente (2026-05-23)
RED: "nada de regex es-only, la app la usa cualquier hablante." → router (inv 4)
y splitter (inv 7) migrados a embeddings multilingües + fallback seguro. Ver
memoria feedback_no_monolingual_regex.

### Sesión 2026-05-24 — auditoría Carter + computer-use (lo nuevo)
- Auditoría PROFUNDA de Carter OS AI (v1-v5, MISMO stack Gemma4/llama.cpp que
  nosotros; cita nuestro harness como ground-truth). En docs/auditoria_carter_os/.
  Resultado: casi todo lo bueno YA lo tenemos o lo iteramos más. Portado lo que
  valía: no_progress (loop), anti-unverified-claim, normalize_tool_name.
- REGLA NUEVA en CLAUDE.md (RED lo vetó): el LLM responde, NADA de respuestas
  enlatadas/hardcoded ni short-circuits canned. Ver feedback_no_canned_replies.
- Audio DUCKING reconstruido (voz: baja volumen al escuchar; no existía, vivía en
  PyQt viejo). Self-hearing (TTS no auto-dispara wake) YA existía.
- Layout de prompt cache-friendly: tool-rules al FINAL (medido: prefijo común
  28%→75%, ~957 tok menos en cambio de dominio de tools). Gate GEMMA4_PROMPT_LAYOUT_V2.
- COMPUTER-USE (el grande): RED quiere controlar el PC como humano. Investigado+
  triangulado, Fase 0 (eval-set GUI) HECHA y MEDIDA. **Ver memoria
  project_computer_use_roadmap_2026_05_24 + docs/research/agent_arquitectura/
  computer_use_sintesis_decisional_2026_05_24.md.** PRÓXIMO = Fase 1 verify_post_action.

### Pendiente menor — RESUELTO (2026-05-25)
- inv 2 capas profundas: **salience + eviction por importancia HECHO** (bc23d0f):
  el cap ya no borra un hecho importante viejo por basura reciente; recall sube
  salience. NO se trajo sqlite-vec/EmbeddingGemma (MiniLM-retrieval ya cubre el
  caso; menos deps/VRAM, alineado con LoCoMo "simple bien hecho > sofisticado").
- Jarvis yes/no: **handshake MULTILINGÜE HECHO** (6aa3849): oferta + respuestas +
  describe en es/en/pt/fr/de/it; responde en el idioma de la oferta.
- Los 2 TestSpotifyAutoPlay siguen fallando por trabajo sin commitear de RED
  (stash + planner.py M) — NO es de las investigaciones.

## GOTCHAS clave
- agent.py = 3249 líneas (orquestación concentrada). Loop max_agent_turns=8.
- Latencia real = thinking (p90 268tok/4.3s), no prefill (888ms). reasoning ON =
  tool-call 6/6, OFF = 2/6 (acoplamiento a romper).
- Cambios pre-existentes sin commitear de RED en domain_tools.py/planner.py — NO
  tocar. test_chaining_nudge.py / TestSpotifyAutoPlay pueden fallar por eso.
- pytest -k amplio crashea en Windows (torch/onnx) → correr por archivo.
