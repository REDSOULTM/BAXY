# Decisión 20: ajuste palanca por palanca de Qwen3.5-4B

Decisión del dueño (2026-10-16): reabrir el ajuste dentro del goal para sacar el máximo de Qwen3.5-4B con buenas
prácticas y fuentes. Cada palanca se investiga con su fuente, se mide por separado en práctica y se queda sólo si
gana por encima del ruido, sin romper `<reglas>` ni los 4 GB. Cuando ninguna gane: congelar, crear y correr UNA vez un
holdout nuevo sellado, y documentar el techo como límite honesto con su evidencia.

## Protocolo de medida

- **Bancos:** sólo los abiertos de práctica.
  - `renew_v1/practica/decision2.json`: 270 turnos, decisión.
  - `renew_v1/escenas/practice.json`: 39 escenas, instinto y silencio.
  - `renew_v1/e2e/practice.json`: computer use y voz, sólo en el PC.

  Ningún banco sellado se abre.
- **Brazos:** `scripts/renew/make_arms_d20.py` escribe cada brazo como una copia de `src/baxy_mind` con una sola
  palanca cambiada, en `F:\BAXYeval\renew_v1\ab\d20-<brazo>-s<semilla>`. Los bancos los miden con `--src`. La mente
  fija su semilla, así que cada brazo se mide con tres semillas (0, 1 y 2).
- **Ruido:** la dispersión entre semillas del brazo `base`. Una palanca gana si la media de sus tres semillas supera
  a la de `base` por más que esa dispersión. Además debe cumplir:
  - no pierde silencios ni suma riesgo en escenas;
  - la decisión mantiene p50 ≤ 1 s;
  - la VRAM queda ≤ 4 GB.
- **Combinación:** lo que gane se combina, y la combinación se vuelve a medir contra `base`.
- **Reglas:** sólo presentación, protocolo o inferencia (reglas 1 y 2). Nada que interprete a la persona en código.

## Palancas

| # | Palanca | Fuente | Estado |
|---|---|---|---|
| P1 | Muestreo recomendado por Qwen (sin razonamiento: temperature 0.7, top_p 0.8, top_k 20, min_p 0, presence_penalty 1.5) | [Ficha Qwen3.5-4B](https://huggingface.co/Qwen/Qwen3.5-4B), Quickstart | Brazos `qwen`, `t07`, `pp15`, `t0` contra `base` (0.2/0.8/20/0) |
| P2 | Razonamiento on/off por tarea | Misma ficha: Qwen3.5 razona por defecto; muestreo con razonamiento 1.0/0.95/20/0/pp1.5 | Brazo `think` (razonamiento en toda decisión). Si gana en aciertos pero rompe el p50, se mide por tipo de tarea |
| P3 | Plantilla nativa de herramientas de Qwen | Ficha: parser `qwen3_coder` (XML `<function=…><parameter=…>`); [llama.cpp function-calling](https://github.com/ggml-org/llama.cpp/blob/master/docs/function-calling.md): `--jinja` usa la plantilla del modelo | **Ya aplicada**. Comprobado el 2026-10-16 con llama-server b11609 y `/apply-template`: la sección `# Tools` va en el sistema, las llamadas en XML y el parser devuelve `tool_calls` correctos. Sin brazo |
| P4 | Menos herramientas por turno con un recuperador del catálogo | [ToolScope, ACL 2026 (arXiv 2510.20036)](https://arxiv.org/abs/2510.20036); [DTDR (arXiv 2512.17052)](https://arxiv.org/abs/2512.17052); contrapunto: [TRAJECT-Bench (arXiv 2510.04550)](https://arxiv.org/pdf/2510.04550) | Pendiente de diseño: la elección de herramientas tiene que ser del modelo (regla 1) y el prefijo cacheado de 37k tokens es lo que da el p50 de 0,83 s |
| P5 | Orden del contexto | Liu et al., [«Lost in the Middle» (TACL 2024)](https://arxiv.org/abs/2307.03172) | Pendiente |
| P6 | Cabecera única de resultados | Anthropic, [«Writing effective tools for agents»](https://www.anthropic.com/engineering/writing-tools-for-agents) | Pendiente |
| P7 | Guías con ejemplos para computer use | Pendiente de fuente | Pendiente; se mide en e2e de práctica (computer use 1/10 en el holdout v2) |
| P8 | Gramática de llamadas en llama.cpp | llama.cpp: gramáticas *lazy* para llamadas nativas (PR #9639, #12034) | Por comprobar con `-v` si ya se aplica a la plantilla XML de Qwen3.5 |

## Resultados

(se completan con cada medición: brazo, semilla, banco, aciertos, p50, silencios y riesgo)
