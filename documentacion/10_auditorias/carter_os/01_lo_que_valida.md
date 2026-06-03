# 01 — Lo que Carter VALIDA de nuestras decisiones

Carter llegó, por un camino independiente y 4 generaciones de bench, a las mismas
conclusiones que ya aplicamos. Esto sube la confianza en decisiones nuestras que
estaban respaldadas por una sola fuente.

| Decisión nuestra | Cómo lo confirma Carter (`11_lecciones_v1_a_v4.md` §5/§6) |
|---|---|
| **Sampling oficial Gemma (T=1.0/top_p=0.95/top_k=64)** en modos de razonamiento; bajar T degrada | Carter §2.2: *"T<0.7 degrada"*, 540/540 con valores oficiales. Coincide con nuestro Inv 0/T4: greedy SOLO para tool-call, defaults en thinking. |
| **Verificación estructural (pycaw/EnumWindows/OCR), NO LLM-as-judge** | Carter L6 + `verify/core.py`: *"NO usamos LLM para verificar (fue uno de los bugs de v3)"*. Nuestro `verify_core.py` + `_verify_chat_header` UIA/OCR es el mismo principio. |
| **Loop detection v2 result-aware + two-tier escalation** | Carter `loop/detection.py` es CASI idéntico a nuestro `loop_detection.py` (mismo hash con result_signature, mismo warning→critical). Misma cita (zeroclaw #2152, Reflexion NeurIPS 2023). |
| **Honestidad por construcción: nunca "DONE" sin verificación** | Carter V3/ContextoCarter = principio fundacional. Nuestro honesty-guard + UNVERIFIED. |
| **Universal cross-lingual SIN listas por idioma** (Snowball stems / embeddings) | Carter L4 + safety multilingüe por Snowball. Coincide EXACTO con tu principio "no regex es-only" y lo que migré en context_router/splitter/Jarvis. |
| **Deeplinks vía registry HKCR, no hardcode** | Carter §2.2 + L4. Nuestro `microagents.py` ya resuelve por protocolo. |
| **Foco Windows: AllowSetForegroundWindow + ALT trick + AttachThreadInput** | Carter §2.2 + L (causal focus). Es el mismo `win_focus.py` que arreglamos (commit con ALT+AttachThreadInput). |
| **Verifier por-misión (Voyager), no solo por-tool** | Carter L6 + `mission/goal.py`. Nosotros YA tenemos `mission_goal.py`. |
| **NO multi-modelo / dual-LLM pipeline** (latencia 2-3× sin ganancia) | Carter §2.1: dual-LLM tiene bug head-of-line + CARGO 76% router. Coincide con nuestra decisión de un solo modelo + router semántico. |
| **Skills locales formato SKILL.md (Anthropic Agent Skills)** | Carter `skills/registry.py`. Nosotros YA tenemos `skills_registry.py` con el mismo patrón. |
| **mmproj-F16 siempre, KV cache F16, NO `--reasoning off`, NO custom chat-template** | Carter §2.1/§2.2 lo midió y descartó las alternativas. Confirma nuestra config. |
| **Vision on-demand, no por default** (latencia +5-10s) | Carter §2.1 (commit `08322e29`). Coincide con nuestro lazy-vision / router-mode. |
| **max_tokens chico causa empty reply** | Carter: max_tokens=512 → 10% empty. Nosotros ya cap más alto en modos de acción + forced-retry. |

## Conclusión de esta sección

No hay nada que "arreglar" acá: **es evidencia de segunda fuente de que vamos
bien**. La coincidencia es alta porque ambos proyectos comparten stack y filosofía
(de hecho v5 nos cita como ground-truth). Donde Carter difiere es en organización
del código (modular vs concentrado), no en las decisiones técnicas de fondo.
