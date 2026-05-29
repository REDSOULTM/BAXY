# Sprint próximo — FR-CoT para latencia de turnos de acción

**Autor:** Opus 4.8, 2026-05-28. **Estado:** **CÓDIGO ESCRITO (dormant, flag
`GEMMA4_FRCOT` off por default) + stub-validado.** FALTA solo: **validación EN
VIVO** (no se pudo — el usuario estaba jugando; y el fallo de FR-CoT es
comportamiento no-determinista del modelo real que los stubs NO atrapan).

## Qué YA está implementado (2026-05-28, dormant)
- `agent_core/agent_prompt.py`: `FRCOT_DIRECTIVE` (plantilla scopeada al canal
  `<think>` + "el reply visible es español natural, NUNCA el formato INTENT/TOOL/
  ARGS/GO") inyectada en `_core_for_profile()` solo si `GEMMA4_FRCOT` on. Es
  constante → no rompe el prefix-cache de Camino C.
- `support/reasoning.py`: guarda ESTRUCTURAL `_FRCOT_LEAK_RE` en `sanitize_text` —
  si el modelo FILTRA el bloque `INTENT:/TOOL:/ARGS:/GO` al reply visible, lo borra.
  **Esta es la red que faltó la vez que rompió media.** Gateada por el flag.
- Stub-validado (`scripts/_verify_frcot.py`, ALL OK): gating on/off + el strip borra
  el bloque (con/sin GO), preserva el reply natural, no toca prosa normal/casual.
  67 tests de reasoning/prompt verdes con el flag OFF (sin regresión).

## Cómo VALIDAR en vivo (cuando el usuario NO juegue) — EL ÚNICO PASO QUE FALTA
```powershell
python scripts\_kill_server_ports.py
$env:GEMMA4_FLASH_ATTN="off"; python scripts\_boot_server_for_eval.py   # server (FR-CoT es client-side, no afecta el boot)
# Agente con el flag + Plan A2:
$env:GEMMA4_FRCOT="1"; $env:GEMMA4_CORE_RULES="session,system,audio,app,web,window"
python scripts\_verify_a2_quality.py   # 8 comandos de acción: media/apps/audio/gui/wifi/...
```
**Gates:** (a) tool-calling ≥ baseline (8/8), 0 regresión — sobre todo en **media**
(lo que rompió antes); (b) el reply visible NUNCA muestra `INTENT:/TOOL:/ARGS:/GO`;
(c) latencia de acción baja (thinking p90 268→~30 tok). Si media regresa, iterar la
plantilla EN VIVO (no con stubs). Si pasa todo → default-on + subir MAX_TOOLS.

---

## (Contexto original del plan, ahora ya implementado arriba)

## Por qué
Tras v22 (FA off + Plan A2), los turnos de **charla/info** están en presupuesto
(0.6–3 s) pero los de **acción** tardan 5–16 s. Diagnóstico medido:
- La multi-call YA está optimizada (summary pass post-tool = thinking-OFF + tools=
  None + 160 tok, `agent.py:1902`).
- El costo dominante es el **thinking de la llamada de DECISIÓN** (p90 268 tok,
  max 841 @ 62 tok/s ≈ 13.5 s), **necesario** en E2B (thinking OFF → 2/6 tool-calls).
- FA off encarece cada prefill ~2×, amplificando lo anterior.

## El fix (research-backed)
**FR-CoT / structured brief CoT** — reemplazar el thinking libre por una plantilla
estructurada ≤32 tok (`INTENT: / TOOL: / ARGS: / GO`). Evidencia: arXiv 2604.02155
(Qi 2026, BFCL v3): Qwen2.5-1.5B 44%→64% tool-call, alucinación 3%→0%, thinking >5×
menos. Ver `gemma4_agent/docs/research/latency/reducir_latencia_thinking_gemma4.md`
(Punto 1, plantilla concreta en sección (c)).

## RIESGO conocido (por qué falló antes)
Memoria `project_bugs_847_fixes_2026_05_23`: un intento previo de FR-CoT **rompió
media (6/6→3/6)** porque "Gemma emitió el formato como texto" — la plantilla se
filtró al REPLY visible en vez de quedar en el canal de thinking.

## Plan
1. **Scopear al canal de thinking.** La plantilla FR-CoT debe instruirse para vivir
   SOLO dentro del razonamiento (`<think>...`/reasoning channel) y el parser/strip
   del agente debe garantizar que NO aparezca en `content`. Verificar con
   `sanitize_assistant_message` / el strip de reasoning en `agent.py`.
2. **Gating.** Aplicar FR-CoT solo en modos de ACCIÓN (quick_action/fast_action),
   no en charla/info (que ya van thinking-OFF o no lo necesitan).
3. **Flag.** `GEMMA4_FRCOT=1` opt-in primero, medir, después default si pasa gates.
4. **Test en vivo EXHAUSTIVO** (cuando el usuario NO esté jugando): media ("pone
   música", "pausa", "siguiente"), apps ("abrí spotify"), audio ("subí volumen",
   "mute"), info, charla, computer-use, ENCADENAMIENTO ("abrí X y hacé Y"). Gate:
   tool-calling ≥ baseline (no regresión), 0 regresión en media, latencia de acción
   p90 ~13s → ~4-6s objetivo.
5. **NO romper el encadenamiento** (el usuario lo pidió explícito): el FR-CoT acelera
   la DECISIÓN de cada paso; el loop de chaining (decide→ejecutar→decide→…) se
   mantiene. Verificar que cadenas de 2-3 pasos sigan funcionando.

## Alternativas si FR-CoT no basta (de `reducir_latencia_thinking_gemma4.md`)
- **Two-Track speculative + filler TTS** (#6 del research): emitir "Abriendo X…" a TTS
  mientras el tool corre en background → enmascara 1-2 s percibidos SIN tocar el
  modelo. Patrón Vapi/GetStream/Sierra. Es cambio de pipeline de voz, no del LLM.
- **Router adaptativo de thinking** (Ares, arXiv 2603.07915): gatear el budget de
  thinking por complejidad del intent (el agente ya tiene router semántico). −52.7%
  tokens, degradación mínima. Más complejo que FR-CoT.

## Restricciones (no cambian)
Gemma 4 sí o sí · 4 GB VRAM (E2B único que entra con visión) · todo OSS · el LLM
responde (sin hardcodes) · latencia tier-Alexa 4-5s.
