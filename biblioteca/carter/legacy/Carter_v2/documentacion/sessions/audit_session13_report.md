# Carter v2 - Audit Session 13

Date: 2026-04-21
Branch: `rebuild/v2-from-scratch`
Scope: code maintained under `Carter_v2/`, with emphasis on `src/carter_v2/`, `tests/`, `probe_all_tools.py`, setup/probe scripts, and current probe artifacts.

This audit did not add product features and did not change public tool names, capability names, parameters, or behavior. The only output files from this session are this report and `audit_session13_findings.json`.

## Executive Summary

Carter v2 is much more solid than it was before the probe/fix/hardening sessions. The architecture is coherent: LLM tool calls flow through a catalog, a registry, capability implementations, risk policy, verification, and probes. The current probe baseline is also strong: the latest confirmed state before this audit was 135 PASS, 0 FAIL, 0 ERROR, 2 SKIP, with 1176 pytest tests passing.

The base is not "done", though. The main remaining risk is not missing features. The risk is uneven hardening across a large and growing tool surface. The most important issues are:

1. Capability exceptions can still escape the capability contract if an implementation misses a local try/except.
2. Critical safety policy documentation and runtime behavior disagree.
3. The compact tool catalog still has visible tools without compact descriptions, which can cause routing regressions with local models.
4. Filesystem, registry, SQL, COM, and network actions have specific edge cases that should be hardened before adding more capabilities.
5. Tests and probes are broad, but some coverage is routing coverage rather than real effect verification.

My recommendation: do a small hardening pass before adding new tools. Do not do a broad refactor yet.

## Architecture Inventory

### Entry Points

- `run.py`: thin launcher that forces UTF-8 output and imports `carter_v2.main`.
- `src/carter_v2/main.py`: main CLI setup, registry construction, humanized output, policy install, and interface initialization.
- `src/carter_v2/__main__.py`: module entry point.
- `probe_all_tools.py`: live LLM probe runner, readiness report, generated assets, skip classification, and result JSON writer.

### Core Flow

The main execution path is:

1. User text enters the turn engine.
2. The backend receives compact or full tool schemas from `adapters/tools.py`.
3. The LLM returns one or more `ToolCall` objects.
4. Tool calls are normalized by `adapters/tool_normalizer.py`.
5. The event bus invokes policy hooks from `session/policy.py`.
6. `dispatch_tool_call()` maps tool name to `CapabilityRequest`.
7. `CapabilityRegistry.execute()` dispatches to a registered `Capability`.
8. The capability returns `CapabilityResult`.
9. `turn/verification.py` records external or synchronous verification status.
10. The action ledger and reply guards shape the final response.

### Major Modules

- `capabilities/`: the OS/tool surface. This is the highest-risk area because it touches files, processes, COM, registry, network, Office, browser, terminal, media, and session power.
- `adapters/`: LLM tool schemas, dispatch, tool-call normalization, UIA adapter.
- `turn/`: agent loop, backend integration, verification, routing, perception, ledger, reply guards.
- `session/`: memory, skills, policy, proactive monitor, store, watchers.
- `interfaces/`: external gateways and relay interfaces.
- `tests/`: broad unit and integration coverage.
- `probe_all_tools.py`: real LLM coverage and environment readiness.

## Contract Audit: LLM -> Tool Schema -> Capability

### What Is Solid

- A catalog check found no duplicate tool names.
- A catalog check found no exposed tool action that was unsupported by its registered capability in normal probe registry context.
- `CapabilityRequest` and `CapabilityResult` are simple and consistent enough for the current system.
- `ToolDefinition` has the right fields for full schema, compact schema, deprecation, timeout, and fallback chains.
- S12 made probe assets and readiness much more reproducible.

### Main Contract Risks

`ToolDefinition.to_openai_schema(compact=True)` uses `self.compact_description or self.description[:10]`. That fallback is too weak for Qwen3-8B. A catalog audit found 24 visible, non-deprecated tools without compact descriptions:

`system_get_gpu_info`, `system_get_audio_device`, `heartbeat_status`, `filesystem_write_text`, `web_navigate`, `web_click`, `web_fill`, `web_screenshot`, `web_extract`, `window_inspect_active`, `window_minimize`, `window_maximize`, `window_restore`, `desktop_clipboard_set`, `desktop_clipboard_get`, `desktop_open_folder`, `vision_find_element_visual`, `download_file`, `steam_open_client`, `steam_install`, `steam_uninstall`, `steam_run`, `input_key_press`, `gui_read`.

This is not theoretical. Previous failures were routing failures. Compact descriptions are now part of product correctness.

Also, `capabilities_as_tools()` swallows all exceptions while building the tool list. That makes optional capability absence graceful, but it also means a real bug in `supports()` can silently remove a tool from the LLM.

## Security Audit

### Strong Parts

- Most external commands use list-form subprocess calls through `run_with_kill`, not shell strings.
- `_subprocess.run_with_kill()` kills process trees on Windows timeout.
- `filesystem.unzip` blocks Zip Slip with resolved path checks.
- S12 git clone/pull/push probe uses local sandboxing instead of real remotes.
- High-risk tools are classified in `session/policy.py`.

### Security Risks To Fix

The policy module says critical tools are always blocked with no override. The implementation only hard-blocks critical risk when a dangerous command pattern matched. Base critical tools like power/session actions can still go through the approval callback path. That mismatch is a real safety problem because future maintainers will trust the module header.

`system_registry_write` can write to HKLM, HKCR, HKU, and HKCC. It is high risk, but not critical. For an assistant that can run with `CARTER_AUTO_APPROVE_HIGH=1` in probes/dev, that is too permissive. Default writes should be HKCU-only unless there is a deliberately guarded mode.

`sqlite_execute` accepts arbitrary SQL even though the tool contract says INSERT/UPDATE/DELETE. It can execute DDL or destructive statements inside allowed DB paths. This is not as severe as shell injection, but it violates the tool contract and makes policy reasoning weaker.

`git_clone` accepts arbitrary URL schemes. It is already high-risk, so this is not an immediate bug, but autonomous or auto-approved contexts should keep it constrained.

## Robustness And Error Handling

The biggest robustness gap is the registry boundary. `CapabilityRegistry.execute()` returns `capability.execute(request)` directly. The agent later catches exceptions in `_execute_with_recovery`, so the turn usually does not crash, but this means the registry contract itself is weak and non-agent callers can still see raw exceptions. The right boundary is the registry: every capability call should become a `CapabilityResult`.

Filesystem is the clearest concrete example. `FileSystemCapability.execute()` directly calls `mkdir`, `write_text`, `path.open`, `path.stat`, `shutil.move`, `path.rename`, `copytree`, `rmtree`, `ZipFile`, `read_text`, and recursive size walking. Many of those calls can fail on permissions, locks, long paths, disappearing files, invalid zip files, or race conditions. Some branches return nice errors; others can raise.

Network has a smaller version of the same issue: `_port_check()` calls socket APIs without wrapping exceptions. DNS lookup is wrapped; port check should be too.

PDF DOCX conversion via Word COM can leave Word or document handles open if exceptions occur after Word starts or after the document opens. That is the kind of Windows integration leak that becomes painful over long sessions.

## Consistency Audit

Patterns are mostly consistent:

- New capabilities generally use `CapabilityResult`.
- Optional dependencies usually return `next_step_hint`.
- Read-only vs mutating tools are usually classified in policy.
- Tests and probes are named clearly.

Inconsistencies that matter:

- Some capabilities catch all local failures; others rely on the agent-level exception catch.
- Path policy differs between capabilities. `database.py` allows paths under home only, while `code.py` allows home or cwd. This is not currently breaking the repo, but it should be documented as deliberate or normalized.
- Some high-impact verifiers are only `_verify_synchronous_ok`, while others externally inspect effects.
- Email backend coverage is uneven: send supports Outlook/SMTP, read supports Outlook/IMAP, reply is Outlook-only.

## Tests And Probe Coverage

### Strengths

- 85 pytest files and roughly 1002 test functions were counted.
- Last known full result was 1176 passing tests.
- `probe_all_tools.py` now has readiness reporting, classified skips, generated assets, and local git sandboxing.
- The LLM routing surface is being tested directly, which is exactly what Carter needs.

### Remaining Gaps

Some probe checks still validate that the correct tool was called, not that the effect succeeded. This is acceptable for external systems like email, calendar, Office placeholder documents, or unavailable windows, but the result JSON should keep distinguishing routing coverage from effect coverage.

Verification covers all visible tools, but many entries use `_verify_synchronous_ok`. That is honest enough if the wording stays clear: it means "the tool returned ok", not "the external world independently confirmed the effect."

Edge tests that would be valuable:

- Filesystem permission failure, locked file, invalid zip, missing delete target.
- Localized ping output.
- Registry write non-HKCU guard.
- Word COM cleanup on exceptions.
- sqlite_execute rejecting unexpected statement types.
- Compact catalog fails if any visible tool lacks a compact description.

## Prioritized Fix Plan

### A. Fix Now

These are small enough and high-value enough to do before new features:

1. Add a registry-level exception boundary in `CapabilityRegistry.execute`.
2. Align critical policy behavior with the documented safety model.
3. Add compact descriptions for all visible non-deprecated tools and test that none are missing.
4. Stop swallowing unexpected exceptions in `capabilities_as_tools`.
5. Harden `FileSystemCapability.execute` operations with structured errors.
6. Restrict or explicitly guard non-HKCU registry writes.
7. Make ping parsing locale-tolerant.
8. Wrap `network._port_check` socket failures.
9. Add COM cleanup in `pdf._from_docx`.
10. Restrict `database._sqlite_execute` to the documented DML statements.

### B. Useful But Not Urgent

1. Split `filesystem.py` into per-action helper functions after hardening tests exist.
2. Cache Whisper model loading.
3. Clarify reply backend support in email.
4. Add stricter env var name validation and Windows environment-change broadcast.
5. Add more independent verifiers for high-impact effects where cheap.

### C. Do Not Touch Now

1. Do not broadly rename tools or capabilities. The public contract is stable and probes rely on it.
2. Do not replace the current architecture. The flow is coherent.
3. Do not generalize the routing normalizer aggressively. It should stay small and regression-driven.
4. Do not refactor the whole tool catalog for aesthetics. Add tests and compact descriptions first.
5. Do not remove routing-only probes just because they are not full effect tests. Label them honestly instead.

## File-By-File Notes

### `src/carter_v2/main.py`

Good: registry construction isolates capability initialization failures. UIA fallback is pragmatic.

Risk: `_build_registry` prints warnings to stderr but does not produce structured readiness. Probe has readiness; runtime startup could benefit later, but this is not urgent.

### `src/carter_v2/capabilities/registry.py`

Needs a final exception boundary. Also duplicate namespace registration should not silently overwrite.

### `src/carter_v2/types.py`

Good as-is. Simple dataclasses are a strength here.

### `src/carter_v2/adapters/tools.py`

Core contract is good. Main issues are missing compact descriptions and silent exception swallowing in catalog filtering.

### `src/carter_v2/adapters/tool_normalizer.py`

Useful and bounded. It fixed real routing issues. Keep it small. Do not turn it into a second planner.

### `src/carter_v2/session/policy.py`

The risk table is useful and mostly comprehensive. The critical behavior mismatch is the most important safety finding in this audit.

### `src/carter_v2/turn/agent.py`

The loop has good practical defenses: timeouts, repeated-call detection, verification warnings, direct replies, and exception conversion in `_execute_with_recovery`. The agent layer should not be the only exception boundary, but it is doing useful work.

### `src/carter_v2/turn/verification.py`

Coverage is complete for visible tools. The caveat is semantic: synchronous-ok is not external verification. That is fine if the UI/reporting stays honest.

### `src/carter_v2/capabilities/filesystem.py`

High value and high risk. It works well in probes, but it should be hardened because it is a shared primitive. The current method is too large and has many unwrapped OS calls.

### `src/carter_v2/capabilities/system.py`

Good breadth. Registry write and env persistence need tighter safety semantics.

### `src/carter_v2/capabilities/network.py`

Good basic implementation. Locale parsing and socket exception handling are the main gaps.

### `src/carter_v2/capabilities/pdf.py`

Good optional dependency handling. Word COM cleanup needs a `finally` pattern.

### `src/carter_v2/capabilities/media_files.py`

Good dependency hints and path guards. Whisper loading is expensive; FFmpeg helper is positional and fragile but currently works.

### `src/carter_v2/capabilities/database.py`

Good path guard and SELECT-only query. `sqlite_execute` contract should be tightened.

### `src/carter_v2/capabilities/code.py`

Good use of list-form subprocess and path guard. Git operations are inherently high risk and should stay guarded in autonomous contexts.

### `src/carter_v2/capabilities/email.py` and `calendar.py`

Pragmatic backend strategy. External integration coverage is naturally environment-dependent. Document backend gaps rather than pretending all operations are equally supported.

### `probe_all_tools.py`

Strong after S12. It now has readiness, classified skips, generated fixtures, and sandboxed git. Remaining weakness is that some cases are routing-only by necessity.

### `tests/`

Broad and valuable. The next best tests are not more happy-path tests; they are failure-mode tests around filesystem, registry, localized network output, COM cleanup, compact catalog completeness, and SQL statement class enforcement.

## Final Assessment

The project is consolidated enough to keep growing, but only if the next step is hardening, not another capability expansion. The current architecture can support more tools, but the tool surface is already large enough that silent catalog problems, weak compact descriptions, and uneven exception handling will get expensive.

The right next session should be a focused hardening sprint over the A-list fixes above. That will reduce future routing regressions, prevent raw exceptions from leaking, and align safety behavior with what the code says it does.

