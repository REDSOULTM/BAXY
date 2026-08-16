# Carter v2 - Session 17 Worktree Consolidation Notes

## Scope

This session continues the post-S16 recommendation without touching voice/camera or changing the product capability surface.

Implemented:

- Generic CLI inspection for universal verified memory.
- Generic CLI inspection for universal verified skills.
- Unit coverage for the formatting layer.

Commands:

- `/universal-memory`
- `/universal-skills`

These commands are inspection-only. They do not mutate memory, promote skills, or execute tools.

## Unrelated dirty worktree left untouched

The following files were already modified/untracked before this session and were intentionally not cleaned or included:

- `Carter_v2/probe_all_results.json`
- `Carter_v2/probe_assets/sample.docx`
- `Carter_v2/src/carter_v2/adapters/tool_normalizer.py`
- `Carter_v2/src/carter_v2/capabilities/registry.py`
- `Carter_v2/src/carter_v2/turn/brain_router.py`
- `Carter_v2/tests/test_registry_errors.py`
- `Carter_v2/tests/test_tool_normalizer.py`
- miscellaneous untracked docs, archives, probes, and prompt files

## Universal design constraint

No app-specific shortcuts, brand-specific behavior, or language keyword routing was added. The CLI commands expose existing generic universal memory/skill records only.
