# 08 — Investigación externa citada

Todas las fuentes que sustentaron decisiones del proyecto, organizadas por tema.

---

## Documentación oficial Google AI

### Modelo y arquitectura
- [Gemma 4 model card](https://ai.google.dev/gemma/docs/core/model_card_4) — overview, quants, sampling oficial T=1.0/top_p=0.95/top_k=64
- [Gemma 4 model overview](https://ai.google.dev/gemma/docs/core) — variantes E2B/E4B/26B-A4B/31B
- [Gemma 4 prompt formatting](https://ai.google.dev/gemma/docs/core/prompt-formatting-gemma4) — chat template `<|turn>system ... <turn|>`

### Function calling
- [Function calling Gemma 4](https://ai.google.dev/gemma/docs/capabilities/text/function-calling-gemma4) — formato nativo `<|tool_call>...<tool_call|>`
- Tokens especiales entrenados: `<|tool>`, `<|tool_call>`, `<|tool_response>` y closing pairs

### Multimodal
- [Vision understanding](https://ai.google.dev/gemma/docs/capabilities/vision) — pointing, OCR, token budget
- [Thinking mode](https://ai.google.dev/gemma/docs/capabilities/thinking) — `<|think|>` token control

### Edge agentic
- [Bring agentic skills to edge](https://developers.googleblog.com/bring-state-of-the-art-agentic-skills-to-the-edge-with-gemma-4/) — performance Raspberry Pi, Snapdragon, etc.
- [Multi-Token Prediction Gemma 4](https://blog.google/innovation-and-ai/technology/developers-tools/multi-token-prediction-gemma-4/) — 3× speedup con drafters

### MoE
- [Gemma 4 MoE explicado — MindStudio](https://www.mindstudio.ai/blog/gemma-4-mixture-of-experts-architecture) — 128 experts, top-8 router learned

---

## llama.cpp — issues y PRs relevantes

### Tool calling y parser
- [PR #21418 — Specialized Gemma 4 parser](https://github.com/ggml-org/llama.cpp/pull/21418) — merged 2026-04-04, mi b9090 lo incluye
- [Issue #21316 — Tool call tokens leak](https://github.com/ggml-org/llama.cpp/issues/21316) — fixed por #21418

### Thinking mode
- [Discussion #21338 — Disable thinking](https://github.com/ggml-org/llama.cpp/discussions/21338) — `--reasoning off` flag

### Cache reuse (BUG conocido)
- [Issue #21468 — Cache reuse no soportado en Gemma 4](https://github.com/ggml-org/llama.cpp/issues/21468) — Shared KV Cache architecture
- [PR #22288 — Fix abierto sin merge confirm en b9090](https://github.com/ggml-org/llama.cpp/pull/22288)

### Audio HTTP
- [Issue #21868 — input_audio HTTP API](https://github.com/ggml-org/llama.cpp/issues/21868) — closed as "not planned"
- [PR #21421 — Audio Conformer encoder](https://github.com/ggml-org/llama.cpp/pull/21421) — encoder soportado en libmtmd, no en server

### Optimización latencia
- [Discussion #20574 — Host-memory prompt caching](https://github.com/ggml-org/llama.cpp/discussions/20574) — 93% TTFT reduction (no aplica Gemma 4 por #21468)
- [Discussion #20969 — TurboQuant KV cache](https://github.com/ggml-org/llama.cpp/discussions/20969) — experimental

### Otros bugs
- [Issue #21424 — Long generation latency Gemma 4](https://github.com/ggml-org/llama.cpp/issues/21424)
- [Issue #21321 — `<unused24>` tokens](https://github.com/ggml-org/llama.cpp/issues/21321)
- [Issue #21384 — Tool call array parameter serialized as JSON string](https://github.com/ggml-org/llama.cpp/issues/21384)
- [Issue #21402 — mmproj crashes on CUDA SIGABRT](https://github.com/ggml-org/llama.cpp/issues/21402)

---

## Engineering best practices

### Anthropic
- [Writing tools for agents](https://www.anthropic.com/engineering/writing-tools-for-agents) — composite tools, namespacing, evaluation-driven
- [Building effective agents](https://www.anthropic.com/research/building-effective-agents) — patrones de orquestación

### GitHub MCP scaling
- [GitHub MCP server scaling — ZenML LLMOps Database](https://www.zenml.io/llmops-database/building-and-scaling-a-production-mcp-server-for-developer-tooling) — 100+ tools rompe agents, bajaron a 40 default

### Routing y multi-agent
- [CARGO routing — arXiv 2509.14899](https://arxiv.org/html/2509.14899v1) — 76.4% accuracy router LLM
- [Why Multi-Agent Systems Fail — arXiv 2503.13657](https://arxiv.org/html/2503.13657v1) — error amplification 17.2× en multi-agent
- [Modular context architecture — DEV.to](https://dev.to/salt_creative/from-monolithic-prompts-to-modular-context-a-practical-architecture-for-agent-memory-1lcp) — split prompt benefits
- [Patronus AI agent routing best practices](https://www.patronus.ai/ai-agent-development/ai-agent-routing)

---

## Cuantización y benchmarks comunidad

### Unsloth (UD dynamic quants)
- [Unsloth Gemma 4 docs](https://unsloth.ai/docs/models/gemma-4) — recomendaciones por tamaño
- [Unsloth Dynamic 2.0 GGUFs](https://unsloth.ai/docs/basics/unsloth-dynamic-2.0-ggufs) — imatrix superior
- [unsloth/gemma-4-E4B-it-GGUF](https://huggingface.co/unsloth/gemma-4-E4B-it-GGUF) — repo oficial GGUFs

### KV cache sensibilidad
- [Gemma 4 KV cache benchmark — localbench](https://localbench.substack.com/p/kv-cache-quantization-benchmark) — Gemma 4 26B-A4B = más sensible a quant tested (q8_0 KL 0.377)
- [Issue #21385 — Per-head adaptive KV cache](https://github.com/ggml-org/llama.cpp/issues/21385) — +8% quality opcional

### VRAM por consumer GPU
- [VRAM table — knightli](https://www.knightli.com/en/2026/05/01/gemma-4-local-vram-quantization-table/) — datos comunidad
- [Gemma 4 VRAM requirements — gemma4guide](https://gemma4guide.com/guides/gemma4-vram-requirements)
- [Gemma 4 GGUF guide — gemma4-ai](https://gemma4-ai.com/blog/gemma4-gguf-guide) — Q4_K_M sweet spot

---

## HuggingFace blogs y discusiones

- [Welcome Gemma 4 — HF blog](https://huggingface.co/blog/gemma4) — overview multimodal frontier
- [Discussion #21334 — How to input audio Gemma 4 E4B](https://github.com/ggml-org/llama.cpp/discussions/21334)

---

## Gemma 4 vs alternativas

### Audio comparativas
- [Whisper Notes — Parakeet v3 vs Whisper](https://whispernotes.app/blog/parakeet-v3-default-mac-model) — 10× faster
- [Northflank — Best open source STT 2026](https://northflank.com/blog/best-open-source-speech-to-text-stt-model-in-2026-benchmarks)
- [parakeet-tdt-0.6b-v3 — HuggingFace](https://huggingface.co/nvidia/parakeet-tdt-0.6b-v3) — multilingual incluyendo es

### Ecosistema
- [Gemma 4 vs Qwen 3.6 Plus — MindStudio](https://www.mindstudio.ai/blog/gemma-4-vs-qwen-3-6-plus-agentic-workflows) — comparativa agentic
- [Gemma 4 production-ready — DEV.to part 3](https://dev.to/system_rationale/part-3-making-gemma-4-agents-production-ready-guardrails-structured-outputs-and-self-healing-575n) — guardrails y structured outputs

---

## Total: ~40 fuentes externas

Cada decisión arquitectural en `REPORTE_GEMMA4_PARA_CARTER.md` tiene al menos 1 fuente citada de esta lista.
