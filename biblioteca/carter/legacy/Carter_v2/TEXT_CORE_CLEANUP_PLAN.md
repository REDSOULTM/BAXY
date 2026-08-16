# TEXT_CORE_CLEANUP_PLAN — Carter v2 (Release Candidate)

Classification of repo files for the post-RC cleanup pass. **No file is deleted
by this document.** Deletions require explicit user confirmation. This is a
plan, not an action.

Buckets:

- **keep** — production code, active runners, current docs.
- **archive** — historical reports / audits worth preserving but not in the
  active doc set; move to `documentacion/archive/` if cleanup is approved.
- **candidate_delete** — superseded artifacts, debug dumps, one-off logs.
- **generated_results** — auto-emitted by runners; safe to regenerate.
- **obsolete** — predates v2 architecture; keep only for reference.
- **do_not_delete** — base configs, root scripts, reference codebases.

---

## Carter_v2/

### keep
- [src/carter_v2/](src/carter_v2) — entire production package.
- [tests/](tests) — full test suite.
- [audit/runners/](audit/runners) — all 18 runners + the 3 new RC runners.
- [audit/hardcode_guard.py](audit/hardcode_guard.py)
- [pyproject.toml](pyproject.toml), [run.py](run.py), [README.md](README.md)
- All `TEXT_CORE_*.md` and `CARTER_TEXT_CORE_*.md` files at the v2 root.

### archive (move to `documentacion/archive/` if cleanup is approved)
- [ACTION_FAILED_ELIMINATION_REPORT.md](../ACTION_FAILED_ELIMINATION_REPORT.md), [ACTION_FAILED_ELIMINATION_AUDIT.md](../ACTION_FAILED_ELIMINATION_AUDIT.md)
- [CARTER_TEXT_FINAL_CLOSURE_REPORT.md](../CARTER_TEXT_FINAL_CLOSURE_REPORT.md), [CARTER_TEXT_FINAL_CLOSURE_AUDIT.md](../CARTER_TEXT_FINAL_CLOSURE_AUDIT.md)
- [FULL_LIVE_LLM_VALIDATION_REPORT.md](../FULL_LIVE_LLM_VALIDATION_REPORT.md)
- [PERFORMANCE_AND_HARDCODE_REPORT.md](../PERFORMANCE_AND_HARDCODE_REPORT.md), [PERFORMANCE_AND_HARDCODE_AUDIT.md](../PERFORMANCE_AND_HARDCODE_AUDIT.md)
- [SKIPPED_LIVE_VALIDATION_REPORT.md](../SKIPPED_LIVE_VALIDATION_REPORT.md), [SKIPPED_LIVE_VALIDATION_AUDIT.md](../SKIPPED_LIVE_VALIDATION_AUDIT.md)
- [ULTRA_LATENCY_REPORT.md](../ULTRA_LATENCY_REPORT.md)
- [LLM_CONTEXT_MEMORY_REPORT.md](LLM_CONTEXT_MEMORY_REPORT.md), [LLM_CONTEXT_MEMORY_AUDIT.md](LLM_CONTEXT_MEMORY_AUDIT.md)
- [FULL_LIVE_LLM_TEST_AUDIT.md](FULL_LIVE_LLM_TEST_AUDIT.md), [REPO_CLEANUP_AUDIT.md](REPO_CLEANUP_AUDIT.md), [ULTRA_LATENCY_AUDIT.md](ULTRA_LATENCY_AUDIT.md), [CODEBASE_DIET_PLAN.md](CODEBASE_DIET_PLAN.md), [LLM_AUTONOMY_BOUNDARY.md](LLM_AUTONOMY_BOUNDARY.md)

### generated_results (safe to regenerate; keep latest, prune older)
- [audit/results/](audit/results) — all `*.json` here. Keep:
  `TEXT_CORE_RC_GATES.json`, `TEXT_CORE_SOAK_TEST.json`,
  `TEXT_CORE_GOLDEN_MATRIX.json`, `CARTER_TEXT_CORE_RC_FINAL_GATE.json`,
  `RUNTIME_TOOL_PROTOCOL_FINAL_GATE.json`,
  `PERFORMANCE_AND_HARDCODE_FINAL_GATE.json`,
  `FULL_LIVE_LLM_VALIDATION_LIVE_SAFE.json`,
  `SKIPPED_LIVE_FINAL_GATE.json`, `AUTO_MODEL_STACK_FINAL_GATE.json`,
  `MODEL_RECOMMENDATION.json`.
- Older variants like `*_PREOPT.json`, `*_postopt1.json`,
  `FULL_LIVE_LLM_VALIDATION_DRY_RUN.json`,
  `FULL_LIVE_LLM_VALIDATION_LIVE_SAFE_ULTRA_CAT12.json`: **candidate_archive**.

### candidate_delete (only after user OK)
- [backups/](backups) — old snapshots; verify before removing.
- [artifacts/](artifacts) — intermediate dumps.
- Top-level legacy debug files: [debug_qwen3_*.txt](Carter_v1/debug_qwen3_chat_raw.txt) (live in Carter_v1, not v2; see below).

## Carter_v1/

### obsolete (kept for reference only)
- Entire [Carter_v1/](../Carter_v1) directory — pre-v2 architecture. Do not
  delete; it documents the historical baseline. Mark read-only in any future
  cleanup.

## Repo root (Carter OS AI/)

### do_not_delete
- [run_carter.bat](../run_carter.bat), [run_carter_gpu.ps1](../run_carter_gpu.ps1), [check_carter_gpu.ps1](../check_carter_gpu.ps1)
- [Referencia OpenClaw/](../Referencia%20OpenClaw) — external reference; never delete.
- [GEMINI.md](../GEMINI.md), [MEMORY.md](../MEMORY.md), [DREAMS.md](../DREAMS.md),
  [JarvisGaps.md](../JarvisGaps.md), [QueEsLoQueEsCarter.md](../QueEsLoQueEsCarter.md), [Loquepuedehacercarterhoy.md](../Loquepuedehacercarterhoy.md), [Loquehizocodex.md](../Loquehizocodex.md), [Investigaciontoolsparacarter.md](../Investigaciontoolsparacarter.md), [PromptCodexJarvis.md](../PromptCodexJarvis.md) — repo-level vision/notes docs; archive if user wants, otherwise keep.

### archive (move to root `documentacion/`)
- All root-level `*_REPORT.md`, `*_AUDIT.md`, `prompt_codex_session*.md`,
  `deep-research-report (1).md`, `Auditoria30/04.md`.
- `probe_recheck_*.txt` — debug captures, archive or delete after user OK.

### candidate_delete (only after user OK)
- [execute_tools.py](../execute_tools.py) — root-level script; verify it is not used by
  current workflow before removing.

---

## Recommended order if cleanup is approved later

1. Create `Carter_v2/documentacion/archive/` and move the **archive** items.
2. Create `Carter_v2/audit/results/archive/` and move superseded gate JSONs.
3. Re-run `python audit/runners/text_core_rc_gates.py` to confirm no path
   regressions.
4. Re-run `python audit/runners/text_core_golden_matrix.py` (paths are
   referenced by the matrix; if any move, update the matrix first).
5. Only after a green RC re-run, propose any actual `candidate_delete`
   removals to the user one-by-one.

**Nothing in this document is executed automatically.**
