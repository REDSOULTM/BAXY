# Carter v2 - Session 16 Preflight Audit

## Scope

Session 16 is limited to universal MemoryPolicy, verified skill promotion, skill reuse context, probes/tests, and documentation. Voice, camera, live STT/TTS, webcam, and screen/camera pipelines are explicitly out of scope.

## Relevant files for this session

- `src/carter_v2/universal/runner.py`
- `src/carter_v2/universal/runner_types.py`
- `src/carter_v2/universal/task_frame_builder.py`
- `src/carter_v2/universal/__init__.py`
- `src/carter_v2/turn/agent.py`
- `tests/test_universal_agent_kernel.py`
- `probe_all_tools.py`

New S16 files expected:

- `src/carter_v2/universal/memory_policy.py`
- `src/carter_v2/universal/memory_store.py`
- `session16_memory_skills_notes.md`
- `probe_session16_results.json`

## Existing unrelated worktree changes not touched

The following were already modified or untracked before S16 and are not part of this session:

- `Carter_v2/probe_all_results.json`
- `Carter_v2/probe_assets/sample.docx`
- `Carter_v2/src/carter_v2/adapters/tool_normalizer.py`
- `Carter_v2/src/carter_v2/capabilities/registry.py`
- `Carter_v2/src/carter_v2/turn/brain_router.py`
- `Carter_v2/tests/test_registry_errors.py`
- `Carter_v2/tests/test_tool_normalizer.py`
- `Loquehizocodex.md`
- Untracked docs/archives/results such as `Carter_v2/Carter_v2.rar`, `DREAMS.md`, `MEMORY.md`, S13/S14 reports, and prompt files.

## Risks

- Mixing pre-existing dirty files with S16 would make it unclear which behavior changed.
- Memory/skill promotion can easily become noisy if it stores every successful output. S16 must keep promotion behind explicit structured policy.
- Universal skill reuse must inform planning, not replace tool selection or force a stale sequence.

## Confirmation

S16 will not touch voice/camera code paths and will not replace existing tools/capabilities.
