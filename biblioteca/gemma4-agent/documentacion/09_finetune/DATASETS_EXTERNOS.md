# Datasets externos — DECISIÓN (research licencias 2026-06-02)

> Nota: este doc dice "63 tools" (el vocab del momento del research). El vocab FINAL es
> **61 tools** (se eliminó `smart_home`; ver `ESTADO_COMPLETO_2026-06-02.md`). Donde diga 63,
> entender 61. Producto = **Baxy**; el MODELO es Gemma 4.

Producto se VENDE → solo datasets con licencia comercial-OK y SIN taint de OpenAI/GPT
(los ToS de OpenAI prohíben entrenar competidores; la etiqueta Apache del repo NO sanea
outputs de GPT). El dominio propio (~4000 curados + 119 encadenamiento) es el NÚCLEO,
los externos SUPLEMENTAN (no reemplazan, no diluyen las 63 tools).

## USAR (sellable, sin taint, verificado en card oficial)
| Dataset | Licencia | Uso | Idiomas |
|---------|----------|-----|---------|
| `Salesforce/xlam-function-calling-60k` | CC-BY-4.0 (gated) | tool-calling: lógica selección+args. Generado DeepSeek/Mixtral (NO OpenAI) | EN → traducir fracción |
| `CohereLabs/aya_dataset` (human) | Apache-2.0 | multilingüe calidad respuesta (es/pt/fr/de/it), anotado por humanos = sin taint | 65 idiomas |
| `OpenAssistant/oasst1` | Apache-2.0 | conversacional/persona multi-turn, humano | 35 idiomas |
| `gorilla-llm/Berkeley-Function-Calling-Leaderboard` | Apache-2.0 | SOLO como EVAL externo de tool-calling (held-out), NO train | EN+ |

## PROBABLE-SÍ (confirmar procedencia antes de escalar)
- `Team-ACE/ToolACE` (Apache, síntesis multi-agente propia, no GPT-4 — riesgo bajo)
- `glaiveai/glaive-function-calling-v2` (Apache, origen propio según 2ª fuente — riesgo medio)
- `NousResearch/hermes-function-calling-v1` (Apache, contiene subset Glaive — verificar por subset)

## DESCARTAR (venta)
- ToolBench (ChatGPT-generado → taint OpenAI)
- OpenHermes 2.5 (GPT-4 → el autor mismo dice CC-BY-NC sería lo correcto)
- APIGen-MT-5k (CC-BY-NC + GPT-4, doble bloqueo)
- Magpie: vendible PERO ataduras Llama ("Built with Llama" + naming + 700M MAU) → Aya es mejor sin ataduras
- pesos xLAM-2 son CC-BY-NC (pero el DATASET xlam-60k sí es CC-BY-4.0 — no confundir)

## PROPORCIÓN (anti-overfit + no diluir dominio)
- Núcleo propio: **50-60%** (único que conoce las 63 tools + estilo). No bajar de ahí.
- Tool-calling externo: 20-25% (xLAM + subset ToolACE), ADAPTADO a las 63 tools.
- Multilingüe instruct: 15-20% (Aya human filtrado es/pt/fr/de/it + OASST1).
- Persona: ~5% (OASST1 alta calidad).
- CAP por idioma: EN externo no debe superar la masa no-EN. Experimento mínimo (5-10%) +
  gate por idioma ANTES de volcar masa. Si un idioma se degrada, recortar ese externo.

## ADAPTACIÓN necesaria
- xLAM/ToolACE: mapear SUS tools → nuestras 63 (o usar como señal genérica "elegir-tool+args"),
  traducir query a es/pt/fr/de/it, recortar reply a estilo voz.
- Aya/OASST: filtrar por idioma + calidad, aplanar a turnos, recortar a estilo voz hablado.

> **[ACTUALIZADO al cierre del FT]** del research a la práctica: el dataset final usó de
> los externos **Aya (553 ejemplos) + OASST (288)** como aporte conversacional 0-tool
> multilingüe (ver `ESTADO_COMPLETO_2026-06-02.md` §DATASET). xLAM/BFCL no terminaron en el
> dataset final; el núcleo propio (cobertura de las 61 tools + flujos multi-paso) quedó como
> mayoría. La nota original "NO se descargó nada aún" era del momento del research.

Fuentes completas en task a91076713.
