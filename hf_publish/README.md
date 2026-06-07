---
license: gemma
base_model: google/gemma-4-E2B-it
base_model_relation: quantized
library_name: gguf
pipeline_tag: text-generation
tags:
  - gguf
  - llama.cpp
  - gemma
  - gemma4
  - baxy
  - voice-assistant
  - tool-calling
  - function-calling
  - quantized
  - q4_k_m
language:
  - es
  - en
  - pt
  - fr
  - de
  - it
---

# Baxy — Gemma 4 E2B (GGUF, fine-tuned)

> **Built with Gemma.** This is a fine-tune of Google's **Gemma 4 E2B-it**,
> quantized to GGUF for local inference with [llama.cpp](https://github.com/ggml-org/llama.cpp).
> It powers **[Baxy](https://github.com/REDSOULTM/Baxy)**, a 100%-local Windows
> voice assistant.

This repo contains the **GGUF artifacts that run in Baxy's production profile**:

| File | Size | What it is |
|---|---|---|
| `gemma-4-E2B-it-Q4_K_M.gguf` | ~3.4 GB | The fine-tuned LLM (Q4_K_M, imatrix). Text + tool-calling. |
| `mmproj-F16.gguf` | ~1.0 GB | Vision projector (mmproj) for Gemma 4 multimodal (screenshots). |

## What the fine-tune does (and what it does NOT)

The base Gemma 4 tends to **invent tools** that don't exist when offered a large
tool catalog, and to **drift to a dominant language** in the short confirmation
it gives after running a tool. This fine-tune targets two **reliability** goals,
both measured live:

- **0% invented tools in production** (with the tool array provided in the prompt).
- **Multilingual post-tool replies** — the action confirmation comes back in the
  user's language (es / en / pt / fr / de / it), not always Spanish.

It is a **reliability / tool-calling** fine-tune, **not** a knowledge upgrade —
Gemma is still Gemma; it just stops inventing tools and respects the input
language. Routing, honesty guards, memory, RAG and computer-use live in the
**Baxy app**, not in these weights.

> **Honesty note:** these numbers were measured with Baxy's harness against the
> real LLM (physical execution mocked). They describe behavior *inside Baxy's
> prompt + tool contract*; a bare `llama-cli` chat won't reproduce the
> tool-calling gate because there are no tools in the prompt.

## How to use

### Download
```bash
# new unified HF CLI
hf download REDSOULTM/baxy-gemma4-E2B-GGUF gemma-4-E2B-it-Q4_K_M.gguf --local-dir ./models/E2B
hf download REDSOULTM/baxy-gemma4-E2B-GGUF mmproj-F16.gguf            --local-dir ./models/E2B
```

### Run with llama.cpp (text)
```bash
llama-server -m gemma-4-E2B-it-Q4_K_M.gguf --host 127.0.0.1 --port 8080 -ngl 99
# then POST to http://127.0.0.1:8080/v1/chat/completions (OpenAI-compatible)
```

### Run with vision (multimodal)
```bash
llama-mtmd-cli -m gemma-4-E2B-it-Q4_K_M.gguf --mmproj mmproj-F16.gguf --image screenshot.png -p "Describe what's on screen"
```

### Use it inside Baxy (the full assistant)
The app downloads these files automatically. See
**[github.com/REDSOULTM/Baxy](https://github.com/REDSOULTM/Baxy)** → Installation.

## Details

- **Base model:** [google/gemma-4-E2B-it](https://huggingface.co/google/gemma-4-E2B-it) (Gemma 4, ~2B active params, MatFormer).
- **Quantization:** `Q4_K_M` with an importance matrix (imatrix) computed over a
  multilingual corpus (es/en/pt/fr/de/it). Quantized from a bf16 merge.
- **Chat template:** Gemma 4 turn-based (`<|turn>role…<turn|>`); native
  function-calling (`<|tool_call>call:NAME{…}<tool_call|>`). The GGUF carries the
  chat template; use a recent llama.cpp build with the Gemma 4 fixes.
- **Hardware target:** runs in ~3.4 GB; designed for a 4 GB-VRAM laptop (or CPU).

## License

This model is a derivative of **Gemma 4** and is distributed under the
[**Gemma Terms of Use**](https://ai.google.dev/gemma/terms). By using it you
agree to those terms, including Google's
[Prohibited Use Policy](https://ai.google.dev/gemma/prohibited_use_policy).
The fine-tuning data, training scripts and the surrounding Baxy application are
released under the Baxy project's own license — see the
[GitHub repo](https://github.com/REDSOULTM/Baxy).

*Gemma is provided under and subject to the Gemma Terms of Use found at
ai.google.dev/gemma/terms.*

## Citation / credits

- **Gemma 4** — Google DeepMind.
- **llama.cpp** — ggml-org.
- **Baxy** — [REDSOULTM](https://github.com/REDSOULTM).
