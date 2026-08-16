# Building a real Jarvis: the definitive desktop agent architecture guide

**The core problem with CARTER OS isn't the LLM — it's the architecture.** Modern desktop agents that achieve human-level performance (Agent S3 at 72.6% on OSWorld, UFO2 across 20+ Windows apps) share a decisive structural pattern: they separate planning from execution, wrap LLM decisions in deterministic state machines, and treat GUI interaction as a last resort behind native APIs. Your agent fails on simple tasks because it asks the LLM to improvise what should be deterministic operations. The fix is a **Planner → Capability Router → Deterministic Executor → Verifier** pipeline where the LLM only handles intent parsing and plan generation, while everything else runs through validated, typed handlers. This report synthesizes findings from every major desktop agent project (2024–2026), model benchmarks, runtime comparisons, and voice pipeline designs into an actionable blueprint for building a real Jarvis on Windows 11 with 16GB VRAM.

---

## A. The correct architecture is planner-executor-verifier, not a single loop

The single observe-think-act loop that most hobby agents use (and that CARTER OS likely uses) is the architecture with the lowest reliability. Every production-grade desktop agent in 2024–2026 has converged on a multi-component design. The evidence is unambiguous.

**Microsoft UFO2** (April 2025) implements a dual-agent hierarchy: a **HostAgent** orchestrates at the desktop level — parsing goals, selecting applications, steering a global finite-state machine — while per-application **AppAgents** execute within each app using a ReAct loop with hybrid control detection. The critical innovation is the **Puppeteer executor** that chooses between native APIs (COM automation for Office, CLI for system ops) and GUI actions (click, type, scroll) as fallback. Actions route through **MCP servers** — WordCOMExecutor, ExcelCOMExecutor, CommandLineExecutor, HardwareExecutor — each providing typed tool interfaces. This means adding a new application adds a new MCP server without modifying core code.

**OS-Copilot/FRIDAY** uses a three-component Planner → Configurator → Actor design. The Planner decomposes tasks into a DAG of subtasks. The Configurator acts as a memory hub (declarative, procedural, working memory) that retrieves relevant tools and context. The Actor runs an **Executor-Critic-Refiner loop** with up to 3 retry cycles per subtask. FRIDAY's defining feature is **self-directed learning**: it autonomously generates curricula, solves them by trial-and-error, and accumulates validated tools (scored 0–10, preserved if >8) in procedural memory. Starting from just 4 base tools, it bootstrapped to 60% success on spreadsheet tasks.

**Agent S2/S3** (Simular AI) takes the compositional approach furthest by separating the planning model (generalist LLM) from the grounding model (specialist like UI-TARS-7B). Agent S3 was the **first system to surpass human performance on OSWorld** at 72.6%, proving that the generalist-specialist split outperforms any single monolithic model.

The consensus architecture looks like this:

```
User Request
    ↓
[PLANNER] ← LLM-driven: decomposes into subtask DAG
    ↓
[CAPABILITY ROUTER] ← Deterministic: matches subtask → handler
    ↓ (prefers API/CLI, falls back to GUI)
[EXECUTOR] ← Hybrid: deterministic handlers + LLM-guided GUI
    ↓
[VERIFIER] ← Hybrid: deterministic checks + LLM critic
    ↓
[MEMORY UPDATE] ← Store successful trajectories, update skill library
```

**What must be deterministic** (never LLM-improvised): file operations, system commands, process management, COM/API calls, state machine transitions, safety gates, schema validation of LLM outputs. **What should be LLM-driven**: intent parsing, plan generation, visual perception, error analysis, deciding which tool to use. The key principle is that the LLM proposes structured actions via function calling, and deterministic code validates and executes them. **Structured output everywhere** — every LLM call returns schema-validated JSON, never free-form text that requires parsing.

---

## B. Capability design: MCP servers and hybrid API-GUI execution

The capability layer is where CARTER OS needs the most radical redesign. The goal is a **Capability Core** with deterministic handlers organized by domain, where adding application support never requires modifying the core agent loop.

**Three proven abstraction patterns exist.** UFO2's MCP Server architecture gives each domain its own typed tool interface — the LLM selects which server to invoke via structured output, and new applications add a new server. OS-Copilot's self-generated tools approach has the LLM create Python classes at runtime, validate them via a critic, and store them for reuse — avoiding hardcoding entirely but requiring robust validation. Agent S2's plugin registry with fallback registers specialist expert modules for specific tasks while generic GUI interaction serves as the universal fallback.

The recommended capability structure for CARTER OS:

```
CapabilityCore/
├── SystemInfo/     → WMI queries, sysinfo CLI (fully deterministic)
├── FileSystem/     → os/shutil/pathlib (fully deterministic)
├── Browser/        → Playwright/CDP programmatic + visual fallback
├── ProcessWindow/  → Win32 API: enumerate, focus, resize, close
├── Audio/          → sounddevice, system mixer APIs
├── OfficeApps/     → COM automation (Word, Excel, PowerPoint)
├── Terminal/       → subprocess with validated commands
├── Downloads/      → urllib/requests with safety checks
└── GUI_Fallback/   → UIA tree query + OmniParser + mouse/keyboard
```

**The decision tree for execution method**: If a native API exists for the operation → use it (deterministic, fast, doesn't steal screen focus). If not → query the UIA accessibility tree for the target control. If UIA finds it → interact via pywinauto patterns (Invoke, Toggle, Select). If UIA misses it → fall back to vision (OmniParser → SoM overlay → LLM selects element → coordinate click). This cascading approach means **90%+ of standard Windows app interactions never touch the vision pipeline at all**.

---

## C. GUI interaction: UIA-first with surgical vision fallback

The debate between UI Automation and vision-first approaches is settled. **Hybrid UIA-first is definitively superior**, and UFO2 proved it with 10% higher task completion than the best vision-only agents.

**Windows UI Automation provides** programmatic access to the accessibility tree: control type, label, bounding box, enabled/visible state, and automation patterns (Invoke, Toggle, SelectionItem, ExpandCollapse). UIA queries complete in **10–50ms**, are deterministic, and provide stable identifiers. Via `pywinauto` (UIA backend) or direct `comtypes` access, UIA covers WPF, WinForms, standard Win32, Office apps, and most UWP/XAML applications with perfect reliability.

**UIA fails in specific, predictable scenarios**: custom-drawn controls (DirectX/OpenGL games, CAD tools), Electron apps without `--force-renderer-accessibility`, web content inside browsers, Adobe Creative Suite canvases, and some WinUI 3 components. For these gaps, vision fills in surgically rather than replacing UIA wholesale.

**The optimal perception pipeline for 16GB VRAM**:

1. **Screenshot capture** (~5ms) via Windows.Graphics.Capture API
2. **Change detection** (~2ms) via pixel diff against cached frame — skip re-analysis if <5% changed
3. **UIA tree query** (~10–50ms) for the active window — get all visible, enabled controls with labels and bounding boxes
4. **If UIA covers the task** (most standard apps): send control list to text LLM → LLM selects action by control ID → execute via pywinauto. Total: **<100ms perception**
5. **If UIA is insufficient**: run OCR on screenshot (~50–200ms via PaddleOCR on CPU or Windows OCR API at zero VRAM cost)
6. **If still insufficient**: run **OmniParser v2** (~0.8s, ~2–3 GB VRAM) — YOLO detector + Florence-2 captioner detects all interactable elements invisible to UIA
7. **Merge** UIA controls + OmniParser detections via IoU deduplication → apply **Set-of-Marks** numbered overlays → send annotated screenshot to LLM

**OmniParser v2 is the right vision component** for 16GB VRAM. At ~2–3 GB, it fits alongside a 14B text model (8–9 GB at INT4) with room to spare. It achieved **39.6% on ScreenSpot-Pro** with GPT-4o — the hardest GUI grounding benchmark where targets are 0.07% of screen area. Dedicated GUI grounding models like UI-TARS-7B achieve higher accuracy but consume 14–17 GB at FP16, making them impossible to co-load with a text model. Smaller alternatives worth evaluating include **Qwen-GUI-3B** (28.7% on ScreenSpot-Pro, ~2 GB at INT4) and **GUI-Eyes-3B** (44.8% on ScreenSpot-Pro with tool-augmented perception, ~2 GB at INT4).

**Never ask the LLM to predict raw pixel coordinates.** Always ground through structured element lists — UIA control IDs, OmniParser bounding boxes, or OCR text positions. The SoM prompting approach (numbered boxes on screenshots) eliminates coordinate hallucination and is used by every top-performing system.

---

## D. The best local models for a 16GB VRAM desktop agent

For agentic desktop tasks, **instruction following and tool calling reliability matter far more than raw reasoning benchmarks**. A model scoring 96% on Math500 but 22% on IFBench (like DeepSeek R1 distills) will constantly break your agent's structured output pipeline. The priority ranking for model selection is: (1) native function calling support, (2) instruction following (IFBench), (3) structured output reliability, (4) code generation quality, (5) reasoning depth.

### Primary recommendation: Qwen3 14B

**Qwen3 14B** fits the 16GB VRAM constraint well at **~9.2 GB (Q4_K_M, 4K context)** and offers hybrid thinking/non-thinking modes. Tool calling works via Hermes-style templates with the Qwen-Agent framework providing canonical implementation including MCP support. Key benchmarks: MMLU-Pro 77.4%, Math500 96.1%, LiveCodeBench 52.3% in reasoning mode. The dual-mode capability lets you toggle between fast non-thinking responses for simple routing and deep reasoning for complex planning — a built-in fast/slow brain.

### Strong alternative: Mistral Small 3.1 24B

**Mistral Small 3.1** has the **best native function calling** among open models, explicitly designed for low-latency tool use with a dedicated `--tool-call-parser mistral` flag in vLLM. At Q4_K_M GGUF, it fits 16GB but with tight context (~16–19K tokens). On an RTX 4080, it achieves **70 tok/s at 19K context** — fast enough for real-time agent use. Choose this when function calling reliability is the absolute priority.

### Best instruction follower: Phi-4-Reasoning 14B

**Phi-4-Reasoning** achieves **83.4% on IFBench** — the highest in its class by a wide margin (vs Qwen3's 40%, DeepSeek R1's 22%). Its structured chain-of-thought with parseable `<think>` blocks makes it excellent for agent integration where you need predictable, compliant outputs. At ~9 GB (Q4_K_M), it fits comfortably. The tradeoff is a shorter default context (16K) and less refined native tool calling compared to Qwen3 or Mistral.

### Dual-brain configuration that fits 16GB

Load both models simultaneously:

- **Fast brain**: Phi-4-mini 3.8B at Q4 (~3.5 GB) — handles simple routing, classification, basic tool calls with native function calling support
- **Complex brain**: Qwen3 14B at Q4 (~9.2 GB) — handles multi-step reasoning, code generation, complex planning
- **Total**: ~12.7 GB, leaving headroom for KV cache and OmniParser

A task complexity classifier in the fast model determines escalation. Simple commands ("open Notepad," "what time is it") stay on the 3.8B model at 50+ tok/s. Complex multi-step tasks ("research X, create a summary document, and email it") route to the 14B.

### Models to avoid for desktop agents

**DeepSeek R1 distills** (any size): 22% IFBench, no tool calling support, prone to language mixing — terrible for structured agent workflows despite strong math reasoning. **Gemma 3 12B**: 13.7% LiveCodeBench, insufficient intelligence for agent tasks. **Any model at Q2/Q3 quantization**: severe quality degradation makes agents unreliable. **70B+ models on 16GB**: heavy CPU offloading drops to 8–12 tok/s, unusable for interactive response.

### Hybrid local + cloud

Default to local for all queries involving sensitive data (screen content, file paths, personal information). Route to cloud (Claude Sonnet, GPT-4) only for highest-complexity multi-step planning where local models demonstrate low confidence. Implement via a confidence-based router: if the local model's structured output fails validation or self-assessed confidence is below threshold, escalate. Expected split: **85% local, 15% cloud**, achieving ~60% cost reduction vs pure cloud.

---

## E. Runtime recommendation: llama.cpp server for maximum control

### The winner for Windows desktop agents: llama-server

**llama.cpp's server** (`llama-server`) provides the best combination of performance, structured output, and Windows compatibility for a real-time desktop agent. Key advantages:

- **Native Windows builds** with pre-compiled binaries, zero wrapper overhead
- **Best structured output**: GBNF grammar system with JSON schema auto-conversion guarantees 100% valid JSON
- **Best speculative decoding**: multiple modes including draftless ngram-mod (no extra VRAM)
- **Prompt caching enabled by default**: ~23% latency reduction for iterative agent queries with shared system prompts
- **Quantized KV cache** (`-ctk q8_0 -ctv q8_0`): halves KV cache VRAM, enabling larger context within 16GB
- **Flash attention** support, continuous batching, full OpenAI API compatibility

Setup command for a 14B agent:
```bash
llama-server -m qwen3-14b-Q4_K_M.gguf -ngl 99 -c 8192 -fa \
  -ctk q8_0 -ctv q8_0 --port 8080 --host 127.0.0.1 --jinja
```

Expected performance: **30–45 tok/s generation** for 14B Q4_K_M on an RTX 4060 Ti 16GB class GPU.

### Runner-up: LM Studio

Choose LM Studio over raw llama-server if you value developer experience: Python/JS SDKs with `.act()` for agentic workflows, CLI daemon mode (`lms daemon up`), built-in tool calling with MCP support, `/v1/responses` API for stateful conversations, and VRAM estimation before loading. Same llama.cpp backend, so performance is nearly identical.

### Ollama: fine for prototyping, suboptimal for production

Ollama adds 10–30% overhead vs raw llama.cpp due to its Go wrapper. Under concurrent load, inter-token latency becomes erratic with head-of-line blocking. Prefix caching works (80%+ cache hit rates) but throughput saturates quickly. Use it for rapid prototyping; graduate to llama-server or LM Studio for production.

### TabbyAPI for maximum quality-per-bit

If model quality is the priority over structured output guarantees, **TabbyAPI + ExLlamaV2** with EXL2 quantization extracts more quality per bit than GGUF. EXL2 offers fine-grained per-layer bit allocation (3–6 bpw), which is excellent for squeezing maximum capability from 16GB. The tradeoff: no built-in grammar-constrained generation, so you rely entirely on the model's instruction-following for JSON. For a critical-reliability agent, this is a risky tradeoff.

### vLLM and SGLang: not for Windows

Both are Linux-first with no native Windows support. SGLang's RadixAttention and XGrammar achieve the best structured output performance (3× faster JSON decoding than alternatives), but requiring WSL2 adds complexity and instability for a desktop agent that needs to interact with native Windows processes. Skip them unless you're running the inference server on a separate Linux machine.

---

## F. Memory: start with SQLite, not vector databases

The most common over-engineering mistake in hobby agent projects is building complex memory systems before the agent can reliably execute single tasks. **Start with the simplest viable memory and add complexity only when measured retrieval quality demands it.**

### Minimal viable memory (build this first)

```
Working Memory (in context window):
├── System prompt with agent persona + behavioral rules (10-15% of tokens)
├── Current task state as compact JSON object (<500 tokens)
├── Last 3-5 conversation turns verbatim
└── Rolling summary of older turns

Persistent Storage (single SQLite file):
├── conversations (FTS5 indexed for keyword search)
├── knowledge (user preferences, facts, with confidence scores)
├── task_history (completed tasks with outcomes + quality scores)
└── skills (validated action recipes, scored 0-10)
```

**Context window budget for 8K tokens**: 10–15% system prompt, 15–20% core memory blocks (user prefs, project context), 15–20% task state and plan, 25–35% dynamically retrieved context (tool docs, past experiences), 15–20% recent conversation, 10–15% reserved for output. This allocation keeps the model focused while preserving essential state.

### Skill library pattern (from OS-Copilot/FRIDAY)

When a task completes successfully, serialize the action sequence as a **recipe** with metadata: task description, app context, step sequence, preconditions, quality score (LLM critic rates 0–10). Store recipes scoring **>8** in the skills table. On future similar tasks, retrieve matching recipes via FTS5 keyword search or embedding similarity, inject as few-shot examples. The LLM decides whether to follow the recipe or deviate. This approach let FRIDAY bootstrap from 4 base tools to mastery across dozens of applications.

### Learning from failures without context pollution

Never inject raw failure traces into future prompts. Instead, extract compact lessons ("When manipulating Excel via UIA and the cell isn't editable, check if the workbook is in Protected View first") and store as semantic memory entries with confidence scores. Apply **confidence decay** — unused entries lose 5% confidence daily, entries accessed recently get boosted, entries below 0.1 threshold get pruned. This keeps the knowledge base fresh without manual maintenance.

### When to add vector search

Add embedding-based retrieval (via **sqlite-vec** extension or **LanceDB**) only when you have >100 stored skills/knowledge entries and FTS5 keyword matching demonstrably misses semantically relevant results. Use **nomic-embed-text v1.5** (~300 MB, 8K token context) via Ollama for local embedding generation. It matches OpenAI text-embedding-3-small quality while running on CPU. For absolute minimalism, all-MiniLM-L6-v2 at 50 MB works.

---

## G. Voice pipeline: achieving conversational Jarvis under 11 GB VRAM

A complete voice pipeline — wake word → VAD → STT → LLM → TTS → speaker — is achievable within the 16GB VRAM budget alongside the text LLM, with total voice components consuming **under 2.5 GB VRAM**.

### TTS: Kokoro for the best quality-to-VRAM ratio

**Kokoro** (82M params, Apache 2.0) achieves **MOS 4.2** at **<1 GB VRAM** with 96× real-time speed on GPU. It runs near real-time on CPU as a fallback. Fourteen built-in voices across 9 languages. Install via `pip install kokoro>=0.8` plus `espeak-ng` on Windows. The limitation is no voice cloning — voices have a neutral quality. For richer emotional expressiveness, **Orpheus TTS** (3B params, Apache 2.0) generates laughing, whispering, and crying at the cost of 3–4 GB VRAM (GGUF quantized) — only viable if your LLM is 8B or smaller.

**Edge TTS** (Microsoft's neural TTS via unofficial WebSocket API) serves as a zero-compute fallback: 300+ voices, streaming, no API key needed, `pip install edge-tts`. Use it when the GPU is saturated or as a resilient backup.

### STT: faster-whisper distil-large-v3 at 1.5 GB

**faster-whisper** with the `distil-large-v3` model at INT8 quantization delivers **2.4% WER** using only **~1.5 GB VRAM**. It transcribes 13 minutes of audio in 22 seconds on an RTX 3070 Ti. The CTranslate2 backend runs 4× faster than OpenAI's original Whisper with less memory. Silero VAD is built in for automatic silence removal. For CPU-only fallback, **whisper.cpp** with the medium model handles real-time transcription without touching the GPU.

### Wake word and VAD

**OpenWakeWord** ships with a pre-trained `"hey_jarvis"` model — no training needed. ONNX models at ~200 KB each, multiple can run simultaneously on CPU with negligible overhead. Custom wake words trainable via Google Colab in under an hour.

**Silero VAD** (1.8 MB, MIT license) processes 30ms audio chunks in <1ms on a single CPU thread via ONNX runtime. Enterprise-grade across 6000+ languages. Integrated into faster-whisper for automatic silence removal.

### Streaming architecture for sub-2-second response

The critical design pattern is **sentence-level chunking with parallel TTS**:

1. LLM streams tokens into a `PunctuatedBufferStreamer`
2. Buffer detects sentence boundaries (`. ! ?`) with minimum 50-char, maximum 200-char chunks
3. Complete sentences push to a thread-safe queue
4. TTS thread consumes sentences and generates audio chunks via Kokoro
5. Audio plays immediately via `sounddevice` while subsequent chunks generate concurrently
6. Silero VAD monitors the microphone continuously during playback for barge-in detection

**Latency budget**: Wake word detection ~80ms → VAD speech-end ~300ms → STT ~200–500ms → LLM time-to-first-token ~200–500ms → sentence accumulation ~200–500ms → TTS first audio ~100–300ms. **Total: ~1.0–2.3 seconds** to first audible response with streaming.

### VRAM budget for full Jarvis stack

| Component | VRAM | When Active |
|---|---|---|
| Text LLM (Qwen3 14B Q4) | ~9 GB | Always loaded |
| STT (faster-whisper distil-large-v3 INT8) | ~1.5 GB | During listening only |
| TTS (Kokoro) | <1 GB | During speaking only |
| OmniParser v2 (on-demand) | ~2–3 GB | During vision fallback |
| VAD + wake word (CPU) | 0 GB | Always running |
| **Total peak** | **~11–13.5 GB** | STT and TTS rarely overlap |

### Interrupt handling

For barge-in detection: run Silero VAD continuously on mic input even during TTS playback. When VAD detects speech >500ms duration (filtering coughs and backchannels), immediately stop TTS playback, clear the audio buffer, cancel pending LLM generation, and transition to listening. For echo cancellation on desktop: the simplest approach is muting the mic input channel during TTS playback. More sophisticated: track the TTS output signal and subtract from mic input (~25ms latency added).

---

## H. Roadmap: phased transformation from current state to full Jarvis

### Phase 1: Deterministic foundation (weeks 1–3)

**Preserve**: your existing Python codebase, Ollama integration, factual verification system (task_state, verified_facts, completion_contract, verification_targets). **Rebuild**: the execution path.

- Implement the **Capability Core** with deterministic handlers for file ops, system info, process/window management, and terminal commands — no LLM involvement in execution
- Switch all LLM calls to **structured output** (JSON schema via Ollama's `response_format` parameter or migrate to llama-server with GBNF grammars)
- Wrap the agent loop in a **finite-state machine**: IDLE → PLANNING → ROUTING → EXECUTING → VERIFYING → COMPLETE/RETRY
- Add the **Capability Router**: a deterministic dispatcher that maps parsed intents to handler functions, with GUI as explicit last-resort fallback
- Migrate from Ollama to **llama-server** for structured output guarantees and prompt caching

**Success metric**: simple tasks (open app, create file, get system info, run terminal command) succeed >95% of the time with zero LLM improvisation in execution.

### Phase 2: GUI perception layer (weeks 4–6)

- Integrate **pywinauto UIA backend** for Window/control enumeration and interaction
- Build the **UIA → OCR → OmniParser** cascading perception pipeline
- Implement **Set-of-Marks** annotation: numbered boxes on screenshots sent to LLM for element selection
- Add **screenshot change detection** and GUI state caching to minimize vision model invocations
- Test against 10 common Windows applications (Settings, File Explorer, Notepad, browser, Office apps)

**Success metric**: agent can interact with standard Windows apps via UIA 90% of the time, falling back to vision only for custom controls.

### Phase 3: Voice pipeline (weeks 7–9)

- Integrate **OpenWakeWord** with `hey_jarvis` model + **Silero VAD** for always-on listening
- Add **faster-whisper** (distil-large-v3 INT8) for speech-to-text
- Add **Kokoro TTS** with sentence-level streaming from LLM output
- Implement the **4-thread async architecture**: audio capture → STT → LLM+TTS → audio playback
- Add barge-in detection and interrupt handling

**Success metric**: complete voice interaction loop under 2.5 seconds latency, reliable wake word activation.

### Phase 4: Memory and learning (weeks 10–12)

- Implement **SQLite-backed persistent memory** with FTS5 indexing
- Add the **skill library**: successful task completions scored by LLM critic, recipes scoring >8 preserved
- Implement **sliding window + summarization** for context management
- Add **failure learning**: extract compact lessons from failures, store as semantic memory with confidence decay
- Optional: add **sqlite-vec** for embedding-based skill retrieval when library exceeds 100 entries

**Success metric**: agent successfully reuses learned recipes for repeated tasks, context window stays within budget on long-running sessions.

### Phase 5: Polish and optimization (weeks 13+)

- Evaluate **dual-brain strategy**: Phi-4-mini for fast routing + Qwen3 14B for complex reasoning
- Add **browser automation** via Playwright/CDP as a dedicated capability (not GUI-based)
- Implement **Office COM automation** handlers for Word, Excel, PowerPoint
- Add hybrid local+cloud fallback with confidence-based routing
- Evaluate newer models as they release (Qwen3.5 series, updated Mistral variants)
- Performance optimization: speculative decoding, KV cache quantization, prefix caching tuning

---

## Conclusion

The gap between CARTER OS and a reliable Jarvis isn't model intelligence — it's architectural discipline. **The single most impactful change is separating what the LLM decides from what deterministic code executes.** UFO2 and Agent S3 prove that wrapping LLM outputs in typed schemas, routing through deterministic dispatchers, and reserving GUI interaction as a fallback behind native APIs transforms desktop agents from impressive demos into reliable tools.

The 16GB VRAM constraint is less limiting than it appears. **Qwen3 14B at Q4_K_M** (~9 GB) plus **OmniParser v2** (~2–3 GB on demand) plus a full voice stack (**Kokoro** <1 GB, **faster-whisper** ~1.5 GB) fits comfortably with headroom. The runtime choice matters — **llama-server** with GBNF grammars guarantees valid structured output, which eliminates an entire class of agent failures caused by malformed LLM responses.

The most underappreciated insight from this research: **OS-Copilot's self-directed learning and skill library pattern is the path to a genuinely improving agent.** Rather than hardcoding handlers for every application, let the agent generate, validate, score, and accumulate tools through experience. A scored skill library with quality-gated preservation (>8/10) naturally builds coverage without manual engineering. This is the mechanism that transforms a narrowly capable agent into something approaching the generalist Jarvis vision — not by making the LLM smarter, but by giving it a growing library of validated, deterministic capabilities to draw from.