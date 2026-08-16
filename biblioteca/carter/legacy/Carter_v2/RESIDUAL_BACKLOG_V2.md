# RESIDUAL_BACKLOG_V2

Open items left after CARTER_TEXT_BLOCK_LANDING_V2. Each entry is a real
behavior observed in run14a/b/c (warm safe-live, qwen2.5:7b-instruct).
Items are kept open here so the next mission cannot silently drop them.

This file *replaces* the open items in
[RESIDUAL_BACKLOG_AFTER_BLOCK.md](RESIDUAL_BACKLOG_AFTER_BLOCK.md) for
the entries that were touched by V2; everything not listed here remains
as documented in that file.

---

## B-1.v2  Case 8 — model hallucinates declarative tool execution

**Symptom (run14a/b/c, all three):**

```
input:  maximiza whatsapp
reply:  'Entendido, he maximizado WhatsApp. ¿Necesitas algo más?'
        result_ok=True   tool_calls=[]
        action_route_inaction=False
```

The model emits `NO_TOOL_NEEDED:` followed by a declarative claim that
the action was performed, plus a courtesy question. Substantive-chat
detection (declarative content before `?`) returns ok=True; the
sentinel skips the resolver retry; the user is told the action
happened when nothing was called.

**Why V2's resolver did not catch this:** the V2 fix made the
clarifying-question path ignore the sentinel, but kept the resolver
respecting the sentinel as the LLM-first override. A declarative reply
with no `?` therefore still bypasses both.

**Why deferred:** the honest fix is a **post-LLM hallucination guard**:
on action-route turns where (a) `hint_no_tools=False`, (b) no tool was
called, (c) the reply contains a first-person past/perfective claim
("he maximizado", "I muted"), AND (d) the ResourceResolver finds a
matching window/process, rewrite the reply to a structural challenge or
force a constrained retry. That requires a structural verb-form
detector (perfective auxiliary in any of the whitelisted languages)
that does **not** hardcode a verb list — non-trivial.

**Acceptance criteria:**
- Cases 6 and 8 produce either a real tool call or a `[needs_user]` /
  `[no_action_executed]` banner in 2 of 3 consecutive safe-live runs.
- No regression on cases 9, 10, 11, 13.
- New unit tests covering declarative-claim-of-action without a tool
  call in es + en.

---

## B-2.v2  Case 11 — declarative-fact memory route still LLM-only

Unchanged from [B-2 in RESIDUAL_BACKLOG_AFTER_BLOCK.md](RESIDUAL_BACKLOG_AFTER_BLOCK.md).
V2 explicitly declared this INVESTIGATED_NOT_LANDED rather than ship a
lexical patch. Live evidence (run14): a/b fail, c passes — model
variance, not a fix. Acceptance criteria from the original B-2 entry
hold.

---

## B-3.v2  Case 1 — last 2-3 s above the 5 s Jarvis budget

V2 closed the 8.0 s contract floor (3/3 runs, 7.3 - 7.7 s). Closing the
remaining gap to ≤ 5 s requires one of:

- An explicit `keep_alive` argument on the preload call so the model
  stays loaded between `__post_init__` and the first user turn.
- A daemon/thread that keeps Ollama warm with periodic zero-token
  pings.
- Moving the preload out of `__post_init__` and into a launcher-side
  pre-warm step that runs before the user types.

All three are operational changes the user should sign off on. Out of
scope for V2.

**Acceptance criteria:** c1 latency ≤ 5 s in 2 of 3 consecutive
safe-live runs against a freshly-launched Ollama, with no regression on
case 9 / 10 / 13 latencies.

---

## B-4  Case 2 — `que?` low-information path

Unchanged from [B-4 in RESIDUAL_BACKLOG_AFTER_BLOCK.md](RESIDUAL_BACKLOG_AFTER_BLOCK.md).
This is a **contract dispute**, not a runtime bug: should an ambiguous
one-token user input be answered with a clarifying question instead of
the generic low-info fallback? Choice belongs to the next mission.

---

## B-5  recovery/classifier.py lexical hardcodes

Unchanged from [B-5 in RESIDUAL_BACKLOG_AFTER_BLOCK.md](RESIDUAL_BACKLOG_AFTER_BLOCK.md).
Pre-existing tech debt; V2 did not touch this file and did not make it
worse.

---

## B-6  dry-run is router-only

Unchanged from [B-6 in RESIDUAL_BACKLOG_AFTER_BLOCK.md](RESIDUAL_BACKLOG_AFTER_BLOCK.md).
V2 still respects the `[ROUTER-ONLY: NOT live evidence]` disclaimer.

---

## V2-NEW  lingua wheel size

The structural language detector pulls in
`lingua-language-detector==2.1.1` whose wheel is **95.9 MB** vs the
≤ 25 MB the V2 spec estimated. Disclosed honestly in the V2 audit;
listed here so the next mission can make an informed choice between
keeping lingua, swapping to a smaller-but-still-structural detector
(`fast-langdetect`, `lingua-py-tinyset`), or accepting the size.

---

## V2-NEW  language detector short-input floor

`detect_language` returns `"und"` for inputs with fewer than four
alphabetic tokens (otherwise lingua mis-classifies short Spanish:
`mutea el pc` → en, `Por eres tan inutil` → it). On `"und"` we defer to
the LLM's existing reply-in-user-language instruction. This is the
honest minimum precision the structural detector can guarantee. Closing
the gap requires either a per-language minimum confidence threshold
tuned against a labelled short-input corpus, or pairing lingua with a
fallback signal (tokenization stats, character-class mix) — out of
scope for V2.

---

## Summary table

| ID       | Case(s) | Status from V2          | Owner of next fix                                           |
| -------- | ------- | ----------------------- | ----------------------------------------------------------- |
| B-1.v2   | 6, 8    | open (resolver respects sentinel) | post-LLM hallucination guard |
| B-2.v2   | 11      | INVESTIGATED_NOT_LANDED | NER-based or classifier-head memory-intent detector         |
| B-3.v2   | 1       | partial (8 s floor closed) | persistent Ollama keep-alive / launcher pre-warm         |
| B-4      | 2       | contract dispute        | next mission decides runtime vs contract                    |
| B-5      | n/a     | pre-existing debt       | recovery classifier rewrite mission                         |
| B-6      | n/a     | structurally fixed      | enforcement only                                            |
| V2-NEW-1 | n/a     | size disclosure         | next mission decides keep / swap / accept                   |
| V2-NEW-2 | short inputs | precision floor    | tuned threshold or paired signal                            |
