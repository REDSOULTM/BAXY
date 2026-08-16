# Carter v2 - Session 15 Gap Audit

Scope: core only. Voice, live STT/TTS conversation, webcam, and screen/camera pipelines are intentionally out of scope.

| Area | Estado | Evidencia | Accion |
|---|---|---|---|
| S9 capabilities | DONE | `src/carter_v2/capabilities/{pdf,email,calendar,media_files,code,database,filesystem,network,system,window,office,scheduler}.py`; unit coverage in `tests/test_*capabilit*.py`, `tests/test_session9_extended_capabilities.py`, `tests/test_code_database_capabilities.py`, `tests/test_window_office_session9.py`; S10 probe block covers the exposed tools. | No tocar capabilities. Mantener skips por dependencia externa con hints. |
| S10 exhaustive probe | DONE | `probe_all_tools.py` has S10 blocks for PDF, email, calendar, media, filesystem, network, system, window, code, database, scheduler, office, plus readiness and classified skip output. `probe_environment_readiness.json` is generated. | Added S15 universal probes without changing existing S10 coverage. |
| S11 fixes | DONE | `probe_session11_failed_results.json` documents no remaining S10 failures after routing fixes; `tests/test_tool_normalizer.py` and `tests/test_registry_errors.py` cover routing/registry regressions. | No S11 fix reopened. |
| auto universal routing | PARTIAL -> DONE | Before S15, universal runner required `/task` or `CARTER_UNIVERSAL_PLAN_RUNNER`. S15 adds non-invasive automatic execution when the normal LLM response itself contains a structurally valid `TaskFrame` that warrants universal execution. Tests in `test_universal_agent_kernel.py`. | Implemented without regex, language branches, or app-specific hacks. Legacy loop still owns ordinary tool calls. |
| rich resume state | PARTIAL -> DONE | Before S15, checkpoint saved graph and node ids only. S15 adds schema version, run summary, artifacts, criteria met/pending, dependency status, failure kind, and node summaries in `universal/runner_types.py`, `runner.py`, and `checkpoint.py`. | Implemented and tested through checkpoint assertions. |
| universal app-building probes | MISSING -> DONE | Before S15, only `UNIV-1..3` simple universal probes existed. S15 adds `S15-APP-1`, `S15-APP-2`, `S15-DATA-1`, `S15-RESUME-1`, `S15-MISSING-1` to `probe_all_tools.py`. | `probe_session15_results.json`: 5/5 PASS, 0 FAIL, 0 ERROR, 0 SKIP. |
| legacy migration | PARTIAL -> DONE for high-value complex cases | Legacy loop remains for simple single-tool and conversation turns. Complex structured `TaskFrame` output now migrates automatically to universal runner. `/task` and `/resume` remain explicit override paths. | Documented in `session15_migration_notes.md`. |
| memory/skills promotion | PARTIAL | Existing main loop promotes deterministic legacy recipes only after successful turns and critic scoring. Universal verified skill promotion is not yet implemented. | No new memory system in S15; keep as future work because it needs product policy decisions and should not be rushed into core execution. |
| S14 no regex/hardcoded-language/app hacks | DONE for new S15 path | Universal auto selector uses `TaskFrame` structure: work unit count, dependencies, success criteria, mutation flags, mutation scope, and requirement count. No localized keyword rules or app-name shortcuts were added. | Existing legacy fallbacks remain as compatibility, not expanded. |

## Brechas cerradas en S15

- Automatic universal path can execute a complex `TaskFrame` emitted by the normal LLM lane without `/task`.
- Universal checkpoints now carry usable resume/debug state, not just completed node ids.
- Universal probes now cover app creation, app execution, data transformation, resume, and honest missing-capability blocking.
- `/tasks` now surfaces pending criteria and artifact counts from rich checkpoints.

## Brechas deliberadamente no cerradas

- Universal skill promotion remains partial. It should only save verified, reusable skills, but tying that into long-running tasks requires a stricter product policy for what counts as reusable learning. The current session did not add speculative memory behavior.
- Voice/camera are intentionally untouched.
