# V2 -> V3 Import Round 4 - Live Log

> Filesystem universal helpers. Minimal public surface, stronger readback.

Date: 2026-05-03
Author: GPT-5.2-Codex

## Plan

1. Import selective filesystem helpers from v2 (safe path, bounded scans, atomic write, backup move).
2. Upgrade ToolDispatcher filesystem handlers (list/read/search/write/delete).
3. Strengthen filesystem verification (hash/size/backup evidence).
4. Tests + required validation.

---

## Steps

### STEP 0 - log created [DONE]

File: `V2_IMPORT_ROUND_4_LOG.md`.

### STEP 1 - filesystem helpers imported [DONE]

**Imports selectivos desde v2:**
- `legacy/Carter_v2/src/carter_v2/capabilities/filesystem.py` ->
  nuevo `src/carter_v3/tools/filesystem_helpers.py` (safe path,
  basename fallback, bounded folder scan, atomic write, backup move).

**Files touched:**
- `src/carter_v3/tools/filesystem_helpers.py` (NEW)

### STEP 2 - dispatcher filesystem upgraded [DONE]

**Files touched:**
- `src/carter_v3/tools/dispatch.py`

**Behavior changes:**
- `filesystem_list_directory` now returns structured entries with
  bounds (`max_entries`, `include_hidden`) and safe-path gating.
- `filesystem_read_text` supports `max_bytes` + readback metadata.
- `filesystem_search_files` uses recursive glob with `max_results`.
- `filesystem_write_text` uses atomic temp write + replace and returns
  hashes for verifier.
- `filesystem_delete` now moves targets into `data_dir/fs_backups` for
  rollback (size-capped), with optional `allow_no_backup` +
  `user_approved` for oversized targets.

### STEP 3 - verifier filesystem strengthened [DONE]

**Files touched:**
- `src/carter_v3/tools/verifier.py`

**Behavior changes:**
- `filesystem_write` now confirms by hash/size when available.
- `filesystem_delete` reports backup evidence without faking success.

### STEP 4 - tests added [DONE]

**Files added:**
- `tests/test_filesystem_dispatch.py`

### STEP 5 - validation [DONE]

- `python -m pytest -q`
  - First run from workspace root failed due to legacy tests
    (missing `httpx`, test module name collisions). Re-run from
    `Carter_v3/` passed.
- `python audit/hardcode_guard.py`: clean (45 files scanned).
- `python audit/full_matrix_runner.py --mode live-safe --label v2_import_round_4_full --out audit/runs/v2_import_round_4_full.json`:
  - global=98.67% P1=99.44% P2=98.01% P3=100.0% cat11=100.0% cat18=100.0% p95=1404.0ms
  - fails: C1.01, C1.02, C14.01, C14.02, C14.03, C14.04, C17.25
- `python audit/full_matrix_runner.py --mode live-safe --category 9 --label v2_import_round_4_cat9 --out audit/runs/v2_import_round_4_cat9.json`:
  - global=100.0% p95=2556.3ms
