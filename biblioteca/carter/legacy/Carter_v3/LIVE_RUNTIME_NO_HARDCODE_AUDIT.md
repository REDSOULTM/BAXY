# LIVE_RUNTIME_NO_HARDCODE_AUDIT

Date: 2026-05-05
Branch: `repo-cleanup-test-rebuild`
Baseline checkpoint: `4d9c9f2f` ("Checkpoint before live runtime repair")
Baseline suite: 398/398 green; `hardcode_guard` clean (56 files).
Predecessor: `REJECTED_HARDCODE_RUNTIME_ATTEMPT_REPORT.md` (rejected pass V1).

This document is **diagnosis only**. No code changes are proposed here.
The repair plan lives in `LIVE_RUNTIME_NO_HARDCODE_PLAN.md`.

---

## 1. Why the V1 attempt was hardcode

V1 tried to repair runtime regressions by adding **semantic intent
detectors** keyed on user phrasing and on brand/category vocabulary in
core routing modules. Specifically it added regex constants
`_ALARM_REMINDER_RE`, `_MEDIA_PLAYBACK_RE`, `_SEND_MESSAGE_RE`,
`_INSTALL_DOWNLOAD_RE`, public `looks_*` helpers over them, an
agent-loop fast-path block of `if looks_X_request(user_text): return ...`
arms, a system-prompt paragraph that listed brand non-capabilities
(`WhatsApp/Telegram/SMS/email/DM/...`), and a `pycaw` substring branch in
the response composer.

This was hardcode in three independent ways:

1. **Phrase-keyed routing** — branching on the user's exact verb+noun
   shape (`pon|programa|crea|set ... alarma|alarm|recordatorio`). The
   router decided behaviour from the message text instead of from
   structural runtime state.
2. **Brand/category vocabulary in core** — `whatsapp|telegram|messenger|signal|discord|slack|tweet|spotify|...`
   used as routing tokens. Future apps would need new branches; absent
   apps would silently bypass the path.
3. **Per-app responses** — pre-written Spanish replies coupled to those
   four categories. The repair "passed the user's log" by encoding the
   log into the code.

## 2. Rules in `ContextoCarter.md` that V1 violated

- "Carter debe ser universal, no hardcodeado."
- "Carter no debe tener hacks por app."
- "Carter no debe tener hardcodes por marca."
- "Carter debe funcionar por intención, capacidades disponibles, recursos
  reales, tool catalog, policy, verifier y contexto estructurado."
- "Carter no debe funcionar por listas de frases."
- "Honest, verifiable, sin fake success."

V1 substituted the capability layer (tool catalog + verifier + policy) with
a phrase layer. Even when its outputs were honest, the *mechanism* was the
exact failure mode `ContextoCarter.md` exists to prevent.

## 3. Real runtime regressions to repair (from the user's live Ollama log)

Each regression below is described as **observed user-visible behaviour**
plus **likely structural root cause**. None of these may be repaired by
phrase matching.

| # | User-visible bug                                                                       | Structural root cause hypothesis |
|---|----------------------------------------------------------------------------------------|----------------------------------|
| 1 | "Abre steam" while Steam already running → confusing UNVERIFIED reply                  | Composer ignores `outcome.evidence["preexisting"]` already produced by `_app_open` verifier. |
| 2 | "Abriste steam?" follow-up replied as a generic LLM (no awareness of last turn)        | Launcher REPL never accumulates `prior_turns`; agent sees each turn in isolation. |
| 3 | "Pon el volumen del PC a 20" → vague "no pude verificar" when `pycaw` is missing        | Composer ignores `data["next_step_hint"]` already produced by `_system_set_volume`; mission status does not map missing-dependency → NEEDS_ENVIRONMENT. |
| 4 | "pon una alarma a las 9 am" → LLM may reply "alarma puesta" with no tool executed       | Catalog has no alarm tool. LLM is not told the catalog explicitly, so it hallucinates. The existing `looks_action && no_tool` NEEDS_USER path catches the no-tool case, but the system prompt doesn't make the LLM honest. |
| 5 | "pausala" / "para la música" with no media context → invented success                   | Same as #4. No media tool in catalog; LLM not constrained. |
| 6 | "envíale por WhatsApp/Discord ..." → could try unsafe routes                            | No messaging tool in catalog; system prompt doesn't enumerate the absence; high-risk tools (`gui_*`, `terminal_*`) require approval but the LLM is not warned. |
| 7 | "instala fall guys" / "descarga X" → could try unsafe routes                             | Same root: catalog has no install/download tool; the existing `install_requires_confirmation` policy rule only fires if a tool is invoked. |
| 8 | "Me llamo red" + "como me llamo?" inconsistent across turns                              | `prior_turns` lost (#2 root cause); `memory_save` flow exists but depends on follow-up/memory-offer state that the launcher does not preserve. |
| 9 | "lee C:\…\ContextoCarter.md que es?" + "Sí" → second turn does not continue read intent | No generic pending-intent state. `pending_tool_approval` exists but only for explicitly offered HIGH-risk approvals, not for generic "want me to read X?" follow-ups. |
| 10 | "Puedes ver tu código?" → LLM denies filesystem capability                              | System prompt does not enumerate tool catalog; LLM defaults to its prior cloud persona. |
| 11 | "Cuál es tu arquitectura?" → generic LLM answer                                          | Same as #10. No persona section derived from project metadata. |
| 12 | "Sos iron man?" → English answer or generic refusal                                      | System prompt has no language-mirroring rule and no Carter persona. |
| 13 | "HGOla" (typo) → classified as action / asks clarification awkwardly                    | Greeting typo trips imperative heuristic in `intent_classifier`; not a hardcode target — accept current behaviour as a downstream concern. |
| 14 | LLM replies "no tengo acceso a archivos" when filesystem tools exist                    | System prompt absent → LLM falls back to its training-time refusal patterns. |

## 4. Universal repair surfaces (and what NOT to touch)

The fixes for items 1–12 cluster onto **seven structural surfaces** that
already exist in the codebase and just need to be used:

A. **Tool catalog as the single source of truth for capabilities.**
   `tools/catalog.py` already declares the 32 tools. The system prompt
   should derive its capability listing from this catalog at build time,
   not from a hand-written sentence. The *absence* of an alarm/media/messaging/install
   tool then becomes self-evident to the LLM without naming any app.

B. **`outcome.evidence["preexisting"]` for `app_open`.**
   `tools/verifier.py::_app_open` already records this flag on PENDING
   outcomes when the matched process predates `launch_time`. The
   composer's `app_open` UNVERIFIED branch must read it and emit a
   different honest sentence ("ya estaba abierto antes de tu comando").
   This is *reading existing structural evidence*, not phrase routing.

C. **`data["next_step_hint"]` propagation.**
   `tools/dispatch_system.py::_system_set_volume` already sets this when
   the `pycaw` import fails. Other dispatchers can do the same on any
   missing dependency. The composer should append this hint generically
   to **any** failed-tool reply (no tool name special-casing). This is
   plumbing, not routing.

D. **`data["missing_dependency"]` → `policy_blocks=["needs_environment ..."]`.**
   `compute_mission_status` already maps `policy_blocks` containing the
   substring `needs_environment` to NEEDS_USER + termination_reason
   `needs_environment`. The agent can convert a single executed tool
   that returned `data["missing_dependency"]` into that policy block.
   Universal: applies to any future dependency too, no per-package code.

E. **`prior_turns` plumbing in the REPL.**
   The launcher already passes `prior_turns` through `engine.run_turn(text, prior_turns=…)`
   in tests; the CLI loop simply does not maintain a list. Restoring it is
   pure infrastructure with no semantic content.

F. **System prompt persona + capability render.**
   `turn_support.build_messages` produces the only system prompt Carter
   sees. Today it is two lines of generic advice. It must:
   - state Carter's identity and locality (one short paragraph, no brand
     list, no NOT-capability list);
   - render the tool catalog as a bulleted list (name + description);
   - mirror the user's language by simple instruction ("respond in the
     user's language");
   - state the no-fake-success contract explicitly;
   - **not** include a brand/category list of forbidden domains. The
     forbidden domains follow automatically from "I can only do what is
     in the listed tools."

G. **`hardcode_guard` hardening.**
   The current guard catches brand strings in `if`-tests and 6+ entry
   lowercase keyword tuples, but ALLOWLISTS `request_patterns.py`. This
   is the gap V1 exploited. The guard must ALSO scan ALLOWLISTED files
   for *named regex constants* whose pattern source contains brand
   tokens, action-category alternations, or the rejected detector
   suffixes (`SEND_MESSAGE_RE`, `MEDIA_PLAYBACK_RE`, `ALARM_REMINDER_RE`,
   `INSTALL_DOWNLOAD_RE`). The allowlist exists for *morphological*
   patterns; semantic intent regex is never allowed regardless of file.

What must NOT be touched:

- Tool dispatcher per-tool semantics.
- Verifier rules.
- Memory store schema.
- Policy engine risk levels.
- `intent_classifier`'s structural heuristics (typos like "HGOla" land
  here; #13 above is out of scope for this pass).
- Any per-brand or per-app code path.

## 5. Modules under review (for reference; not all will change)

- [src/carter_v3/cli/launcher.py](src/carter_v3/cli/launcher.py) — REPL `prior_turns` plumbing only (E).
- [src/carter_v3/turn_support.py](src/carter_v3/turn_support.py) — `build_messages` system prompt rewrite (F).
- [src/carter_v3/response_composer.py](src/carter_v3/response_composer.py) — read existing evidence/data fields (B, C).
- [src/carter_v3/agent.py](src/carter_v3/agent.py) — convert `missing_dependency` to policy block (D); no semantic fast paths.
- [src/carter_v3/contracts.py](src/carter_v3/contracts.py) — already maps `needs_environment`; no change expected.
- [src/carter_v3/tools/catalog.py](src/carter_v3/tools/catalog.py) — read-only (A).
- [audit/hardcode_guard.py](audit/hardcode_guard.py) — harden (G).
- [tests/](tests/) — add `test_no_semantic_hardcodes.py`, `test_runtime_persona_and_capabilities.py`, `test_pending_intent_followups.py`, `test_runtime_no_fake_success_live_cases.py`, `test_live_regressions_from_user_log.py`. Tests assert *behaviour*, never specific phrasing fixtures.

## 6. Things that must NOT be implemented in this pass

- ❌ Any `_*_RE` regex constant whose body lists action verbs paired with
  category nouns (alarm/media/message/install/download).
- ❌ Any `looks_alarm_*`, `looks_media_*`, `looks_send_message_*`,
  `looks_install_*`, `looks_*_intent` helper.
- ❌ Any `if looks_X_request(user_text):` branch in agent/composer/router.
- ❌ Any tuple/set/dict literal in core routing whose elements are app
  brand names (`steam|spotify|whatsapp|...`).
- ❌ Any `_DONE_ANCHORS`-style multilingual claim list extension. The
  existing `_DONE_ANCHORS` is grandfathered as the single audited
  security guard list and remains size-frozen.
- ❌ Any composer arm that returns a hand-written app/category-specific
  sentence ("no tengo backend de alarmas …", "no envío whatsapp …").
- ❌ Any prompt sentence that names a brand or category as a
  non-capability. The catalog list does the job.

## 7. Invariants the repair must preserve

- `pytest` baseline stays 398/398 (any new test only adds, never relaxes).
- `hardcode_guard` returns 0 (and gets stricter, not laxer).
- No tool semantics change.
- No mission_status mapping rule loosens.
- No live action is taken without verifier or approval.
- Repository memory in [/memories/repo/](../../memories/repo/) is not edited.

---
End of audit.
