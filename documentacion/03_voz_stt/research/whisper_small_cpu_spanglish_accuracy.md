# Maximizing Whisper-small CPU Accuracy for a Local Spanglish Voice Assistant

## TL;DR
- **The single highest-ROI change is to stop relying on `initial_prompt`/`hotwords` for proper-noun biasing** (in faster-whisper both are just decoder-prompt token prepends, not shallow fusion — confirmed by reading `transcribe.py` and the maintainer's own statement that "shallow fusion … is not yet available in faster-whisper nor in CTranslate2") and instead invest in (1) CPU denoising via DeepFilterNet3 before Whisper, (2) a real phonetic post-corrector, and (3) padding short clips deterministically to mitigate Whisper's documented 30-second training bias. These are CPU-cheap, low-risk to multi-voice generality, and have published evidence behind them.
- **No drop-in OSS CPU model clearly beats Whisper-small for Spanish + intra-utterance English code-switching today.** Parakeet-TDT-0.6b-v3 (CC-BY-4.0, ONNX-on-CPU) is the most credible alternative on raw accuracy, but its own HuggingFace model card warns it "may produce transcription errors, particularly with code-switching or noisy input"; NVIDIA's actual Spanish-English code-switch Parakeet is gated behind the Riva/NIM container (GPU + NVIDIA AI Enterprise license); Moonshine's Spanish model ships under the non-commercial Moonshine Community License; and distil-whisper's README explicitly states "Distil-Whisper is only available for English speech recognition." Whisper-large-v3-turbo (809 M) is encoder-bound on CPU and not viable for sub-300 ms voice commands.
- **A "cheap" LoRA fine-tune of Whisper-small is the next escalation** (5–10 h of mixed real + synthetic Spanglish, rank ≤16, adapter-only). Diabolocom's published Whisper-medium LoRA on Québécois telephone speech reduced WER from 77.38% to 45.74% (a 31.64-point absolute drop), and arXiv 2506.21555 reports 10% relative gains in language-aware and 15% in language-agnostic scenarios for LoRA language experts. But the literature also confirms (a) TTS-only data overfits to acoustic artifacts (Rossenbach et al., arXiv 2407.17997; Kwok et al., Interspeech 2025) and (b) aggressive fine-tuning degrades multi-speaker generality unless adapters are used — keep the LoRA adapter swappable per profile.

---

## Key Findings

1. **`hotwords` is not contextual biasing.** Reading `faster_whisper/transcribe.py` confirms that `hotwords` is implemented as `tokenizer.encode(" " + hotwords.strip())` prepended to the decoder prompt before the `<|startofprev|>`/`<|sot|>` tokens — i.e. the same mechanism as `initial_prompt`, just positioned differently. There is no FST, no per-step logit boost, no shallow fusion. SYSTRAN issue #1232 confirms: "shallow fusion … is not yet available in faster-whisper nor in CTranslate2." Consequence: enriching prompts further will not solve "Chrome → Aurekrom"; your earlier "enriched prompt was worse" result is consistent with the U-WER ceiling that KWS-Whisper (Sun et al., arXiv 2309.09552) describes as "a slight increase in mixed-error-rate (MER) … due to catastrophic forgetting."

2. **Whisper internally zero-pads to 30 s, so very short clips are a known failure mode.** The encoder fixes the spectrogram at (80, 3000) = 30 s; shorter audio is zero-padded. The WhisperFlow paper (Wang et al., MobiSys '25, arXiv 2412.11272) shows that naive padding of short clips causes accuracy degradation and proposes a learned "hush word" of ~0.5 s appended to short audio to reduce hallucinations. Sherpa-onnx maintainers (k2-fsa/sherpa-onnx discussion #2787) concur: under-30-s input "makes hallucination" without padding. Without retraining, the next best thing is a small (0.2–0.5 s) low-noise pad before invoking Whisper.

3. **Hallucinations on degraded speech follow a small, enumerable bag.** Barański et al. (arXiv 2501.11378) catalogue Whisper's hallucinations as a "Bag-of-Hallucinations" — "Gracias por ver el video", "Suscríbete al canal", "Subtítulos por la comunidad de Amara.org", "thanks for watching", etc. — and show simple delooping + Aho-Corasick post-filtering catches the bulk. Your current substring filter is on the right track; extend it with the published BoH list.

4. **Audio pre-processing has a strong, cheap evidence base.** Schröter et al. (DeepFilterNet, arXiv 2305.08227, Interspeech 2023) report PESQ 3.17, CSIG 4.34, CBAK 3.61, COVL 3.77, STOI 0.944 on the VCTK/DEMAND test set, while achieving a real-time factor of 0.19 on a single-threaded i5-8250U with ~40 ms algorithmic latency. RNNoise is even cheaper (~10 ms, minimal CPU) but side-by-side practical tests (noisereducerai.com/rnnoise) report that "DeepFilterNet3 handled it noticeably better" on TV/echo/speech-like noise — which matches your reported echo/ambience problem. WebRTC AEC3 and SpeexDSP both have Python bindings (`speexdsp-python` on PyPI; PJSIP docs list both as supported software echo cancellers).

5. **Multilingual code-switching on Whisper: fixing the language is correct.** Whisper's autodetection only looks at the first 30 s and frequently fails to switch back (openai/whisper discussions #49 and #2009). The academic remedy (Zhao et al., arXiv 2412.16507, "Adapting Whisper for Code-Switching through Encoding Refining and Language-Aware Decoding") requires adapter training; for inference-only, fixing `language="es"` is documented best practice for Spanglish where Spanish is the matrix language.

6. **No CPU-friendly drop-in beats Whisper-small for es+en code-switching today.**
   - NVIDIA `parakeet-ctc-0.6b-es` (Spanish-English code-switch, 600 M params, trained on 28 000 h, with the model card stating "The model transcribes speech in Spanish and English, in upper case and lower case alphabets, along with punctuations") is **NIM/Riva-only, GPU-required, NVIDIA AI Enterprise license**, with no public ONNX or HuggingFace checkpoint (docs.nvidia.com/nim/speech/latest/asr/deploy-asr-models/parakeet-ctc-es-us.html).
   - `nvidia/parakeet-tdt-0.6b-v3` IS CC-BY-4.0, has an ONNX CPU runtime (`istupakov/parakeet-tdt-0.6b-v3-onnx`, usable via the `onnx-asr` library), reports ~22–26× real-time INT8 throughput on x86 CPU and 9.7% average WER across 24 languages (arXiv 2509.14128), but its model card explicitly warns: "The model may produce transcription errors, particularly with code-switching or noisy input" — i.e. per-utterance language detection, not intra-utterance switching.
   - Moonshine v2 Spanish exists (github.com/moonshine-ai/moonshine), with Linux x86 CPU latencies of ~165 ms (Small, 123 M, 7.84% English WER) and ~269 ms (Medium, 245 M, 6.65% WER) vs Whisper-small's 3 425 ms on the same machine per Moonshine's own benchmarks — **but the Spanish model ships under the Moonshine Community License (non-commercial)**, and per-language design means no code-switching.
   - Distil-Whisper README is explicit: "Distil-Whisper is only available for English speech recognition. For multilingual speech recognition, we recommend … Whisper Turbo" (github.com/huggingface/distil-whisper).
   - Community `marianbasti/distil-whisper-large-v3-es` exists (MIT, distilled from large-v3 on Common Voice 16.1) but unverified on code-switching.
   - Whisper-large-v3-turbo (809 M) at INT8 CTranslate2 is feasible to load on CPU but the **encoder is identical to large-v3** and dominates CPU compute; faster-whisper maintainers note Turbo "was not trained with translation data" and report more hallucinations on short/noisy clips. Not recommended for sub-300 ms voice commands.

7. **Cheap fine-tuning is realistic but adapter-only.** LoRA/PEFT of Whisper-small with as little as 5–10 h of audio is repeatedly demonstrated (Vaibhavs10/fast-whisper-finetuning; Diabolocom write-up). ICASSP 2024 DistilWhisper (Ferraz et al., arXiv 2311.01070) and arXiv 2506.21555/2506.21576 show LoRA experts + soft-prompt tuning beat standard fine-tuning on multilingual code-switching while keeping the base frozen — exactly the property you need for multi-user/multi-language profiles. Synthetic-only TTS data is documented to overfit; arXiv 2507.13875 (Catalan-Spanish CS) and arXiv 2601.00935 (Mandarin-English CS) both show synthetic data helps **only when mixed with real audio**, and Kwok et al. (Interspeech 2025) state plainly: "synthetic audio data introduce artifacts that differ from natural speech … can lead to overfitting when training the biasing module."

---

## Details — Answers to your research questions, with ROI ordering

Ordered by gain × (1/cost) × (1/risk-to-generality). I distinguish **Solid evidence** (≥1 paper/repo benchmark) from **Worth trying** (mechanistic plausibility, weaker evidence).

### Tier 1 — Solid evidence, deploy first

**R1. Add DeepFilterNet3 as a single CPU pre-processing stage between VAD and Whisper.** [Audio Q4]
- **What:** Insert DeepFilterNet on the 16 kHz mono int16 stream after Silero VAD trims silence but before Whisper. Use the official ONNX runtime build (`pip install deepfilternet`); set 48 kHz internally with resampling, or use the lighter RNNoise if you must stay 16 kHz throughout.
- **Expected gain:** Direct WER improvement on noisy/echo clips. DeepFilterNet paper reports PESQ 3.17, CSIG 4.34, CBAK 3.61, COVL 3.77, STOI 0.944 on VCTK/DEMAND at RTF 0.19 single-threaded on i5-8250U; ClearlyIP's voice-bot pre-processing review and noisereducerai.com both report DeepFilterNet3 outperforming RNNoise on TV/echo noise.
- **Latency/CPU/RAM cost:** ~40 ms algorithmic look-ahead + ~RTF 0.19 of audio duration; for a 2 s command on a 4-core x86 this is ~80 ms additional CPU. RAM ~80 MB.
- **Risk to universal use:** Very low — denoising acts speaker-agnostically. The one documented failure is over-suppression of soft consonants; mitigate by keeping wet/dry mix at 80/20.
- **Effort:** ~1 day. Replace your peak-RMS gate with DeepFilterNet + a simpler RMS guard.

**R2. Pad short clips deterministically before sending to Whisper.** [Decode Q2]
- **What:** Before invoking `model.transcribe`, if the captured audio is <1.0 s, pad with ~0.5 s of low-level pink noise (NOT pure zeros) at the end. Do NOT let very short clips reach Whisper raw — Whisper's internal zero-pad to 30 s on a 200 ms clip is the documented hallucination regime.
- **Expected gain:** Reduces the "kill it ace" / "Suscríbete" class of hallucinations on short, degraded speech.
- **Evidence:** WhisperFlow (Wang et al., MobiSys '25, arXiv 2412.11272) shows naive padding of under-30-s clips causes WER degradation and that an appended ~0.5 s "hush" segment helps (theirs is trained; an unlearned low-noise pad is the OSS analog). Barański et al. (arXiv 2501.11378): hallucination rate also spikes when augmentations are very short.
- **Cost:** Negligible — just appends samples.
- **Risk:** Very low; pink noise at –45 dBFS is below Silero VAD's threshold.
- **Effort:** ~1 hour.

**R3. Extend the post-STT hallucination filter with the published BoH (Bag-of-Hallucinations).** [Decode]
- **What:** Add Aho-Corasick matching (`pyahocorasick` on PyPI) over the Barański et al. canonical hallucination list (Spanish + English subtitle/YouTube artifacts) plus a generic n-gram delooping rule ("X X X X …" → drop).
- **Source:** Barański et al., "Investigation of Whisper ASR Hallucinations Induced by Non-Speech Audio", arXiv 2501.11378, Table 1 + top-30 list.
- **Cost:** O(n) string scan, sub-millisecond.
- **Risk:** None to generality.
- **Effort:** ~half a day.

**R4. Replace the RapidFuzz-only post-corrector with a hybrid phonetic + edit-distance corrector tuned for Spanish.** [Post-processing Q8]
- **What:** For each token that does not lex-match the closed inventory (apps/artists/verbs), compute (a) RapidFuzz token-sort ratio (you already do this), AND (b) Double Metaphone code (via `jellyfish.metaphone`, the `metaphone` PyPI package, or a Spanish-tuned `phonetics` package) on both transcript token and inventory entry. Accept the inventory candidate if either similarity ≥ threshold OR both are above weaker thresholds.
- **Why:** "Aurekrom" / "cross" → "Chrome" is a pure phonetic match (CHROME ≈ KROM in Metaphone), unreachable by edit distance alone; "Jema" / "Ejema" → "Gemma" likewise. Per Sun et al. (arXiv 2309.09552, Interspeech 2024): "Our system enhances entity recall with absolute improvements of up to 80% on Aishell hot word subsets and up to 10% on internal code-switching datasets" — when phonetic-similarity matching is combined with a frozen Whisper. The same paper also notes a "slight increase in mixed-error-rate (MER) … due to catastrophic forgetting," so cap the corrector with a stop-list of frequent Spanish vocabulary to avoid over-correcting.
- **Cost:** Negligible; Metaphone is O(n) per token, dictionary precomputed once.
- **Risk:** Low.
- **Effort:** ~1 day.

**R5. Add WebRTC AEC3 (or SpeexDSP) since TTS and mic share the device.** [Audio Q5]
- **What:** When TTS is playing, route the TTS audio as the far-end reference through an AEC stage on the captured near-end signal. `speexdsp-python` (github.com/xiongyihui/speexdsp-python) is the easier integration; WebRTC AEC3 is higher quality but only works correctly at 32 or 48 kHz (groups.google.com/g/discuss-webrtc/c/T0W8m5Wy7RM).
- **Expected gain:** Eliminates TTS-bleed-induced false wakes and hallucinations during barge-in.
- **Cost:** ~5% CPU during TTS playback, near-zero otherwise.
- **Risk:** Low; AEC is content-agnostic.
- **Effort:** 1–2 days, including buffering/sync between playback and capture.

### Tier 2 — Worth trying, plausible gains

**R6. Keep `language="es"` fixed; DO NOT add `task="translate"`; DO NOT enable autodetect.** [Decode Q1] — Whisper "decides" the language token, then tends not to switch back mid-utterance (openai/whisper #49, #2009). Your current config is correct; document this as non-negotiable.

**R7. Keep `condition_on_previous_text=False`.** Whisper #29: "this makes the decoding more prone to repetition looping" when True on independent commands. Confirmed in your config.

**R8. Stop touching beam_size, temperature_fallback, log_prob/compression thresholds.** [Decode Q1] Your own measurements show beam_size=5 and threshold/fallback combinations gave WER 0.625 vs 0.608 baseline at 30% more latency, consistent with the Whisper paper's finding that fallback only helps long-form chunk-stitched decoding. The HuggingFace Whisper docs explicitly say `logprob_threshold` and `no_speech_threshold` are "Only relevant for long-form transcription" (huggingface.co/docs/transformers/en/model_doc/whisper).

**R9. Try `hotwords` once with the closed proper-noun list and benchmark.** [Decode Q3] Mechanistically `hotwords` ≡ `initial_prompt` minus positional difference; the trade-off your enriched prompt already exposed (improved rare-word recall, slight common-word degradation) is the same regime Sun et al. document. Move budget to phonetic post-correction (R4) and LoRA (R12) rather than further prompt tuning.

**R10. Use the LLM that is already running for a *constrained* second-pass repair.** [Post-processing Q9]
- **What:** After STT, if RapidFuzz+phonetic confidence is low, send a one-shot prompt to the local LLM: `"User said something in Spanglish. Inventory: <closed list>. Whisper output: <text>. Output ONLY the corrected command or NONE."`
- **Evidence:** Wang et al. (arXiv 2502.16142) report: "the LLM contributes significantly to improvements in rare word error rate (R-WER), while the speech encoder primarily determines overall transcription performance (Orthographic Word Error Rate, O-WER, and Normalized Word Error Rate, N-WER)" — the LLM repairs the rare/entity tail without altering the common-word baseline.
- **Risk:** Latency. Only invoke when post-corrector flags ambiguity (no inventory match within fuzzy threshold). With a 6 GB GPU LLM already warm, a 30-token completion is typically <150 ms.

### Tier 3 — Bigger investment, only if Tiers 1–2 are insufficient

**R11. Evaluate `nvidia/parakeet-tdt-0.6b-v3` via ONNX on CPU as a secondary model for non-code-switching utterances.** [Models Q6]
- **What:** Run side-by-side on your 105-command bench. If Spanish-only commands beat Whisper-small at ≤2× the latency, you could route via a heuristic.
- **Evidence:** arXiv 2509.14128 reports 9.7% average WER over 24 languages, edging Whisper-large-v3 (9.9%); FluidInference's OpenVINO Intel NPU build reports 5.4% Spanish WER on Intel Core Ultra 7 155H. CC-BY-4.0. Caveat: official model card warns "may produce transcription errors, particularly with code-switching or noisy input."
- **Cost:** ~600 M params, 1.2–1.8 GB RAM INT8; comparable or higher CPU per inference than whisper-small int8 — not a free win.
- **Risk:** Medium. Code-switching is its weak spot.

**R12. LoRA fine-tune Whisper-small with adapter swapping per language profile.** [Fine-tune Q10]
- **What:** Use PEFT + LoRA (sanchit-gandhi/Vaibhavs10/fast-whisper-finetuning on GitHub), rank=8–16, target `q_proj`/`v_proj`/`out_proj`. Train on ~5–10 h: ~70% Common Voice 17 Spanish + ~20% real Spanglish recordings + ~10% Piper-synthesized command templates with English app names, with SNR augmentation (noise mix from MUSAN at 5–20 dB) to mask TTS artifacts.
- **Expected gain:** Per Diabolocom's published experiment (diabolocom.com/research/fine-tuning-asr-focus-on-whisper/), fine-tuning Whisper-medium with LoRA on the TalkBank Québécois telephone-speech subset reduced WER from 77.38% to 45.74% — an absolute improvement of 31.64 WER points. arXiv 2506.21555 (Efficient Multilingual ASR Finetuning via LoRA Language Experts) reports "approximately 10% and 15% relative performance gains in language-aware and language-agnostic scenarios, respectively." Your relative gains will be smaller than Québécois (because your baseline WER is already much better) but the direction is consistent.
- **Cost:** ~6 h on a single 24 GB consumer GPU (rentable), no GPU at inference (LoRA can be merged into the FP16/INT8 CT2 export or kept as a small adapter swap).
- **Risk:** **Real risk to multi-voice generality.** Diabolocom and the HF community note overfitting if dataset is small/single-speaker; Rossenbach et al. (arXiv 2407.17997) and Kwok et al. (Interspeech 2025) confirm synthetic-only data degrades downstream ASR. Mitigations: keep base frozen, rank ≤16, ≤3 epochs, include a held-out Common Voice 17 test set as a non-regression gate.
- **Effort:** ~2 weeks including data curation.

**R13. Generate Spanglish eval/training data — multilingual TTS, not Piper alone.** [Eval+Synth Q11, Q12]
- **What:** Piper voices are monolingual per checkpoint (`es_ES-davefx-medium`, `en_US-lessac-medium`). For "abre Spotify" with realistic Spanglish prosody, use CosyVoice2 or XTTS-v2 (license-permitting); for strict OSS-free constraints, fall back to splicing two Piper outputs at word boundaries. arXiv 2601.00935 demonstrates CosyVoice2-augmented Mandarin-English CS data dropped MER from 12.1% to 10.1% on DevMan and from 17.8% to 16.0% on DevSGE. arXiv 2507.13875 (Catalan-Spanish CS) confirms the synthetic-data benefit is highest when it is the *minority* of training data.
- **Eval-set creation:** Generate ~1000 templated commands (`abre {APP}`, `pon {SONG} de {ARTIST}`, `pon {SERIES} en {STREAMER}`) across 8–12 Piper Spanish voices + 4–6 English voices spliced for app names. Apply SNR augmentation, add reverb (`pyroomacoustics`) to simulate your echo conditions. This becomes a wake-anchored, label-aligned eval bench at zero labeling cost.
- **Metrics beyond WER:** Track Entity-WER (errors restricted to proper-noun spans), Intent-Accuracy (after fuzzy → did intent match), Keyword-Recall (was the app/artist token found anywhere), AND classical WER. OSS tools: `jiwer` (WER), `huggingface/evaluate`, `Lhotse` for corpora handling, `pyctcdecode` if you later move to a CTC model.
- **Caveat:** Always maintain a small, hand-labeled multi-real-speaker set; do NOT trust synthetic-only scores.

---

## Recommendations — staged plan

**Stage 0 (this week, no model changes, ~3 days):**
- (a) Insert DeepFilterNet3 ONNX denoise before Whisper (R1).
- (b) Pad <1.0 s clips to 1.0 s with –45 dBFS pink noise (R2).
- (c) Add Aho-Corasick BoH filter (R3) and integrate Double-Metaphone branch into the post-corrector (R4).
- (d) Commit `language="es"`, `condition_on_previous_text=False`, beam=1, temp=0, no thresholds — your measured baseline (R6–R8).
- **Continue if:** WER drops below ~0.45 on the existing 105-command bench AND Anglicism entity-recall is >80%. Else stop here, you are done.

**Stage 1 (1–2 weeks):**
- (e) Add WebRTC/Speex AEC for TTS barge-in (R5).
- (f) Build the synthetic-CS eval bench (R13) — target ≥500 well-aligned commands across ≥4 voices, then re-run all prior changes against it.
- (g) Wire constrained LLM second-pass repair on low-confidence transcripts (R10).
- **Escalate if:** intent accuracy still <90% or Anglicism entity-recall <90%.

**Stage 2 (when justified):**
- (h) LoRA fine-tune Whisper-small (R12) with adapter swapping per language profile; require non-regression on Common Voice es-test and an EN-only held-out set before shipping.
- (i) Pilot Parakeet-TDT-0.6b-v3 ONNX (R11) as a secondary engine; only deploy if CPU latency budget permits and it wins on your real bench.

**Hard "do not do" list:**
- Don't enable autodetect or `task="translate"` (openai/whisper #49, #2009).
- Don't keep enriching `initial_prompt` further — you are at the U-WER ceiling (Sun et al., arXiv 2309.09552).
- Don't move to large-v3-turbo on CPU for short commands — encoder-bound; not designed for low-latency CPU.
- Don't ship Moonshine Spanish without resolving the Moonshine Community License (non-commercial restriction; github.com/moonshine-ai/moonshine).
- Don't fine-tune on synthetic-only data (arXiv 2407.17997; Kwok et al., Interspeech 2025).

---

## Caveats

- The published WER and RTF numbers cited above are dataset- and hardware-specific. Your real 105-command bench is the ground truth; treat external benchmarks as priors, not promises.
- WhisperFlow hush-word numbers (arXiv 2412.11272, MobiSys '25) require fine-tuning to fully reproduce; the unlearned silence-pad recommendation here is the OSS analog and the gain may be smaller than the paper's.
- Double Metaphone implementations (`jellyfish`, `metaphone`, `doublemetaphone` on PyPI) were tuned primarily for English surnames; for production Spanish you may need to add manual rules (Spanish J vs English J, V≈B, soft G/J, "ll"/"y") on top.
- Synthetic data via Piper/CosyVoice is useful for eval-set bootstrapping but never for sole training data; corroborate every synthetic gain on a small real-speaker held-out set.
- Whisper-small at int8 (~900 MB RAM) plus DeepFilterNet (~80 MB) plus AEC (~10 MB) plus VAD (~30 MB) totals ~1 GB before LLM/TTS — fits a typical 8 GB laptop but is tight on 4 GB; verify on lowest target hardware.
- The Diabolocom Québécois LoRA result (WER 77.38 → 45.74) is on heavily accented telephone speech where the baseline WER is unusually high; do not project the same 31.64-point absolute drop onto your bench, which already starts at 0.608 WER on a noisy ground-truth alignment. Expect a smaller absolute but consistent relative improvement.
- Wang et al. (arXiv 2502.16142) qualitatively report LLM-second-pass correction "contributes significantly" to R-WER, but the abstract does not publish a single summary R-WER reduction figure; treat R10's gain as directionally well-supported but not numerically guaranteed.
- The Spanish-English Parakeet code-switch model card (NVIDIA NIM) describes ~28 000 h of training data but does not publish per-dataset WER in the public-facing catalog page; numerical WER claims for that specific model are presently unverified outside NVIDIA's gated channels.