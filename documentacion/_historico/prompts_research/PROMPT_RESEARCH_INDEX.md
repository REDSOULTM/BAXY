# Índice de prompts de investigación — Carter Agent (vram4)

8 prompts para mandar a Claude (research). Cada uno es independiente y lleva la
RESTRICCIÓN DURA: todo debe correr en **vram4 = Gemma 4 E4B-it Q4_K_M** (~4B, GPU
4-6 GB, latencia 4-5 s), sin asumir modelo más grande ni petar el programa.

Marcá acá cuáles ya mandaste / cuáles volvieron, para no perderte.

| # | Archivo | Tema | Ataca | Mandado | Volvió |
|---|---|---|---|:---:|:---:|
| 1 | PROMPT_RESEARCH_1_toolcalling_structured.md | Tool-calling + structured output (grammar/sampling) | El 2/6 sin reasoning → tool-call fiable sin thinking caro | ☐ | ☐ |
| 2 | PROMPT_RESEARCH_2_memoria_personalizacion.md | Memoria / personalización / entity-grounding | Bug WhatsApp (chat equivocado) + entity-recall STT | ☐ | ☐ |
| 3 | PROMPT_RESEARCH_3_verificacion_recovery.md | Verificación de acciones + recovery | No decir "Listo" si la acción falló | ☐ | ☐ |
| 4 | PROMPT_RESEARCH_4_contexto_multiturno.md | Contexto / historial multi-turno | Compaction sin romper cache, coherencia | ☐ | ☐ |
| 5 | PROMPT_RESEARCH_5_aprendizaje_proactivo.md | Aprendizaje proactivo (Jarvis) | Observar hábitos → ofrecer automatizar | ☐ | ☐ |
| 6 | PROMPT_RESEARCH_6_estabilidad_no_crash.md | Estabilidad / no-crash | Presión VRAM, aislar tools, self-check | ☐ | ☐ |
| 7 | PROMPT_RESEARCH_7_nlu_comandos_ambiguos.md | NLU: ambigüedad / multi-intent / clarificación | "abrí Spotify y bajá volumen", "mandale a Juan" (sin texto) | ☐ | ☐ |
| 8 | PROMPT_RESEARCH_8_automatizacion_gui_desktop.md | Automatización GUI/desktop (UIA vs OCR/visión) | Operar apps fiable sin visión cara | ☐ | ☐ |

## Orden de impacto sugerido (para aplicar las respuestas)
1 (tool-calling) → 5 (Jarvis) → 7 (multi-intent) → 6 (estabilidad) → 2 (memoria)
→ 3 (verificación) → 8 (GUI) → 4 (contexto). Pero los 8 valen; aplicá en el
orden en que vuelvan.

## Metodología al aplicar cada investigación (regla de RED, no negociable)
1. Leer la investigación + el código real del subsistema.
2. Contrastar: ¿la afirmación es cierta en NUESTRO build/entorno? (los informes
   ya fallaron en ≥4 detalles: -ub, ctx-checkpoints, n_swa, FR-CoT-en-Gemma).
3. Definir gate (qué se mide, criterio de éxito) ANTES de tocar.
4. Implementar el cambio mínimo; medir con scripts/smoke_e2e.py BAJO vram4.
5. Si mejora medible y no degrada nada → commit. Si dudoso → opt-in (flag,
   default OFF). Si rompe algo → revertir y documentar.
6. Un cambio = un commit bilingüe + Co-Authored-By.

## Prompts previos (contexto, ya no son los principales)
PROMPT_RESEARCH_arquitectura_llm.md (visión general), _latencia_prefill_cache.md,
_thinking_latencia.md, _router_encadenamiento_foco.md, _router_y_encadenamiento.md.
