# Carter v2 - Session 16 MemoryPolicy and Verified Skills

## MemoryPolicy

Universal memory now uses an explicit policy in `src/carter_v2/universal/memory_policy.py`.

Decisions:

- `STORE`: verified, durable, reusable memory.
- `UPDATE_EXISTING`: same as `STORE`, but updates an existing key/kind.
- `SKIP_TEMPORARY`: temporary run output, scratch path, or ephemeral context.
- `SKIP_UNVERIFIED`: candidate was not verified.
- `SKIP_LOW_VALUE`: not durable/reusable, empty, oversized, or unsupported kind.
- `SKIP_SENSITIVE`: candidate is marked sensitive.

The policy only accepts structured candidates. It does not scrape arbitrary LLM prose or store every successful output.

Allowed durable kinds:

- `preference`
- `project_convention`
- `tool_choice`
- `operational_constraint`

## Skill Promotion

Universal skills are stored separately from product tools. A promoted skill is a reusable workflow hint, not a new capability.

A universal skill is promoted only when:

- the run succeeded,
- all non-skipped executed nodes are verified as `confirmed` or `skipped`,
- the graph has reusable structure such as multiple tools/nodes,
- success criteria exist,
- artifacts do not look like checkpoint/internal implementation details.

Rejected skills are persisted with a reason:

- `run failed or was blocked`
- `not verified`
- `low reuse value`
- `missing success criteria`
- `too context-specific`

## Persistence

`src/carter_v2/universal/memory_store.py` persists three separate streams:

- `universal_memory`: durable accepted memory.
- `universal_skills`: promoted reusable workflows.
- `universal_rejections`: rejected memory/skill candidates with reason and payload.

Default DB:

`%USERPROFILE%/.carter/universal_memory_skills.db`

Override:

`CARTER_UNIVERSAL_MEMORY_DB`

## Reuse

`UniversalMemoryStore.format_skill_context()` retrieves matching promoted skills by structural tokens and tool overlap. `AgentEngine` injects this as `UNIVERSAL_VERIFIED_SKILLS` context. The context is explicitly advisory: tool schemas and current evidence remain authoritative.

## Probes

S16 probes added to `probe_all_tools.py`:

- `S16-MEM-1`: verified durable memory is stored.
- `S16-MEM-2`: temporary memory candidate is rejected.
- `S16-SKILL-1`: verified multi-step workflow promotes a skill.
- `S16-SKILL-2`: similar task retrieves promoted skill context.

Latest run:

- `probe_session16_results.json`
- 4/4 PASS
- 0 FAIL
- 0 ERROR
- 0 SKIP

## Limitations

- S16 does not infer memories from arbitrary output text. That is deliberate.
- S16 does not convert promoted universal skills into executable macros. They are planning hints only.
- Existing legacy `SkillLibrary` remains intact; universal skills are separate to avoid polluting deterministic legacy recipes.
- Voice and camera remain untouched.
