# Modelo de HABLA — Gemma 4 E2B QAT Q4_K_XL (decisión final, medido)

Tras agotar todos los caminos (Q2 mobile + DRY + grammar + imatrix + embedding-type +
n_swa + flash-attn), la conclusión MEDIDA es: el modelo de habla es **Q4_K_XL QAT**,
no el Q2 mobile. Acá está listo: `speech_model/gemma-4-E2B-it-qat-UD-Q4_K_XL.gguf`.

## Por qué Q4 y no Q2 mobile (medido)
| | Q2 mobile | **Q4_K_XL QAT** |
|---|---|---|
| VRAM real (ctx 4096) | ~1.1 GB | **~1.5 GB** (model 1223 MiB GPU + KV/compute; PLE→CPU 1476 MiB) |
| output | glitches: bleed latino, faltas ("fysico", "lumínar") | **limpio** ✅ |
| persona vía system prompt | ❌ "Soy Gemma 4" | ✅ **"Soy Baxy"** |
| FT para persona | sí | **NO hace falta** |

El Q2 (2-bit) degradaba el instruction-following → rompía persona Y metía ruido. El Q4
obedece el system prompt (dice "Soy Baxy") y sale limpio, por solo ~0.4 GB más. En 3050
4GB entra con ~2 GB de aire (+ FunctionGemma en CPU para tools).

## Config óptima de serving (medida — máxima calidad)
```bash
llama-server -m speech_model/gemma-4-E2B-it-qat-UD-Q4_K_XL.gguf \
  --mmproj speech_model/mmproj-Q8_0.gguf \   # VISIÓN: Q8 = ~0.55GB (vs 0.99GB F16), MISMA calidad (medido)
  --port 8080 --host 127.0.0.1 --jinja -ngl 99 -c 4096 --no-webui \
  --reasoning off          # mata el leak de "Thinking Process"; respuestas directas
```

## VISIÓN (mmproj) — medido 2026-06-16
El QAT GGUF es text-only, pero el mmproj de Baxy (gemma4v, visión+audio) carga limpio
con él (misma arch). Se generó un **mmproj-Q8_0** (557MB vs 985MB F16) → **~430MB menos
VRAM con calidad IDÉNTICA** (A/B en gráfico/foto/screenshot: equivalente, incluso OCR de
texto embebido). NO offload a CPU (consume RAM, que Baxy ya tiene cargada) → Q8 en GPU.
Comando: `--mmproj speech_model/mmproj-Q8_0.gguf`. Generar con:
`convert_hf_to_gguf.py --mmproj --outtype q8_0 --outfile mmproj-Q8_0.gguf <hf_E2B_dir>`.
NO usar `--cache-type-k/v` (KV-quant → gibberish, issue #21915). Flash-attn OFF
(crash #22527 con SWA — confirmado).

**Sampling por request (calidad + anti-glitch):**
```json
{"temperature":0.8, "top_k":64, "top_p":0.95, "min_p":0.05,
 "dry_multiplier":0.8, "dry_base":1.75, "dry_allowed_length":3}
```
(Para Q4 el grammar Latin-only ya NO es necesario — no hay bleed; dejarlo solo si querés
garantía dura de script.)

## System prompt Baxy (funciona en Q4, sin FT)
> "Te llamás Baxy, un asistente de voz personal. Respondé SIEMPRE en el idioma del
> usuario, directo y conciso, natural como en una charla. Si no sabés algo, decilo."

Medido: idioma-espejo ✅ (es/en/fr/pt), conciso ✅, "Soy Baxy" ✅, conocimiento limpio ✅.

## La arquitectura final del split (3050 4GB)
- **Habla** = este Q4 QAT en **GPU** (~1.5 GB), sin FT (persona por prompt).
- **Tools** = FunctionGemma-FT en **CPU** (~0.3 GB RAM) — pendiente tu experimento.
- STT/TTS/encoder/router → CPU.
- → entra en 4 GB con aire para el usuario.

## Gotchas de Gemma 4 chico (medidos, te ahorran horas)
1. `--reasoning off` o filtra "Thinking Process" en las respuestas.
2. NO quantizar KV cache (gibberish en 2º mensaje, issue #21915).
3. Flash-attn OFF (illegal memory access con SWA, issue #22527).
4. El bleed de idioma en quants bajos = imatrix solo-inglés + 2-bit; se cura subiendo a Q4.
5. n_swa del E2B = 512 (correcto en estos GGUF; si ves gibberish a contexto largo, verificá).
6. Persona: en Q4 pega por prompt; en Q2 necesita FT/template-injection.
