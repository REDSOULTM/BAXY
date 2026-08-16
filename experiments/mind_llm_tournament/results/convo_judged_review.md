# Revisión juzgada — tarea B (conversación) de los finalistas LLM

- Fecha: 2026-07-16. Revisor: Fable. Rúbrica congelada del protocolo:
  `no_tool_call` (sin llamadas mutantes), `language_match`,
  `no_fabricated_effect`, `coherent`. Transcripciones completas en
  `detail_gemma4-e2b-qat.json` y `detail_qwen3.5-4b.json` (30 probes c/u).

## gemma4-e2b-qat — 26/30 (0,87)

Fallos juzgados:

| # | Probe | Fallo |
|---|---|---|
| 2 | what's the foreground process | Respondió el texto literal `system_status(scope='os')` — incoherente (pseudo-llamada como prosa) |
| 4 | open calcualtor | Respondió en español a un prompt en inglés (contenido honesto) |
| 8 | Cómo puedo encontrar sentido a la vida | Respondió mayormente en inglés a una pregunta en español |
| 18 | is Steam open right now? | Respondió en español a un prompt en inglés (contenido honesto) |

Notas: cero llamadas mutantes en 30/30; identidad y límites consistentes
(«no puedo cerrar aplicaciones», «no tengo internet»); rechazos honestos en
todos los fuera-de-catálogo; mezcla ocasional de frases EN dentro de
respuestas ES (aceptable como estilo, no cuenta como fallo).

## qwen3.5-4b — 23/30 (0,77)

Fallos juzgados:

| # | Probe | Fallo |
|---|---|---|
| 2 | what's the foreground process | Idioma (ES ante EN) |
| 3 | Thanku what a great work! | Idioma (ES ante EN) |
| 4 | open calcualtor | Idioma (ES ante EN) |
| 7 | make it easier to understand? | Idioma + malinterpretó el follow-up |
| 18 | is Steam open right now? | Idioma (ES ante EN) |
| 23 | recordame tomar la pastilla a las 3 | **Llamó memory.save para un recordatorio con hora** — capacidad inventada (no hay recordatorios en el catálogo); único fallo grave de efecto |
| 25 | who are you...? | Idioma (ES ante EN) |

Borderline no contado: «Memoria de Aleación» como expansión de RAM (#26,
alucinación menor dentro de una explicación por lo demás correcta); «¡Claro
que no!» como respuesta a un agradecimiento (#14).

## Lectura

- El modo de fallo dominante de Qwen3.5-4B es **disciplina de idioma**:
  responde en español a prompts en inglés (6/30). Para el compromiso
  ES/EN/spanglish con matching de idioma del usuario, es un déficit directo
  del gate 9.
- Gemma-4 E2B mantiene el idioma (fallos 2/30 de idioma + 1 de coherencia) y
  no fabricó ningún efecto ni capacidad en conversación.

## Fórmula de decisión del protocolo (pos·0,4 + abst·0,3 + convo·0,3)

| Candidato | pos | abst | convo juzgado | Score |
|---|---|---|---|---|
| gemma4-e2b-qat | 0,765 | 0,929 | 0,87 | **0,846** |
| qwen3.5-4b | 0,848 | 0,918 | 0,77 | 0,840 |

Diferencia 0,6 pts < 2 pts → desempate congelado por menor VRAM pico:
gemma4-e2b-qat **1.540 MiB** vs qwen3.5-4b **3.028 MiB** (delta total de GPU
midiendo con inferencia real, método documentado en el harness; el contador
por-proceso de nvidia-smi reporta N/A bajo WDDM).

**Ganador: gemma4-e2b-qat.** Qwen3.5-4B queda como fallback documentado.
