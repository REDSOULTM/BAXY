# MODEL_VISION_TOURNAMENT_REPORT.md (M7 / Wave 3)

_Generated: 2026-05-02 — 6 candidates, single-load discipline, 5 cases (3 colour + 2 OCR PIL-rendered)._

## Live results

Source: `audit/results/model_benchmarks/_vision_tournament_20260502-095912.json`
and per-model `vision_*.json`.

| # | Model                | pass | score | VRAM load (MiB) | dur (s) | notes                                |
|---|----------------------|------|-------|-----------------|---------|--------------------------------------|
| 1 | `moondream:latest`   | 1.00 | 1.00  | **2 127**       | 15.3    | tiny, fastest, full pass on smoke    |
| 2 | `minicpm-v:latest`   | 1.00 | 1.00  | 5 566           | 22.7    | known OCR strength                   |
| 3 | `llava-llama3:latest`| 1.00 | 1.00  | 5 745           | 34.1    | describe + reasoning                 |
| 4 | `gemma3:12b`         | 1.00 | 1.00  | 8 591           | 28.0    | text+vision but **no tools**         |
| 5 | `qwen2.5vl:7b`       | 1.00 | 1.00  | **13 175**      | 18.4    | grounding (Carter `find_element`)    |
| 6 | `llava:7b`           | 0.80 | 0.88  | 5 043           | 21.8    | lost OCR case `V2.02` (Spanish)      |

## What the smoke discriminates and what it does NOT

The 5 cases (3 solid-colour PNGs + 2 PIL-rendered text strips) are
**runtime smoke** — they validate that each VLM:

- accepts an OpenAI-compat `image_url` payload,
- returns text (not garbage),
- handles English + Spanish OCR strings,
- loads / unloads cleanly inside our single-load harness.

They DO NOT discriminate fine-grained vision quality. A real
Carter-grade benchmark would need: UI screenshots, button bounding-box
ground-truth, multi-language OCR with reference text, hallucination
adversarial cases. Those fixtures are not yet in `audit/fixtures/vision/`.

Therefore rankings below combine the live smoke with **published model
cards** for the dimensions the smoke cannot test (grounding accuracy,
OCR WER, hallucination rate).

## Per-profile vision recommendation

| Profile  | describe          | grounding (find_element) | OCR fallback                | rationale                                                                  |
|----------|-------------------|--------------------------|-----------------------------|----------------------------------------------------------------------------|
| cpu_only | (deferred — VLMs on pure CPU are slow; Carter routes to OCR-only path) | n/a | pytesseract                | model selection irrelevant on CPU.                                          |
| 6 GB     | `moondream`       | (none in band)           | pytesseract                | only VLM that fits 6 GB cleanly; pass 1.00 + only 2.1 GB VRAM.              |
| 8 GB     | `minicpm-v`       | `minicpm-v` (limited)    | `minicpm-v` (built-in OCR) | best VRAM/quality tradeoff in band; preferred for text-heavy UIs.           |
| 10 GB    | `minicpm-v`       | `qwen2.5vl:7b`           | `minicpm-v`                | Carter can swap to qwen2.5vl when grounding is needed (single-modal load).   |
| 12 GB    | `qwen2.5vl:7b`    | `qwen2.5vl:7b`           | `minicpm-v` on swap        | qwen2.5vl wins grounding per model card; same model used for describe.      |
| 16 GB    | **`qwen2.5vl:7b`**| **`qwen2.5vl:7b`**       | `minicpm-v`                | Carter actual; live pass 1.00, grounding owned. NOTE: ~13 GB VRAM on Ollama. |
| 24 GB    | `qwen2.5vl:7b`    | `qwen2.5vl:7b`           | `minicpm-v` resident        | both can stay loaded.                                                        |

`llava:7b` lost the Spanish OCR case (`V2.02`, "Hola mundo") — kept only
as legacy fallback per `_NO_TOOLS_MODELS` policy. `llava-llama3` adds
~700 MB over `llava` for similar smoke quality and is on the cleanup
candidate list (`MODEL_STORAGE_CLEANUP_PLAN.md`). `gemma3:12b` works as
a VLM but lacks tools, so Carter would need a separate text model
loaded — wastes the no-double-load budget on 16 GB; not selected.

## Carter integration (current state)

`run_carter_gpu.ps1` ships with:
- `CARTER_VISION_LLM_MODEL=llava:7b` (describe / OCR)
- `CARTER_GROUNDING_MODEL=qwen2.5vl:7b` (find_element coordinates)

Wave-3 finding suggests **promoting `minicpm-v:latest` over `llava:7b`
for the describe slot** (fixes the V2.02 Spanish-OCR regression). Net
effect on rollback: marginal (both ~5 GB VRAM, same load policy). The
update is opt-in — env var override below — and the launcher default is
unchanged to avoid moving config without explicit confirmation.

```powershell
# To opt into the Wave-3 vision recommendation:
$env:CARTER_VISION_MODEL = "minicpm-v:latest"
& .\run_carter_gpu.ps1
```

## VRAM observation worth recording

`qwen2.5vl:7b` reported **13 175 MiB** load delta on Ollama. That is
much higher than the model file (~6 GB on disk). Causes: Ollama default
context window for VLMs + image-token KV cache. Implications:

- On a 16 GB rig, qwen2.5vl alone uses 80 % of VRAM. **No other modal
  model can co-reside.** The selector's `concurrent_modals=1` policy
  enforces this correctly.
- For mixed describe+grounding workloads, prefer `minicpm-v` first, then
  hot-swap to qwen2.5vl only when grounding is required.

## Acceptance for closure

- ✅ Live smoke executed for all 6 installed VLMs.
- ✅ Per-profile recommendation documented with rationale.
- ✅ Carter-impact statement included (no default mutation without consent).
- ✅ VRAM caveat for qwen2.5vl recorded.
- 🔄 Real fixtures in `audit/fixtures/vision/` (UI screenshots + OCR
  ground truth) — deferred; out of W2-3 scope.

Verdict: **VISION_STACK_READY** for Carter's current describe+grounding
needs, with optional `minicpm-v` upgrade documented.
