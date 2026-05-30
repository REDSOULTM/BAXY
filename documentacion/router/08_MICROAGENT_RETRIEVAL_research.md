# Microagent selection — research & rediseño (R3.3, 2026-05-30)

## El problema medido

Los microagents (markdown de conocimiento inyectado condicionalmente al system
prompt: glossary, troubleshoot, tools-cheat-sheet, windows-commands) se
seleccionaban por **substring matching** de `triggers` (patrón heredado de
OpenHands `.openhands/microagents/`). Medido sobre 1492 mensajes reales:

- **61/1492 (4.1%) disparaban** un microagent, mayoría **falsos positivos**.
- Bugs concretos del substring:
  - `"House of Dragon"` → glossary (trigger **"RAG"** ⊂ "D**rag**on").
  - `"dile que es gordo"` → glossary (trigger **"que es"** substring).
  - `"video que estoy viendo"` → glossary ("que es" ⊂ "e**stoy**").
- Resultado: 3 KB de jerga técnica irrelevante inyectada en mensajes de
  WhatsApp/media/charla.
- **Monolingüe**: los triggers eran keywords en español (con duplicación
  tilde/sin-tilde). Un usuario en inglés/portugués no disparaba nada.

Esto viola CLAUDE.md ("nada de listas de keywords por idioma") y el presupuesto
de latencia.

## Estado del arte (fuentes verificadas)

Investigación 2026-05-30 (fuentes primarias leídas esta sesión):

1. **OpenHands SIGUE usando substring matching** — verificado en su código
   actual (`agent-sdk` main) y legacy (v0.20/v0.30): `if keyword.lower() in
   message.lower()`. Mismo bug. La propuesta de overhaul (issue #7547) fue
   cerrada "not planned". → OpenHands es referencia de **formato**, no de
   algoritmo. (https://github.com/OpenHands/agent-sdk)

2. **Contexto irrelevante DAÑA, no solo desperdicia** — y peor en modelos chicos:
   - "Adaptive Distraction" (arXiv:2502.01609, Feb 2025): contexto coherente
     pero irrelevante → **~45% de degradación** promedio.
   - "Context Length Alone Hurts" (arXiv:2510.05381, Oct 2025, EMNLP): input más
     largo degrada **13.9–85%** incluso con retrieval perfecto.
   - "Sufficient Context" (arXiv:2411.06037, ICLR 2025): los modelos responden
     MAL en vez de abstenerse cuando el contexto es insuficiente → **abstener
     gana**. Modelos chicos (Mistral/Gemma) menos robustos.
   → **Un falso positivo de inyección es activamente dañino.** Optimizar
     PRECISIÓN sobre recall.

3. **Mecanismo correcto** = retrieval semántico denso + gate de abstención
   (embed query, embed docs, coseno + umbral/margen). Mismo stack que skills.

4. **Word-boundary, no substring** — MDN `\b`: `/\bthanks\b/` matchea "Thanks!"
   pero NO "Thanksgiving". Soluciona "RAG en Dragon". Caveat: `\b` es
   monolingüe; usar como **backstop estructural**, no como selector primario.

## El rediseño (lo que se hizo)

Insight clave: **no todos los microagents son del mismo tipo**.

| Microagent | Naturaleza | Mecanismo elegido |
|---|---|---|
| **glossary** | léxico (términos) | **word-boundary** de siglas técnicas exactas (HKCR, GGUF, VRAM…) — son universales (iguales en todo idioma). NO semántico: el encoder no distingue "qué es mmproj" de "qué es la fotosíntesis" (medido). |
| **troubleshoot** | semántico (intención) | **embeddings multi-vector + umbral/margen** (es/en/pt). |
| **windows-commands** | híbrido | **semántico** (intención "cómo ejecuto un comando") + word-boundary léxico para nombres de shell exactos (powershell/cmd/bash/wsl). |
| **tools-cheat-sheet** | semántico | **embeddings** ("qué podés hacer / tus capacidades"). |

`select_microagents(user_text, mas, embed_fn=...)` corre DOS mecanismos, ambos
multilingües/estructurales, NUNCA substring:

1. **Léxico word-boundary** (`_word_boundary_hit`): trigger de 1 palabra debe
   estar entre las tokens del texto (no substring); frase multi-palabra exige
   bordes de espacio. "House of Dragon" → tokens {house, of, dragon}, "RAG" NO
   está → no dispara.
2. **Semántico** (si hay encoder): examples → vectores; coseno MAX; dispara si
   `top ≥ 0.60` Y `gap top1−top2 ≥ 0.03`. Multilingüe. Fallback seguro sin
   encoder (cae a léxico).

Gates: `GEMMA4_MICROAGENT_THRESHOLD` (0.60), `GEMMA4_MICROAGENT_MARGIN` (0.03).

## Resultado medido

| Métrica | Antes (substring) | Después (semántico+word-boundary) |
|---|---|---|
| Disparo en 1492 reales | 61 (4.1%) | **13 (0.9%)** |
| glossary FP | 47 (RAG-en-Dragon, que-es-gordo…) | **0** (2 disparos legítimos: "usas embeddings", "cuánta VRAM") |
| Hard-negatives FP | varios | **0** |
| Recall (GOLD) | — | **9/10** (el miss "el micrófono no anda" es un caso ambiguo audio↔falla, sacrificado para matar 18 FP de mute/silencia) |
| Multilingüe | NO (es-only) | **SÍ (es/en/pt)** |
| Verificado en vivo (4B real) | — | **8/8 PASS** |

Bug del parser arreglado de paso: `_split_inline_list` respeta comillas (antes
`re.split(",")` partía las comas DENTRO de un example, duplicando la lista).

## Decisiones honestas / techos

- **Precisión > recall** (justificado por arXiv:2502.01609/2510.05381): se
  sacrificó recall en casos ambiguos ("el micrófono no anda" = ¿roto o mutear?)
  para 0 FP. Mejor no inyectar que inyectar mal.
- **glossary NO usa examples semánticos**: medido que el encoder no separa "qué
  es <término técnico>" de "qué es <cosa general>". La señal está en el término,
  no en la forma. Word-boundary del término exacto es la solución correcta.
- **Pendiente (no forzado)**: la investigación sugiere que glossary podría ser
  un **tool `define(term)`** (lookup) en vez de inyección, y cheat-sheet podría
  fundirse con el skill-retrieval. No se hizo ahora (cambio de mayor alcance);
  el word-boundary actual ya elimina los FP. Ver 06_PENDIENTE_Y_NO_FORZADO.md.

## Fuentes

- OpenHands agent-sdk (substring verbatim): https://github.com/OpenHands/agent-sdk
- Adaptive Distraction ~45%: https://arxiv.org/pdf/2502.01609 (Feb 2025)
- Context Length Alone Hurts 13.9–85%: https://arxiv.org/abs/2510.05381 (Oct 2025)
- Sufficient Context (abstener gana): https://arxiv.org/abs/2411.06037 (ICLR 2025)
- Lost in the Middle: https://arxiv.org/abs/2307.03172 (TACL 2024)
- MDN word boundary `\b`: https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Regular_expressions/Word_boundary_assertion
- (compartidas con skills) Re-Invoke 2408.01875, Tool-DE 2510.22670, Conformal IR 2410.02914
