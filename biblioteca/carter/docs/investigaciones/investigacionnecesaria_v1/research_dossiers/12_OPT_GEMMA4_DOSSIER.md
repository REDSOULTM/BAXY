# Carter v4 — Optimization Dossier for Gemma 4 E4B-it (UD-IQ2_M) on llama.cpp b9090 CUDA / RTX 4060 Ti 16 GB

> **Bottom line up front:** Gemma 4 IS a real Google release (announced **April 2, 2026**, model card last updated 2026‑04‑17 on ai.google.dev). The Unsloth GGUF `gemma-4-E4B-it-UD-IQ2_M.gguf` (3.55 GB) is the correct artifact, the `mmproj` reporting `projector: gemma4a` is consistent with the new audio-capable Gemma 4 vision/audio projector. Run it with `temp=1.0, top_p=0.95, top_k=64`, `--jinja`, `--flash-attn on`, **f16 KV cache** (NOT q8_0 — Gemma is the most KV-quant-sensitive family tested, see Axis 5), `-c 16384`, thinking disabled by default for a Jarvis-style assistant (E4B does not emit empty thought blocks when thinking is off, so it is safe). The biggest risks vs. your qwen3 baseline are the **`<|"|>` string-delimiter token leaking into JSON** (issue #21316, partially fixed by PRs #21326/#21343/#21418 — verify on b9090) and the **multi-newline tokenization bug** (PR #21406). If your 91.7% PASS bench is still green after switching, ship; if not, the most likely culprit is the JSON delimiter leak, not sampling.

---

## TL;DR (3 bullets)

- **Gemma 4 E4B-it exists** (Google DeepMind, Apache 2.0, Apr 2 2026); use Google's **canonical sampling** `temp=1.0 / top_p=0.95 / top_k=64`, `repeat_penalty=1.0`, NO presence penalty. Community testing (HF discussion on the 26B variant) actually went *higher* (T=1.5) for coding — there is **no qwen3-style post-DPO calibration mismatch**; lowering temperature does not help and can hurt.
- **Three Gemma-4-specific landmines on llama.cpp** you must address: (1) JSON tool-call args contain `<|"|>` delimiter tokens unless PRs #21326+#21343+#21418 are present (b9090 has them); (2) **DO NOT use q8_0/q4_0 KV cache** — Gemma 4 has KL divergence ~5–10× higher than Qwen at the same KV quant (localbench Substack); use **f16 KV** even though you have margin to spare; (3) **disable thinking** for Carter via `--chat-template-kwargs "{\"enable_thinking\":false}"` (E4B is the "good" case — no empty thought block leakage).
- **Decision-ready recommendations:** keep `-c 16384` for Mission, drop to 8192/4096 for Tool/Trivial; use `--flash-attn on` with **f16 K and V** (the SWA+global hybrid breaks under FA-off); keep `--mmproj` loaded only if you actually need vision/audio that turn — it costs ~300–500 MB VRAM; rewrite CORE_PROMPT to ~900 tokens hybrid English/Spanish; for DESTRUCTIVE_STRICT use **T=0.6, top_p=0.9, top_k=40, min_p=0.02** (do NOT go to T=0.2 — Gemma 4 was DPO'd at T=1.0 and degrades sharply below ~0.5 per the HF community thread).

---

## Key Findings

### Model verification (the user's first question)
| Claim | Status |
|---|---|
| Gemma 4 is a real Google release | **TRUE.** [blog.google](https://blog.google/innovation-and-ai/technology/developers-tools/gemma-4/) (Apr 2 2026), [deepmind.google/models/gemma/gemma-4](https://deepmind.google/models/gemma/gemma-4/), [ai.google.dev model card 4](https://ai.google.dev/gemma/docs/core/model_card_4) (last updated 2026-04-17). Family: E2B, E4B, 26B A4B, 31B; Apache 2.0. |
| `gemma-4-E4B-it-UD-IQ2_M.gguf` exists at 3.55 GB | **TRUE.** Confirmed at [huggingface.co/unsloth/gemma-4-E4B-it-GGUF/tree/main](https://huggingface.co/unsloth/gemma-4-E4B-it-GGUF/tree/main), filename and size match (3.55 GB). |
| `projector: gemma4a` in mmproj | **Consistent.** Gemma 4 E2B/E4B include native audio (vision encoder ~150M, audio encoder ~300M). The "a" suffix tracks the audio-capable projector variant; this is *not* a sign of a wrong file. |
| llama.cpp issue #21316 is real | **TRUE.** [github.com/ggml-org/llama.cpp/issues/21316](https://github.com/ggml-org/llama.cpp/issues/21316) — Gemma 4 tool calls leak `<|"|>` delimiter tokens into JSON args. Fix PRs: #21326 (template), #21343 (tokenizer), #21390 (final_logit_softcapping), #21406 (newline split), #21418 (specialized parser), #21500 (BOS), #21488 (BPE byte tokens), #21566 (CUDA buffer overlap). |
| Build b9090 contains all the Gemma 4 fixes | **PROBABLY YES, but VERIFY.** b9090 was built 2026-05-09; all listed PRs landed on master in April 2026. Run a quick smoke test (Axis 8 below) — if you see literal `<|\"|>` substrings inside `arguments`, you got an unfixed build. |

### Architectural facts that drive every recommendation
- **Hybrid attention** (interleaved local sliding-window + full global, final layer always global). E4B has 42 layers, sliding window = 512 tokens, context = 128K, vocab = 262K, RoPE base 1,000,000 / SWA RoPE base 10,000, final logit soft-capping = 30.0.
- **Native function calling** uses six dedicated tokens: `<|tool>`/`<tool|>`, `<|tool_call>`/`<tool_call|>`, `<|tool_response>`/`<tool_response|>`, plus the **string delimiter `<|"|>`** that wraps every string value in tool args. `<|tool_response>` doubles as a stop sequence.
- **Thinking** uses `<|think|>` placed at the **start of the system prompt** to enable; remove to disable. **E4B (and E2B) does NOT emit an empty `<|channel>thought\n<channel|>` block when disabled** — only the larger 26B/31B variants do. Good for Carter: clean output by default.
- **Native system role** is supported in Gemma 4 (new vs. Gemma 3). Use it.
- **EOS/turn end token** is `<turn|>` (single token id 106 in the GGUF metadata). The BOS `<bos>` is auto-emitted by the chat template.
- **MMPROJ matters for VRAM:** the audio+vision projector for E4B is ~300–500 MB. If Carter's *current* turn is text-only, omit `--mmproj` — it doesn't help.

### Tool-calling correctness (the only thing that matters for Jarvis)
- Google publishes BFCL-adjacent numbers as **τ²-bench**: 31B = 76.9 %, 26B A4B = 68.2 %, **E4B = 42.2 %**, E2B = 24.5 % (model card). These are the closest published proxies for BFCL multi-turn for Gemma 4. **No public BFCL multi-turn entry for Gemma 4 E4B exists as of May 9 2026** — the user is correct to be skeptical; treat E4B as a **~42 %** baseline on agentic tool use and budget for 2–3 retries.
- Quantization to IQ2_M will degrade this further. There is no published number for E4B at IQ2_M; community KLD work (localbench, Unsloth) shows Gemma 4 is sensitive to weight quantization. Expect a measurable but not fatal drop. **Validate with your bench, do not trust theory.**
- Tool-calling format inside the model is a **custom dict-of-tokens**, not JSON: `<|tool_call>call:get_weather{location:<|"|>London<|"|>}<tool_call|>`. llama.cpp's specialized Gemma 4 parser (PR #21418, chat format `peg-gemma4` in logs) converts this to OpenAI-format tool_calls in `/v1/chat/completions`. **You don't need to handle it manually if `--jinja` is on and the parser is registered.**

### Build b9090 specifics
- Released **2026-05-09 12:45 UTC**, commit `5757c4d`, Windows x64 (CUDA 12) prebuilt available. The b9090 release notes themselves are mostly cmake/BoringSSL — the *Gemma 4 fixes* landed in the b863x → b870x window in April. b9090 inherits all of them. There are still **open** Gemma 4 issues at b8975+ (issue #22527 — 31B SWA crash on RTX 4060 Ti 16 GB with FA off; issue #21384 — array-of-string args still serialize as string in some cases). **For E4B specifically, no open critical bug as of b9090.**

---

## Details — by the 8 axes

### Axis 1 — Sampling for function calling

**Official (model card):** `temperature=1.0, top_p=0.95, top_k=64`. No `min_p` recommendation. **Disable repetition/presence penalty** (or set to 1.0). Apply across all use cases — Google explicitly says this is a *standardized* config.

**Tool-calling specific:** Same as text. There is **no published evidence of qwen3-style calibration mismatch** (where T=0.1 broke tool emission post-DPO). The HF community thread on the 26B variant ([discussions/21](https://huggingface.co/unsloth/gemma-4-26B-A4B-it-GGUF/discussions/21)) found Gemma 4 actually **gets worse at lower T**, e.g. lowering to 0.3 broke previously-working code generations; pushing to T=1.5 helped on some code tasks. **Do not lower T below 0.7 for Carter.** For deterministic tool emission, prefer narrowing top_k/top_p over lowering T.

**BFCL multi-turn:** No public entry for Gemma 4 E4B. Use τ²-bench from Google's card (E4B = 42.2 %) as the closest proxy. **Honest:** until you run your own bench at your IQ2_M quant, you don't know the real number — the user is right to ask for measurement, not theory.

### Axis 2 — Special tokens, stops, chat template

**Token inventory** (from [Gemma 4 prompt formatting doc](https://ai.google.dev/gemma/docs/core/prompt-formatting-gemma4)):

| Category | Tokens |
|---|---|
| Turn delimiters | `<|turn>` (start), `<turn|>` (end, also EOS) |
| Roles | `system`, `user`, `model` (literal text after `<|turn>`) |
| Multimodal | `<|image|>`, `<|audio|>`, `<|video|>` (placeholders); `<|image>...<image|>`, `<|audio>...<audio|>` (embedding wrappers) |
| Thinking | `<|think|>` (system-prompt activator), `<|channel>thought\n...<channel|>` (output) |
| Tools | `<|tool>declaration:NAME{...}<tool|>` (in system), `<|tool_call>call:NAME{args}<tool_call|>` (model), `<|tool_response>response:NAME{result}<tool_response|>` (developer) |
| String delimiter | `<|"|>` — wraps every string value in tool args |

**Stops:**
- **Mandatory** for the inference loop: `<turn|>` (it IS the EOS, set automatically by GGUF metadata; do not add manually unless you also strip BOS/EOOS handling).
- **Implicit additional stop:** `<|tool_response>` — Google's docs say it acts as an extra stop sequence so the engine pauses for tool execution. llama.cpp's `peg-gemma4` parser handles this internally.
- **Do NOT add as stops:** `<channel|>`, `<tool_call|>`, `<tool|>`. Adding `<channel|>` will break thinking-mode prematurely; adding `<tool_call|>` will truncate the call before the parser can consume it.

**Chat template — three options:**
1. **Unsloth GGUF embedded template (default).** As of the 2026-04 update, Unsloth ships Google's official template baked into the GGUF metadata. **Use this.** It works with `--jinja` and llama.cpp's specialized `peg-gemma4` parser.
2. **`tool_chat_template_gemma4.jinja`** (vLLM/llama.cpp examples dir, also derived from Google). Same content, externally pinned. Use if you ever need to override.
3. **Custom `gemma4_jinja` (asf0 style "anti-thinking-leak"):** unnecessary on E4B, which doesn't leak. Skip unless you're running 26B/31B.

**Known template bug** (issue around PR #21326 thread): older Gemma 4 GGUF templates had `value['type'] | upper` that crashes when a JSON-Schema parameter type is an array like `["string","null"]`. **Re-download the GGUF if it predates April 11 2026** (the user's file dated "5 days ago" on HF as of recently is the post-fix version — should be fine).

### Axis 3 — Optimal llama-server flags for E4B / RTX 4060 Ti

| Flag | Recommended value | Rationale |
|---|---|---|
| `--jinja` | **ON** | Required for Gemma 4 tool template + `peg-gemma4` parser. |
| `-ngl` | **99** | Full offload. E4B at IQ2_M is ~3.55 GB; with f16 KV at 16K ctx the total is ~5–6 GB, comfortable on 16 GB. |
| `-c` | **16384** for Mission, **8192** Tool, **4096** Trivial | E4B max is 128K but quality and tool reliability degrade well before that on a small model. |
| `--cache-ram` | **0** (disable) | Carter is single-user, single-slot; the 8 GB default prompt cache competes with VRAM headroom and the log line is misleading (issue #22127). Disable it unless you measure benefit on your bench. |
| `-t / --threads` | **6** (= P-cores - 1 on a typical 4060 Ti box) | CPU only matters for prompt tokenization and embeddings extraction; full GPU offload makes thread count low-impact. |
| `--threads-batch` | **6** | Same. |
| `-b / --batch-size` | **2048** | Default; matches Gemma 4 examples. |
| `-ub / --ubatch-size` | **512** | Lower ubatch = less VRAM spike during prefill of long system prompt. |
| `-fa / --flash-attn` | **on** | **Required** on E4B because the SWA + global hybrid pads V cache to max head dim when FA is off, blowing VRAM (issue #22527, on your exact GPU). FA-on is also stable on E4B (the 31B FA crash is dense-model-only). |
| `--cache-type-k` | **f16** | See Axis 5. q8_0 raises Gemma KL divergence to ~0.108 vs ~0.04 for Qwen at the same setting. f16 is non-negotiable until you measure otherwise. |
| `--cache-type-v` | **f16** | Same. |
| `--no-warmup` | **OFF** (i.e., do warm up) | The first request after load is otherwise ~3× slower; Carter's <5 s p99 trivial budget will miss without warmup. |
| `--reasoning-budget` | **0** for Carter (no thinking) | Cuts thinking off; pair with `--chat-template-kwargs "{\"enable_thinking\":false}"` for belt-and-braces. On E4B this is mostly cosmetic since the small model doesn't leak. |
| `--chat-template-kwargs` | `"{\"enable_thinking\":false}"` (PowerShell-escaped) | Authoritative way to suppress `<|think|>`. Use it. |
| `--mmproj` | **omit** for v1 of Carter | Loads ~300–500 MB of vision+audio encoder weights even when unused this turn. Omit until you actually do vision/audio. The user's exclusion list confirms this is OK. |
| `--reasoning` | **off** | Belt for the braces. |
| `--alias` | `"carter-v4-gemma4"` | For nice OpenAI-API logging. |
| `--api-key` | optional | Set if you bind to 0.0.0.0. |
| `--port` | 8080 | Default. |
| `--host` | 127.0.0.1 | Loopback only for security. |
| `--no-context-shift` | **ON** | Carter's compaction layer handles eviction; context shift can corrupt SWA caches on Gemma. |
| `--checkpoint-every-n-tokens` | **2048** | Allows fast partial replays after compaction. |
| `--cache-reuse` | **256** | Token-level prefix reuse; helps the static system prompt skip reprocessing across turns. (Discussion #22354.) |

**New flags introduced after the qwen3 May-2026 research that matter:**
- `--cache-ram N` (PR #16391) — explicit prompt-cache size cap, can disable with 0.
- `--cache-idle-slots` — auto-clears stale slots; safe with `--cache-ram>0` only.
- `--reasoning-budget N` and `--reasoning-budget-message` (PR #13771) — hard cap on thinking tokens.
- `--reasoning {auto,on,off}` — orthogonal to `enable_thinking`; `off` forces parser to treat output as final.
- `--flash-attn` now takes `on|off|auto` (was a bool).
- `--checkpoint-every-n-tokens` — periodic KV checkpoint for fast replay (matters when compacting).
- `--sleep-idle-seconds` — model auto-unload to RAM (PR #18228); set to 0 to keep model resident (Ollama keep_alive=-1 equivalent).

### Axis 4 — System prompt for Gemma 4 (HYBRID English/Spanish)

**Style Gemma 4 follows best:** Google trained on English instruction data with a strong `system` role; the model is exceptionally instruction-following ("LOW thinking" can be elicited by SI alone — see prompt-formatting doc). Use **direct English imperatives** for rules; Gemma 4 respects negation ("do not …") structurally without needing a positive contrastive twin most of the time, but for *safety-critical negations* (DESTRUCTIVE rule), give one negative + one positive example to anchor.

**No measurable "few-shot collapse" reported on Gemma 4** (in contrast to qwen3 / Tang et al. 2025). 2–4 contrastive few-shots is the sweet spot.

**Tool descriptions:** Gemma 4's `apply_chat_template(tools=[...])` produces the canonical `<|tool>declaration:...<tool|>` block. **Do NOT also describe tools inline in the system prompt** — that doubles the token cost and confuses the parser. Pass tools via the `tools=[...]` API parameter only.

**Optimal size for Carter:**
| Length | Expected behavior |
|---|---|
| ~800 tokens | Best latency, slight risk of forgetting rare rules |
| **~900–1100 tokens (recommended)** | **Sweet spot for E4B at IQ2_M** |
| ~1500 tokens | Marginal value; latency ↑ |
| ~3000 tokens | Diminishing returns; potential rule-conflict noise |

E4B is small enough that long prompts crowd out attention to the user message. Aim ~900.

### Axis 5 — Compaction and context management

- **Degradation point:** community KLD work and tau²-bench numbers suggest small Gemma 4 models start to wobble around **50–60 % of declared context** on agentic tasks (similar to qwen3). For E4B at 16 K declared, expect quality wobble starting ~9–10 K. Keep working context under **10 K** for tool-calling reliability; trigger compaction at ~8 K.
- **KV cache type — the most important finding:** [localbench substack](https://localbench.substack.com/p/kv-cache-quantization-benchmark) measured **Gemma 4 26B A4B at q8_0 KV cache: KL = 0.377** vs **Qwen 3.6 q8_0: KL < 0.04**. q4_0 is worse. "q8_0 is practically lossless" is **wrong for Gemma**. **Use f16 K and V on E4B.** If VRAM ever gets tight, drop `-c` to 8192 with f16 KV before you drop KV precision.
- **Flash attention with Gemma 4:** stable on E4B with f16 KV in b9090 per all reports we found (the open #22527 SWA crash is **31B-specific**). Stable enough to ship; if you ever see "illegal memory access after SWA KV cache checkpoint", that's the bug — turn off `--checkpoint-every-n-tokens` and report.
- **Hallucinations with FA on/off:** no Gemma-4-specific hallucination reports tied to FA toggling on E4B in our research window. FA-off is *worse* (VRAM blowup), not better.
- **Always `-c 16384`?** No — drop to 4 K for trivial chat to halve KV VRAM and TTFT. The dynamic config in Axis 7 does this.

### Axis 6 — Env vars and runtime config

- `LLAMA_ARG_*` env vars (e.g. `LLAMA_ARG_CACHE_RAM=0`, `LLAMA_ARG_FLASH_ATTN=on`, `LLAMA_ARG_THINK=none`, `LLAMA_ARG_CHAT_TEMPLATE_FILE=...`) override CLI; useful in service config. (See [tools/server/README.md](https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md).)
- `GGML_CUDA_NO_GRAPHS=1` — set this if you see CUDA graph capture errors on Gemma 4. Multiple recent issues mention CUDA graphs interacting badly with the SWA path on certain drivers.
- **Do NOT use CUDA 13.2 runtime** — Unsloth explicitly warns: "Do NOT use CUDA 13.2 runtime for any GGUF as it will cause poor outputs." Use CUDA 12.x. b9090 Windows pre-built is "CUDA 12" — good.
- `GGML_CUDA_FORCE_MMQ=1` — leave **off** on Ada (4060 Ti); MMQ kernels are slower than tensor-core matmul on this gen.
- **Keep model resident:** llama-server keeps the model loaded for the process lifetime. The new `--sleep-idle-seconds` flag will unload after N seconds; set to **0 (disabled)** or simply omit. Ollama's `keep_alive=-1` equivalent = "don't pass `--sleep-idle-seconds`."

### Axis 7 — Per-turn profile tuning

See drop-in code section. Three archetypes calibrated to the Alexa-tier latency budget on a 4060 Ti running E4B at IQ2_M (~50 tok/s decode per Artificial Analysis median):
- **Trivial:** 4 K ctx, T=1.0, top_k=64, num_predict=128, no thinking → **<5 s p99** comfortable.
- **Tool:** 8 K ctx, T=1.0 (per Google), top_k=64, num_predict=384, no thinking → **<8 s p99** if first call succeeds.
- **Mission:** 16 K ctx, T=1.0, num_predict=768, no thinking, but allow up to 4 tool retries → 4-tool budget under **<20 s** is realistic at 50 tok/s decode if you keep thinking off.

### Axis 8 — Destructive intent detector

Carter's qwen3 numbers (T=0.2, top_p=0.8, top_k=20, min_p=0.05) **will likely hurt Gemma 4** because the HF community thread shows Gemma 4 was DPO/RLHF-tuned at T=1.0 and degrades at low T. For determinism without breaking tool emission, **stay closer to canonical**:

- **DESTRUCTIVE_STRICT recommended:** `temperature=0.6, top_p=0.9, top_k=40, min_p=0.02, repeat_penalty=1.0`. This is conservative-but-not-broken: still inside the high-density region of the model's calibrated distribution.
- Gemma 4 *does* respect destructive-intent negations structurally (140+ language pre-training, strong instruction-following), but the response variance under T=1.0 means you should still gate destructive operations behind an **explicit confirmation tool call** (e.g. `confirm_destructive(action, target)`) — solve the safety problem at the system level, not via T=0.2.
- Do **NOT** push to greedy (T=0). Reports across HF discussions and the localbench KLD work show Gemma 4 deteriorates more sharply at greedy than peers.

---

## 1) Drop-in `LlamaCppConfig` dataclass

```python
# Carter_v4/src/carter_v4/llama_cpp_config.py
from dataclasses import dataclass, field
from typing import Literal, Optional

@dataclass(frozen=True)
class LlamaCppConfig:
    # --- Model identity ---
    model_path: str = r"C:\models\unsloth\gemma-4-E4B-it-GGUF\gemma-4-E4B-it-UD-IQ2_M.gguf"
    mmproj_path: Optional[str] = None  # leave None until vision/audio is wired in
    alias: str = "carter-v4-gemma4-E4B-IQ2_M"

    # --- Sampling (Google canonical for Gemma 4) ---
    temperature: float = 1.0
    top_p: float = 0.95
    top_k: int = 64
    min_p: float = 0.0           # Gemma 4 model card does not specify min_p; leave off
    repeat_penalty: float = 1.0  # Unsloth/Google: keep at 1.0 unless you SEE looping
    presence_penalty: float = 0.0
    frequency_penalty: float = 0.0
    seed: int = -1               # random per request

    # --- Context / runtime ---
    n_ctx: int = 16384           # Mission default; per-turn override
    n_predict: int = 768         # Mission default; per-turn override
    n_gpu_layers: int = 99
    n_threads: int = 6
    n_threads_batch: int = 6
    n_batch: int = 2048
    n_ubatch: int = 512

    # --- KV cache ---
    cache_type_k: Literal["f16","q8_0","q4_0"] = "f16"  # DO NOT change for Gemma 4
    cache_type_v: Literal["f16","q8_0","q4_0"] = "f16"
    flash_attn: Literal["on","off","auto"] = "on"

    # --- Server runtime ---
    cache_ram_mib: int = 0           # disable prompt cache (Carter manages context)
    cache_reuse: int = 256           # token-level prefix reuse for static system prompt
    no_context_shift: bool = True
    checkpoint_every_n_tokens: int = 2048
    no_warmup: bool = False          # warmup ON
    sleep_idle_seconds: int = 0      # 0 = keep model resident (Ollama keep_alive=-1)

    # --- Chat / template ---
    jinja: bool = True
    chat_template_kwargs_json: str = '{"enable_thinking":false}'
    reasoning: Literal["on","off","auto"] = "off"
    reasoning_budget: int = 0

    # --- Network ---
    host: str = "127.0.0.1"
    port: int = 8080
    api_key: Optional[str] = None

    # Stops are NOT user-set; the GGUF emits <turn|> as EOS, and llama.cpp's
    # peg-gemma4 parser handles <|tool_response> internally.
    stop_sequences: tuple[str, ...] = field(default_factory=tuple)
```

---

## 2) Stops and chat template

- **Stops to send via API:** **none.** `<turn|>` is the model's EOS via GGUF metadata; `<|tool_response>` is handled by the `peg-gemma4` parser. Adding more breaks tool calling.
- **Chat template:** use the GGUF-embedded template from Unsloth's post-2026-04-11 build. Confirm at startup:

```powershell
# Smoke test: should print "peg-gemma4" in the chat format line
.\llama-server.exe --model $MODEL --jinja -c 4096 -ngl 99 --port 8080 2>&1 | Select-String "Chat format"
```

If you ever need to override (e.g. to patch the array-type `| upper` bug from PR #21326 if the GGUF predates April 11 2026):

```powershell
# Pseudocode: download known-good template and pass file
Invoke-WebRequest -Uri "https://raw.githubusercontent.com/vllm-project/vllm/main/examples/tool_chat_template_gemma4.jinja" -OutFile gemma4.jinja
.\llama-server.exe --model $MODEL --jinja --chat-template-file .\gemma4.jinja ...
```

---

## 3) PowerShell launch command (justified)

```powershell
# Carter v4 — llama-server.exe launch (b9090 CUDA, RTX 4060 Ti 16 GB, Gemma 4 E4B-it IQ2_M)
$env:LLAMA_ARG_CACHE_RAM = "0"            # disable misleading 8192 MiB prompt cache
$env:GGML_CUDA_NO_GRAPHS = "0"            # leave CUDA graphs ON (faster); flip to 1 if you see capture errors

$MODEL  = "C:\models\unsloth\gemma-4-E4B-it-GGUF\gemma-4-E4B-it-UD-IQ2_M.gguf"
$BUILD  = "C:\llama.cpp\b9090\llama-server.exe"

& $BUILD `
    --model        $MODEL `
    --alias        "carter-v4-gemma4-E4B-IQ2_M" `
    --host         127.0.0.1 `
    --port         8080 `
    -ngl           99 `
    -c             16384 `
    -b             2048 `
    -ub            512 `
    --threads      6 `
    --threads-batch 6 `
    --flash-attn   on `
    --cache-type-k f16 `
    --cache-type-v f16 `
    --cache-ram    0 `
    --cache-reuse  256 `
    --no-context-shift `
    --checkpoint-every-n-tokens 2048 `
    --jinja `
    --reasoning    off `
    --reasoning-budget 0 `
    --chat-template-kwargs "{\""enable_thinking\"":false}" `
    --temp         1.0 `
    --top-p        0.95 `
    --top-k        64 `
    --repeat-penalty 1.0
```

**Why each flag:**
- `-ngl 99`: ~3.55 GB model + ~1.2 GB KV @ 16K f16 ≈ 4.8 GB; full offload safe on 16 GB.
- `-c 16384`: Mission upper bound; per-turn profile lowers it.
- `--flash-attn on`: required to avoid V-cache padding blowup on Gemma 4 SWA+global (issue #22527 confirmation).
- `--cache-type-k/v f16`: localbench KLD evidence; q8_0 KV breaks Gemma quality.
- `--cache-ram 0` + `--cache-reuse 256`: skip the redundant prompt cache, but enable token-level prefix reuse so the static system prompt is reused turn-to-turn (Discussion #22354 pattern).
- `--no-context-shift`: Carter compacts; context-shift on Gemma SWA risks corrupted KV.
- `--jinja` + `--chat-template-kwargs`: required for Gemma 4 tool template; the kwargs disable thinking authoritatively.
- `--reasoning off` + `--reasoning-budget 0`: belt-and-braces; on E4B is mostly cosmetic but safe.
- No `--mmproj`: text-only first; add when wiring vision/audio.

---

## 4) Refined `CORE_PROMPT` (~900 tokens, hybrid English/Spanish)

Paste this as the value of `CORE_PROMPT` in `prompt.py`. Tool list comes from the OpenAI `tools=[...]` parameter; do NOT inline tools here.

```text
You are Carter, a Windows 11 voice assistant for a single trusted user. Speak Rioplatense Spanish to the user. Reason silently in English. Always answer in Spanish unless the user asks for another language.

## CORE RULES (strict, English, do not paraphrase)

1. HONESTY. If you do not know, say "no lo sé" and stop. Do not invent file paths, app names, URLs, IDs, dates, or quantities. If a tool returns no data, say so.
2. MULTI-STEP. If the user request needs more than one tool call, plan briefly in your hidden reasoning, then execute the tools one at a time, waiting for each tool_response before the next call.
3. NEGATION. When the user says "no abrir X", "no borrar Y", "no enviar Z" — never call the tool that would do that, even partially, even as a draft.
4. DESTRUCTIVE. Operations that delete, format, shutdown, kill processes, overwrite without backup, send messages to others, or move money are DESTRUCTIVE. For every DESTRUCTIVE action you must first call confirm_destructive(action, target, reason) and wait. If the user did not ask explicitly, refuse.
5. SCOPE. You only act on this Windows 11 machine and only via the registered tools. You do not browse the open internet unless web_search is provided this turn. You do not execute arbitrary code unless run_command is explicitly listed.
6. NO INVENTED TOOLS. Use only tools provided in the current tools=[...] payload. If the right tool is missing, say "no tengo herramienta para eso" and stop.
7. SHORT ANSWERS. Default to one or two sentences. Expand only if the user asks "explicame" or "más detalle".
8. NO THINKING TAGS. Never output <|channel>, <|think|>, or any of the model's special tokens to the user. Final user-visible text must be plain Spanish.

## EXAMPLES (Rioplatense Spanish, contrastive)

User: "che, ¿qué hora es?"
Assistant (correct): calls get_time() → answers "Son las 14:32."
Assistant (wrong): inventing a time without the tool → forbidden by rule 1.

User: "abrime el navegador y borrá la carpeta Descargas"
Assistant (correct): calls open_app("browser"); then for the deletion calls confirm_destructive("delete_folder","C:/Users/.../Downloads","user request") and waits.
Assistant (wrong): calling delete_folder directly → forbidden by rule 4.

User: "agendame una reunión mañana a las 10, pero no me mandes el mail al equipo todavía"
Assistant (correct): calls calendar_create(...); does NOT call send_email. Confirms only the calendar action.
Assistant (wrong): also sending the email → forbidden by rule 3 (negation).

User: "¿cómo se configura el firewall en Linux?"
Assistant (correct): "no lo sé con seguridad para Linux desde acá; este equipo es Windows 11. ¿Querés que busque en Windows?" → forbidden to invent a Linux answer (rule 1).

User: "buscá en mis documentos el PDF de la factura de marzo"
Assistant (correct): calls search_files(query="factura marzo", ext="pdf", folder="Documents") and returns the top match.

## ERROR MESSAGES (Spanish, user-facing)

- Tool failure: "Disculpame, la herramienta {name} falló: {error_breve}."
- Missing tool: "No tengo herramienta para eso en este turno."
- Refused destructive: "Eso es destructivo. Necesito que me lo confirmes explícitamente antes."
- Unknown answer: "No lo sé."

End of system instructions.
```

**Token estimate: ~880 tokens (Gemma 4 tokenizer, mixed EN/ES).** Within the 900-target band.

Why hybrid works on Gemma 4:
- Rules in English: Gemma 4 instruction-following is strongest in English (model card data mix, English-dominant fine-tune); strict rules in EN reduces interpretation drift.
- Examples in Rioplatense Spanish: anchors output style and dialect (Gemma 4 supports 140+ pre-trained languages, 35+ instruction-tuned — Spanish is in-distribution).
- Tool descriptions in English via `tools=[...]`: matches OpenAI schema and the `peg-gemma4` parser expectation.
- Error messages in Spanish: user-facing.

---

## 5) Per-turn profile drop-in (`turn_profile.py`)

```python
# Carter_v4/src/carter_v4/turn_profile.py
from dataclasses import dataclass
from typing import Literal

@dataclass(frozen=True)
class TurnProfile:
    name: str
    n_ctx: int
    n_predict: int
    temperature: float
    top_p: float
    top_k: int
    min_p: float
    repeat_penalty: float
    enable_thinking: bool
    reasoning_budget: int  # -1 unrestricted, 0 disabled

# --- PRINCIPAL profiles ---

TRIVIAL = TurnProfile(
    name="trivial",
    n_ctx=4096, n_predict=128,
    temperature=1.0, top_p=0.95, top_k=64, min_p=0.0,
    repeat_penalty=1.0,
    enable_thinking=False, reasoning_budget=0,
)

TOOL = TurnProfile(
    name="tool",
    n_ctx=8192, n_predict=384,
    temperature=1.0, top_p=0.95, top_k=64, min_p=0.0,
    repeat_penalty=1.0,
    enable_thinking=False, reasoning_budget=0,
)

MISSION = TurnProfile(
    name="mission",
    n_ctx=16384, n_predict=768,
    temperature=1.0, top_p=0.95, top_k=64, min_p=0.0,
    repeat_penalty=1.0,
    enable_thinking=False, reasoning_budget=0,
)

# --- DESTRUCTIVE_STRICT (used only when intent detector flags borrar/format/shutdown/rm -rf) ---
# Rationale: Gemma 4 was tuned at T=1.0; T=0.2 (qwen3 number) hurts emission.
# Tighten distribution moderately, don't collapse it.
DESTRUCTIVE_STRICT = TurnProfile(
    name="destructive_strict",
    n_ctx=8192, n_predict=256,
    temperature=0.6, top_p=0.9, top_k=40, min_p=0.02,
    repeat_penalty=1.0,
    enable_thinking=False, reasoning_budget=0,
)

PROFILES = {p.name: p for p in [TRIVIAL, TOOL, MISSION, DESTRUCTIVE_STRICT]}
```

---

## 6) KV cache, flash attention, compaction recommendations

| Concern | Recommendation | Why |
|---|---|---|
| KV K type | **f16** | Gemma 4 q8_0 KV → KL ≈ 0.108 (31B), 0.377 (26B-A4B); f16 baseline. (localbench Substack KLD bench.) |
| KV V type | **f16** | Same. |
| Flash attention | **`--flash-attn on`** | E4B + FA on f16 KV is the only stable combo on the SWA/global hybrid. FA off → V-cache padding blowup (issue #22527). |
| Context size policy | Trivial 4K · Tool 8K · Mission 16K | Keeps KV VRAM and TTFT proportional to actual need. |
| Compaction trigger | Compact at **8K used** (50 % of 16K Mission) | Conservative; tool reliability degrades before declared ctx limit. |
| Compaction strategy | Keep last 2 turns verbatim; summarize older turns into ≤256 tokens; preserve all `tool_calls`/`tool_responses` from current turn (Google rule 3). | Summarizing is safe for Gemma 4 between turns. NEVER summarize within an in-flight tool sequence (Google rule: thoughts must NOT be removed mid-call). |
| Build choice | **Stay on b9090** | Has all critical Gemma 4 fixes (#21326, #21343, #21390, #21406, #21418, #21500, #21566). Move to b9100+ only if a future PR fixes #21384 (array-type arg edge case) — not currently blocking. |

---

## 7) Comparison table — current (qwen3) vs recommended (Gemma 4)

| Parameter | Current (qwen3 baseline) | Recommended (Gemma 4 E4B IQ2_M) | Expected delta | Source |
|---|---|---|---|---|
| temperature | 0.7 (qwen3 default) | **1.0** | More diverse; tool emission unchanged | Google model card |
| top_p | 0.8 | **0.95** | Slightly broader head | Google model card |
| top_k | 20 | **64** | Broader head; matches RLHF | Google model card |
| min_p | 0.0 / 0.05 | **0.0** | Not part of Gemma 4 spec | Google model card |
| repeat_penalty | 1.05 | **1.0** | Avoids interfering with calibrated logits | Unsloth docs |
| presence_penalty | 0 / 0.5 | **0.0** | Same | Google model card |
| `-c` | varies | **4K/8K/16K per archetype** | KV ↓, TTFT ↓ for Trivial/Tool | Carter requirements |
| `--cache-type-k/v` | q8_0 (likely) | **f16** | +~50 % KV VRAM, but quality-critical | localbench KLD bench |
| `--flash-attn` | on/off mixed | **on** | Required for stability on SWA+global | issue #22527 |
| `--jinja` | optional | **required** | Tool template + parser | issue #21316 thread |
| `--reasoning` | n/a | **off** | No thinking tokens to user | Gemma 4 prompt-format docs |
| `--chat-template-kwargs` | n/a | **`{"enable_thinking":false}`** | Authoritative thinking off | Unsloth docs |
| `--cache-ram` | default 8192 | **0** | No interference with Carter's compaction | issue #22127 |
| `--cache-reuse` | n/a | **256** | Static prompt skip across turns | Discussion #22354 |
| `--no-context-shift` | maybe off | **on** | Avoids SWA KV corruption | Gemma 4 hybrid attention |
| stops | varies | **none** (let GGUF + peg-gemma4 handle) | Prevents tool truncation | Gemma 4 prompt-format docs |
| CORE_PROMPT size | ~5600 tok | **~900 tok** hybrid | TTFT ↓ ~3–4 s on prefill | Carter requirements |
| DESTRUCTIVE T | 0.2 | **0.6** | Avoid post-DPO collapse | HF discussions/21 thread |
| DESTRUCTIVE top_k | 20 | **40** | Less aggressive narrowing | Same |
| Build | varies | **b9090 CUDA 12** | All Gemma 4 fixes present | llama.cpp release notes |

---

## 8) Validation plan — 3–5 minimum experiments (~1.5 h budget)

Run with `evidencia pruebas gemma4/harness/run_bench_extended.py`. Each experiment is **one A/B switch** vs the new baseline (the recommended config above). Hypothesis ranked by criticality.

**Experiment H1 (CRITICAL, must pass before ship) — Tool-call delimiter integrity**
- Config A (control): full recommended config above.
- Config B: same but `--cache-type-k q8_0 --cache-type-v q8_0`.
- Prompt subset: 20 cases from your 60-case bench that contain DESTRUCTIVE intent + tool args with strings containing `{`, `}`, or quotes.
- Success metric: 0 cases where `arguments` contains a literal substring `<|"|>` after JSON-parse round-trip.
- Expected: A passes 100 %, B may show occasional KV-quant-induced regressions on string args.
- Time: ~25 min.
- Decision: if B = A (no leakage), you have margin to enable q8_0 KV later for VRAM savings. If A still leaks, b9090 does not contain all the fixes — pin b9100+ or patch.

**Experiment H2 (CRITICAL) — Thinking off vs on, latency**
- Config A: recommended (`--reasoning off --reasoning-budget 0 --chat-template-kwargs "..."`).
- Config B: thinking ON (`--reasoning on --reasoning-budget -1`, no `enable_thinking:false`).
- Prompt subset: 20 cases mixed Trivial+Tool.
- Metric: p99 latency, PASS rate (your current scoring rubric).
- Expected: A latency ≈ 0.4–0.6× B; PASS rate equal or A slightly higher (E4B doesn't benefit much from thinking on simple Carter tasks).
- Time: ~25 min.

**Experiment H3 (HIGH) — Sampling: T=1.0 vs T=0.7 vs T=0.5 on tool calls**
- Three runs, only `--temp` varies.
- Prompt subset: the 30 tool-calling cases.
- Metric: PASS rate, count of malformed tool args.
- Expected: T=1.0 ≥ T=0.7 ≥ T=0.5 on Gemma 4 (consistent with HF community thread).
- Time: ~30 min.
- Decision: if T=0.7 ≥ T=1.0, bend the canonical and ship at 0.7. If T=1.0 wins, **keep canonical** even though it feels counter-intuitive.

**Experiment H4 (MEDIUM) — DESTRUCTIVE_STRICT calibration**
- Config A: DESTRUCTIVE_STRICT as defined (T=0.6/top_p=0.9/top_k=40).
- Config B: T=0.2/top_p=0.8/top_k=20 (the qwen3 numbers, as a control).
- Prompt subset: 10 destructive-intent cases.
- Metric: rate of correctly-called `confirm_destructive` tool, rate of refusals (rule 4).
- Expected: A ≥ B on tool-call success; B may emit malformed args or freeze.
- Time: ~15 min.

**Experiment H5 (MEDIUM, optional) — System prompt size**
- 900-token Carter prompt (recommended) vs 1500-token version (add more few-shots).
- Metric: PASS on the 60-case bench, p50/p99 latency.
- Expected: 900 ≥ 1500 on PASS for E4B (small models attention-dilute on long prompts), and ~1.5–2 s faster TTFT.
- Time: ~25 min.
- Skip if total budget exceeded.

**Total time:** ~95–120 min ≈ 1.5–2 h, in line with the user's budget.

**Why these won't degrade the 91.7 % PASS:** every recommended change is either (a) a known Gemma-4-specific bug avoidance (FA-on, f16 KV, jinja, peg-gemma4 stops) or (b) the model card's explicit canonical sampling. The biggest behavioral change is `T=1.0` vs whatever qwen3 was using — H3 explicitly tests this with a fall-back.

---

## Recommendations (staged, with thresholds)

**Stage 0 — Verify build (10 min, do FIRST).** Spin up `llama-server.exe` from b9090 with the launch command, send a single tool-calling request, grep server log for `Chat format: peg-gemma4`. Grep response JSON for `<|"|>`. **If you see literal delimiters, STOP — your build does not have PR #21418's parser.** Pin b9100+ or rebuild from master.

**Stage 1 — Ship the new config behind a feature flag.** Drop in `LlamaCppConfig` and `turn_profile.py`. Run the existing 60-case bench. **Threshold:** must hit ≥ 91.7 % PASS (no regression). If you don't hit it, run H1+H2 to localize.

**Stage 2 — Run H1+H2 (50 min).** Both must pass. H1 is non-negotiable. H2 confirms the latency budgets are realistic.

**Stage 3 — Run H3+H4 (45 min).** Iterate sampling for tools and destructive. Lock numbers.

**Stage 4 — (Optional) H5 prompt-size sweep (25 min).** Lock CORE_PROMPT length.

**Promotion criteria to "production":** PASS ≥ 91.7 %, p99 latencies within targets (Trivial <5 s, Tool <8 s, Mission <20 s), and zero `<|"|>` leaks across 100 turns.

**Reverse-out trigger:** any of: PASS < 90 %, more than 1 % tool-call malformed, latency p99 over budget. Roll back and re-run H1.

---

## Caveats — places I am NOT certain

- **BFCL multi-turn for Gemma 4 E4B is unpublished as of May 9 2026.** The closest proxy is τ²-bench from Google's model card (E4B = 42.2 %). I would not generalize this number to your bench. Run H3 before fixing.
- **IQ2_M-specific quality at the tool layer is not benchmarked publicly.** Unsloth's KLD work covers UD-Q4_K_XL and Q8_0; IQ2_M is more aggressive. **Expect a measurable hit relative to Q4_K_XL; you have not confirmed it won't break Carter.** If H1/H3 fail, consider moving to UD-Q3_K_XL (~4.59 GB, still fits).
- **Whether b9090 contains every necessary Gemma 4 fix:** I confirmed that PRs #21326, #21343, #21390, #21406, #21418, #21500, #21488, #21566 all merged in April 2026, well before b9090 (May 9). I have NOT reviewed b9090's commit history line-by-line. **Verify with the smoke test in Stage 0.**
- **Issue #21384 (array-of-objects with `{` `}` in string values serialized as JSON-encoded string instead of array)** is **still open** at the time of writing. If Carter's tools include array-of-object args with curly-brace-containing strings (e.g. `edits=[{oldText, newText}]`), expect occasional malformed args. Workaround: keep tool args flat (no nested object arrays) where possible.
- **Flash-attn + SWA on Gemma 4 31B has an open crash (#22527, on RTX 4060 Ti 16 GB no less).** I am operating on the assumption — backed by absence of similar reports for E4B — that this is **31B-dense-specific.** If you ever see "illegal memory access" on E4B, that assumption is wrong; turn off `--checkpoint-every-n-tokens` first, then `-fa off` only if you also drop ctx to 4K.
- **Unsloth GGUFs published before April 11 2026 had template bugs.** The user's file's HF-modified-date should be after that; if you re-cloned recently, you're fine. If you cached the file in early April, re-download.
- **Honest acknowledgment:** I do not have direct experimental data on YOUR 60-case bench at IQ2_M. Every recommendation here is grounded in (a) Google's model card, (b) Unsloth's published benchmarks, (c) llama.cpp issue tracker, and (d) community reports. The validation plan exists because some of this WILL surprise you. **Do not skip it.**
- **CUDA 13.2 caveat:** Unsloth states CUDA 13.2 produces poor outputs with Gemma 4 GGUFs. b9090 Windows pre-built ships CUDA 12.4 DLLs — you're safe. If you self-build, **build against CUDA 12.x.**
- "Wait for b9100+" trigger: **only** if the Stage 0 smoke test shows `<|"|>` leakage. As of the data I gathered, b9090 should be fine for E4B text-only tool calling.