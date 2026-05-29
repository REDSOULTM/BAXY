# Prompt para continuar — pegar en terminal de Claude Code

Leé primero `Investigaciones/RESUMEN_SESION_2026_05_28_v21_v22.md` de punta a punta — ahí está todo el contexto de la sesión anterior (Opus 4.7) y por qué v21 está en working tree sin commitear. Entendelo antes de tocar nada.

Tu trabajo: terminar el sprint v22 que quedó a mitad de camino. El binario nuevo `b9384` ya está descargado y extraído en `%TEMP%\llama-b9384-extract\` listo para instalar. Mi v21 (recovery simple del 27-may + Plan A flags + MAX_TOOLS=5) está aplicada en disco y da 6/6 OK con 0 crashes en uso normal, pero limita al agent a 5 tools por turn. El objetivo es subir ese cap sin que el server crashee.

Plan, en orden, parando en el primer paso que sea suficiente (gate: ≥30 turns variados con prompts ≥13k tokens, 0 CUDA errors en `gemma4_agent/logs/llama-server.err.log`):

1. **Backup** de `tools/llama-cuda/` completo a `tools/llama-cuda.b9260-backup/` (cp recursivo). Sin esto no toques nada — el binario actual funciona y el rollback debe ser instantáneo.

2. **Instalar b9384** copiando todo el contenido de `%TEMP%\llama-b9384-extract\*` sobre `tools/llama-cuda/`. Verificá con `tools\llama-cuda\llama-server.exe --version` que diga 9384.

3. **Smoke test baseline con MAX_TOOLS=5** (mismas envs que v21): `python scripts/_kill_server_ports.py` + `python scripts/_boot_server_for_eval.py` + `python scripts/_revert_live_probe.py`. Gate: 6/6 OK como con b9260. Si falla acá, rollback y reportá qué cambió.

4. **Probar MAX_TOOLS=8** seteando `$env:GEMMA4_MAX_SELECTED_TOOLS=8` y `$env:GEMMA4_HARD_TOOL_CAP=8`, reiniciá el server, corré el live probe + escribí un stress de 30+ prompts variados (mezclá conversacionales, info, tool real, deícticos cortos, mensajes largos para forzar prompts ≥14k tokens). Medí: tasa de crash CUDA en `llama-server.err.log` durante la corrida (no histórico) + latencia por turn.

5. **Si MAX=8 con b9384 da 0 crashes:** subí también el `MAX_SELECTED_TOOLS` literal en `gemma4_agent/routing/planner.py:22` y el `_hard_cap` default en `gemma4_agent/agent_core/agent.py` (~línea 1671). Actualizá tests si rompen. Documentá la victoria en `Investigaciones/RESULTADO_FINAL_V22.md`. Pará acá.

6. **Si MAX=8 con b9384 crashea:** template Jinja compacto. Creá `gemma4_agent/data/gemma4-compact.jinja` que serialice los tools en formato 2-3× más corto que el JSON schema completo (firma compacta: nombre + descripción truncada + params required en una línea). Agregá `--chat-template-file` al `_build_server_cmd` en `gemma4_agent/infra/llama_server.py`. Validá que el log del server siga diciendo `Chat format: peg-gemma4` (si cae a "Generic", el parser está roto y consume MÁS tokens). Re-medí con `scripts/_measure_agent_prompt_live.py` que el prompt con 8 tools quede ≤10k. Re-corré el stress.

7. **Si template compact tampoco alcanza:** two-phase routing. El agent ya tiene router semántico en `gemma4_agent/routing/planner.py`. Extendelo a una primera llamada cheapa al LLM que reciba un mini-prompt sin tools + un único tool `route(query)→[tool_names]` para clasificar intent; segunda llamada con el subset ≤15 que devolvió. Esto mantiene catálogo de 66+ tools disponible pero el LLM nunca ve más de 15 por turn. Costo ~4-6h, +1-2s latencia por turn pero ningún prompt cruza umbral. Fuente verificada: NousResearch hermes-agent #6839.

8. **Si nada de lo anterior funciona:** detenete y reportá honesto. NO arranques el Sprint #1 (parchar binario llama.cpp) sin que el usuario lo apruebe — está documentado en `documentacion/SPRINT_llama_cpp_recompile_swa_patch.md` para esa eventualidad pero requiere mantener fork local.

Reglas firmes durante todo el trabajo:

- **No commitees nada hasta validar.** El working tree tiene cambios v21 sin commit + cualquier cosa que agregués vos. Cuando hayas decidido qué quedó funcionando, hacé UN commit limpio con mensaje claro y referenciá esta sesión.
- **Antes de cualquier cambio destructivo (cp sobre tools/llama-cuda, edit de planner.py, etc.) confirmá con el usuario.** El backup del paso 1 es la excepción autorizada por mí.
- **Medí, no celebres.** Cada paso requiere su gate medido (live probe + grep CUDA en err.log + count de tokens del prompt). "Pasó el smoke" no es suficiente; el bug es a tamaño de prompt grande, no a 6 turns conversacionales.
- **El revert v21 que hizo Opus 4.7 es la base.** El recovery simple del 27-may + cap=5 + Plan A flags se mantiene como fallback. Si algo de lo que agregás v22 regresa la latencia de recovery a 30s+, descartalo — el usuario lo va a notar y va a estar peor que v21.
- **No corras `gui.{type,click,keypress}` ni `pytest` sobre tests GUI** — eso cierra VS Code donde corre Claude Code. Está documentado en CLAUDE.md. Verificá EN VIVO con `agent.run_content` vía `scripts/_revert_live_probe.py` o similar.
- **Lo físico irreversible (envío real de WhatsApp, llamada al banco) se delega al usuario, no se simula.** El resto lo probás vos.

Cuando termines, escribí `Investigaciones/RESULTADO_FINAL_V22.md` con: qué quedó instalado, qué `MAX_TOOLS` logramos, latencias medidas (turn conversacional / turn con tool / recovery cuando ocurre), conteo de crashes CUDA en la corrida final de validación, y qué próximos pasos quedan (si los hay). Actualizá `MEMORY.md` con el aprendizaje no-obvio de esta iteración.

Tenés autorización para instalar deps OSS faltantes sin volver a preguntar (ninja, etc.). La guardia de compra sigue para software pago.

Arrancá con `git status` + `Get-Item tools\llama-cuda\llama-server.exe | Select-Object LastWriteTime` para confirmar el estado, después leé el resumen, después actuá.
