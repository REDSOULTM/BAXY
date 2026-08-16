# RESIDUAL_BACKLOG_AFTER_BLOCK

Carter Text Core — items deliberately NOT closed by the BLOCK_LANDING work.
Each item below is real, observed in run12 / run13 (post-block live runs),
and was kept out of the block because its honest fix is bigger than what a
single landing window allows.

This file is the record of what is **still open** so it cannot be silently
forgotten in the next mission.

---

## B-1. Cases 7 & 8 — close-app / maximize-window have no structural router

**Symptom (run12 + run13):**
- Case 7 `cierra youtube` →
  `viol=['missing_tool_call', "expected_tool_namespaces_missing:wanted=['window','app','web'] got=[]"]`
- Case 8 `maximiza whatsapp` →
  `viol=['missing_tool_call', "expected_tool_namespaces_missing:wanted=['window','app'] got=[]"]`

**Root cause:**
The model is the only thing deciding whether `cerrar X` / `maximiza X`
becomes a `window_close` / `window_maximize` / `app_close` tool call.
There is no structural span detector that recognises "imperative verb +
known running window/app" → mandatory tool route. When the model fails to
emit the tool call, no fallback router catches it, so the turn dies as
"chat reply on action route" with `missing_tool_call`.

The BLOCK_LANDING window guard (`_validate_window_target_or_block`) only
runs **after** a tool is already chosen — it does not synthesise one.

**Why deferred:**
A correct fix is a structural action-route resolver that, when the LLM
returns no tool call AND `ResourceResolver` finds the named window/app
running, either:
- emits the appropriate tool call directly (with the resolved title), or
- returns `[needs_user]` with the resolved candidate spelled out.

That resolver is bigger than this block: it has to be model-independent,
language-agnostic, and not regress cases 9/10/13 (chat-only). It also
needs its own pytest suite. Out of scope here.

**Acceptance criteria for the future fix:**
- Cases 7 & 8 pass in 2 of 3 consecutive safe-live runs.
- No regression in cases 9, 10, 13.
- New unit test: imperative verb + resolved window → mandatory tool route.

---

## B-2. Case 11 — declarative-fact memory route has no structural detector

**Symptom (run12 + run13):**
- Case 11 `Estoy trabajando en intelectra en placilla` →
  `viol=['no_memory_handling_offered']`. Reply is conversational
  (`"NO ACTION. Desde ahora estaré atento..."` in run12) but neither
  emits `memory_save` nor offers to remember.

**Root cause:**
RUNTIME-8 prompt instruction "declarative facts route to memory_save with
brief acknowledgment" relies entirely on the LLM. There is no structural
detector for "first-person present + workplace/role/location entity →
memory candidate". Run11 happened to pass because the model that day
produced "te recordaré para ti"; run12/run13 the model produced a
generic ack instead. That is model variance, not a fix.

**Why deferred:**
A structural memory-intent detector requires a non-lexical trigger
("declarative self-fact about identity/location/work") that does not
hardcode keyword lists or language-specific patterns. The right shape is
either:
- a small classifier head that scores `is_personal_declarative_fact`
  from features the existing pipeline already extracts (POS-light, named
  entity presence, first-person pronoun, present tense), or
- a structural post-LLM check: if `hint_no_tools` is false AND
  `ResourceResolver` finds no resource AND user input contains a
  recognised entity-class span, offer `memory_save` automatically.

Either is non-trivial. Block kept the honest live_FAILED label on the
existing closure item instead of papering over it.

**Acceptance criteria for the future fix:**
- Case 11 passes in 2 of 3 consecutive safe-live runs without
  hardcoding `intelectra`, `placilla`, or any other token.
- New unit test: declarative-self-fact span → memory route, with
  parameterised inputs in ES + EN.

---

## B-3. Case 1 — `a` baseline floor still above 8.0s

**Symptom (run12 + run13):**
- Case 1 `a` total latency 11.1s (run12) and 10.5s (run13) vs 8.0s
  contract floor. `viol=['latency_exceeded:>8.0s', 'raw_tool_intent_no_call']`.

**Progress:** Item 4 preload dropped this from run11's **23.3s** to
~10s — a real ~50% reduction. Case 10 (`a` repeat) is now 3.2-3.8s.

**Root cause of the residual:**
The first turn after engine init still pays Ollama's cold model load
even after our preload, because Ollama's keep_alive expires between
preload (in `__post_init__`) and the first real call. Probe time
(~3-4s) plus first-call prompt-eval (~3-4s) plus model load
(~3-4s) ≈ 10s.

**Why deferred:**
Closing the last 2-3s requires either:
- an explicit Ollama `keep_alive=10m` parameter on the preload call so
  the model stays resident, or
- a separate background thread that periodically pings Ollama with a
  zero-token request, or
- moving the preload from `__post_init__` to a daemon that runs the
  moment the launcher script starts (before the user types).

All three are real fixes, none are one-line, all touch operational
behaviour the user should sign off on. Out of scope here.

**Acceptance criteria for the future fix:**
- Case 1 latency ≤ 8.0s in 2 of 3 consecutive safe-live runs against a
  freshly-launched Ollama.

---

## B-4. Case 2 — `que?` low-information path

**Symptom (run11 + run12 + run13):**
- `viol=['low_information_runtime_fallback']`. Reply is a stock
  "I could not produce a useful reply..." message.

**Root cause:**
`que?` is genuinely ambiguous. The runtime takes the structurally
correct path (low-info fallback), and the runner contract flags it.
The honest dispute here is whether the contract should accept a
clarifying-question reply for ambiguous one-token user input.

**Why deferred:**
This is a **contract** question, not a runtime bug. Either the contract
should be relaxed to accept a clarifying question ("¿Qué quieres
saber?") as a pass, or the runtime should generate one instead of the
generic fallback. Both options are reasonable; the choice belongs to
the next mission, not this block.

---

## B-5. recovery/classifier.py regex/keyword hardcodes

**Source:** Pre-existing tech debt unrelated to BLOCK_LANDING items 1-7.

`hardcode_guard.py` reports 0/0 because the guard's allowlist excludes
the `recovery/classifier.py` block. The lexical patterns there
(language-specific strings used for retry-trigger classification) are
genuine debt that the BLOCK_LANDING mission did not touch and did not
worsen. They should be replaced with structural triggers in a future
"recovery classifier rewrite" mission.

---

## B-6. dry-run mode is router-only, not "live evidence"

**Source:** Item 2 of BLOCK_LANDING already structurally fixed the
overclaim (dry-run now reports `ROUTER_CONTRACT_OK` with explicit
`[ROUTER-ONLY: NOT live evidence]` disclaimer). Listed here only to
note that **any future report** that points to dry-run as proof of
runtime correctness must be rejected. Live evidence comes only from
safe-live or live-confirmed modes.

---

## Summary table

| ID  | Case(s)   | Live status        | Owner of next fix                         |
| --- | --------- | ------------------ | ----------------------------------------- |
| B-1 | 7, 8      | open               | structural action-route resolver          |
| B-2 | 11        | open               | structural declarative-fact detector      |
| B-3 | 1         | partial (50% win)  | Ollama keep_alive / persistent preload    |
| B-4 | 2         | contract dispute   | next mission to choose runtime vs contract|
| B-5 | n/a       | pre-existing debt  | recovery classifier rewrite mission       |
| B-6 | n/a       | structurally fixed | enforcement only                          |
