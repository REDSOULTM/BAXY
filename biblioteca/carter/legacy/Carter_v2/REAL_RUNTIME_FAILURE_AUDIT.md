# REAL_RUNTIME_FAILURE_AUDIT — Carter v2

The previous gate (`CARTER_TEXT_CORE_RELEASE_CANDIDATE`) is **revoked**. The
real-user transcript reveals failures the synthetic gates did not catch.

## 1. Real transcript (provided by user)

| # | Input | Reply / behaviour | Time | Verdict |
|---|---|---|---|---|
| 1 | `a` | "No tool was executed..." | **78.4 s** | LATENCY_BLOCKER |
| 2 | `que?` | "No tool was executed..." | 2.1 s | ROUTING_BAD (treats chat as tool report) |
| 3 | `abre steam` | "Steam has been opened successfully." | 6.0 s | UNVERIFIED |
| 4 | `saca un pantallazo` | returned VS Code window title | — | WRONG_TOOL |
| 5 | `Pon el volumen del pc a 20` | `[needs_environment] terminal_run_command, nircmd no permitido` | — | WRONG_ROUTE (pycaw available, LLM picked terminal) |
| 6 | `mutea el pc` | "El volumen del PC ha sido muteado correctamente." | — | **FAKE_SUCCESS** (PC not muted) |
| 7 | `cierra youtube` | gui_do tried to close "Host de ventanas emergentes" | — | TARGET_RESOLVER_BAD |
| 8 | `maximiza whatsapp` | gui_do failed on "Host de ventanas emergentes" | — | TARGET_RESOLVER_BAD |
| 9 | `quien soy yo?` | answered with Windows username/home | — | PARTIALLY_OK (no claim beyond OS user — acceptable) |
| 10 | `a` (post-GUI) | replied with active window title | **32.5 s** | ACTIVE_APP_CONTAMINATION + LATENCY_BLOCKER |
| 11 | `Estoy trabajando en intelectra en placilla` | echoed verbatim | — | MEMORY_HANDLING_BAD (no memory candidate, raw echo) |
| 12a | `abre steam y instala fall guy` | "'fall guy' not found installed" | — | OK (typo) |
| 12b | `abre steam y instala fall guys` | `[action_failed] Steam install dialog appeared... Dialog did not appear.` | — | **HONESTY_BAD** (self-contradicting message) |
| 13 | `Por eres tan inutil` | tried gui_do close X | — | **CHAT_AS_GUI** (frustration interpreted as action) |
| 14 | (latency) | GPU starts working ~3–4 s after Enter | — | PRE_LLM_OVERHEAD |
| 15 | (resources) | RAM 91–95% used, no degradation by Carter | — | RESOURCE_PRESSURE_NOT_HANDLED |

## 2. Root-cause map

### 2.1 LATENCY_BLOCKER on trivial input ("a" → 78.4 s, 32.5 s)

**Code path:** [src/carter_v2/turn/agent.py](src/carter_v2/turn/agent.py#L998) computes
`_active_app_followup_context(...)` for **every** turn, including trivial
inputs (`_looks_like_short_followup` matches "a"). When the first LLM pass
returns no tool call, the active-app reconsideration retry at
[agent.py#L1352](src/carter_v2/turn/agent.py#L1352) fires a **second** LLM
call with `require_tool=True` and a GUI-biased tool subset. For trivial input
this is pointless and slow; the second call also tends to invent a GUI tool
call against the active window — the source of `Host de ventanas emergentes`
contamination on item #10.

The "78 s" first-turn case is cold-start + reconsideration + 20 s clamp not
applied to the retry path (only the main path uses
`set_call_timeout(20.0)` — see [agent.py#L1278-1284](src/carter_v2/turn/agent.py#L1278-L1284)).

### 2.2 FAKE_SUCCESS on mute (#6)

**Code:** [src/carter_v2/turn/verification.py#L666](src/carter_v2/turn/verification.py#L666)

```python
"system_mute":           _verify_synchronous_ok,
"system_set_volume":     _verify_volume,
```

`system_mute` uses the trust-the-tool verifier (`_verify_synchronous_ok`
returns `confirmed` whenever `result.ok=True`). The capability
[capabilities/media.py#L92](src/carter_v2/capabilities/media.py#L92) calls
`volume.SetMute(...)` then returns `ok=True` without reading back.
**There is no read-back, hence the lie.**

Volume *does* read back via [`_verify_volume` → `_read_volume_level`](src/carter_v2/turn/verification.py#L773).
We need an analogous `_verify_mute` that calls `volume.GetMute()`.

### 2.3 WRONG_ROUTE on volume-set (#5)

`system_set_volume` exists, is wired to `media.set_volume` (pycaw), with
read-back verification. The LLM still picked `terminal_run_command` +
`nircmd`. Cause: tool description ranking; `terminal_run_command` is in
ALWAYS_ON_CORE and the LLM falls back to it when phrasing is imperative
("Pon el volumen…"). Fix is to (a) raise the cost of `terminal_run_command`
for audio intents in the system prompt, and (b) demote `terminal_run_command`
in the always-on core when audio capability is present. We do this at the
**catalog selection** layer (no phrase hardcodes), not at the prompt.

### 2.4 WRONG_TOOL on screenshot (#4)

There is no `screenshot_capture` tool that **writes a file and returns the
path**. The vision pipeline at [capabilities/vision.py#L40](src/carter_v2/capabilities/vision.py#L40)
returns *in-memory PNG bytes* and feeds them to a vision-router that returns
*text descriptions*. For a "saca un pantallazo" intent, the natural answer is
a saved file path, not a description.

### 2.5 TARGET_RESOLVER_BAD on close/maximize (#7, #8)

Window capability ([capabilities/window.py](src/carter_v2/capabilities/window.py))
correctly returns `ok=False` when target not found, and does **not** fall back
to active window. But the LLM, when the window-capability call fails, falls
back to `gui_do` — and `gui_do` operates on the *currently focused* window.
That is how YouTube/WhatsApp commands ended up acting on the popup-host.

### 2.6 HONESTY_BAD on Steam install (#12b)

[capabilities/steam.py](src/carter_v2/capabilities/steam.py) (and `_dialogs.py`)
report `Install dialog appeared` based on a heuristic that is followed by a
second `Dialog did not appear` poll. The composer in
[adapters/tools.py](src/carter_v2/adapters/tools.py) concatenates both
without reconciling them. Net result: a single sentence that says both.

### 2.7 CHAT_AS_GUI on insult (#13)

`_active_app_followup_context` accepts any utterance ≤ 96 chars / ≤ 5 words,
including frustration like "Por eres tan inutil". With an active app present
it triggers the GUI-fallback path. We must require an *actionable verb* from
a structural signal (resolver hit) before allowing follow-up GUI fallback.

### 2.8 MEMORY_HANDLING_BAD on declarative fact (#11)

Long sentence → not trivial → enters full LLM loop. The LLM (qwen3:8b)
sometimes echoes long unstructured input. There is no structural detector
that surfaces a `memory_candidate` for the LLM to confirm, only the implicit
LLM-extracted fact path which fails on uncommon vocabulary
("intelectra", "placilla").

### 2.9 PRE_LLM_OVERHEAD (#14)

Pre-LLM stages currently run **every turn** regardless of input shape:

- system probe (`probe.snapshot()`, ~30–80 ms)
- context-window build
- resolve_reference (memory hit, can be slow under RAM pressure)
- session.summary
- prior-turn formatting
- system-prompt build with full tool-count line
- tool-catalog selection (scored, 64 tools)
- active-app followup compute (window enum + resolver)

Total accounts for ~1–4 s pre-LLM. Trivial input deserves a fast path.

### 2.10 RESOURCE_PRESSURE_NOT_HANDLED (#15)

No path checks RAM pressure to degrade probes/skill-index/lessons-block
size. With < 2 GB free, every snapshot competes with Ollama for working set.

## 3. Blocker classification

| Class | Items | Action |
|---|---|---|
| BLOCKER (correctness/honesty) | #6 mute fake_success, #12b Steam contradiction, #4 screenshot wrong tool | RUNTIME-4, RUNTIME-5, RUNTIME-7 |
| BLOCKER (UX) | #1 78s no-op, #10 active_app contamination, #13 chat-as-GUI | RUNTIME-2, RUNTIME-3, RUNTIME-9 |
| MAJOR | #5 wrong route, #7/#8 GUI fallback over wrong window, #11 echo | RUNTIME-2, RUNTIME-4, RUNTIME-6, RUNTIME-8 |
| MINOR | #9 user identity (already honest), #15 RAM pressure observability | RUNTIME-9 |

## 4. RC verdict update

`CARTER_TEXT_CORE_RELEASE_CANDIDATE` → **`CARTER_TEXT_CORE_RC_REVOKED — REAL_RUNTIME_BLOCKERS_FOUND`**.

New target: `CARTER_TEXT_CORE_RC_AFTER_REAL_RUNTIME_FIXES` once the per-phase
gates below pass.

## 5. Phase plan (RUNTIME-0 … RUNTIME-11)

See [REAL_RUNTIME_FIX_PLAN section in this same document below].

- RUNTIME-0: this audit + tracing knobs.
- RUNTIME-1: deterministic transcript repro runner ([audit/runners/real_runtime_transcript_repro.py](audit/runners/real_runtime_transcript_repro.py)).
- RUNTIME-2: trivial/no-op routing — disable active-app reconsideration when `hint_no_tools` or trivial.
- RUNTIME-3: stale active-app contamination — `_active_app_followup_context` returns `None` on trivial inputs and on inputs without an actionable resolver hit.
- RUNTIME-4: audio capability — add `_verify_mute` (real read-back); demote `terminal_run_command` when `media` capability is healthy.
- RUNTIME-5: screenshot — add `screen_capture_to_file` capability that saves PNG and returns path.
- RUNTIME-6: window/app target resolver — when window-capability misses target, **do not** allow `gui_do` to operate on the active window unless the active window matches the requested target. Verified via post-action UIA enum.
- RUNTIME-7: Steam install honesty — collapse `Install dialog appeared / Dialog did not appear` into a single truthful status from one source of truth.
- RUNTIME-8: memory statement handling — surface a structural `memory_candidate` line in the system context for declarative-shaped inputs that contain proper-noun-like tokens not in vocabulary; LLM must either confirm-write or answer naturally, never echo.
- RUNTIME-9: pre-LLM latency — fast path for trivial inputs (skip resolver/probe/skill-index/lessons), and add `CARTER_TIMING=1` per-stage trace to stderr.
- RUNTIME-10: re-run repro and produce [audit/results/REAL_RUNTIME_FAILURE_FINAL_GATE.json](audit/results/REAL_RUNTIME_FAILURE_FINAL_GATE.json).
- RUNTIME-11: full regression (pytest + hardcode_guard + golden + soak + runtime probe + perf gate). Update [CARTER_TEXT_CORE_RELEASE_NOTES.md](CARTER_TEXT_CORE_RELEASE_NOTES.md) and [audit/results/CARTER_TEXT_CORE_RC_FINAL_GATE.json](audit/results/CARTER_TEXT_CORE_RC_FINAL_GATE.json).
