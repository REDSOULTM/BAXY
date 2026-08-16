# Session 21 - Full Closure Audit

## Scope

Repo: `Carter_v2/`  
Branch observed: `rebuild/v2-from-scratch`

Voice and camera are explicitly out of scope. No STT, live TTS, webcam, screen-vision/camera pipeline, or camera integration is touched.

## Worktree Classification

| Path | Classification | Action |
| --- | --- | --- |
| `Carter_v2/probe_all_results.json` | Generated probe output from previous runs | Leave untouched |
| `Carter_v2/probe_assets/sample.docx` | Binary generated/fixture asset already dirty before S21 | Leave untouched |
| `Loquehizocodex.md` | Personal/session note outside core implementation | Leave untouched |
| `.claude/settings.json` | External editor/tool config | Leave untouched |
| `Carter_v2/Carter_v2.rar` | Archive artifact | Leave untouched |
| `Carter_v2/DREAMS.md`, `DREAMS.md`, `MEMORY.md`, `Carter_v2/MEMORY.md` | Notes/memory artifacts | Leave untouched |
| `Carter_v2/audit_session13_*`, `Carter_v2/research_session14_*` | Historical audit/research artifacts | Leave untouched |
| `Carter_v2/probe_results.json`, `probe_universal_results.json`, `probe_session11_failed_results.json` | Historical/generated probe artifacts | Leave untouched |
| `prompt_codex_session*.md`, `Investigaciontoolsparacarter.md`, `Loquepuedehacercarterhoy.md`, `deep-research-report (1).md`, `execute_tools.py` | External prompts/research/scripts not required for S21 core closure | Leave untouched |
| `Carter_v2/tests/test_carter_capabilities.py`, `Carter_v2/tests/test_carter_v2.py` | Untracked tests present before S21 | Leave untouched unless proven required |

## S15-S20 State Matrix

| Area | Status | Evidence | S21 Action |
| --- | --- | --- | --- |
| TaskFrame / TaskFrameBuilder | DONE | `src/carter_v2/universal/task_frame.py`, `task_frame_builder.py`, `tests/test_universal_agent_kernel.py` | No change |
| ToolIndex / PlanGraph | DONE | `tool_index.py`, `plan_graph.py`, universal tests | No change |
| PlanGraphRunner execution | DONE | `runner.py`, S15/S20 commits, universal tests | Extend only resource context integration |
| Checkpoints enriched | PARTIAL | `checkpoint.py` schema 3 exists, but `/tasks` did not expose resource evidence | Add resource count/summary to list rows and CLI formatter |
| ResourceResolver | DONE | `resource_resolver.py`, `tests/test_resource_resolver.py` | No semantic rewrite; use it from AgentEngine with bases |
| Auto universal routing | PARTIAL | `AgentEngine._try_universal_plan_runner` and `_try_universal_frame_text` did not pass `resource_base_dirs` | Pass structured workspace/base dirs automatically |
| Memory/skills promotion | DONE | `memory_policy.py`, `memory_store.py`, S16 tests | No change |
| CLI universal memory/skills | DONE | `main.py` `/universal-memory`, `/universal-skills` | No change |
| Human inspection of resolved resources | MISSING | `/tasks` showed artifacts only, no resolved resource evidence | Add concise resource summary |
| Probe artifact + resource evidence + resume | MISSING | Existing S15/S16 probes did not assert schema 3 `resolved_resources` through resume | Add S21 probe and run it |
| App hack cleanup | DONE | `tool_normalizer.py`, `brain_router.py`, tests | No change |
| Voice/camera | OUT_OF_SCOPE | User restriction | No touch |

## Breaches Closed In This Session

1. Auto-routed and forced universal runs did not pass workspace/resource base dirs to `PlanGraphRunner`.
2. `/tasks` did not show `resolved_resources`, making checkpoint grounding hard to inspect.
3. No S21 probe validated artifact creation, later artifact use, checkpoint schema 3, resume, and persisted resource evidence in one flow.

## Guardrails Checked

- No public tool names changed.
- No capability interfaces changed.
- No product/app dictionary added.
- No language-specific branch added.
- No filesystem crawling added.
- No URL guessing from plain service names added.
