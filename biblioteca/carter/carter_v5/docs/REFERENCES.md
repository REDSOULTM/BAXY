# Carter v5 — Bibliography & References

Every architectural decision in Carter v5 traces back to one of these
sources. This document is the audit trail for "why we did it this way."

---

## Internal sources

### Carter project history
- [`legacy/Carter_v1`](../../legacy/Carter_v1/) — initial attempt (Q4 2024)
- [`legacy/Carter_v2`](../../legacy/Carter_v2/) — rebuild from-scratch
- [`legacy/Carter_v3`](../../legacy/Carter_v3/) — refactor with mission_detector + planner
- [`legacy/Carter_v4`](../../legacy/Carter_v4/) — Gemma 4 migration

### Carter design documents
- [`../../ContextoCarter.md`](../../ContextoCarter.md) — the 30 design values
- [`../../La razon de carter/11_lecciones_v1_a_v4.md`](../../La razon de carter/11_lecciones_v1_a_v4.md) — what worked & what didn't
- [`../../La razon de carter/12_carter_v5_arquitectura.md`](../../La razon de carter/12_carter_v5_arquitectura.md) — v5 architecture rationale
- [`../../La razon de carter/13_carter_v5_perfiles_vram.md`](../../La razon de carter/13_carter_v5_perfiles_vram.md) — per-tier specs

### Probando Gemma 4 (validated harness)
- `Probando Gemma 4/harness_carter540/` — 540/540 PASS reproducible
- `Probando Gemma 4/docs/REPORTE_GEMMA4_PARA_CARTER.md` — main report
- `Probando Gemma 4/docs/REPORTE_EXTENDIDO.md` — bench Fase 2 (60 tests × 21 models)
- `Probando Gemma 4/documentacion/04_vram_y_hardware/` — measured VRAM per quant
- `Probando Gemma 4/documentacion/06_consolidacion_tools/` — 60→16 tools rationale
- `Probando Gemma 4/documentacion/09_arquitectura_decisiones/` — 14 measured decisions

---

## Scientific papers (peer-reviewed)

### Agent loop & verification
- **Voyager**: Wang et al., *Voyager: An Open-Ended Embodied Agent with Large Language Models*, NeurIPS 2023. <https://voyager.minedojo.org/>
  - Used in: `mission/goal.py` — verifier verifies the OBJECTIVE, not the action.
- **Reflexion**: Shinn et al., *Reflexion: Language Agents with Verbal Reinforcement Learning*, NeurIPS 2023. <https://arxiv.org/abs/2303.11366>
  - Used in: `loop/detection.py` — two-tier escalation (warning → critical).
- **ReAct**: Yao et al., *ReAct: Synergizing Reasoning and Acting in Language Models*, ICLR 2023. <https://arxiv.org/abs/2210.03629>
  - Used in: agent loop base pattern (think → tool_call → observe → repeat).

### Tool use & retrieval
- **RAG-MCP**: *RAG-MCP: Mitigating Prompt Bloat in LLM Tool Selection*, 2025. <https://arxiv.org/abs/2505.03275>
  - Status: NOT used. v5 design choice P5 — static tools_subset per tier preserves prompt cache. Dynamic retrieval was tried in v3-v4 and removed; the cache cost outweighed the accuracy delta for Gemma 4 with 16 consolidated tools. Re-evaluate only if tool count grows past ~30.
- **Tool-to-Agent Retrieval**: arxiv 2511.01854. <https://arxiv.org/pdf/2511.01854>
- **Online-Optimized RAG**: arxiv 2509.20415. <https://arxiv.org/html/2509.20415v1>

### GUI agents (state of the art)
- **UI-TARS-2**: ByteDance, 2025. <https://arxiv.org/abs/2509.02544>
  - Used in: `core/execution.py:_vision_auto_step` — perception integrated to action.
- **UI-TARS-1**: arxiv 2501.12326.
- **ShowUI**: CVPR 2025.

### Benchmark / evaluation
- **OSWorld**: NeurIPS 2024. <https://os-world.github.io/>
- **OSWorld-Human (efficiency)**: MLSys 2026. <https://mlsys.wuklab.io/posts/oshuman/>
  - Insight: "each successive step 3x longer" → minimize follow-up LLM calls.

---

## Official documentation

### Google AI — Gemma 4
- [Welcome Gemma 4 (blog)](https://huggingface.co/blog/gemma4) — model card, multimodal specs
- [Function calling with Gemma 4](https://ai.google.dev/gemma/docs/capabilities/text/function-calling-gemma4) — special tokens, schema format
- [Gemma 4 prompt formatting](https://ai.google.dev/gemma/docs/core/prompt-formatting-gemma4)

### Anthropic
- [Building Effective Agents](https://www.anthropic.com/research/building-effective-agents) — "keep loop minimal, 98.4% deterministic infra"
- [Advanced Tool Use](https://www.anthropic.com/engineering/advanced-tool-use)
- [Writing Tools for Agents](https://www.anthropic.com/engineering/writing-tools-for-agents) — "composite tools > excessive splitting"
- [Computer Use Tool](https://platform.claude.com/docs/en/agents-and-tools/tool-use/computer-use-tool)

### llama.cpp
- [Function calling docs](https://github.com/ggml-org/llama.cpp/blob/master/docs/function-calling.md)
- PR #21418 — Gemma 4 specialized parser (b9090+)
- PR #21421 — Gemma 4 audio Conformer encoder
- Issue #21868 — input_audio HTTP routing missing
- Issue #21325 — initial Gemma 4 audio support gap

### Microsoft (Windows)
- [AllowSetForegroundWindow](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-allowsetforegroundwindow)
- [Registering URI Schemes (HKCR)](https://learn.microsoft.com/en-us/previous-versions/windows/internet-explorer/ie-developer/platform-apis/aa767914(v=vs.85))
- [pywinauto docs](https://pywinauto.readthedocs.io/) — UIA backend, set_focus()

### Unsloth (Gemma 4 GGUF)
- [Gemma 4 — How to Run Locally](https://unsloth.ai/docs/models/gemma-4) — quant recommendations
- Imatrix dynamic quant (Q3_K_XL, IQ4_XS) — better than plain Q3_K_M

### KV cache quantization
- [localbench KV cache benchmark](https://localbench.substack.com/p/kv-cache-quantization-benchmark) — Gemma 4 26B-A4B most sensitive (KL 0.377 with q8_0)

---

## Whisper STT

- [faster-whisper](https://github.com/SYSTRAN/faster-whisper) — CTranslate2 backend
- [Whisper Large V3 Turbo](https://www.baseten.co/library/whisper-large-v3-turbo-streaming/) — May 2026 release, 216x realtime factor

---

## Related open-source

- [ByteDance UI-TARS](https://github.com/bytedance/UI-TARS) — reference GUI agent
- [Pydantic AI](https://ai.pydantic.dev/agent/) — typed agent contracts (inspiration for `core/types.py`)
- [ggml-org/llama.cpp](https://github.com/ggml-org/llama.cpp) — backend

---

## Industry case studies

- **GitHub MCP** (2025-2026 scaling experience): "100+ tools → agents confused/forgetful → bajaron a 40". Source: ZenML LLMOps Database, GitHub MCP case study 2026.
  - Justifies: 16 composite tools default in Carter v5.

---

## How this document is maintained

Each PR that adds or changes an architectural decision must:
1. Reference at least one source from this list (or add a new one).
2. Update the relevant `core/`, `mission/`, or `profiles/` module with a docstring citing the source.
3. Update `docs/ARCHITECTURE.md` if the decision affects flow.

The audit trail is what allows Carter v5 to defend its choices against
"why not [some other approach]?" questions.
