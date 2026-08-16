# REJECTED_HARDCODE_RUNTIME_ATTEMPT_REPORT

Date: 2026-05-05
Branch: `repo-cleanup-test-rebuild`
Checkpoint preserved: `4d9c9f2f` "Checkpoint before live runtime repair"
Diff archived: `Carter_v3/REJECTED_HARDCODE_RUNTIME_ATTEMPT.patch` (15,706 bytes)

---

## 1. What was attempted (and rejected)

A first pass of LIVE_SAFE_RUNTIME_REPAIR introduced **semantic intent detectors
keyed on user phrases and brand/category vocabulary** in core routing modules.
Concretely, the rejected diff added:

### `src/carter_v3/request_patterns.py`
- `_ALARM_REMINDER_RE` — regex over `pon|programa|set|crea ... alarma|alarm|recordatorio|reminder|despertador|temporizador|timer|countdown|cuenta regresiva`.
- `_MEDIA_PLAYBACK_RE` — regex over `reproduce|play|pause|skip|next ... cancion|song|musica|playlist|album|podcast|radio|audio`.
- `_SEND_MESSAGE_RE` — regex over `envia|send|text ... mensaje|sms|correo|email|dm|whatsapp|telegram|messenger|signal|discord|slack|tweet`.
- `_INSTALL_DOWNLOAD_RE` — regex over `instala|install|descarga|download ... juego|game|app|aplicacion|programa|driver|extension`.
- Public helpers `looks_alarm_or_reminder_request`, `looks_media_playback_request`, `looks_send_message_third_party_request`, `looks_install_or_download_request`, `looks_file_read_intent`.
- A `_FILE_READ_VERB_RE` keyed on `lee|leer|abre el archivo|muestrame|read|open the file|show the file`.

### `src/carter_v3/agent.py`
- A "capability-missing fast paths" block injected into `_run_turn_inner`
  immediately after intent classification that branched on the four
  semantic detectors above and short-circuited the turn with hand-written
  Spanish replies and `policy_blocks=["needs_environment ..."]` /
  `["needs_permission ..."]` strings. Pure if/elif over phrase shape.

### `src/carter_v3/turn_support.py`
- A new system-prompt paragraph that **enumerated brand-coupled
  non-capabilities** ("WhatsApp/Telegram/SMS/email/DM ... alarms/timers ...
  music/video"). Even inside the prompt this is brand-list policy, not a
  capability registry derivation.

### `src/carter_v3/response_composer.py`
- A `pycaw` substring branch inside `system_set_volume` that matched on the
  literal token `"pycaw"` from `next_step_hint` data.
- An `app_open` branch reading `outcome.evidence["preexisting"]` — this one
  is structural and acceptable in principle, but it was bundled with the
  rejected hardcodes and must be re-introduced separately under the V2
  plan.

### `src/carter_v3/cli/launcher.py`
- A `prior_turns` accumulator. Structural / acceptable; reverted only because
  it was in the same patch and must come back under V2 with its own audit.

---

## 2. Why this violates `ContextoCarter.md`

`ContextoCarter.md` defines Carter as **universal, local-first, honest,
verifiable, capability-driven**. Several explicit constraints were broken:

- **"Sin hardcodes por marca"** — `whatsapp|telegram|messenger|signal|discord|slack|tweet|spotify` etc. are brand strings used as routing signals. Forbidden in core.
- **"Sin hacks por app"** — alarm/reminder/media/install routes are app-category hacks: they exist *because the user log mentions those apps*, not because Carter's architecture surfaces them.
- **"Carter no debe responder por listas de frases"** — `pon|programa|crea|set ... alarma|alarm|recordatorio` is exactly a phrase list. Same for media verbs and install verbs.
- **"Universal, no hardcodeado"** — the right answer is to derive
  capability presence/absence from the **tool catalog + capability
  registry**, not from regex over the user message. If `tool_call alarm_*`
  does not exist, the router/LLM should not be able to claim success;
  that property must hold for *any* missing tool, not for a curated list
  of four.
- **"No relajar `hardcode_guard`"** — these regexes ironically
  *hardcoded* exactly the lowercase-keyword shape that `hardcode_guard`
  is supposed to prevent. They slipped through only because
  `request_patterns.py` is on the ALLOWLIST. The right move is to
  *tighten* the guard, not exploit the allowlist.
- **"Honest, verifiable"** — branching on user phrase to emit a
  pre-written "no puedo hacer X" is fake honesty: it bypasses the
  capability layer instead of representing missing capabilities as
  first-class.

In short: the patch tried to **solve runtime regressions by encoding the
user's specific log into the router**. That is exactly the failure mode
`ContextoCarter.md` exists to prevent.

---

## 3. What was reverted

| File | Action |
|---|---|
| `src/carter_v3/request_patterns.py` | `git checkout HEAD --` (back to checkpoint `4d9c9f2f`) |
| `src/carter_v3/response_composer.py` | `git checkout HEAD --` (back to checkpoint `4d9c9f2f`) |
| `src/carter_v3/agent.py` | already reverted by user undo before this session resumed |
| `src/carter_v3/turn_support.py` | already reverted by user undo |
| `src/carter_v3/cli/launcher.py` | already reverted by user undo |
| `LIVE_RUNTIME_FAILURE_AUDIT.md`, `LIVE_SAFE_RUNTIME_MATRIX.md`, `LIVE_SAFE_RUNTIME_REPAIR_PLAN.md` | already removed by user undo (were untracked) |

The full rejected diff is preserved at
`Carter_v3/REJECTED_HARDCODE_RUNTIME_ATTEMPT.patch` for audit. It is **not
applied** and must not be applied as-is.

No other files were touched. No previously accepted reports were deleted.
No `git clean` was run.

---

## 4. Post-revert state

```
$ git status --short --untracked-files=all
?? REJECTED_HARDCODE_RUNTIME_ATTEMPT.patch     # this audit artifact only
```

```
$ git log --oneline -3
4d9c9f2f (HEAD -> repo-cleanup-test-rebuild) Checkpoint before live runtime repair
12723caf WIP: snapshot current project state
63c45c50 Carter_v3: land round 10 baseline and audit closure
```

Working tree is identical to the checkpoint commit `4d9c9f2f`.

---

## 5. Validation after revert

### `python -m pytest --tb=short`
```
398 passed in 145.32s (0:02:25)
```

### `python audit/hardcode_guard.py`
```
hardcode_guard: clean (56 files scanned)
```

Baseline matches the pre-attempt baseline exactly. No regression introduced
by the revert.

---

## 6. Lessons for the next pass (V2, no hardcodes)

1. **Capability presence is derived, not detected.** If Carter cannot do
   X, that fact must come from "no tool in the catalog implements X" or
   "the tool exists but its provider raised `MissingDependency`", never
   from "the user message matches regex R".
2. **`request_patterns.py` ALLOWLIST is not a license.** Any new pattern
   added there must encode a *structural* signal (path shape, URL shape,
   number, format), not a *semantic* one (verb+noun categories, brand
   names, action families).
3. **`hardcode_guard` needs a stronger rule.** Detect identifier names
   like `*_RE` / `*_REQUEST` / `looks_*` whose body contains brand tokens
   or whose alternation list exceeds a small-N structural threshold,
   even inside ALLOWLIST files. To be added under V2 Phase 0 before any
   code change.
4. **Persona/identity belongs in a derived prompt section**, not in a
   hand-written brand-blacklist sentence. The "what Carter cannot do"
   line must enumerate from the absent capability set, not from a
   curated list.
5. **Two acceptable structural bits got contaminated by being in the
   same patch** (Windows path extraction, `prior_turns` plumbing,
   `evidence["preexisting"]` reading). They must be re-proposed in V2
   with their own justification, their own tests, and *no* coupling to
   semantic detectors.
6. **The user log is evidence of bugs, not a test fixture.** Tests must
   assert *general* behaviour ("any missing capability → NEEDS_USER with
   honest reply"), never "the literal phrase 'pon una alarma' produces
   the literal reply 'no tengo backend de alarmas'".

---

## 7. Status

- Repo: clean, on checkpoint `4d9c9f2f`.
- Suite: 398/398 green.
- `hardcode_guard`: clean.
- Rejected diff: archived as patch, not applied.
- **Next step:** wait for explicit go-ahead before starting
  `LIVE_SAFE_RUNTIME_REPAIR_V2_NO_HARDCODES`. Per the V2 charter, the
  first artifacts of V2 will be `LIVE_RUNTIME_NO_HARDCODE_AUDIT.md` and
  `LIVE_RUNTIME_NO_HARDCODE_PLAN.md` — *no code edits yet*.
